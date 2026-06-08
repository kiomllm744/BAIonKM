"""
Flask routes for the Disease Portal application.
"""
import json
import re
import hmac
import difflib
import threading
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session
from sqlalchemy import func, desc, text, case
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from models import Herb, AnalysisResult, ExternalLookupCache, Disease
from services import analyze_prescriptions, compute_disease_venn
from config import Config
from llm_service import generate_full_ai_analysis
from umls_service import candidate_names_for_open_targets, translate_clinical_text

from herb_mappings import (
    search_herbs_bilingual,
    validate_herb_bilingual,
    get_korean_name,
)

# Create blueprint
main_bp = Blueprint('main', __name__)

# Create engine and session (shared engine options across all modules)
engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, **Config.engine_options())
Session = sessionmaker(bind=engine)


DISEASE_MATCH_STOPWORDS = {
    'a', 'an', 'and', 'are', 'blood', 'cell', 'cells', 'clinical', 'disease', 'disorder',
    'for', 'from', 'in', 'left', 'lower', 'of', 'right', 'score', 'sign',
    'spectrum', 'syndrome', 'serum', 'the', 'to', 'upper', 'with'
}
GENERIC_LOCATION_TOKENS = {
    'abdomen', 'abdominal', 'chest', 'flank', 'groin', 'pelvis', 'pelvic',
    'region', 'site'
}


def _meaningful_tokens(text_value):
    """Return content tokens used to reject unrelated Open Targets guesses."""
    tokens = re.findall(r'[a-z0-9]+', (text_value or '').lower())
    normalized = []
    for token in tokens:
        if token == 'abdominal':
            token = 'abdomen'
        normalized.append(token)
    return {
        token for token in normalized
        if len(token) > 2 and token not in DISEASE_MATCH_STOPWORDS
    }


def _is_relevant_open_targets_suggestion(suggestion, reference_terms):
    suggestion_tokens = _meaningful_tokens(suggestion)
    if not suggestion_tokens:
        return False

    for reference in reference_terms:
        reference_tokens = _meaningful_tokens(reference)
        if not reference_tokens:
            continue
        overlap = suggestion_tokens & reference_tokens
        if not overlap:
            continue
        non_generic_overlap = overlap - GENERIC_LOCATION_TOKENS
        if non_generic_overlap:
            return True
        if len(overlap) >= 2:
            return True
    return False


# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            # Pass a RELATIVE next (path+query) so it can be safely validated on
            # the way back in (avoids open-redirect via an absolute URL).
            return redirect(url_for('main.login', next=request.full_path))
        return f(*args, **kwargs)
    return decorated_function


def _is_safe_next(target):
    """Only allow same-site relative redirects, to prevent open-redirect abuse."""
    if not target:
        return False
    parsed = urlparse(target)
    # Reject anything with a scheme/host (absolute URL) or protocol-relative //.
    return (
        not parsed.scheme
        and not parsed.netloc
        and target.startswith('/')
        and not target.startswith('//')
    )


def _saved_result_data(result, tab=None):
    """Build the result.html context dict from a saved AnalysisResult row.

    A 'both' row stores {both, modes:{intersection, union}}; we render ONE mode
    at a time (the active tab) and attach tab-bar info. The AI blob is mode-keyed
    ({mode: ai}); a legacy bare AI blob is treated as the current mode's.
    """
    try:
        data = json.loads(result.results_json)
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    if data.get('both'):
        modes = data.get('modes', {}) or {}
        active = tab if tab in modes else 'intersection'
        ctx = modes.get(active) or {}
        ctx['_tabs'] = {
            'active': active,
            'order': [m for m in ('intersection', 'union') if m in modes],
            'disease_name': data.get('disease_name', ''),
        }
        if data.get('provenance') and not ctx.get('provenance'):
            ctx['provenance'] = data.get('provenance')
        current_mode = active
    else:
        ctx = data
        current_mode = ctx.get('disease_gene_mode') or 'union'

    ctx['result_id'] = result.id

    if result.ai_analysis_json:
        try:
            ai = json.loads(result.ai_analysis_json)
            if isinstance(ai, dict) and 'has_ai_analysis' in ai:
                ai = {current_mode: ai}          # legacy bare blob -> key by mode
            ctx['saved_ai_analysis'] = ai.get(current_mode) if isinstance(ai, dict) else None
        except Exception:
            ctx['saved_ai_analysis'] = None
    return ctx


def _run_and_save(disease_name, disease_id, diseases, herb_lists, selected_libs, mode):
    """Run the analysis for the chosen disease-gene mode (or both), save ONE
    history row, and Post/Redirect/Get to the result view."""
    if mode == 'both':
        r_int = analyze_prescriptions(disease_name, herb_lists, efo_id=disease_id or None,
                                      diseases=diseases, libraries=selected_libs or None,
                                      disease_gene_mode='intersection')
        r_uni = analyze_prescriptions(disease_name, herb_lists, efo_id=disease_id or None,
                                      diseases=diseases, libraries=selected_libs or None,
                                      disease_gene_mode='union')
        results = {
            'both': True,
            'modes': {'intersection': r_int, 'union': r_uni},
            'disease_name': r_uni.get('disease_name') or disease_name,
            'disease_gene_mode': 'both',
        }
        common_src = r_uni            # union -> non-empty common count for the history list
    else:
        results = analyze_prescriptions(disease_name, herb_lists, efo_id=disease_id or None,
                                        diseases=diseases, libraries=selected_libs or None,
                                        disease_gene_mode=mode)
        common_src = results

    try:
        prov = _build_provenance()
    except Exception as e:
        print(f"Error building provenance: {e}")
        prov = None
    if prov:
        results['provenance'] = prov
        if results.get('both'):
            results['modes']['intersection']['provenance'] = prov
            results['modes']['union']['provenance'] = prov

    result_id = None
    db_session = Session()
    try:
        _common = set()
        for _rx in (common_src or {}).get('prescriptions', []):
            _common.update(_rx.get('common_genes', []))
        new_result = AnalysisResult(
            disease_name=results.get('disease_name') or disease_name,
            prescriptions=json.dumps(herb_lists),
            results_json=json.dumps(results, default=str),
            common_genes_count=len(_common),
            created_at=datetime.utcnow()
        )
        db_session.add(new_result)
        db_session.commit()
        result_id = new_result.id
    except Exception as e:
        print(f"Error saving result: {e}")
        db_session.rollback()
    finally:
        db_session.close()

    if result_id is not None:
        session['last_result_id'] = result_id
        return redirect(url_for('main.view_last_result'), code=303)

    # Save failed (rare) -> render directly (pick the intersection tab for 'both').
    if results.get('both'):
        ctx = dict(results['modes'].get('intersection') or {})
        ctx['_tabs'] = {'active': 'intersection',
                        'order': [m for m in ('intersection', 'union') if m in results['modes']],
                        'disease_name': results.get('disease_name', '')}
        return render_template('result.html', results=ctx)
    return render_template('result.html', results=results)


