"""
UMLS terminology service.

This module normalizes user-entered disease or symptom text before the app
passes the final disease label to Open Targets. It does not replace Open
Targets for gene associations.
"""
import hashlib
import json
from datetime import datetime, timedelta

import requests
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import sessionmaker

from config import Config
from models import ExternalLookupCache


engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
Session = sessionmaker(bind=engine)


def _cache_key(provider, query_str):
    normalized = (query_str or '').strip().lower()
    digest = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    return f"{provider}:v1:{digest}"


def _get_cached_response(session, provider, query_str):
    entry = session.query(ExternalLookupCache).filter(
        ExternalLookupCache.cache_key == _cache_key(provider, query_str),
        ExternalLookupCache.expires_at > datetime.utcnow()
    ).first()
    if not entry:
        return None
    try:
        return json.loads(entry.response_json)
    except json.JSONDecodeError:
        return None


def _save_cached_response(session, provider, query_str, payload, source="umls"):
    now = datetime.utcnow()
    expires_at = now + timedelta(days=Config.UMLS_CACHE_TTL_DAYS)
    key = _cache_key(provider, query_str)
    payload_json = json.dumps(payload, ensure_ascii=False)

    entry = session.query(ExternalLookupCache).filter(
        ExternalLookupCache.cache_key == key
    ).first()

    if not entry:
        session.execute(
            sql_text(
                "INSERT INTO external_lookup_cache "
                "(provider, cache_key, query, response_json, source, created_at, updated_at, expires_at) "
                "VALUES (:provider, :cache_key, :query, :response_json, :source, :created_at, :updated_at, :expires_at)"
            ),
            {
                "provider": provider,
                "cache_key": key,
                "query": query_str,
                "response_json": payload_json,
                "source": source,
                "created_at": now,
                "updated_at": now,
                "expires_at": expires_at,
            }
        )
    else:
        session.execute(
            sql_text(
                "UPDATE external_lookup_cache "
                "SET response_json = :response_json, source = :source, updated_at = :updated_at, expires_at = :expires_at "
                "WHERE cache_key = :cache_key"
            ),
            {
                "response_json": payload_json,
                "source": source,
                "updated_at": now,
                "expires_at": expires_at,
                "cache_key": key,
            }
        )
    session.commit()


