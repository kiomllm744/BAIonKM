"""
Core services for gene analysis - ONLINE REAL-TIME VERSION.
Contains the main business logic for disease-herb gene analysis using Open Targets API.
"""
import json
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import func, create_engine, text, inspect as sa_inspect
from sqlalchemy.orm import sessionmaker
from models import Herb, Disease
from config import Config
from opentargets_service import (
    search_disease_efo_id, fetch_live_associated_genes,
    fetch_disease_target_datatypes, fetch_disease_target_count,
)
from umls_service import candidate_names_for_open_targets

# Create engine with optimized settings for local herbs caching
engine_args = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}
if Config.SQLALCHEMY_DATABASE_URI.startswith('sqlite'):
    engine_args['connect_args'] = {'check_same_thread': False}

engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, **engine_args)
Session = sessionmaker(bind=engine)


def _exact_catalogue_disease(disease_name):
    """Return (efo_id, name) for an exact (case-insensitive) match in the local
    disease catalogue, or None. Used to avoid fuzzy Open Targets surprises
    (e.g. "abc" resolving to aneurysmal bone cyst via its abbreviation)."""
    disease_name = (disease_name or '').strip()
    if not disease_name:
        return None
    try:
        if 'diseases' not in sa_inspect(engine).get_table_names():
            return None
    except Exception:
        return None
    session = Session()
    try:
        return session.query(Disease.efo_id, Disease.name).filter(
            func.lower(Disease.name) == disease_name.lower()
        ).first()
    except Exception:
        return None
    finally:
        session.close()


def resolve_disease_to_open_targets(disease_name):
    """
    Resolve a user disease/symptom string to an Open Targets disease ID.

    Order: a raw EFO/MONDO/Orphanet ID is used as-is; then an EXACT local
    catalogue name match (deterministic, no surprises); only then the UMLS +
    Open Targets fuzzy search. UMLS adds standardized terminology candidates, but
    Open Targets remains the final authority for EFO/MONDO IDs and associations.
    """
    disease_name = (disease_name or '').strip()
    if not disease_name:
        return None

    if disease_name.startswith('EFO_') or disease_name.startswith('MONDO_') or disease_name.startswith('Orphanet_'):
        return {
            "efo_id": disease_name,
            "name": disease_name,
            "description": "",
            "matched_input": disease_name,
            "match_source": "user_identifier",
            "umls_cui": None,
            "umls_semantic_types": [],
            "umls_root_source": None,
            "candidates_checked": [disease_name],
        }

    # Exact local catalogue match takes precedence over fuzzy search, so an exact
    # disease name always maps to that exact disease (not Open Targets' top fuzzy hit).
    exact = _exact_catalogue_disease(disease_name)
    if exact:
        return {
            "efo_id": exact[0],
            "name": exact[1],
            "description": "",
            "matched_input": disease_name,
            "match_source": "catalogue_exact",
            "umls_cui": None,
            "umls_semantic_types": [],
            "umls_root_source": None,
            "candidates_checked": [disease_name],
        }

    candidates = candidate_names_for_open_targets(disease_name, limit=5)
    checked = []
    for candidate in candidates:
        candidate_name = candidate["name"]
        checked.append(candidate_name)
        match = search_disease_efo_id(candidate_name)
        if match:
            return {
                **match,
                "matched_input": candidate_name,
                "match_source": candidate.get("source", "open_targets"),
                "umls_cui": candidate.get("cui"),
                "umls_semantic_types": candidate.get("semantic_types", []),
                "umls_root_source": candidate.get("root_source"),
                "candidates_checked": checked,
            }

    return {
        "efo_id": None,
        "name": disease_name,
        "description": "",
        "matched_input": None,
        "match_source": "unresolved",
        "umls_cui": None,
        "umls_semantic_types": [],
        "umls_root_source": None,
        "candidates_checked": checked,
    }


def search_disease_genes_with_scores(disease_name):
    """
    Search for genes associated with a disease along with their association scores.
    Calls Open Targets GraphQL API in real-time online.
    """
    disease_name = (disease_name or '').strip()
    if not disease_name:
        return {}
        
    res = resolve_disease_to_open_targets(disease_name)
    if not res or not res.get("efo_id"):
        return {}
    efo_id = res["efo_id"]
        
    return fetch_live_associated_genes(efo_id)