# Ensure the analysis_results table has the ai_analysis_json column
def init_results_table():
    """Create/update the analysis_results table."""
    from sqlalchemy import MetaData, Table, Column, Integer, Text, DateTime, inspect
    
    inspector = inspect(engine)
    
    # Check if table exists
    if 'analysis_results' in inspector.get_table_names():
        # Check if ai_analysis_json column exists
        columns = [col['name'] for col in inspector.get_columns('analysis_results')]
        if 'ai_analysis_json' not in columns:
            # Add the column
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE analysis_results ADD COLUMN ai_analysis_json TEXT"))
                conn.commit()
                print("[DB] Added ai_analysis_json column to analysis_results table")
    else:
        # Create the table
        metadata = MetaData()
        analysis_results = Table(
            'analysis_results', metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('disease_name', Text, nullable=False),
            Column('prescriptions', Text, nullable=False),
            Column('results_json', Text, nullable=False),
            Column('ai_analysis_json', Text, nullable=True),
            Column('common_genes_count', Integer, default=0),
            Column('created_at', DateTime, default=datetime.utcnow)
        )
        metadata.create_all(engine)
        print("[DB] Created analysis_results table")

    # Ensure the external API cache table exists. opentargets_service and
    # umls_service read/write it, but nothing else creates it -- a freshly
    # built herbs DB would otherwise make all caching silently fail (INSERTs
    # raise "no such table", swallowed by their broad excepts). checkfirst
    # makes this a no-op when the table is already present.
    ExternalLookupCache.__table__.create(bind=engine, checkfirst=True)

    # Shared "AI generation in progress" marker, keyed by (result_id, mode). Lives
    # in the DB so it is visible to ALL gunicorn workers (an in-memory set is not,
    # which made polls on a different worker wrongly report "absent"). Composite PK
    # makes _claim_ai_inflight's INSERT atomic across workers.
    from sqlalchemy import MetaData as _MD, Table as _T, Column as _C, Integer as _I, Text as _Tx, DateTime as _DT
    _md = _MD()
    _T('ai_inflight', _md,
       _C('result_id', _I, primary_key=True),
       _C('mode', _Tx, primary_key=True),
       _C('started_at', _DT, nullable=False))
    _md.create_all(engine, checkfirst=True)

# Initialize table on import
init_results_table()


@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle login for demo access."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        # Constant-time comparison avoids leaking match length via timing.
        user_ok = hmac.compare_digest(username, Config.DEMO_USERNAME or '')
        pass_ok = hmac.compare_digest(password, Config.DEMO_PASSWORD or '')
        if user_ok and pass_ok:
            session['logged_in'] = True
            session['username'] = username
            requested = request.args.get('next')
            next_url = requested if _is_safe_next(requested) else url_for('main.results')
            return redirect(next_url)
        else:
            return render_template('login.html', error='Invalid username or password')
    
    return render_template('login.html')


@main_bp.route('/logout')
def logout():
    """Handle logout."""
    session.pop('logged_in', None)
    session.pop('username', None)
    return redirect(url_for('main.index'))


@main_bp.context_processor
def _inject_enrichment_options():
    """Make the enrichment-library choices available to every template
    (so all index.html renders, including error fallbacks, have them).
    Also expose herb_korean() so templates can render the Korean (Hangul)
    name for a pinyin herb (returns '' when there is no mapping)."""
    return {
        'enrichment_options': [
            {'value': name, 'label': label, 'default': name in Config.ENRICHMENT_LIBRARIES}
            for name, label in Config.ENRICHMENT_LIBRARY_LABELS.items()
        ],
        'herb_korean': get_korean_name,
    }


@main_bp.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')


@main_bp.route('/database')
def database():
    """Render the database explorer page."""
    return render_template('database.html')


@main_bp.route('/results')
@login_required
def results():
    """Render the results history page (login required)."""
    return render_template('results_history.html')


@main_bp.route('/about')
def about():
    """Render the about page."""
    return render_template('about.html')


@main_bp.route('/api/database/diseases')
def get_diseases_paginated():
    """Browse diseases.

    If the local disease index (built by build_disease_index.py) is present,
    paginate/search the FULL Open Targets catalogue locally. Otherwise fall back
    to a live Open Targets search. Disease genes are always fetched live.
    """
    from sqlalchemy import inspect as sa_inspect
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    search = request.args.get('search', '').strip()
    if page < 1:
        page = 1

    # --- Preferred: browse the full local catalogue ---
    if 'diseases' in sa_inspect(engine).get_table_names():
        session = Session()
        try:
            if session.query(Disease.efo_id).first() is not None:
                q = session.query(Disease.efo_id, Disease.name)
                if search:
                    # Match every whitespace-separated token in any order, e.g.
                    # "diabetes 2" matches "type 2 diabetes mellitus".
                    for token in search.lower().split():
                        q = q.filter(func.lower(Disease.name).like(f"%{token}%"))
                total = q.count()
                # Sort A->Z (case-insensitive); names starting with a digit/symbol
                # (e.g. "11-beta-hydroxylase deficiency") go AFTER Z, not first.
                _first = func.lower(func.substr(Disease.name, 1, 1))
                _alpha_first = case((_first.between('a', 'z'), 0), else_=1)
                rows = (q.order_by(_alpha_first, func.lower(Disease.name))
                        .offset((page - 1) * per_page)
                        .limit(per_page)
                        .all())
                data = [{'name': n, 'efo_id': e, 'gene_count': 'Live online'} for e, n in rows]
                total_pages = (total + per_page - 1) // per_page if per_page else 1
                return jsonify({
                    'data': data, 'total': total, 'page': page, 'per_page': per_page,
                    'total_pages': total_pages, 'search': search, 'source': 'catalogue'
                })
        finally:
            session.close()

    # --- Fallback: live Open Targets search (index not built yet) ---
    if not search:
        search = "diabetes"  # search needs a query; default so the tab isn't empty
    try:
        from opentargets_service import search_diseases_multi_online
        result = search_diseases_multi_online(search, limit=per_page, page_index=page - 1)
        ot_results = result.get('diseases', [])
        total = result.get('total', len(ot_results))
        data = [{'name': d['disease'], 'gene_count': 'Live online'} for d in ot_results]
        total_pages = (total + per_page - 1) // per_page if per_page else 1
        return jsonify({
            'data': data, 'total': total, 'page': page, 'per_page': per_page,
            'total_pages': total_pages, 'search': search, 'source': 'live'
        })
    except Exception as e:
        print(f"Error in paginated diseases: {e}")
        return jsonify({
            'data': [], 'total': 0, 'page': page, 'per_page': per_page,
            'total_pages': 0, 'search': search, 'source': 'live'
        })