def _dedupe_concepts(concepts):
    seen = set()
    deduped = []
    for concept in concepts:
        key = (concept.get("cui"), concept.get("name", "").lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(concept)
    return deduped


def search_umls_concepts(query_text, limit=10):
    """
    Search UMLS for disease/symptom concepts.

    Returns concepts with CUI, preferred name, semantic type, and source
    vocabulary metadata. If no UMLS key is configured, returns an empty list.
    """
    query_text = (query_text or '').strip()
    if not query_text or not Config.UMLS_API_KEY:
        return []

    cache_query = json.dumps(
        {
            "query": query_text,
            "sabs": Config.UMLS_SABS,
            "semanticTypes": Config.UMLS_SEMANTIC_TYPES,
            "limit": limit,
        },
        sort_keys=True
    )

    session = Session()
    try:
        cached = _get_cached_response(session, "umls_search", cache_query)
        if cached is not None:
            return cached

        url = f"{Config.UMLS_BASE_URL.rstrip('/')}/search/current"
        params = {
            "apiKey": Config.UMLS_API_KEY,
            "string": query_text,
            "sabs": Config.UMLS_SABS,
            "semanticTypes": Config.UMLS_SEMANTIC_TYPES,
            "searchType": "words",
            "pageSize": min(max(limit, 1), 200),
        }

        response = requests.get(
            url,
            params=params,
            timeout=Config.UMLS_TIMEOUT_SECONDS,
            verify=Config.EXTERNAL_API_VERIFY_SSL
        )
        response.raise_for_status()
        raw_results = response.json().get("result", {}).get("results", [])

        concepts = []
        for rank, item in enumerate(raw_results[:limit], start=1):
            ui = item.get("ui")
            name = item.get("name")
            if not ui or ui == "NONE" or not name:
                continue
            concepts.append({
                "cui": ui,
                "preferred_name": name,
                "name": name,
                "semantic_types": item.get("semanticTypes", []),
                "root_source": item.get("rootSource"),
                "uri": item.get("uri"),
                "rank": rank,
                "source": "umls",
            })

        concepts = _dedupe_concepts(concepts)
        _save_cached_response(session, "umls_search", cache_query, concepts)
        return concepts
    except Exception as exc:
        print(f"[UMLS] Search failed for {query_text}: {exc}")
        return []
    finally:
        session.close()


def candidate_names_for_open_targets(query_text, limit=5):
    """
    Build ordered disease-name candidates for Open Targets lookup.

    The original query is always first, so UMLS can improve recall without
    blocking standard Open Targets behavior.
    """
    query_text = (query_text or '').strip()
    candidates = []
    if query_text:
        candidates.append({
            "name": query_text,
            "source": "user_input",
            "cui": None,
            "semantic_types": [],
            "root_source": None,
            "rank": 0,
        })

    concepts = search_umls_concepts(query_text, limit=limit)
    for concept in concepts:
        name = concept.get("preferred_name") or concept.get("name")
        if not name:
            continue
        candidates.append({
            "name": name,
            "source": "umls",
            "cui": concept.get("cui"),
            "semantic_types": concept.get("semantic_types", []),
            "root_source": concept.get("root_source"),
            "rank": concept.get("rank"),
        })

    seen = set()
    deduped = []
    for candidate in candidates:
        key = candidate["name"].lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def get_icd10_code(cui):
    """Return an ICD-10-CM code for a UMLS concept (CUI), or None. Cached.

    Doctors think in ICD-10, so we surface it for the primary interpreted concept.
    """
    cui = (cui or '').strip()
    if not cui or not Config.UMLS_API_KEY:
        return None

    session = Session()
    try:
        cached = _get_cached_response(session, "umls_icd10", cui)
        if cached is not None:
            return cached or None  # cached "" means "looked up, none found"

        url = f"{Config.UMLS_BASE_URL.rstrip('/')}/content/current/CUI/{cui}/atoms"
        params = {"apiKey": Config.UMLS_API_KEY, "sabs": "ICD10CM", "pageSize": 25}
        resp = requests.get(
            url, params=params,
            timeout=Config.UMLS_TIMEOUT_SECONDS,
            verify=Config.EXTERNAL_API_VERIFY_SSL,
        )

        code = None
        if resp.ok:
            for atom in resp.json().get("result", []):
                # atom["code"] is a URI ending in the source code, e.g. ".../ICD10CM/I21.9"
                tail = (atom.get("code") or "").rstrip("/").split("/")[-1]
                if tail and tail not in ("NONE", "ICD10CM"):
                    code = tail
                    break

        _save_cached_response(session, "umls_icd10", cui, code or "")
        return code
    except Exception as exc:
        print(f"[UMLS] ICD-10 lookup failed for {cui}: {exc}")
        return None
    finally:
        session.close()


def translate_clinical_text(query_text, limit=10):
    """Return a UI/API friendly UMLS translation payload."""
    concepts = search_umls_concepts(query_text, limit=limit)
    if concepts:
        # Enrich the top (primary) concept with an ICD-10 code, best-effort.
        try:
            concepts[0] = dict(concepts[0])
            concepts[0]["icd10"] = get_icd10_code(concepts[0].get("cui"))
        except Exception:
            pass
    return {
        "query": query_text,
        "source": "umls" if concepts else "fallback_open_targets",
        "umls_available": bool(Config.UMLS_API_KEY),
        "concepts": concepts,
        "candidate_names": candidate_names_for_open_targets(query_text, limit=limit),
    }