def search_herb_genes_batch(herb_names):
    """
    Search for genes targeted by a list of herbs.
    OPTIMIZED: Single batch query instead of multiple queries.
    """
    if not herb_names:
        return [], []
    
    session = Session()
    try:
        # Normalize herb names to lowercase for comparison
        herb_names_lower = [h.lower() for h in herb_names]
        herb_names_map = {h.lower(): h for h in herb_names}  # Map to original case
        
        # Single batch query for all herbs - MUCH faster!
        herb_records = session.query(Herb.herbName, Herb.Genes).filter(
            func.lower(Herb.herbName).in_(herb_names_lower)
        ).all()
        
        # Group genes by herb
        found_herbs = set()
        gene_symbols = []
        
        for herbName, gene in herb_records:
            found_herbs.add(herbName.lower())
            gene_symbols.append(gene)
        
        # Find missing herbs
        missing_herbs = [herb_names_map[h] for h in herb_names_lower if h not in found_herbs]
        
        return gene_symbols, missing_herbs
    finally:
        session.close()


def find_common_genes(disease_genes, herb_genes_list):
    """
    Find common genes between disease and each herb prescription.
    OPTIMIZED: Uses set operations.
    """
    disease_genes_set = set(disease_genes)
    all_common_genes = []

    for herb_genes in herb_genes_list:
        herb_genes_set = set(herb_genes)
        common_genes = disease_genes_set & herb_genes_set
        all_common_genes.append(list(common_genes))

    return all_common_genes


def find_unique_genes(all_common_genes):
    """
    Find genes unique to each prescription.
    """
    all_unique_genes = []

    for i, genes in enumerate(all_common_genes):
        if len(all_common_genes) > 1:
            other_genes = set().union(*all_common_genes[:i], *all_common_genes[i + 1:])
            unique_genes = set(genes) - other_genes
        else:
            unique_genes = set(genes)
        
        all_unique_genes.append(unique_genes)

    return all_unique_genes


def upload_single_gene_list(gene_list, index):
    """Upload a single gene list to Enrichr (for parallel execution)."""
    upload_url = f'{Config.ENRICHR_BASE_URL}/addList'
    genes_str = "\n".join(list(gene_list))
    payload = {'list': (None, genes_str)}
    
    response = requests.post(
        upload_url,
        files=payload,
        timeout=30,
        verify=Config.EXTERNAL_API_VERIFY_SSL
    )
    if not response.ok:
        raise Exception(f'Error uploading gene list {index} to Enrichr')
    
    data = json.loads(response.text)
    data['index'] = index
    return data


def upload_gene_lists_to_enrichr_parallel(gene_lists):
    """
    Upload gene lists to Enrichr API.
    OPTIMIZED: Parallel uploads using ThreadPoolExecutor.
    """
    all_data = [None] * len(gene_lists)
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(upload_single_gene_list, gene_list, i): i 
            for i, gene_list in enumerate(gene_lists)
        }
        
        for future in as_completed(futures):
            try:
                data = future.result()
                all_data[data['index']] = data
            except Exception as e:
                print(f"Error uploading gene list: {e}")
    
    return [d for d in all_data if d is not None]


def fetch_enrichment_single(user_list_id, library, index):
    """Fetch enrichment for a single gene list (for parallel execution)."""
    enrich_url = f'{Config.ENRICHR_BASE_URL}/enrich'
    response = requests.get(
        f'{enrich_url}?userListId={user_list_id}&backgroundType={library}',
        timeout=60,
        verify=Config.EXTERNAL_API_VERIFY_SSL
    )
    
    if not response.ok:
        raise Exception(f"Error fetching enrichment for userListId: {user_list_id}")
    
    return index, json.loads(response.text)


