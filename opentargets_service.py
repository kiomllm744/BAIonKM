"""
Open Targets GraphQL API Service with Database Caching.
Provides real-time target-disease associations and autocomplete disease searches.
"""
import json
from datetime import datetime, timedelta
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text as sql_text

from config import Config
from models import ExternalLookupCache

# Setup database session for caching (shared engine options, see config.py)
engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, **Config.engine_options())
Session = sessionmaker(bind=engine)


def _normalize_query(text_val):
    return ' '.join((text_val or '').strip().lower().split())


def _cache_key(provider, query_str):
    return f'{provider}:v1:{_normalize_query(query_str)}'


def _get_cached_response(session, provider, query_str):
    """Retrieve response from cache if not expired."""
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


def _save_cached_response(session, provider, query_str, payload, source="opentargets"):
    """Save response to cache with a configured TTL."""
    now = datetime.utcnow()
    # Cache for 15 days to reduce api dependency and speed up repeated requests
    expires_at = now + timedelta(days=15)
    key = _cache_key(provider, query_str)
    
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
                'provider': provider,
                'cache_key': key,
                'query': query_str,
                'response_json': json.dumps(payload, default=str),
                'source': source,
                'created_at': now,
                'updated_at': now,
                'expires_at': expires_at
            }
        )
    else:
        entry.query = query_str
        entry.response_json = json.dumps(payload, default=str)
        entry.source = source
        entry.updated_at = now
        entry.expires_at = expires_at
    session.commit()


def get_open_targets_version():
    """Return the live Open Targets data release (e.g. '26.03'), cached.

    The disease genes/scores are fetched live, so this is the actual release the
    analysis used -- shown for provenance and to flag a stale local catalogue.
    """
    session = Session()
    try:
        cached = _get_cached_response(session, 'opentargets_meta', 'version')
        if cached:
            return cached
        resp = requests.post(
            Config.OPENTARGETS_API_URL,
            json={"query": "{ meta { dataVersion { year month } } }"},
            timeout=10,
            verify=Config.EXTERNAL_API_VERIFY_SSL,
        )
        resp.raise_for_status()
        dv = resp.json().get("data", {}).get("meta", {}).get("dataVersion", {}) or {}
        ver = f"{dv['year']}.{dv['month']}" if dv.get("year") and dv.get("month") else None
        if ver:
            _save_cached_response(session, 'opentargets_meta', 'version', ver)
        return ver
    except Exception as exc:
        print(f"[OpenTargets] meta version failed: {exc}")
        return None
    finally:
        session.close()


def search_disease_efo_id(disease_name):
    """
    Search Open Targets Platform to find matching disease EFO ID and metadata.
    Uses caching to avoid repeated API requests.
    """
    disease_name = (disease_name or '').strip()
    if not disease_name:
        return None

    session = Session()
    try:
        # Check cache
        cached = _get_cached_response(session, 'opentargets_search', disease_name)
        if cached:
            return cached

        # Query Open Targets
        query = """
        query searchDisease($queryString: String!) {
          search(queryString: $queryString, entityNames: ["disease"], page: {index: 0, size: 5}) {
            hits {
              id
              name
              description
            }
          }
        }
        """
        variables = {"queryString": disease_name}
        headers = {"Content-Type": "application/json"}
        
        response = requests.post(
            Config.OPENTARGETS_API_URL,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=Config.OPENTARGETS_TIMEOUT_SECONDS,
            verify=Config.EXTERNAL_API_VERIFY_SSL
        )
        response.raise_for_status()
        
        hits = response.json().get("data", {}).get("search", {}).get("hits", [])
        if not hits:
            return None
            
        best_match = {
            "efo_id": hits[0]["id"],
            "name": hits[0]["name"],
            "description": hits[0].get("description", "")
        }
        
        # Save to cache
        _save_cached_response(session, 'opentargets_search', disease_name, best_match)
        return best_match
    except Exception as exc:
        print(f"[OpenTargets] Disease search failed for {disease_name}: {exc}")
        return None
    finally:
        session.close()


