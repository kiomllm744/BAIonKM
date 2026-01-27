"""
Application configuration settings for Flask Disease Portal.
"""
import secrets
import os

class Config:
    """Flask configuration class."""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    
    # Database configuration
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    # Handle DATABASE_URL from Render (PostgreSQL)
    # Render uses 'postgres://' but SQLAlchemy needs 'postgresql://'
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_DATABASE_URI = database_url or f'sqlite:///{os.path.join(BASE_DIR, "diseaseportal.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Enrichr API settings
    ENRICHR_BASE_URL = 'https://maayanlab.cloud/Enrichr'
    DEFAULT_GENE_LIBRARY = 'DisGeNET'
    
    # Search and analysis settings
    MAX_SUGGESTIONS = 50
    MAX_ENRICHMENT_RESULTS = 15
    ADJUSTED_PVALUE_THRESHOLD = 0.05
    
    # LLM Settings (Gemini API)
    # IMPORTANT: Set GEMINI_API_KEY as environment variable
    # - Local: Use .env file
    # - Production: Set in server environment variables
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    
    # Demo Login Credentials (for professor access)
    # You can change these or set via environment variables
    DEMO_USERNAME = os.environ.get('DEMO_USERNAME', 'professor')
    DEMO_PASSWORD = os.environ.get('DEMO_PASSWORD', 'kiom2026')