@main_bp.route('/api/database/herbs')
def get_herbs_paginated():
    """API endpoint to get paginated herbs data."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    search = request.args.get('search', '').strip()
    
    session = Session()
    try:
        query = session.query(
            Herb.herbName,
            func.count(Herb.Genes).label('gene_count'),
            func.count(func.distinct(Herb.Compound)).label('compound_count')
        ).group_by(Herb.herbName)
        
        if search:
            query = query.filter(Herb.herbName.ilike(f'%{search}%'))
        
        total = query.count()
        
        herbs = query.order_by(Herb.herbName)\
            .offset((page - 1) * per_page)\
            .limit(per_page)\
            .all()
        
        return jsonify({
            'data': [{'name': h[0], 'gene_count': h[1], 'compound_count': h[2]} for h in herbs],
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })
    finally:
        session.close()


@main_bp.route('/api/database/disease/<disease_name>/genes')
def get_disease_genes(disease_name):
    """API endpoint to get genes for a specific disease from Open Targets in real-time."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    try:
        from services import search_disease_genes_with_scores
        gene_scores = search_disease_genes_with_scores(disease_name)
        
        gene_list = [
            {'gene': gene, 'gene_id': gene, 'score': round(score, 4)} 
            for gene, score in gene_scores.items()
        ]
        
        gene_list.sort(key=lambda x: x['score'], reverse=True)
        
        total = len(gene_list)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_data = gene_list[start_idx:end_idx]
        
        return jsonify({
            'disease': disease_name,
            'data': paginated_data,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })
    except Exception as e:
        print(f"Error getting disease genes: {e}")
        return jsonify({
            'disease': disease_name,
            'data': [],
            'total': 0,
            'page': page,
            'per_page': per_page,
            'total_pages': 0
        })


@main_bp.route('/api/database/herb/<herb_name>/genes')
def get_herb_genes(herb_name):
    """API endpoint to get genes for a specific herb, grouped by compound."""
    session = Session()
    try:
        # Get all genes for this herb
        records = session.query(Herb.Compound, Herb.Genes, Herb.GeneId).filter(
            func.lower(Herb.herbName) == herb_name.lower()
        ).order_by(Herb.Compound, Herb.Genes).all()
        
        # Group by compound
        compounds_dict = {}
        for compound, gene, gene_id in records:
            if compound not in compounds_dict:
                compounds_dict[compound] = []
            compounds_dict[compound].append({
                'gene': gene,
                'gene_id': gene_id
            })
        
        # Convert to list format
        compounds_list = [
            {
                'compound': compound,
                'genes': genes,
                'gene_count': len(genes)
            }
            for compound, genes in compounds_dict.items()
        ]
        
        return jsonify({
            'herb': herb_name,
            'compounds': compounds_list,
            'total_compounds': len(compounds_list),
            'total_genes': len(records)
        })
    finally:
        session.close()


# --- Local disease autocomplete (clinician-friendly) ---------------------------
# Vocabulary of words appearing in disease names, used to fuzzy-correct typos.
# Cached in memory; rebuilt on process restart (re-run build_disease_index.py +
# restart to refresh after a new Open Targets release).
_DISEASE_VOCAB = None


def _disease_word_vocab():
    global _DISEASE_VOCAB
    if _DISEASE_VOCAB is None:
        words = set()
        session = Session()
        try:
            for (name,) in session.query(Disease.name).all():
                for w in re.findall(r'[a-z0-9]+', name.lower()):
                    if len(w) >= 4:
                        words.add(w)
        finally:
            session.close()
        _DISEASE_VOCAB = sorted(words)
    return _DISEASE_VOCAB


def _correct_token(token):
    """Fuzzy-correct a (>=4 char) token to the nearest disease-vocabulary word."""
    if len(token) < 4:
        return token
    match = difflib.get_close_matches(token, _disease_word_vocab(), n=1, cutoff=0.82)
    return match[0] if match else token


# Generic "this looks like a primary disease entity" words. A name containing one
# of these (e.g. "diabetes MELLITUS", "Down SYNDROME") is more likely the disease a
# clinician means than an adjective-led complication ("DIABETIC foot"), so it is
# boosted. This is a tiny set of generic disease-category words, NOT a disease list.
_BASE_DISEASE_WORDS = {
    'disease', 'diseases', 'syndrome', 'disorder', 'deficiency', 'mellitus',
    'cancer', 'carcinoma', 'tumor', 'tumour', 'neoplasm', 'failure', 'infection',
    'anemia', 'anaemia', 'insufficiency', 'dystrophy', 'sclerosis', 'fibrosis',
}


def _relevance_score(name, stems, term):
    """Rank a candidate disease name for a (possibly corrected) query.

    Priority: exact name > name that LEADS with the searched word
    ("diabetes mellitus") > the word as a standalone word anywhere
    ("type 2 diabetes mellitus") > a name that only contains it as a substring/
    adjective ("diabetic foot"). Real disease entities (names with a base-disease
    word) are boosted; fewer/shorter words break ties. Replaces the old
    "shortest-name-wins" sort, which surfaced complications above the disease."""
    n = (name or '').lower().strip()
    words = re.findall(r'[a-z0-9]+', n)
    if not words:
        return -1e9
    wordset = set(words)
    s = 0.0
    if n == term:
        s += 1000
    if words[0] in stems:
        s += 300
    elif any(n.startswith(st) for st in stems):
        s += 200
    if wordset & stems:
        s += 150
    if wordset & _BASE_DISEASE_WORDS:
        s += 200
    s -= 5 * len(words)        # prefer fewer words (more canonical)
    s -= 0.4 * len(n)          # mild preference for shorter names
    return s