def fetch_live_associated_genes(efo_id, limit=300):
    """
    Query Open Targets Platform in real-time to get target genes and scores for an EFO ID.
    Uses caching to avoid repeated API calls.
    """
    efo_id = (efo_id or '').strip()
    if not efo_id:
        return {}

    session = Session()
    try:
        # Check cache
        cached = _get_cached_response(session, 'opentargets_genes', efo_id)
        if cached is not None:
            return cached

        query = """
        query getAssociatedTargets($efoId: String!, $size: Int!) {
          disease(efoId: $efoId) {
            id
            name
            associatedTargets(page: {index: 0, size: $size}) {
              rows {
                target {
                  id
                  approvedSymbol
                }
                score
              }
            }
          }
        }
        """
        variables = {"efoId": efo_id, "size": limit}
        headers = {"Content-Type": "application/json"}
        
        response = requests.post(
            Config.OPENTARGETS_API_URL,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=Config.OPENTARGETS_TIMEOUT_SECONDS,
            verify=Config.EXTERNAL_API_VERIFY_SSL
        )
        response.raise_for_status()
        
        disease = (response.json().get("data") or {}).get("disease") or {}
        rows = (disease.get("associatedTargets") or {}).get("rows", [])

        gene_scores = {}
        for row in rows:
            gene_symbol = row.get("target", {}).get("approvedSymbol")
            score = row.get("score", 0.0)
            if gene_symbol:
                # DisGeNET scores were in 0.0-1.0 range, Open Targets association score is also 0.0-1.0.
                gene_scores[gene_symbol] = score
                
        # Save to cache
        _save_cached_response(session, 'opentargets_genes', efo_id, gene_scores)
        return gene_scores
    except Exception as exc:
        print(f"[OpenTargets] Fetch associated targets failed for {efo_id}: {exc}")
        return {}
    finally:
        session.close()


# Open Targets evidence datatype id -> short, clinician-friendly label.
EVIDENCE_LABELS = {
    "genetic_association": "genetic",
    "somatic_mutation": "somatic mutation",
    "known_drug": "known drug",
    "affected_pathway": "pathway",
    "literature": "literature",
    "animal_model": "animal model",
    "rna_expression": "expression",
}


def fetch_disease_target_count(efo_id):
    """Total number of targets Open Targets associates with a disease (UNCAPPED).
    Cheap (asks only for the count, not the rows). Cached."""
    efo_id = (efo_id or '').strip()
    if not efo_id:
        return 0
    session = Session()
    try:
        cached = _get_cached_response(session, 'opentargets_count', efo_id)
        if cached is not None:
            return cached
        query = "query($e:String!){ disease(efoId:$e){ associatedTargets(page:{index:0,size:1}){ count } } }"
        response = requests.post(
            Config.OPENTARGETS_API_URL,
            json={"query": query, "variables": {"e": efo_id}},
            headers={"Content-Type": "application/json"},
            timeout=Config.OPENTARGETS_TIMEOUT_SECONDS,
            verify=Config.EXTERNAL_API_VERIFY_SSL,
        )
        response.raise_for_status()
        disease = (response.json().get("data") or {}).get("disease") or {}
        count = (disease.get("associatedTargets") or {}).get("count", 0) or 0
        _save_cached_response(session, 'opentargets_count', efo_id, count)
        return count
    except Exception as exc:
        print(f"[OpenTargets] target count failed for {efo_id}: {exc}")
        return 0
    finally:
        session.close()


def fetch_disease_target_datatypes(efo_id, limit=300):
    """
    For a disease, return {gene_symbol: [evidence labels]} describing WHY each gene
    is associated (genetic / known drug / literature / ...). Cached. This makes the
    association clinically interpretable rather than just a number.
    """
    efo_id = (efo_id or '').strip()
    if not efo_id:
        return {}

    session = Session()
    try:
        cached = _get_cached_response(session, 'opentargets_datatypes', efo_id)
        if cached is not None:
            return cached

        query = """
        query getTargetDatatypes($efoId: String!, $size: Int!) {
          disease(efoId: $efoId) {
            associatedTargets(page: {index: 0, size: $size}) {
              rows {
                target { approvedSymbol }
                datatypeScores { id score }
              }
            }
          }
        }
        """
        response = requests.post(
            Config.OPENTARGETS_API_URL,
            json={"query": query, "variables": {"efoId": efo_id, "size": limit}},
            headers={"Content-Type": "application/json"},
            timeout=Config.OPENTARGETS_TIMEOUT_SECONDS,
            verify=Config.EXTERNAL_API_VERIFY_SSL,
        )
        response.raise_for_status()
        disease = (response.json().get("data") or {}).get("disease") or {}
        rows = (disease.get("associatedTargets") or {}).get("rows", [])

        evidence = {}
        for row in rows:
            gene = row.get("target", {}).get("approvedSymbol")
            if not gene:
                continue
            labels = [
                EVIDENCE_LABELS.get(dt.get("id"), dt.get("id"))
                for dt in (row.get("datatypeScores") or [])
                if (dt.get("score") or 0) > 0
            ]
            if labels:
                evidence[gene] = labels

        _save_cached_response(session, 'opentargets_datatypes', efo_id, evidence)
        return evidence
    except Exception as exc:
        print(f"[OpenTargets] Fetch target datatypes failed for {efo_id}: {exc}")
        return {}
    finally:
        session.close()


