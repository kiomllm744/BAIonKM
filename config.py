"""
Application configuration settings.
"""
import secrets
import os

# Try to import streamlit secrets (for Streamlit Cloud deployment)
def get_streamlit_secret(key, default=None):
    """Safely get a secret from Streamlit, returning default if not available."""
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except:
        pass
    return default

class Config:
    """Base configuration class."""
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    
    # Database - use absolute path for production
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(BASE_DIR, "diseaseportal.db")}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Enrichr API settings
    ENRICHR_BASE_URL = 'https://maayanlab.cloud/Enrichr'
    DEFAULT_GENE_LIBRARY = 'DisGeNET'
    
    # Search settings
    MAX_SUGGESTIONS = 50
    MAX_ENRICHMENT_RESULTS = 15
    ADJUSTED_PVALUE_THRESHOLD = 0.05
    
    # LLM Settings (Gemini API)
    # Priority: Environment variable > Streamlit secrets
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY') or get_streamlit_secret('GEMINI_API_KEY')