def _local_disease_match(session, term, limit, correct=False):
    """Diseases whose label contains every token of `term` (any order), ranked by
    clinical relevance (see _relevance_score) instead of name length. When
    `correct` is set, the salient (longest) token is typo-corrected to SEVERAL
    nearest disease-vocabulary words (not just one) and unioned, so e.g.
    "diabetis" surfaces BOTH "diabetes ..." and "diabetic ..." diseases rather than
    locking onto one arbitrary stem."""
    from sqlalchemy import or_
    term = (term or '').lower().strip()
    tokens = re.findall(r'[a-z0-9]+', term)
    if not tokens:
        return []
    stems = set(tokens)
    groups = []  # list of OR-groups; a name must match one variant from each
    if correct:
        salient = max(tokens, key=len)
        for t in tokens:
            if t == salient and len(t) >= 4:
                variants = difflib.get_close_matches(t, _disease_word_vocab(), n=6, cutoff=0.80)
                if variants:
                    stems.update(variants)
                    groups.append(variants)
                else:
                    groups.append([t])
            else:
                c = _correct_token(t)
                stems.add(c)
                groups.append([c])
    else:
        groups = [[t] for t in tokens]
    q = session.query(Disease.name, Disease.efo_id)
    for group in groups:
        q = q.filter(or_(*[func.lower(Disease.name).like(f"%{v}%") for v in group]))
    # fetch a candidate pool (shortest first), then re-rank by relevance in Python
    pool = q.order_by(func.length(Disease.name)).limit(max(limit * 6, 60)).all()
    pool.sort(key=lambda r: _relevance_score(r[0], stems, term), reverse=True)
    return pool[:limit]


def _blend_open_targets_relevance(query, local):
    """Reorder local autocomplete suggestions by Open Targets' own relevance
    ranking (OT is purpose-built for "which disease did they mean", so it floats
    the prominent disease — e.g. type 2 diabetes mellitus — above obscure
    subtypes), then append any local-only extras. Cached + fail-safe: if Open
    Targets is slow/unavailable it returns the local order unchanged, so
    autocomplete never hangs or breaks."""
    from opentargets_service import ranked_disease_search, looks_like_disease

    def _ok(it):
        return looks_like_disease(it.get('id') or '', it.get('name') or '')

    local = [it for it in local if _ok(it)]   # strip trait/process junk from local too
    try:
        ot = ranked_disease_search(query, limit=Config.MAX_SUGGESTIONS)
        if not ot and local:
            # OT couldn't match the raw text (e.g. a typo like "diabetis"); seed it
            # with our best local (typo-corrected) match so OT can still
            # relevance-rank the family ("diabetes mellitus" -> type 2 DM, ...).
            ot = ranked_disease_search(local[0].get('name', ''), limit=Config.MAX_SUGGESTIONS)
    except Exception:
        ot = []
    if not ot:
        return local
    seen, blended = set(), []
    for item in ot:
        nm = item.get('name') or ''
        k = nm.lower()
        if nm and _ok(item) and k not in seen:
            seen.add(k)
            blended.append({'name': nm, 'id': item.get('id')})
    for item in local:
        k = (item.get('name') or '').lower()
        if k and k not in seen:
            seen.add(k)
            blended.append(item)
    return blended


def _umls_open_targets_bridge(query):
    """Last-resort, STRICTLY ADDITIVE autocomplete help. Runs only when every other
    path (catalogue + UMLS-against-catalogue + typo correction + OT raw-text
    relevance) found NOTHING. It tries the top UMLS-standardized names against
    Open Targets' live search -- the same exact-resolution call the analysis
    resolver uses -- and returns the diseases they resolve to (with real EFO IDs).

    This surfaces lay phrases like "tummy ache" -> dyspepsia, where the raw text
    matches neither the catalogue nor OT's text search, but a UMLS synonym
    ("Stomach ache") does. Because these are exact, high-confidence resolutions
    (a real EFO id), they bypass the fuzzy token-overlap filter that (correctly)
    rejects them as loose name suggestions. Cached + trait-filtered + fail-safe;
    never affects a query that already returns results."""
    try:
        from opentargets_service import search_disease_efo_id, looks_like_disease
        cands = candidate_names_for_open_targets(query, limit=4)
    except Exception as exc:
        print(f"[autocomplete] UMLS->OT bridge failed: {exc}")
        return []
    seen, out = set(), []
    for cand in cands:
        nm = (cand.get('name') if isinstance(cand, dict) else cand) or ''
        if not nm or nm.lower() == query.lower():
            continue  # skip the raw text -- it already failed every earlier path
        try:
            m = search_disease_efo_id(nm)
        except Exception:
            m = None
        if m and m.get('efo_id') and m['efo_id'] not in seen \
                and looks_like_disease(m['efo_id'], m.get('name', '')):
            seen.add(m['efo_id'])
            out.append({'name': m['name'], 'id': m['efo_id']})
    return out