def get_disease_suggestions_online(query_str, limit=15):
    """
    Fetch autocomplete disease suggestions in real-time from Open Targets EFO/MONDO indexes.
    """
    query_str = (query_str or '').strip()
    if not query_str:
        return []

    try:
        query = """
        query searchDiseaseSuggestions($queryString: String!, $size: Int!) {
          search(queryString: $queryString, entityNames: ["disease"], page: {index: 0, size: $size}) {
            hits {
              id
              name
            }
          }
        }
        """
        variables = {"queryString": query_str, "size": limit}
        headers = {"Content-Type": "application/json"}
        
        response = requests.post(
            Config.OPENTARGETS_API_URL,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=5,
            verify=Config.EXTERNAL_API_VERIFY_SSL
        )
        response.raise_for_status()
        hits = response.json().get("data", {}).get("search", {}).get("hits", [])
        return [hit["name"] for hit in hits if "name" in hit]
    except Exception as exc:
        print(f"[OpenTargets] Fetching autocomplete suggestions failed: {exc}")
        return []


def ranked_disease_search(query_str, limit=15):
    """Open Targets disease search returning relevance-ranked [{'name','id'}] hits,
    cached (15 days). Used to reorder local autocomplete suggestions by Open
    Targets' own relevance (so e.g. 'type 2 diabetes mellitus' floats up over
    obscure subtypes). Short timeout + returns [] on any failure, so callers can
    fall back to local ordering without hanging."""
    query_str = (query_str or '').strip()
    if not query_str:
        return []
    cache_q = f"{query_str}|{limit}"
    session = Session()
    try:
        cached = _get_cached_response(session, 'opentargets_suggest', cache_q)
        if cached is not None:
            return cached
        query = """
        query rankedDiseaseSearch($q: String!, $size: Int!) {
          search(queryString: $q, entityNames: ["disease"], page: {index: 0, size: $size}) {
            hits { id name }
          }
        }
        """
        response = requests.post(
            Config.OPENTARGETS_API_URL,
            json={"query": query, "variables": {"q": query_str, "size": limit}},
            headers={"Content-Type": "application/json"},
            timeout=5,
            verify=Config.EXTERNAL_API_VERIFY_SSL,
        )
        response.raise_for_status()
        hits = (response.json().get("data", {}).get("search", {}) or {}).get("hits", [])
        out = [{"name": h["name"], "id": h["id"]} for h in hits if h.get("name") and h.get("id")]
        _save_cached_response(session, 'opentargets_suggest', cache_q, out)
        return out
    except Exception as exc:
        print(f"[OpenTargets] ranked suggest failed for '{query_str}': {exc}")
        return []
    finally:
        session.close()


def search_diseases_multi_online(query_str, limit=15, page_index=0):
    """
    Search Open Targets for diseases matching query_str (paginated).

    Returns {'diseases': [{'disease': name, 'cui': EFO_id}, ...], 'total': int}
    so callers can build real pagination over the live search results.
    """
    query_str = (query_str or '').strip()
    if not query_str:
        return {"diseases": [], "total": 0}

    try:
        query = """
        query searchDiseasesMulti($queryString: String!, $index: Int!, $size: Int!) {
          search(queryString: $queryString, entityNames: ["disease"], page: {index: $index, size: $size}) {
            total
            hits {
              id
              name
            }
          }
        }
        """
        variables = {"queryString": query_str, "index": max(page_index, 0), "size": limit}
        headers = {"Content-Type": "application/json"}

        response = requests.post(
            Config.OPENTARGETS_API_URL,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=10,
            verify=Config.EXTERNAL_API_VERIFY_SSL
        )
        response.raise_for_status()
        search = response.json().get("data", {}).get("search", {}) or {}
        hits = search.get("hits", [])
        diseases = [
            {"disease": hit["name"], "cui": hit["id"]}
            for hit in hits
            if "id" in hit and "name" in hit
        ]
        return {"diseases": diseases, "total": search.get("total", len(diseases))}
    except Exception as exc:
        print(f"[OpenTargets] Batch search failed for '{query_str}': {exc}")
        return {"diseases": [], "total": 0}
