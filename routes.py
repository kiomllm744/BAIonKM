"""
Flask routes for the Disease Portal application.
"""
import json
import re
import hmac
import difflib
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session
from sqlalchemy import func, desc, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from models import Herb, AnalysisResult, ExternalLookupCache, Disease
from services import analyze_prescriptions
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


def _saved_result_data(result):
    """Build the result.html context dict from a saved AnalysisResult row."""
    try:
        data = json.loads(result.results_json)
        data['result_id'] = result.id
    except Exception:
        data = {}
    if result.ai_analysis_json:
        try:
            data['saved_ai_analysis'] = json.loads(result.ai_analysis_json)
        except Exception:
            data['saved_ai_analysis'] = None
    return data


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
                rows = (q.order_by(Disease.name)
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


def _local_disease_match(session, term, limit, correct=False):
    """Return (name, efo_id) for diseases whose label contains every token of
    `term` (any order). Shorter (more canonical) names first. Optionally
    typo-correct the tokens."""
    tokens = re.findall(r'[a-z0-9]+', term.lower())
    if not tokens:
        return []
    if correct:
        tokens = [_correct_token(t) for t in tokens]
    q = session.query(Disease.name, Disease.efo_id)
    for t in tokens:
        q = q.filter(func.lower(Disease.name).like(f"%{t}%"))
    q = q.order_by(func.length(Disease.name), Disease.name).limit(limit)
    return q.all()


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
                    return jsonify(out[:Config.MAX_SUGGESTIONS])
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

    payload = translate_clinical_text(query, limit=10)
    payload['success'] = True
    return jsonify(payload)




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
        'enrichment': f"Enrichr / {Config.DEFAULT_GENE_LIBRARY}",
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
        
        # Perform analysis (exact picked ID skips re-resolution; diseases list = multi-disease union)
        results = analyze_prescriptions(disease_name, herb_lists, efo_id=disease_id or None, diseases=diseases)

        # Record the data sources/versions used, so the result is auditable and reproducible
        try:
            results['provenance'] = _build_provenance()
        except Exception as e:
            print(f"Error building provenance: {e}")
        
        # Save to history (try/finally so the DB session never leaks on error)
        result_id = None
        db_session = Session()
        try:
            # common genes live per-prescription, not at the top level
            _common = set()
            for _rx in results.get('prescriptions', []):
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

        # Post/Redirect/Get: stash the id in the server-side session and redirect
        # to a GET view, so a browser refresh/back does NOT re-POST and re-run the
        # whole analysis (which previously also inserted a duplicate history row).
        # The id lives in the session, not the URL, so there's no enumerable public
        # link to saved results (history viewing stays login-gated).
        if result_id is not None:
            session['last_result_id'] = result_id
            return redirect(url_for('main.view_last_result'), code=303)

        # Saving failed (rare) -> render directly so the user still sees results.
        return render_template('result.html', results=results)

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
    db_session = Session()
    try:
        result = db_session.query(AnalysisResult).filter(AnalysisResult.id == result_id).first()
        if not result:
            return redirect(url_for('main.index'))
        return render_template('result.html', results=_saved_result_data(result))
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
    db_session = Session()
    try:
        result = db_session.query(AnalysisResult).filter(AnalysisResult.id == result_id).first()
        if not result:
            return redirect(url_for('main.results'))
        return render_template('result.html', results=_saved_result_data(result))
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


@main_bp.route('/api/ai-analysis', methods=['POST'])
def ai_analysis():
    """API endpoint to generate AI analysis for results.
    
    Returns structured JSON with:
    - summary_table: Comparison table data
    - detailed_analysis: Full markdown analysis
    - clinical_questions: Diagnostic interview questions
    
    If result_id is provided, saves the AI analysis to the database.
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    disease_name = data.get('disease_name', '')
    prescription_enrichments = data.get('prescription_enrichments', {})
    result_id = data.get('result_id')  # Optional: save to this result
    
    if not disease_name:
        return jsonify({'error': 'Disease name is required'}), 400
    
    if not Config.GEMINI_API_KEY:
        return jsonify({
            'error': 'AI analysis not configured. Please set the GEMINI_API_KEY environment variable.',
            'has_ai_analysis': False
        }), 503
    
    try:
        # Build the results structure for generate_full_ai_analysis
        analysis_results = {
            'prescription_enrichments': prescription_enrichments
        }

        # Pull the saved prescriptions (with ClinGen common_genes_validity) so the
        # AI gets the clinical-validity overlay. The frontend only sends enrichment
        # tables, so load the rest from the saved analysis row.
        if result_id:
            _sess = Session()
            try:
                _row = _sess.query(AnalysisResult).filter(AnalysisResult.id == result_id).first()
                if _row:
                    _saved = json.loads(_row.results_json)
                    analysis_results['prescriptions'] = _saved.get('prescriptions', [])
            except Exception as e:
                print(f"[ai-analysis] could not load saved prescriptions: {e}")
            finally:
                _sess.close()

        # Generate full AI analysis (summary_table, detailed_analysis, clinical_questions)
        ai_results = generate_full_ai_analysis(disease_name, analysis_results)
        
        # Save AI analysis to database if result_id provided and analysis succeeded
        if result_id and ai_results.get('has_ai_analysis'):
            _save_sess = Session()
            try:
                result = _save_sess.query(AnalysisResult).filter(AnalysisResult.id == result_id).first()
                if result:
                    # Ensure AI analysis can be serialized to JSON
                    try:
                        result.ai_analysis_json = json.dumps(ai_results, default=str, ensure_ascii=False)
                        _save_sess.commit()
                        print(f"[DB] Saved AI analysis for result {result_id}")
                    except (TypeError, ValueError) as json_err:
                        print(f"[DB] JSON serialization error: {json_err}")
                        # Try with more aggressive cleaning
                        import re
                        def clean_for_json(obj):
                            if isinstance(obj, str):
                                # Remove control characters
                                return re.sub(r'[\x00-\x1f\x7f-\x9f]', '', obj)
                            elif isinstance(obj, dict):
                                return {k: clean_for_json(v) for k, v in obj.items()}
                            elif isinstance(obj, list):
                                return [clean_for_json(i) for i in obj]
                            return obj
                        result.ai_analysis_json = json.dumps(clean_for_json(ai_results), default=str)
                        _save_sess.commit()
                        print(f"[DB] Saved cleaned AI analysis for result {result_id}")
            except Exception as e:
                print(f"[DB] Error saving AI analysis: {e}")
                _save_sess.rollback()
            finally:
                _save_sess.close()
        
        return jsonify(ai_results)
        
    except Exception as e:
        return jsonify({
            'error': f'AI analysis failed: {str(e)}',
            'has_ai_analysis': False,
            'summary_table': [],
            'detailed_analysis': None,
            'clinical_questions': None
        }), 500


@main_bp.route('/api/ai-analysis/status')
def ai_analysis_status():
    """Check if AI analysis is available (API key configured)."""
    return jsonify({
        'available': bool(Config.GEMINI_API_KEY),
        'message': 'AI analysis is available' if Config.GEMINI_API_KEY else 'GEMINI_API_KEY not configured'
    })