@main_bp.route('/api/diseases')
def get_disease_suggestions():
    """Disease autocomplete.

    Local-first over the full Open Targets catalogue (instant, any-word-order),
    augmented by UMLS so clinical synonyms/symptoms/abbreviations (e.g. "MI",
    "heart attack", "high blood sugar") resolve to a real disease, with a typo
    -correcting fallback. Falls back to live Open Targets search if the local
    index isn't built.
    """
    from sqlalchemy import inspect as sa_inspect
    query = request.args.get('q', '').strip()
    if len(query) < 1:
        return jsonify([])

    # --- Preferred: the local catalogue (built by build_disease_index.py) ---
    if 'diseases' in sa_inspect(engine).get_table_names():
        session = Session()
        try:
            if session.query(Disease.efo_id).first() is not None:
                seen, out = set(), []

                def _add(rows):
                    for name, efo in rows:
                        k = name.lower()
                        if k not in seen:
                            seen.add(k)
                            out.append({'name': name, 'id': efo})

                direct = _local_disease_match(session, query, Config.MAX_SUGGESTIONS)

                # Short inputs are usually abbreviations (MI, MS, RA, HTN, CKD)
                # whose substring matches are noisy -- resolve via UMLS first.
                abbrev_like = 2 <= len(query) <= 3
                umls_names = []
                if abbrev_like or len(direct) < 5:
                    try:
                        for cand in candidate_names_for_open_targets(query, limit=5):
                            nm = cand.get('name')
                            if nm and nm.lower() != query.lower():
                                umls_names += _local_disease_match(session, nm, 8)
                    except Exception as exc:
                        print(f"[autocomplete] UMLS bridge failed: {exc}")

                if abbrev_like:
                    _add(umls_names)   # UMLS-resolved disease first
                    _add(direct)
                else:
                    _add(direct)       # exact/any-order matches first
                    _add(umls_names)

                # typo-correcting fallback (only if still nothing)
                if not out and len(query) >= 4:
                    _add(_local_disease_match(session, query, Config.MAX_SUGGESTIONS, correct=True))

                if out:
                    out = _blend_open_targets_relevance(query, out)
                    return jsonify(out[:Config.MAX_SUGGESTIONS])

                # Still nothing: a lay phrase ("tummy ache") that matches neither the
                # catalogue nor OT's raw-text search, but whose UMLS-standardized
                # name resolves at Open Targets ("Stomach ache" -> dyspepsia).
                # Strictly additive -- runs ONLY when every other path found nothing,
                # so no query that already works is affected.
                bridged = _umls_open_targets_bridge(query)
                if bridged:
                    return jsonify(bridged[:Config.MAX_SUGGESTIONS])
        finally:
            session.close()

    # --- Fallback: live Open Targets search + UMLS (index not built) ---
    try:
        from opentargets_service import get_disease_suggestions_online
        suggestions = []
        seen = set()
        candidate_terms = [query]
        candidates = candidate_names_for_open_targets(query, limit=5)
        candidate_terms.extend(candidate["name"] for candidate in candidates)

        for candidate in candidates:
            candidate_suggestions = get_disease_suggestions_online(
                candidate["name"],
                limit=Config.MAX_SUGGESTIONS
            )
            for suggestion in candidate_suggestions:
                key = suggestion.lower()
                if key in seen:
                    continue
                if not _is_relevant_open_targets_suggestion(suggestion, candidate_terms):
                    continue
                seen.add(key)
                suggestions.append({'name': suggestion, 'id': None})
                if len(suggestions) >= Config.MAX_SUGGESTIONS:
                    break
            if len(suggestions) >= Config.MAX_SUGGESTIONS:
                break

        return jsonify(suggestions)
    except Exception as e:
        print(f"Error in autocomplete: {e}")
        return jsonify([])


@main_bp.route('/api/translate-symptoms')
def translate_symptoms():
    """
    Translate free clinical disease/symptom text through UMLS.

    This endpoint is informational and keeps the analysis source of truth in
    Open Targets. It lets the UI show what standardized UMLS concepts were
    used to improve disease lookup.
    """
    query = request.args.get('q', '').strip()
    if len(query) < 1:
        return jsonify({
            'success': False,
            'source': 'empty_query',
            'query': query,
            'concepts': [],
            'candidate_names': []
        }), 400

    payload = translate_clinical_text(query, limit=15)
    payload['success'] = True
    return jsonify(payload)


@main_bp.route('/api/resolve-trace')
def resolve_trace():
    """Run the REAL disease -> Open Targets resolver and report WHO resolved it,
    so the UI can label precisely. match_source is one of:
      catalogue_exact (exact local match) | user_input (Open Targets resolved your
      raw text) | umls (a UMLS-standardized name resolved it) | unresolved.
    """
    query = (request.args.get('q') or '').strip()
    if not query:
        return jsonify({'success': False, 'query': query, 'match_source': 'empty'}), 400
    from services import resolve_disease_to_open_targets
    res = resolve_disease_to_open_targets(query) or {}
    return jsonify({
        'success': True,
        'query': query,
        'match_source': res.get('match_source'),
        'matched_input': res.get('matched_input'),
        'efo_id': res.get('efo_id'),
        'name': res.get('name'),
        'umls_cui': res.get('umls_cui'),
        'candidates_checked': res.get('candidates_checked', []),
    })




@main_bp.route('/api/herbs')
def get_herb_suggestions():
    """API endpoint to get herb name suggestions with Korean support.
    
    Supports searching in both English (Pinyin) and Korean (한글).
    Returns: [{'english': 'huang qi', 'korean': '황기'}, ...]
    """
    query = request.args.get('q', '').strip()
    
    if len(query) < 1:
        return jsonify([])
    
    session = Session()
    try:
        # Get all unique herb names from database
        all_herbs = session.query(Herb.herbName).distinct().all()
        all_herb_names = [h[0] for h in all_herbs]
        
        # Check if query is Korean (contains Hangul characters)
        is_korean_query = any('\uac00' <= char <= '\ud7a3' for char in query)
        
        if is_korean_query:
            # Search using bilingual function for Korean input
            results = search_herbs_bilingual(query, all_herb_names)
        else:
            # English search with Korean names added
            query_lower = query.lower()
            matching_herbs = [h for h in all_herb_names if query_lower in h.lower()]
            
            # Sort by relevance
            def relevance_score(name):
                name_lower = name.lower()
                if name_lower == query_lower:
                    return (0, len(name), name_lower)
                elif name_lower.startswith(query_lower):
                    return (1, len(name), name_lower)
                elif any(word.startswith(query_lower) for word in name_lower.split()):
                    return (2, len(name), name_lower)
                else:
                    pos = name_lower.find(query_lower)
                    return (3, pos, len(name), name_lower)
            
            matching_herbs.sort(key=relevance_score)
            
            # Add Korean names
            results = []
            for herb in matching_herbs[:Config.MAX_SUGGESTIONS]:
                results.append({
                    'english': herb,
                    'korean': get_korean_name(herb)
                })
        
        return jsonify(results[:Config.MAX_SUGGESTIONS])
    finally:
        session.close()


@main_bp.route('/api/herbs/validate')
def validate_herb():
    """API endpoint to validate if a herb exists (supports Korean and English)."""
    name = request.args.get('name', '').strip()
    
    if not name:
        return jsonify({'valid': False, 'english': None, 'korean': None})
    
    session = Session()
    try:
        # Get all herb names for validation
        all_herbs = session.query(Herb.herbName).distinct().all()
        all_herb_names = [h[0] for h in all_herbs]
        
        # Use bilingual validation
        result = validate_herb_bilingual(name, all_herb_names)
        
        if result['valid']:
            return jsonify({
                'valid': True,
                'name': result['english'],  # Always return English for internal use
                'english': result['english'],
                'korean': result['korean']
            })
        
        # Fallback: Try exact match in database (case-insensitive)
        herb = session.query(Herb.herbName).filter(
            func.lower(Herb.herbName) == name.lower()
        ).first()
        
        if herb:
            return jsonify({
                'valid': True, 
                'name': herb[0],
                'english': herb[0],
                'korean': get_korean_name(herb[0])
            })
        
        return jsonify({'valid': False, 'name': None, 'english': None, 'korean': None})
    finally:
        session.close()


