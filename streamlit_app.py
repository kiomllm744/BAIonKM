"""
Disease Portal - Streamlit Application
A modern, AI-powered disease-herb gene analysis tool.
"""
import streamlit as st
import pandas as pd
import json
from datetime import datetime
import sqlite3
import os

# Check if database exists, if not try to download it
DB_PATH = os.path.join(os.path.dirname(__file__), "diseaseportal.db")
if not os.path.exists(DB_PATH):
    st.warning("Database not found. Attempting to download...")
    try:
        from download_db import download_from_gdrive, GDRIVE_FILE_ID
        download_from_gdrive(GDRIVE_FILE_ID, DB_PATH)
        st.success("Database downloaded successfully!")
        st.rerun()
    except Exception as e:
        st.error(f"Failed to download database: {e}")
        st.stop()

# Import our services (after database check)
from services import (
    search_disease_genes,
    search_herb_genes_batch,
    find_common_genes,
    find_unique_genes,
    upload_gene_lists_to_enrichr_parallel,
    perform_enrichment_analysis_parallel
)
from llm_service import generate_full_ai_analysis
from config import Config

# Page config
st.set_page_config(
    page_title="Disease Portal - Gene Analysis",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern styling
st.markdown("""
<style>
    /* Main styling */
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1a365d;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #4a5568;
        margin-bottom: 2rem;
    }
    
    /* Card styling */
    .stCard {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        margin-bottom: 1rem;
    }
    
    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
    }
    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
    }
    .metric-label {
        font-size: 0.9rem;
        opacity: 0.9;
    }
    
    /* Prescription tags */
    .herb-tag {
        display: inline-block;
        background: #e2e8f0;
        color: #2d3748;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        margin: 0.25rem;
        font-size: 0.85rem;
    }
    
    /* Status badges */
    .status-success {
        background: #c6f6d5;
        color: #22543d;
        padding: 0.25rem 0.75rem;
        border-radius: 4px;
        font-size: 0.85rem;
    }
    .status-warning {
        background: #fef3c7;
        color: #92400e;
        padding: 0.25rem 0.75rem;
        border-radius: 4px;
        font-size: 0.85rem;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #f1f5f9;
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #3b82f6;
        color: white;
    }
</style>
""", unsafe_allow_html=True)


# Database connection helper
def get_db_connection():
    """Get a database connection."""
    db_path = os.path.join(os.path.dirname(__file__), "diseaseportal.db")
    return sqlite3.connect(db_path)


@st.cache_data(ttl=3600)
def get_all_diseases():
    """Get all unique disease names from database."""
    conn = get_db_connection()
    df = pd.read_sql("SELECT DISTINCT diseaseName FROM diseases ORDER BY diseaseName", conn)
    conn.close()
    return df['diseaseName'].tolist()


@st.cache_data(ttl=3600)
def get_all_herbs():
    """Get all unique herb names from database."""
    conn = get_db_connection()
    df = pd.read_sql("SELECT DISTINCT herbName FROM herbs ORDER BY herbName", conn)
    conn.close()
    return df['herbName'].tolist()


@st.cache_data(ttl=3600)
def get_database_stats():
    """Get database statistics."""
    conn = get_db_connection()
    
    disease_count = pd.read_sql("SELECT COUNT(DISTINCT diseaseName) as count FROM diseases", conn).iloc[0]['count']
    herb_count = pd.read_sql("SELECT COUNT(DISTINCT herbName) as count FROM herbs", conn).iloc[0]['count']
    
    conn.close()
    return {'diseases': disease_count, 'herbs': herb_count}


def analyze_prescriptions_streamlit(disease_name, herb_lists):
    """
    Main analysis function adapted for Streamlit.
    """
    results = {
        'disease_name': disease_name,
        'prescriptions': [],
        'enrichment_data': None,
        'prescription_enrichments': {},
        'errors': []
    }
    
    # Get disease genes
    disease_genes = search_disease_genes(disease_name)
    results['disease_gene_count'] = len(disease_genes)
    
    if not disease_genes:
        results['errors'].append(f"No genes found for disease: {disease_name}")
        return results
    
    # Get herb genes for each prescription
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
    
    # Find common genes
    common_genes = find_common_genes(disease_genes, all_herb_genes)
    
    for i, genes in enumerate(common_genes):
        results['prescriptions'][i]['common_gene_count'] = len(genes)
        results['prescriptions'][i]['common_genes'] = list(genes)
    
    # Store all common genes
    all_common = set()
    for genes in common_genes:
        all_common.update(genes)
    results['common_genes'] = list(all_common)
    
    if not any(common_genes):
        results['errors'].append("No common genes found between disease and any prescription")
        return results
    
    # Find unique genes
    unique_genes = find_unique_genes(common_genes)
    
    for i, genes in enumerate(unique_genes):
        results['prescriptions'][i]['unique_gene_count'] = len(genes)
        results['prescriptions'][i]['unique_genes'] = list(genes)
    
    # Perform enrichment analysis
    if any(len(genes) > 0 for genes in unique_genes):
        try:
            non_empty_indices = [i for i, genes in enumerate(unique_genes) if len(genes) > 0]
            non_empty_genes = [unique_genes[i] for i in non_empty_indices]
            
            upload_data = upload_gene_lists_to_enrichr_parallel(non_empty_genes)
            enrichment_results = perform_enrichment_analysis_parallel(upload_data)
            results['enrichment_data'] = enrichment_results
            
            # Format for AI analysis
            for idx, data in enumerate(enrichment_results):
                rx_key = f"Rx{non_empty_indices[idx] + 1}"
                if 'enrichment_data' in data:
                    formatted_enrichment = []
                    for item in data['enrichment_data']:
                        formatted_enrichment.append({
                            'term': item.get('Term name', ''),
                            'p_value': item.get('P-value', 0),
                            'adjusted_p_value': item.get('Adjusted p-value', 0),
                            'combined_score': item.get('Combined score', 0),
                            'genes': item.get('Overlapping genes', '')
                        })
                    results['prescription_enrichments'][rx_key] = {
                        'DisGeNET': formatted_enrichment
                    }
                    
        except Exception as e:
            results['errors'].append(f"Enrichment analysis error: {str(e)}")
    
    return results


# Initialize session state
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'prescriptions' not in st.session_state:
    st.session_state.prescriptions = [{'herbs': []}]
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'analysis'


# Sidebar navigation
with st.sidebar:
    st.markdown("### 🧬 Disease Portal")
    st.markdown("---")
    
    page = st.radio(
        "Navigation",
        ["🔬 Analysis", "📊 Database Explorer", "📜 History", "ℹ️ About"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # Quick stats
    stats = get_database_stats()
    st.metric("Diseases", f"{stats['diseases']:,}")
    st.metric("Herbs", f"{stats['herbs']:,}")
    
    # AI Status
    st.markdown("---")
    if Config.GEMINI_API_KEY:
        st.success("🤖 AI Analysis: Ready")
    else:
        st.warning("🤖 AI Analysis: Not configured")


# Main content based on navigation
if page == "🔬 Analysis":
    st.markdown('<h1 class="main-header">🧬 Disease-Herb Gene Analysis</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Discover common genes between diseases and traditional herbal prescriptions using enrichment analysis.</p>', unsafe_allow_html=True)
    
    # Analysis form
    with st.form("analysis_form"):
        # Disease selection
        all_diseases = get_all_diseases()
        disease_name = st.selectbox(
            "🦠 Select Disease",
            options=[""] + all_diseases,
            help="Start typing to search for a disease"
        )
        
        st.markdown("---")
        st.markdown("### 🌿 Prescriptions")
        
        # Get all herbs for selection
        all_herbs = get_all_herbs()
        
        # Dynamic prescription inputs
        num_prescriptions = st.number_input(
            "Number of prescriptions to compare",
            min_value=1,
            max_value=5,
            value=1
        )
        
        prescription_herbs = []
        cols = st.columns(min(num_prescriptions, 3))
        
        for i in range(num_prescriptions):
            col_idx = i % 3
            with cols[col_idx] if num_prescriptions <= 3 else st.container():
                st.markdown(f"**Prescription {i+1}**")
                selected_herbs = st.multiselect(
                    f"Select herbs for Rx{i+1}",
                    options=all_herbs,
                    key=f"herbs_{i}",
                    help="Select multiple herbs for this prescription"
                )
                prescription_herbs.append(selected_herbs)
        
        st.markdown("---")
        
        # Submit button
        submitted = st.form_submit_button("🔬 Analyze", use_container_width=True, type="primary")
    
    # Handle form submission
    if submitted:
        if not disease_name:
            st.error("Please select a disease")
        elif not any(prescription_herbs):
            st.error("Please add at least one herb to a prescription")
        else:
            # Filter out empty prescriptions
            herb_lists = [h for h in prescription_herbs if h]
            
            with st.spinner("Analyzing prescriptions... This may take a moment."):
                results = analyze_prescriptions_streamlit(disease_name, herb_lists)
                st.session_state.analysis_results = results
            
            st.success("Analysis complete!")
    
    # Display results
    if st.session_state.analysis_results:
        results = st.session_state.analysis_results
        
        st.markdown("---")
        st.markdown("## 📊 Analysis Results")
        
        # Show errors if any
        if results.get('errors'):
            for error in results['errors']:
                st.warning(error)
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Disease", results['disease_name'][:30] + "..." if len(results['disease_name']) > 30 else results['disease_name'])
        
        with col2:
            st.metric("Disease Genes", results.get('disease_gene_count', 0))
        
        with col3:
            st.metric("Prescriptions", len(results.get('prescriptions', [])))
        
        with col4:
            st.metric("Common Genes", len(results.get('common_genes', [])))
        
        # Prescription details
        st.markdown("### 📋 Prescription Details")
        
        tabs = st.tabs([f"Rx {p['index']}" for p in results.get('prescriptions', [])])
        
        for idx, tab in enumerate(tabs):
            with tab:
                prescription = results['prescriptions'][idx]
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Herbs", len(prescription['herbs']))
                with col2:
                    st.metric("Common Genes", prescription.get('common_gene_count', 0))
                with col3:
                    st.metric("Unique Genes", prescription.get('unique_gene_count', 0))
                
                # Show herbs
                st.markdown("**Herbs:**")
                herb_tags = " ".join([f'<span class="herb-tag">{h}</span>' for h in prescription['herbs']])
                st.markdown(herb_tags, unsafe_allow_html=True)
                
                # Show missing herbs if any
                if prescription.get('missing_herbs'):
                    st.warning(f"Not found: {', '.join(prescription['missing_herbs'])}")
                
                # Show unique genes
                if prescription.get('unique_genes'):
                    with st.expander(f"View Unique Genes ({len(prescription['unique_genes'])})"):
                        st.write(", ".join(sorted(prescription['unique_genes'])))
        
        # Enrichment results
        if results.get('enrichment_data'):
            st.markdown("### 🧪 Enrichment Analysis (DisGeNET)")
            
            for i, enrichment in enumerate(results['enrichment_data']):
                if enrichment and enrichment.get('enrichment_data'):
                    with st.expander(f"Prescription {i+1} - Enrichment Results ({len(enrichment['enrichment_data'])} terms)", expanded=(i==0)):
                        df = pd.DataFrame(enrichment['enrichment_data'])
                        
                        if not df.empty:
                            # Format display columns
                            display_df = df[['Rank', 'Term name', 'Adjusted p-value', 'Combined score', 'Overlapping genes']].copy()
                            display_df['Adjusted p-value'] = display_df['Adjusted p-value'].apply(lambda x: f"{x:.2e}")
                            display_df['Combined score'] = display_df['Combined score'].apply(lambda x: f"{x:.2f}")
                            
                            st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # AI Analysis section
        if Config.GEMINI_API_KEY and results.get('prescription_enrichments'):
            st.markdown("---")
            st.markdown("## 🤖 AI-Powered Analysis")
            
            if st.button("Generate AI Analysis", type="primary", use_container_width=True):
                with st.spinner("Generating AI analysis... This may take 30-60 seconds."):
                    ai_results = generate_full_ai_analysis(
                        results['disease_name'],
                        {'prescription_enrichments': results['prescription_enrichments']}
                    )
                    st.session_state.ai_results = ai_results
            
            if 'ai_results' in st.session_state and st.session_state.ai_results:
                ai_results = st.session_state.ai_results
                
                if ai_results.get('has_ai_analysis'):
                    # Summary Table
                    if ai_results.get('summary_table'):
                        st.markdown("### 📊 Comparative Summary")
                        summary_df = pd.DataFrame(ai_results['summary_table'])
                        st.dataframe(summary_df, use_container_width=True, hide_index=True)
                    
                    # Detailed Analysis
                    if ai_results.get('detailed_analysis'):
                        st.markdown("### 📝 Detailed Analysis")
                        with st.expander("View Full Analysis", expanded=True):
                            st.markdown(ai_results['detailed_analysis'])
                    
                    # Clinical Questions
                    if ai_results.get('clinical_questions'):
                        st.markdown("### 🏥 Clinical Interview Guide")
                        
                        for card in ai_results['clinical_questions']:
                            with st.container():
                                st.markdown(f"#### {card.get('group_label', 'Analysis')}")
                                st.markdown(f"**Suspected Driver:** {card.get('suspected_driver', 'N/A')}")
                                
                                st.markdown("**Clinical Questions:**")
                                for q in card.get('clinical_questions', []):
                                    st.markdown(f"- {q}")
                                
                                with st.expander("View Rationale"):
                                    st.markdown(card.get('rationale_hidden', 'No rationale available.'))
                                
                                st.markdown("---")
                else:
                    if ai_results.get('error'):
                        st.error(f"AI Analysis Error: {ai_results['error']}")


elif page == "📊 Database Explorer":
    st.markdown("## 📊 Database Explorer")
    
    tab1, tab2 = st.tabs(["🦠 Diseases", "🌿 Herbs"])
    
    with tab1:
        st.markdown("### Disease Database")
        
        # Search
        search_disease = st.text_input("Search diseases", placeholder="Type to search...")
        
        conn = get_db_connection()
        
        if search_disease:
            query = f"SELECT diseaseName, COUNT(geneName) as gene_count FROM diseases WHERE diseaseName LIKE '%{search_disease}%' GROUP BY diseaseName ORDER BY diseaseName LIMIT 100"
        else:
            query = "SELECT diseaseName, COUNT(geneName) as gene_count FROM diseases GROUP BY diseaseName ORDER BY diseaseName LIMIT 100"
        
        df = pd.read_sql(query, conn)
        conn.close()
        
        st.dataframe(df, use_container_width=True, hide_index=True, column_config={
            "diseaseName": "Disease Name",
            "gene_count": "Gene Count"
        })
    
    with tab2:
        st.markdown("### Herb Database")
        
        # Search
        search_herb = st.text_input("Search herbs", placeholder="Type to search...")
        
        conn = get_db_connection()
        
        if search_herb:
            query = f"SELECT herbName, COUNT(DISTINCT Genes) as gene_count, COUNT(DISTINCT Compound) as compound_count FROM herbs WHERE herbName LIKE '%{search_herb}%' GROUP BY herbName ORDER BY herbName LIMIT 100"
        else:
            query = "SELECT herbName, COUNT(DISTINCT Genes) as gene_count, COUNT(DISTINCT Compound) as compound_count FROM herbs GROUP BY herbName ORDER BY herbName LIMIT 100"
        
        df = pd.read_sql(query, conn)
        conn.close()
        
        st.dataframe(df, use_container_width=True, hide_index=True, column_config={
            "herbName": "Herb Name",
            "gene_count": "Gene Count",
            "compound_count": "Compound Count"
        })


elif page == "📜 History":
    st.markdown("## 📜 Analysis History")
    st.info("Analysis history is stored in your session. Results are cleared when you close the browser.")
    
    if st.session_state.analysis_results:
        st.markdown("### Last Analysis")
        results = st.session_state.analysis_results
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Disease", results['disease_name'][:25] + "...")
        with col2:
            st.metric("Prescriptions", len(results.get('prescriptions', [])))
        with col3:
            st.metric("Common Genes", len(results.get('common_genes', [])))
        
        if st.button("View Full Results"):
            st.session_state.current_page = 'analysis'
            st.rerun()
    else:
        st.info("No analysis results yet. Go to the Analysis page to get started!")


elif page == "ℹ️ About":
    st.markdown("## ℹ️ About Disease Portal")
    
    st.markdown("""
    ### 🧬 What is Disease Portal?
    
    Disease Portal is an AI-powered bioinformatics tool that helps researchers and clinicians:
    
    - **Discover gene-disease associations** from the DisGeNET database
    - **Analyze traditional herbal prescriptions** and their target genes
    - **Find common therapeutic pathways** between diseases and herbal treatments
    - **Generate AI-powered insights** for pathway analysis and clinical applications
    
    ### 🔬 How It Works
    
    1. **Select a Disease**: Choose from thousands of diseases in our database
    2. **Add Prescriptions**: Input one or more herbal prescriptions to analyze
    3. **Gene Analysis**: The system finds common genes between disease and herbs
    4. **Enrichment Analysis**: Uses Enrichr API to identify enriched pathways
    5. **AI Insights**: Google Gemini generates comparative analysis and clinical questions
    
    ### 📊 Data Sources
    
    - **Disease-Gene Associations**: DisGeNET database
    - **Herb-Gene Associations**: BATMAN-TCM database
    - **Pathway Enrichment**: Enrichr API (Ma'ayan Lab)
    - **AI Analysis**: Google Gemini 2.0 Flash
    
    ### 🛠️ Technology Stack
    
    - **Frontend**: Streamlit
    - **Database**: SQLite
    - **AI**: Google Gemini API
    - **Analysis**: Enrichr API
    
    ### 📧 Contact
    
    For questions or feedback, please open an issue on our [GitHub repository](https://github.com/umarashraf914/Systems_Biology).
    
    ---
    
    *Built with ❤️ for the research community*
    """)


# Footer
st.markdown("---")
st.markdown(
    '<p style="text-align: center; color: #718096; font-size: 0.85rem;">Disease Portal v2.0 | Powered by DisGeNET, BATMAN-TCM, Enrichr & Google Gemini</p>',
    unsafe_allow_html=True
)
