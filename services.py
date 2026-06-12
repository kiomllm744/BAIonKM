"""
Core services for gene analysis - ONLINE REAL-TIME VERSION.
Contains the main business logic for disease-herb gene analysis using Open Targets API.
"""
import json
import re
import time
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

# Create engine with shared settings (see Config.engine_options)
engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, **Config.engine_options())
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

        # De-duplicate: the herbs table is at the (herb, compound, gene) level, so the
        # same gene appears once per compound (and once per herb). Return UNIQUE gene
        # symbols (dropping any empty/None) so gene_count / the Venn reflect the real
        # number of distinct herb-target genes, not the raw row count.
        return sorted({g for g in gene_symbols if g}), missing_herbs
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


def _enrichr_request(method, url, *, attempts=None, **kwargs):
    """Call Enrichr with retry + exponential backoff.

    Enrichr (a free academic service) rate-limits and intermittently times out,
    especially under parallel load. Retrying transient failures (timeouts, 5xx,
    connection resets) makes enrichment self-heal instead of dropping a
    prescription. Raises the last error if every attempt fails.
    """
    attempts = attempts or Config.ENRICHR_MAX_RETRIES
    kwargs.setdefault('timeout', 30)
    kwargs.setdefault('verify', Config.EXTERNAL_API_VERIFY_SSL)
    last_err = None
    for i in range(attempts):
        try:
            resp = requests.request(method, url, **kwargs)
            if resp.ok:
                return resp
            last_err = Exception(f'Enrichr HTTP {resp.status_code}')
        except Exception as e:  # timeout, connection error, etc.
            last_err = e
        if i < attempts - 1:
            time.sleep(0.6 * (2 ** i))  # 0.6s, 1.2s, 2.4s ...
    raise last_err if last_err else Exception('Enrichr request failed')


def upload_single_gene_list(gene_list, index):
    """Upload a single gene list to Enrichr (for parallel execution)."""
    upload_url = f'{Config.ENRICHR_BASE_URL}/addList'
    genes_str = "\n".join(list(gene_list))
    payload = {'list': (None, genes_str)}

    response = _enrichr_request('POST', upload_url, files=payload, timeout=30)
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
    """Fetch enrichment for a single gene list against one library."""
    enrich_url = f'{Config.ENRICHR_BASE_URL}/enrich'
    response = _enrichr_request(
        'GET',
        f'{enrich_url}?userListId={user_list_id}&backgroundType={library}',
        timeout=60,
    )
    return index, library, json.loads(response.text)


def perform_enrichment_analysis_parallel(data_list, libraries=None):
    """
    Perform enrichment analysis using Enrichr against one or more libraries.

    Each uploaded gene list is scored against every library in `libraries`
    (default Config.ENRICHMENT_LIBRARIES -- pathway/process libraries such as
    KEGG, Reactome, GO). Results from all libraries are merged per prescription,
    tagged with their source library, then ranked by significance.
    """
    if libraries is None:
        libraries = Config.ENRICHMENT_LIBRARIES

    for d in data_list:
        d['enrichment_data'] = []

    # one fetch per (gene list, library) pair, all in parallel
    tasks = [
        (i, d['userListId'], lib)
        for i, d in enumerate(data_list)
        for lib in libraries
    ]
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(fetch_enrichment_single, ulid, lib, i): (i, lib)
            for (i, ulid, lib) in tasks
        }
        for future in as_completed(futures):
            try:
                index, lib, enrichment_data = future.result()
                process_enrichment_data(data_list[index], enrichment_data, lib)
            except Exception as e:
                print(f"Error fetching enrichment: {e}")

    # rank merged results by adjusted p-value and cap per prescription
    for d in data_list:
        d['enrichment_data'].sort(key=lambda r: r.get('Adjusted p-value', 1.0))
        d['enrichment_data'] = d['enrichment_data'][:Config.MAX_ENRICHMENT_RESULTS]

    return data_list