@main_bp.route('/api/stats')
def get_stats():
    """API endpoint to get database statistics."""
    from sqlalchemy import inspect as sa_inspect
    session = Session()
    try:
        herb_count = session.query(Herb.herbName).distinct().count()

        # Real count when the local index is built; otherwise the catalogue estimate.
        disease_count = "24,000+ (Open Targets)"
        if 'diseases' in sa_inspect(engine).get_table_names():
            local_count = session.query(Disease).count()
            if local_count > 0:
                disease_count = local_count

        return jsonify({
            'diseases': disease_count,
            'herbs': herb_count
        })
    finally:
        session.close()


def _build_provenance():
    """Data sources + versions behind an analysis (for the version footer,
    a staleness check, and reproducibility). All best-effort."""
    from sqlalchemy import inspect as sa_inspect
    prov = {
        'open_targets_live': None,                 # release the live genes came from
        'disease_catalogue': {},                   # local browse index
        'herb_db': {'name': 'BATMAN-TCM', 'herbs': None},
        'terminology': 'UMLS (NLM)',
        'enrichment': "Enrichr / " + ", ".join(
            Config.ENRICHMENT_LIBRARY_LABELS.get(lib, lib) for lib in Config.ENRICHMENT_LIBRARIES
        ),
        'stale': False,
    }
    try:
        from opentargets_service import get_open_targets_version
        prov['open_targets_live'] = get_open_targets_version()
    except Exception:
        pass

    session = Session()
    try:
        try:
            prov['herb_db']['herbs'] = session.query(Herb.herbName).distinct().count()
        except Exception:
            pass
        if 'data_meta' in sa_inspect(engine).get_table_names():
            rows = dict(session.execute(text("SELECT key, value FROM data_meta")).fetchall())
            prov['disease_catalogue'] = {
                'count': rows.get('disease_catalogue_count'),
                'ot_version': rows.get('disease_catalogue_ot_version'),
                'built': (rows.get('disease_catalogue_built') or '')[:10],
            }
            cat_ver = rows.get('disease_catalogue_ot_version')
            if cat_ver and prov['open_targets_live'] and cat_ver != prov['open_targets_live']:
                prov['stale'] = True
    finally:
        session.close()
    return prov


@main_bp.route('/api/provenance')
def api_provenance():
    """Data sources/versions + freshness, for the UI footer."""
    return jsonify(_build_provenance())


@main_bp.route('/analyze', methods=['POST'])
def analyze():
    """Handle form submission and perform analysis."""
    if request.method == 'POST':
        # Get form data
        disease_name = request.form.get('disease', '').strip()
        disease_id = request.form.get('disease_id', '').strip()  # exact Open Targets ID if picked
        diseases_json = request.form.get('diseases_data', '').strip()  # list of {name,id} (1-3)
        herbs_data_json = request.form.get('herbs_data', '[]')

        # Multi-disease: a list of {name, id}. Falls back to the single disease box.
        diseases = None
        if diseases_json:
            try:
                parsed = json.loads(diseases_json)
                diseases = [d for d in parsed if (d.get('name') or '').strip()]
            except json.JSONDecodeError:
                diseases = None
        if not diseases and not disease_name:
            return render_template('index.html', error="Please enter a disease name")
        
        try:
            herbs_data = json.loads(herbs_data_json)
        except json.JSONDecodeError:
            return render_template('index.html', error="Invalid herbs data format")
        
        if not herbs_data:
            return render_template('index.html', error="Please add at least one prescription with herbs")
        
        # Parse herb lists
        herb_lists = []
        for herbs_string in herbs_data:
            herbs = [herb.strip() for herb in herbs_string.split(',') if herb.strip()]
            if herbs:
                herb_lists.append(herbs)
        
        if not herb_lists:
            return render_template('index.html', error="Please add at least one herb to a prescription")
        
        # User-chosen enrichment libraries (falls back to the config default).
        selected_libs = [lib for lib in request.form.getlist('enrichment_libraries') if lib]

        # Disease-gene mode: union / intersection / both. Empty on the first POST.
        mode = request.form.get('disease_gene_mode', '').strip()
        n_diseases = len(diseases) if diseases else (1 if disease_name else 0)

        # Single disease -> union == intersection; skip the choice screen.
        if n_diseases <= 1:
            return _run_and_save(disease_name, disease_id, diseases, herb_lists, selected_libs, 'union')

        # 2+ diseases, no mode chosen yet -> show the disease Venn + choice buttons.
        # The buttons re-POST this same form with disease_gene_mode set.
        if mode not in ('union', 'intersection', 'both'):
            venn = compute_disease_venn(disease_name, efo_id=disease_id or None, diseases=diseases)
            return render_template(
                'choose_mode.html', venn=venn,
                # echo the RAW posted strings so the re-POST is byte-identical
                form_disease=disease_name, form_disease_id=disease_id,
                form_diseases=diseases_json, form_herbs=herbs_data_json,
                form_libs=selected_libs,
            )

        # 2+ diseases + a mode was chosen -> run it (or both).
        return _run_and_save(disease_name, disease_id, diseases, herb_lists, selected_libs, mode)

    return redirect(url_for('main.index'))


@main_bp.route('/result')
def view_last_result():
    """Render the most recently computed analysis (the PRG target; public).

    Reads the id from the session rather than the URL so refresh/back is
    idempotent and there is no enumerable public link to stored results.
    """
    result_id = session.get('last_result_id')
    if not result_id:
        return redirect(url_for('main.index'))
    tab = request.args.get('tab')   # 'intersection' | 'union' for a 'both' result
    db_session = Session()
    try:
        result = db_session.query(AnalysisResult).filter(AnalysisResult.id == result_id).first()
        if not result:
            return redirect(url_for('main.index'))
        return render_template('result.html', results=_saved_result_data(result, tab=tab))
    finally:
        db_session.close()