def perform_enrichment_analysis_parallel(data_list, library=None):
    """
    Perform enrichment analysis using Enrichr API.
    OPTIMIZED: Parallel API calls.
    """
    if library is None:
        library = Config.DEFAULT_GENE_LIBRARY

    # Parallel fetch enrichment results
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(fetch_enrichment_single, data['userListId'], library, i): i
            for i, data in enumerate(data_list)
        }
        
        for future in as_completed(futures):
            try:
                index, enrichment_data = future.result()
                process_enrichment_data(data_list[index], enrichment_data)
            except Exception as e:
                print(f"Error fetching enrichment: {e}")

    return data_list


def process_enrichment_data(data, enrichment_data):
    """Process raw enrichment data into structured format.

    Enrichr's /enrich response is a dict keyed by library name whose values
    are lists of result rows, e.g. {"DisGeNET": [[rank, term, p, ...], ...]}.
    """
    data['enrichment_data'] = []

    for rows in enrichment_data.values():
        for element in rows:
            rank = element[0]
            term_name = element[1]
            p_value = element[2]
            z_score = element[3]
            combined_score = element[4]
            overlapping_genes = ', '.join(element[5])
            adjusted_p_value = element[6]
            old_p_value = element[7]
            old_adjusted_p_value = element[8]

            if adjusted_p_value < Config.ADJUSTED_PVALUE_THRESHOLD:
                new_row = {
                    'Rank': rank,
                    'Term name': term_name,
                    'P-value': p_value,
                    'Z-score': z_score,
                    'Combined score': combined_score,
                    'Overlapping genes': overlapping_genes,
                    'Adjusted p-value': adjusted_p_value,
                    'Old p-value': old_p_value,
                    'Old adjusted p-value': old_adjusted_p_value
                }
                data['enrichment_data'].append(new_row)

    # Keep only top results
    data['enrichment_data'] = data['enrichment_data'][:Config.MAX_ENRICHMENT_RESULTS]


# ClinGen classification ranking + mapping to the levels the LLM formatter uses.
_CLINGEN_RANK = {
    'Definitive': 6, 'Strong': 5, 'Moderate': 4, 'Limited': 3,
    'Disputed': 2, 'Refuted': 1, 'No Known Disease Relationship': 0,
}
_CLINGEN_LEVEL = {
    'Definitive': 'Definitive', 'Strong': 'Strong', 'Moderate': 'Moderate',
    'Limited': 'Limited', 'Disputed': 'Limited', 'Refuted': 'Limited',
    'No Known Disease Relationship': 'Limited',
}


def _disease_tokens(name):
    return {t for t in re.findall(r'[a-z0-9]+', (name or '').lower()) if len(t) > 3}


def _score_bucket(score):
    if score >= 0.4:
        return 'Strong'
    if score >= 0.2:
        return 'Moderate'
    return 'Limited'


def _clingen_validity_for(common_genes, gene_scores, diseases, gene_evidence=None):
    """Build the common_genes_validity map consumed by the LLM ClinGen formatter.

    `diseases` is a list of {'name', 'efo_id'} (one or several). A ClinGen entry
    is "disease_specific" if it matches ANY of the analysed diseases.

    Each common gene gets either an official ClinGen classification (clinical-grade
    gene-disease validity, with the ClinGen disease named for transparency, and a
    disease_specific flag when it matches the analysed disease) or a local
    DisGeNET/Open-Targets score bucket as fallback.
    """
    clingen_rows = {}
    try:
        if common_genes and 'clingen_validity' in sa_inspect(engine).get_table_names():
            session = Session()
            try:
                genes = list(common_genes)
                placeholders = ','.join(f':g{i}' for i in range(len(genes)))
                params = {f'g{i}': g for i, g in enumerate(genes)}
                res = session.execute(
                    text(f"SELECT gene, disease, mondo_id, classification "
                         f"FROM clingen_validity WHERE gene IN ({placeholders})"),
                    params,
                )
                for gene, disease, mondo, classification in res:
                    clingen_rows.setdefault(gene, []).append((disease, mondo, classification))
            finally:
                session.close()
    except Exception as exc:
        print(f"[ClinGen] lookup failed: {exc}")

    gene_evidence = gene_evidence or {}
    match_efos = {(d.get('efo_id') or '') for d in (diseases or []) if d.get('efo_id')}
    match_tokens = set()
    for d in (diseases or []):
        match_tokens |= _disease_tokens(d.get('name'))
    validity = {}
    for gene in common_genes:
        score = round(gene_scores.get(gene, 0.0), 4)
        evidence = gene_evidence.get(gene, [])
        rows = clingen_rows.get(gene)
        if rows:
            def is_match(mondo, label):
                if mondo and mondo in match_efos:
                    return True
                return bool(match_tokens & _disease_tokens(label))
            matched = [(d, m, c) for (d, m, c) in rows if is_match(m, d)]
            pool = matched or rows
            disease, mondo, classification = max(pool, key=lambda r: _CLINGEN_RANK.get(r[2], 0))
            ds = bool(matched)
            text_label = f"{classification} for {disease}" if disease else classification
            if not ds:
                text_label += " [different disease]"
            validity[gene] = {
                'score': score,
                'evidence': evidence,
                'clingen': {
                    'level': _CLINGEN_LEVEL.get(classification, 'Limited'),
                    'classification': text_label,
                    'source': 'clingen',
                    'disease_specific': ds,
                },
            }
        else:
            validity[gene] = {
                'score': score,
                'evidence': evidence,
                'clingen': {'level': _score_bucket(score), 'source': 'disgenet'},
            }
    return validity


