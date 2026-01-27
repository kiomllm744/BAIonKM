"""
Core services for gene analysis - OPTIMIZED VERSION.
Contains the main business logic for disease-herb gene analysis.
"""
import json
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import func, create_engine, text
from sqlalchemy.orm import sessionmaker
from models import Disease, Herb
from config import Config


# Create engine with optimized settings
# Only use check_same_thread for SQLite (not valid for PostgreSQL)
engine_args = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}
if Config.SQLALCHEMY_DATABASE_URI.startswith('sqlite'):
    engine_args['connect_args'] = {'check_same_thread': False}

engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, **engine_args)
Session = sessionmaker(bind=engine)


def search_disease_genes(disease_name):
    """
    Search for genes associated with a disease.
    OPTIMIZED: Uses indexed query.
    """
    session = Session()
    try:
        # Use LOWER() which is now indexed
        matching_records = session.query(Disease.geneName).filter(
            func.lower(Disease.diseaseName) == disease_name.lower()
        ).all()
        disease_gene_symbols = [record[0] for record in matching_records]
        return disease_gene_symbols
    finally:
        session.close()


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


# Keep original function for compatibility but use optimized version
def search_herb_genes(herb_names):
    """Alias for batch function."""
    return search_herb_genes_batch(herb_names)


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
    
    response = requests.post(upload_url, files=payload, timeout=30)
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
        timeout=60
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
    """Process raw enrichment data into structured format."""
    df = pd.DataFrame(enrichment_data)
    data['enrichment_data'] = []

    for _, row in df.iterrows():
        for element in row:
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


# Backwards compatibility aliases
upload_gene_lists_to_enrichr = upload_gene_lists_to_enrichr_parallel
perform_enrichment_analysis = perform_enrichment_analysis_parallel


def analyze_prescriptions(disease_name, herb_lists):
    """
    Main analysis function - OPTIMIZED VERSION.
    """
    results = {
        'disease_name': disease_name,
        'prescriptions': [],
        'enrichment_data': None,
        'errors': []
    }
    
    # Get disease genes (now indexed - fast!)
    disease_genes = search_disease_genes(disease_name)
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