@main_bp.route('/api/results/history')
@login_required
def get_results_history():
    """API endpoint to get analysis results history (login required)."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    session = Session()
    try:
        query = session.query(AnalysisResult).order_by(desc(AnalysisResult.created_at))
        
        total = query.count()
        
        results = query.offset((page - 1) * per_page).limit(per_page).all()
        
        data = []
        for r in results:
            try:
                prescriptions = json.loads(r.prescriptions)
                herb_count = sum(len(p) for p in prescriptions)
            except:
                prescriptions = []
                herb_count = 0
            
            data.append({
                'id': r.id,
                'disease_name': r.disease_name,
                'prescriptions_count': len(prescriptions),
                'herbs_count': herb_count,
                'common_genes_count': r.common_genes_count,
                'created_at': r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else 'Unknown'
            })
        
        return jsonify({
            'data': data,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })
    finally:
        session.close()


@main_bp.route('/api/results/<int:result_id>')
@login_required
def get_result_detail(result_id):
    """API endpoint to get a specific analysis result (login required)."""
    session = Session()
    try:
        result = session.query(AnalysisResult).filter(AnalysisResult.id == result_id).first()
        
        if not result:
            return jsonify({'error': 'Result not found'}), 404
        
        try:
            results_data = json.loads(result.results_json)
        except:
            results_data = {}
        
        return jsonify({
            'id': result.id,
            'disease_name': result.disease_name,
            'prescriptions': json.loads(result.prescriptions),
            'results': results_data,
            'created_at': result.created_at.strftime('%Y-%m-%d %H:%M:%S') if result.created_at else 'Unknown'
        })
    finally:
        session.close()


@main_bp.route('/results/<int:result_id>')
@login_required
def view_result(result_id):
    """View a specific saved result (login required)."""
    tab = request.args.get('tab')   # 'intersection' | 'union' for a 'both' result
    db_session = Session()
    try:
        result = db_session.query(AnalysisResult).filter(AnalysisResult.id == result_id).first()
        if not result:
            return redirect(url_for('main.results'))
        return render_template('result.html', results=_saved_result_data(result, tab=tab))
    finally:
        db_session.close()


@main_bp.route('/api/results/<int:result_id>', methods=['DELETE'])
@login_required
def delete_result(result_id):
    """Delete a specific analysis result (login required)."""
    session = Session()
    try:
        result = session.query(AnalysisResult).filter(AnalysisResult.id == result_id).first()
        
        if not result:
            return jsonify({'error': 'Result not found'}), 404
        
        session.delete(result)
        session.commit()
        
        return jsonify({'success': True})
    finally:
        session.close()


# --- Background-job bookkeeping for AI analysis ----------------------------------
# AI generation is a long (~30s) Gemini call run in a background thread; the client
# polls /api/ai-analysis/result until it is saved. The "currently generating"
# marker lives in the DATABASE (table ai_inflight), NOT in process memory, so it is
# shared across all gunicorn workers -- otherwise the worker that starts a
# generation and the worker that handles a poll disagree, the poll wrongly reports
# "absent", and the UI shows a spurious error / re-triggers. A timestamp lets a
# crashed generation's marker go stale and be reclaimed.
# Above the client's max polling window (~210s) so a slow generation never goes
# stale mid-run; only a crashed worker's marker is reclaimed (its finally never ran).
AI_INFLIGHT_TTL_SECONDS = 300


def _ai_inflight_stale_before():
    from datetime import timedelta
    return datetime.utcnow() - timedelta(seconds=AI_INFLIGHT_TTL_SECONDS)


def _claim_ai_inflight(result_id, mode):
    """Atomically claim AI generation for (result_id, mode) across all workers.
    Returns True if WE should generate, False if another worker already is."""
    s = Session()
    try:
        # clear a stale marker (a crashed/killed generation) so it can be retried
        s.execute(text("DELETE FROM ai_inflight WHERE result_id=:r AND mode=:m AND started_at < :t"),
                  {"r": result_id, "m": mode, "t": _ai_inflight_stale_before()})
        s.commit()
        try:
            s.execute(text("INSERT INTO ai_inflight (result_id, mode, started_at) VALUES (:r, :m, :t)"),
                      {"r": result_id, "m": mode, "t": datetime.utcnow()})
            s.commit()
            return True
        except IntegrityError:
            s.rollback()          # another worker holds a fresh marker
            return False
    except Exception as e:
        print(f"[ai-inflight] claim failed: {e}")
        s.rollback()
        return True               # fail open: better to generate than to stall
    finally:
        s.close()


def _release_ai_inflight(result_id, mode):
    s = Session()
    try:
        s.execute(text("DELETE FROM ai_inflight WHERE result_id=:r AND mode=:m"),
                  {"r": result_id, "m": mode})
        s.commit()
    except Exception as e:
        print(f"[ai-inflight] release failed: {e}")
        s.rollback()
    finally:
        s.close()


def _is_ai_inflight(result_id, mode):
    """True if a fresh generation marker exists for (result_id, mode)."""
    s = Session()
    try:
        row = s.execute(text("SELECT 1 FROM ai_inflight WHERE result_id=:r AND mode=:m AND started_at >= :t"),
                        {"r": result_id, "m": mode, "t": _ai_inflight_stale_before()}).first()
        return row is not None
    except Exception:
        return False
    finally:
        s.close()


def _saved_ai_for(result_id, mode):
    """Return the saved AI dict for (result_id, mode) if present and complete,
    else None. Handles the mode-keyed blob and the legacy bare blob."""
    if not result_id:
        return None
    s = Session()
    try:
        row = s.query(AnalysisResult).filter(AnalysisResult.id == result_id).first()
        if not row or not row.ai_analysis_json:
            return None
        blob = json.loads(row.ai_analysis_json)
        if isinstance(blob, dict):
            if 'has_ai_analysis' in blob:            # legacy bare blob (single mode)
                return blob if blob.get('has_ai_analysis') else None
            entry = blob.get(mode)
            if isinstance(entry, dict) and entry.get('has_ai_analysis'):
                return entry
        return None
    except Exception:
        return None
    finally:
        s.close()


def _run_ai_generation(disease_name, prescription_enrichments, result_id, mode, language):
    """Build the inputs, run the Gemini analysis, and (when result_id is given)
    save it mode-keyed onto the row. Returns the ai_results dict. Runs either
    synchronously (no result_id) or inside a background thread (result_id)."""
    analysis_results = {'prescription_enrichments': prescription_enrichments}

    # Pull saved prescriptions (with the ClinGen overlay) for the active mode.
    if result_id:
        _sess = Session()
        try:
            _row = _sess.query(AnalysisResult).filter(AnalysisResult.id == result_id).first()
            if _row:
                _saved = json.loads(_row.results_json)
                if isinstance(_saved, dict) and _saved.get('both'):
                    _mode_data = (_saved.get('modes', {}) or {}).get(mode, {}) or {}
                    analysis_results['prescriptions'] = _mode_data.get('prescriptions', [])
                else:
                    analysis_results['prescriptions'] = _saved.get('prescriptions', [])
        except Exception as e:
            print(f"[ai-analysis] could not load saved prescriptions: {e}")
        finally:
            _sess.close()

    ai_results = generate_full_ai_analysis(disease_name, analysis_results, language=language)

    # Save mode-keyed, merging so a 'both' row keeps the other tab's AI.
    if result_id and ai_results.get('has_ai_analysis'):
        _save_sess = Session()
        try:
            result = _save_sess.query(AnalysisResult).filter(AnalysisResult.id == result_id).first()
            if result:
                payload = {}
                if result.ai_analysis_json:
                    try:
                        _prev = json.loads(result.ai_analysis_json)
                        if isinstance(_prev, dict) and 'has_ai_analysis' not in _prev:
                            payload = _prev
                    except Exception:
                        payload = {}
                payload[mode] = ai_results
                try:
                    result.ai_analysis_json = json.dumps(payload, default=str, ensure_ascii=False)
                    _save_sess.commit()
                    print(f"[DB] Saved AI analysis ({mode}) for result {result_id}")
                except (TypeError, ValueError) as json_err:
                    print(f"[DB] JSON serialization error: {json_err}")
                    import re
                    def clean_for_json(obj):
                        if isinstance(obj, str):
                            return re.sub(r'[\x00-\x1f\x7f-\x9f]', '', obj)
                        elif isinstance(obj, dict):
                            return {k: clean_for_json(v) for k, v in obj.items()}
                        elif isinstance(obj, list):
                            return [clean_for_json(i) for i in obj]
                        return obj
                    payload[mode] = clean_for_json(ai_results)
                    result.ai_analysis_json = json.dumps(payload, default=str)
                    _save_sess.commit()
                    print(f"[DB] Saved cleaned AI analysis ({mode}) for result {result_id}")
        except Exception as e:
            print(f"[DB] Error saving AI analysis: {e}")
            _save_sess.rollback()
        finally:
            _save_sess.close()

    return ai_results


@main_bp.route('/api/ai-analysis', methods=['POST'])
def ai_analysis():
    """API endpoint to generate AI analysis for results.

    Returns structured JSON with:
    - summary_table: Comparison table data
    - detailed_analysis: Full markdown analysis
    - clinical_questions: Diagnostic interview questions

    If result_id is provided, saves the AI analysis to the database.
    Deduplicated: an already-saved (result_id, mode) is returned as-is, and a
    generation already in flight returns {status: 'processing'} (HTTP 202) so the
    client polls instead of starting a second Gemini call.
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    disease_name = data.get('disease_name', '')
    prescription_enrichments = data.get('prescription_enrichments', {})
    result_id = data.get('result_id')  # Optional: save to this result
    language = (data.get('language') or 'en')  # UI language for the AI analysis text
    mode = (data.get('mode') or 'union')  # which disease-gene mode this AI run is for
    if mode not in ('union', 'intersection'):
        mode = 'union'

    if not disease_name:
        return jsonify({'error': 'Disease name is required'}), 400

    if not Config.GEMINI_API_KEY:
        return jsonify({
            'error': 'AI analysis not configured. Please set the GEMINI_API_KEY environment variable.',
            'has_ai_analysis': False
        }), 503

    # Background-job dedup (shared across workers via the ai_inflight table):
    # return a finished analysis directly, or tell the client to poll if a
    # generation is already running (don't start a duplicate).
    if result_id:
        already = _saved_ai_for(result_id, mode)
        if already:
            return jsonify(already)
        if not _claim_ai_inflight(result_id, mode):
            # another worker is already generating this (result_id, mode)
            return jsonify({'status': 'processing', 'has_ai_analysis': False}), 202

        # We claimed it: run Gemini in a background thread so the request returns
        # immediately (never cut off by the gunicorn timeout). The client polls
        # /api/ai-analysis/result -- which now reads the shared marker -- until saved.
        def _bg(disease_name=disease_name, prescription_enrichments=prescription_enrichments,
                result_id=result_id, mode=mode, language=language):
            try:
                _run_ai_generation(disease_name, prescription_enrichments, result_id, mode, language)
            except Exception as e:
                print(f"[ai-analysis] background generation failed: {e}")
            finally:
                _release_ai_inflight(result_id, mode)

        threading.Thread(target=_bg, daemon=True).start()
        return jsonify({'status': 'processing', 'has_ai_analysis': False}), 202

    # No result_id: cannot save or poll, so run synchronously and return the result.
    try:
        ai_results = _run_ai_generation(disease_name, prescription_enrichments, None, mode, language)
        return jsonify(ai_results)
    except Exception as e:
        return jsonify({
            'error': f'AI analysis failed: {str(e)}',
            'has_ai_analysis': False,
            'summary_table': [],
            'detailed_analysis': None,
            'clinical_questions': None
        }), 500


