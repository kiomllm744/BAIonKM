"""
Core services for gene analysis - ONLINE REAL-TIME VERSION.
Contains the main business logic for disease-herb gene analysis using Open Targets API.
"""
import json
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import func, create_engine
from sqlalchemy.orm import sessionmaker
from models import Herb
from config import Config
from opentargets_service import search_disease_efo_id, fetch_live_associated_genes
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


def resolve_disease_to_open_targets(disease_name):
    """
    Resolve a user disease/symptom string to an Open Targets disease ID.

    UMLS is used to add standardized terminology candidates, but Open Targets
    remains the final authority for EFO/MONDO IDs and gene associations.
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


def analyze_prescriptions(disease_name, herb_lists):
    """
    Main analysis function - ONLINE REAL-TIME VERSION.
    """
    disease_name = (disease_name or '').strip()
    resolution = resolve_disease_to_open_targets(disease_name)
    efo_id = resolution.get("efo_id") if resolution else None
    real_name = resolution.get("name") if resolution and resolution.get("name") else disease_name

    results = {
        'disease_name': real_name,
        'disease_cui': efo_id or '',
        'disease_resolution': resolution or {},
        'prescriptions': [],
        'enrichment_data': None,
        'errors': []
    }
    
    # Get disease genes with scores dynamically from Open Targets
    gene_scores = {}
    if efo_id:
        gene_scores = fetch_live_associated_genes(efo_id)
    disease_genes = list(gene_scores.keys())
    results['disease_gene_count'] = len(disease_genes)
    
    if not disease_genes:
        results['errors'].append(f"No genes found for disease: {disease_name}")
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
    
    if not any(common_genes):
        results['errors'].append("No common genes found between disease and any prescription")
        return results
    
    # Find unique genes
    unique_genes = find_unique_genes(common_genes)
    
    for i, genes in enumerate(unique_genes):
        results['prescriptions'][i]['unique_gene_count'] = len(genes)
    
    # Perform enrichment analysis (parallel API calls - faster!)
    if any(len(genes) > 0 for genes in unique_genes):
        try:
            # Filter out empty gene lists
            non_empty_indices = [i for i, genes in enumerate(unique_genes) if len(genes) > 0]
            non_empty_genes = [unique_genes[i] for i in non_empty_indices]
            
            upload_data = upload_gene_lists_to_enrichr_parallel(non_empty_genes)
            results['enrichment_data'] = perform_enrichment_analysis_parallel(upload_data)
        except Exception as e:
            results['errors'].append(f"Enrichment analysis error: {str(e)}")
    
    return results