def process_enrichment_data(data, enrichment_data, library=None):
    """Append significant enrichment rows (tagged with their source library).

    Enrichr's /enrich response is a dict keyed by library name whose values
    are lists of result rows, e.g. {"KEGG_2021_Human": [[rank, term, p, ...]]}.
    Rows are ACCUMULATED (so multiple libraries merge per prescription); the
    caller sorts and caps the merged list. `library` is the Enrichr library the
    rows came from; it is stored as a short human label for the UI/AI.
    """
    if not data.get('enrichment_data'):
        data['enrichment_data'] = []

    label = Config.ENRICHMENT_LIBRARY_LABELS.get(library, library) if library else None

    for rows in enrichment_data.values():
        for element in rows:
            try:
                adjusted_p_value = element[6]
            except (IndexError, TypeError):
                continue  # malformed row -> skip rather than crash

            if adjusted_p_value < Config.ADJUSTED_PVALUE_THRESHOLD:
                data['enrichment_data'].append({
                    'Rank': element[0],
                    'Term name': element[1],
                    'P-value': element[2],
                    'Z-score': element[3],
                    'Combined score': element[4],
                    'Overlapping genes': ', '.join(element[5]),
                    'Adjusted p-value': adjusted_p_value,
                    'Old p-value': element[7],
                    'Old adjusted p-value': element[8],
                    'Library': label,
                })


def _score_bucket(score):
    """Open Targets association-score tier (drives gene-chip colour + the prompt)."""
    if score >= 0.4:
        return 'Strong'
    if score >= 0.2:
        return 'Moderate'
    return 'Weak'


def _target_validity_for(common_genes, gene_scores, gene_evidence=None):
    """Build the common_genes_validity map -- Open Targets ONLY (ClinGen removed).

    Each common gene carries its Open Targets association score (0-1, for the analysed
    disease), the evidence datatypes, and a tier (Strong >=0.4 / Moderate >=0.2 / Weak).
    """
    gene_evidence = gene_evidence or {}
    validity = {}
    for gene in common_genes:
        score = round(gene_scores.get(gene, 0.0), 4)
        validity[gene] = {
            'score': score,
            'evidence': gene_evidence.get(gene, []),
            'tier': _score_bucket(score),
        }
    return validity