@main_bp.route('/api/ai-analysis/result')
def ai_analysis_result():
    """Poll endpoint for a background AI-analysis run.

    Returns the saved analysis for (result_id, mode) once it is ready, otherwise
    {status: 'processing'} while it is still generating or {status: 'absent'} if
    nothing is running. Lets a tab fill itself in when ready without re-triggering
    Gemini on every tab switch.
    """
    result_id = request.args.get('result_id', type=int)
    mode = request.args.get('mode') or 'union'
    if mode not in ('union', 'intersection'):
        mode = 'union'
    if not result_id:
        return jsonify({'status': 'absent', 'has_ai_analysis': False})
    saved = _saved_ai_for(result_id, mode)
    if saved:
        return jsonify(saved)
    # Shared marker -> a poll on ANY worker sees a generation started on any other.
    processing = _is_ai_inflight(result_id, mode)
    return jsonify({'status': 'processing' if processing else 'absent', 'has_ai_analysis': False})


@main_bp.route('/api/ai-analysis/status')
def ai_analysis_status():
    """Check if AI analysis is available (API key configured)."""
    return jsonify({
        'available': bool(Config.GEMINI_API_KEY),
        'message': 'AI analysis is available' if Config.GEMINI_API_KEY else 'GEMINI_API_KEY not configured'
    })