def analyze_prescriptions(disease_name, herb_lists, efo_id=None, diseases=None):
    """
    Main analysis function - ONLINE REAL-TIME VERSION.

    Supports ONE or SEVERAL diseases. With multiple diseases the disease gene
    sets are UNIONed (a gene linked to ANY selected disease is included), keeping
    the best Open Targets score and tracking which diseases each gene came from;
    genes shared by ALL diseases are recorded as the "shared core". `diseases` is
    a list of {'name', 'efo_id'/'id'}; if omitted it falls back to the single
    disease_name/efo_id. An exact efo_id skips name re-resolution.
    """
    # Normalise inputs into a list of diseases
    if diseases:
        disease_inputs = []
        for d in diseases:
            nm = (d.get('name') or '').strip()
            eid = (d.get('efo_id') or d.get('id') or '').strip()
            if nm or eid:
                disease_inputs.append({'name': nm, 'efo_id': eid})
    else:
        disease_inputs = [{'name': (disease_name or '').strip(), 'efo_id': (efo_id or '').strip()}]
    disease_inputs = [d for d in disease_inputs if d['name'] or d['efo_id']]

    results = {
        'disease_name': '',
        'disease_cui': '',
        'disease_resolution': {},
        'diseases': [],
        'shared_core_genes': [],
        'prescriptions': [],
        'enrichment_data': None,
        'errors': [],
    }
    if not disease_inputs:
        results['errors'].append("No disease provided")
        return results

    # Resolve each disease and fetch its genes + evidence
    resolved = []
    for d in disease_inputs:
        if d['efo_id']:
            resn = {
                "efo_id": d['efo_id'], "name": d['name'] or d['efo_id'], "description": "",
                "matched_input": d['name'], "match_source": "catalogue_id",
                "umls_cui": None, "umls_semantic_types": [], "umls_root_source": None,
                "candidates_checked": [d['efo_id']],
            }
        else:
            resn = resolve_disease_to_open_targets(d['name']) or {}
        eid = resn.get('efo_id')
        nm = resn.get('name') or d['name'] or eid or ''
        scores = fetch_live_associated_genes(eid) if eid else {}
        evid = fetch_disease_target_datatypes(eid) if eid else {}
        total = fetch_disease_target_count(eid) if eid else 0
        resolved.append({'name': nm, 'efo_id': eid, 'resolution': resn, 'scores': scores, 'evidence': evid})
        results['diseases'].append({
            'name': nm,
            'efo_id': eid,
            'gene_count': len(scores),                       # used in analysis (capped at 300)
            'total_gene_count': max(total, len(scores)),     # true Open Targets total (uncapped)
            'match_source': (resn.get('match_source') or ''),
        })
        if not scores:
            results['errors'].append(f"No genes found for disease: {nm}")

    names = [r['name'] for r in resolved if r['name']]
    results['disease_name'] = " + ".join(names) if names else (disease_name or '')
    results['disease_cui'] = resolved[0]['efo_id'] if len(resolved) == 1 else ''
    results['disease_resolution'] = resolved[0]['resolution'] if resolved else {}

    # Union disease genes (best score per gene), track source diseases + evidence
    gene_scores = {}
    gene_diseases = {}
    gene_evidence = {}
    per_disease_sets = []
    for r in resolved:
        s = set(r['scores'].keys())
        if s:
            per_disease_sets.append(s)
        for g, sc in r['scores'].items():
            if sc > gene_scores.get(g, -1.0):
                gene_scores[g] = sc
            gene_diseases.setdefault(g, set()).add(r['name'])
        for g, labels in r['evidence'].items():
            gene_evidence.setdefault(g, set()).update(labels)
    gene_evidence = {g: sorted(v) for g, v in gene_evidence.items()}

    disease_genes = list(gene_scores.keys())
    results['disease_gene_count'] = len(disease_genes)
    # shared core = genes associated with ALL diseases that returned any genes
    shared_core = set.intersection(*per_disease_sets) if per_disease_sets else set()
    results['shared_core_genes'] = sorted(shared_core)
    multi = len(resolved) > 1
    match_diseases = [{'name': r['name'], 'efo_id': r['efo_id']} for r in resolved]

    # Venn region counts for the gene sets used (2 or 3 diseases) -> overlap diagram
    results['venn'] = None
    _ds = [(r['name'], set(r['scores'].keys())) for r in resolved if r['scores']]
    if len(_ds) == 2:
        (na, a), (nb, b) = _ds
        results['venn'] = {
            'n': 2, 'names': [na, nb], 'sizes': [len(a), len(b)],
            'regions': {'A': len(a - b), 'B': len(b - a), 'AB': len(a & b)},
        }
    elif len(_ds) == 3:
        (na, a), (nb, b), (nc, c) = _ds
        results['venn'] = {
            'n': 3, 'names': [na, nb, nc], 'sizes': [len(a), len(b), len(c)],
            'regions': {
                'A': len(a - b - c), 'B': len(b - a - c), 'C': len(c - a - b),
                'AB': len((a & b) - c), 'AC': len((a & c) - b), 'BC': len((b & c) - a),
                'ABC': len(a & b & c),
            },
        }

    if not disease_genes:
        results['errors'].append("No genes found for the selected disease(s)")
        return results
        
    # Get herb genes for each prescription (batch queries - fast!)
    all_herb_genes = []
    for i, herb_names in enumerate(herb_lists):
        herb_genes, missing_herbs = search_herb_genes_batch(herb_names)
        
        prescription_info = {
            'index': i + 1,
            'herbs': herb_names,
            'gene_count': len(herb_genes),
            'missing_herbs': missing_herbs
        }
        results['prescriptions'].append(prescription_info)
        all_herb_genes.append(herb_genes)
        
        if missing_herbs:
            results['errors'].append(f"Prescription {i+1}: Herbs not found - {', '.join(missing_herbs)}")
    
    # Find common genes (set operations - very fast!)
    common_genes = find_common_genes(disease_genes, all_herb_genes)
    
    for i, genes in enumerate(common_genes):
        results['prescriptions'][i]['common_gene_count'] = len(genes)
        # Store common genes as a simple list with their Open Targets scores
        results['prescriptions'][i]['common_genes'] = sorted(genes)
        results['prescriptions'][i]['common_genes_scores'] = {
            gene: round(gene_scores.get(gene, 0.0), 4) for gene in genes
        }
        # ClinGen clinical-validity overlay + Open Targets evidence types for the
        # common (disease-relevant) genes
        results['prescriptions'][i]['common_genes_validity'] = _clingen_validity_for(
            genes, gene_scores, match_diseases, gene_evidence
        )
        results['prescriptions'][i]['common_genes_evidence'] = {
            g: gene_evidence[g] for g in genes if gene_evidence.get(g)
        }
        # Which selected disease(s) each common gene is linked to (multi-disease only)
        results['prescriptions'][i]['common_genes_diseases'] = (
            {g: sorted(gene_diseases.get(g, [])) for g in genes} if multi else {}
        )
    
    if not any(common_genes):
        results['errors'].append("No common genes found between disease and any prescription")
        return results
    
    # Find genes distinctive to each prescription (for the gene-overlap panel)
    unique_genes = find_unique_genes(common_genes)
    for i, genes in enumerate(unique_genes):
        results['prescriptions'][i]['unique_gene_count'] = len(genes)
        results['prescriptions'][i]['distinctive_genes'] = sorted(genes)

    # Gene-overlap summary (pure set logic, no API). This is how prescriptions are
    # compared -- "core" targets shared across formulas vs targets distinctive to
    # one -- instead of enriching the tiny unique sets, which collapse to noise
    # when formulas share herbs.
    common_sets = [set(c) for c in common_genes]
    non_empty_common = [s for s in common_sets if s]
    shared_core = sorted(set.intersection(*non_empty_common)) if non_empty_common else []
    results['gene_overlap'] = {
        'shared_core': shared_core,  # disease targets hit by every prescription that hits the disease
        'distinctive': [
            {
                'index': i + 1,
                'herbs': results['prescriptions'][i].get('herbs', []),
                'genes': sorted(unique_genes[i]),
            }
            for i in range(len(common_genes))
        ],
    }

    # Venn of the disease-associated (common) genes ACROSS prescriptions -- how the
    # intersecting targets overlap between formulas. Center = hit by every formula.
    results['common_union_count'] = len(set.union(*non_empty_common)) if non_empty_common else 0
    results['prescription_venn'] = None
    _ps = [(results['prescriptions'][i]['index'], common_sets[i])
           for i in range(len(common_sets)) if common_sets[i]]
    if len(_ps) == 2:
        (ia, a), (ib, b) = _ps
        results['prescription_venn'] = {
            'n': 2, 'indices': [ia, ib], 'sizes': [len(a), len(b)],
            'regions': {'A': len(a - b), 'B': len(b - a), 'AB': len(a & b)},
        }
    elif len(_ps) == 3:
        (ia, a), (ib, b), (ic, c) = _ps
        results['prescription_venn'] = {
            'n': 3, 'indices': [ia, ib, ic], 'sizes': [len(a), len(b), len(c)],
            'regions': {
                'A': len(a - b - c), 'B': len(b - a - c), 'C': len(c - a - b),
                'AB': len((a & b) - c), 'AC': len((a & c) - b), 'BC': len((b & c) - a),
                'ABC': len(a & b & c),
            },
        }

    # Enrichment runs on each prescription's COMMON genes (the disease-relevant
    # targets the formula actually hits) -- a statistically meaningful input --
    # not the unique set. Prescriptions with fewer than MIN_ENRICHMENT_GENES
    # common genes are skipped (too few for reliable enrichment); they still
    # appear in the gene-overlap panel above.
    enrich_indices = [
        i for i, genes in enumerate(common_genes)
        if len(genes) >= Config.MIN_ENRICHMENT_GENES
    ]
    if enrich_indices:
        try:
            enrich_gene_lists = [list(common_genes[i]) for i in enrich_indices]
            upload_data = upload_gene_lists_to_enrichr_parallel(enrich_gene_lists)
            enrichment_results = perform_enrichment_analysis_parallel(upload_data)

            # Stamp each result with the ORIGINAL prescription number (1-based,
            # matching prescriptions[].index), its herbs, and the gene count it
            # was based on (so the UI/AI can judge confidence). Use each entry's
            # own 'index' (its slot in enrich_gene_lists) rather than list
            # position, so this holds even if an Enrichr upload was dropped.
            for entry in enrichment_results:
                slot = entry.get('index')
                if slot is None or slot >= len(enrich_indices):
                    continue
                original_i = enrich_indices[slot]
                entry['prescription_index'] = original_i + 1
                entry['herbs'] = results['prescriptions'][original_i].get('herbs', [])
                entry['gene_count'] = len(common_genes[original_i])

            results['enrichment_data'] = enrichment_results
        except Exception as e:
            results['errors'].append(f"Enrichment analysis error: {str(e)}")

    return results