def analyze_prescriptions(disease_name, herb_lists, efo_id=None, diseases=None,
                          libraries=None, disease_gene_mode='union'):
    """
    Main analysis function - ONLINE REAL-TIME VERSION.

    `libraries` is the list of Enrichr libraries to enrich against (user choice);
    when None it falls back to Config.ENRICHMENT_LIBRARIES.

    `disease_gene_mode` selects which disease-gene set drives the whole pipeline
    (common genes, per-prescription Venns, enrichment, AI):
      - 'union' (default): genes associated with ANY selected disease.
      - 'intersection': only genes associated with ALL selected diseases (the
        "shared core"). With a single disease it is identical to union.

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

    # Both sets are always computed (cheap, no API): the UNION (genes in ANY
    # disease) and the shared core = INTERSECTION (genes in ALL diseases). The
    # chosen mode decides which one drives the rest of the pipeline.
    union_genes = list(gene_scores.keys())
    shared_core = set.intersection(*per_disease_sets) if per_disease_sets else set()
    results['shared_core_genes'] = sorted(shared_core)
    multi = len(resolved) > 1
    results['disease_gene_mode'] = disease_gene_mode
    results['union_gene_count'] = len(union_genes)
    if disease_gene_mode == 'intersection' and multi:
        disease_genes = sorted(shared_core)          # genes shared by ALL diseases
    else:
        disease_genes = union_genes                  # union (also used for 1 disease)
    results['disease_gene_count'] = len(disease_genes)

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
        if disease_gene_mode == 'intersection' and multi:
            # The diseases share no gene at all -> intersection mode has nothing
            # to analyse. Flag it so the UI can show a friendly empty state (the
            # disease summary + Venn are already populated above).
            results['empty_intersection'] = True
            results['errors'].append(
                "No genes are shared by all selected diseases (intersection is empty)."
            )
        else:
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

    # Order disease-relevant gene lists by Open Targets association score (desc),
    # breaking ties alphabetically -- the most disease-associated targets first.
    def _by_ot_score(gene_iterable):
        return sorted(gene_iterable, key=lambda g: (-gene_scores.get(g, 0.0), g))

    for i, genes in enumerate(common_genes):
        results['prescriptions'][i]['common_gene_count'] = len(genes)
        # Open Targets association-score overlay (score + evidence + Strong/Moderate/Weak
        # tier) -- drives both the gene-chip colours and the ordering below.
        validity = _target_validity_for(genes, gene_scores, gene_evidence)

        # Order by Open Targets association score (desc), then gene name -- most
        # disease-relevant targets first.
        ordered = sorted(genes, key=lambda g: (-gene_scores.get(g, 0.0), g))
        results['prescriptions'][i]['common_genes'] = ordered
        results['prescriptions'][i]['common_genes_scores'] = {
            gene: round(gene_scores.get(gene, 0.0), 4) for gene in ordered
        }
        results['prescriptions'][i]['common_genes_validity'] = validity
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
        results['prescriptions'][i]['distinctive_genes'] = _by_ot_score(genes)

    # Gene-overlap summary (pure set logic, no API). This is how prescriptions are
    # compared -- "core" targets shared across formulas vs targets distinctive to
    # one -- instead of enriching the tiny unique sets, which collapse to noise
    # when formulas share herbs.
    common_sets = [set(c) for c in common_genes]
    non_empty_common = [s for s in common_sets if s]
    shared_core = _by_ot_score(set.intersection(*non_empty_common)) if non_empty_common else []
    results['gene_overlap'] = {
        'shared_core': shared_core,  # disease targets hit by every prescription that hits the disease
        'distinctive': [
            {
                'index': i + 1,
                'herbs': results['prescriptions'][i].get('herbs', []),
                'genes': _by_ot_score(unique_genes[i]),
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
    # libraries to enrich against: user choice, else the config default
    active_libraries = [lib for lib in (libraries or Config.ENRICHMENT_LIBRARIES) if lib] \
        or Config.ENRICHMENT_LIBRARIES
    # the human-friendly library labels used for enrichment (for the UI heading)
    results['enrichment_libraries'] = [
        Config.ENRICHMENT_LIBRARY_LABELS.get(lib, lib) for lib in active_libraries
    ]
    if enrich_indices:
        try:
            enrich_gene_lists = [list(common_genes[i]) for i in enrich_indices]
            upload_data = upload_gene_lists_to_enrichr_parallel(enrich_gene_lists)
            enrichment_results = perform_enrichment_analysis_parallel(upload_data, libraries=active_libraries)

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

            # Surface any prescription that was eligible for enrichment but came
            # back empty (e.g. a transient Enrichr upload/fetch failure), so it is
            # reported rather than silently missing from the results.
            returned = {e.get('prescription_index') for e in enrichment_results}
            for i in enrich_indices:
                if (i + 1) not in returned:
                    results['errors'].append(
                        f"Prescription {i+1}: enrichment could not be retrieved from Enrichr "
                        "(transient error) — try running again."
                    )

            results['enrichment_data'] = enrichment_results
        except Exception as e:
            results['errors'].append(f"Enrichment analysis error: {str(e)}")

    return results


def compute_disease_venn(disease_name, efo_id=None, diseases=None):
    """Resolve the selected diseases and fetch ONLY their gene sets (no herbs,
    no enrichment, no AI) so the choice screen can show the disease Venn fast.

    Reuses analyze_prescriptions (with empty herb_lists) so the Venn here is
    byte-identical to the one on the result page -- the disease resolution +
    Open Targets fetches are cached, so the subsequent full run is ~free.
    Returns the disease list, the Venn, and the union / intersection counts.
    """
    res = analyze_prescriptions(disease_name, [], efo_id=efo_id, diseases=diseases)
    intersection_count = len(res.get('shared_core_genes', []))
    # This call deliberately passes NO herbs (we only want the disease Venn before
    # the user picks a mode), so the herb-overlap check fires a "No common genes
    # found between disease and any prescription" error that is meaningless here.
    # Drop it; keep genuine disease-resolution errors.
    venn_errors = [
        e for e in res.get('errors', [])
        if 'No common genes found' not in e
    ]
    return {
        'diseases': res.get('diseases', []),
        'venn': res.get('venn'),
        'disease_name': res.get('disease_name', ''),
        'union_count': res.get('union_gene_count', res.get('disease_gene_count', 0)),
        'intersection_count': intersection_count,
        'has_intersection': intersection_count > 0,
        'errors': venn_errors,
    }
