"""
Application configuration settings for Flask Disease Portal.
"""
import secrets
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Flask configuration class."""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))

    # Session-cookie hardening. HttpOnly stops page JS from reading the session
    # cookie; SameSite=Lax stops the browser from sending it on cross-site POST
    # requests, which blocks the basic CSRF vector against the cookie-authed
    # mutating endpoints (e.g. the saved-result DELETE). Secure is enabled when
    # the app is served over HTTPS (set SESSION_COOKIE_SECURE=true in prod).
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() in ('1', 'true', 'yes')
    
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
    # Default enrichment library is DisGeNET (a disease->gene library), shown as the
    # default in the top-bar "Libraries" picker. Pathway/process libraries (KEGG,
    # Reactome, GO, WikiPathways) are available as opt-in choices in that picker.
    # Override the default with the ENRICHMENT_LIBRARIES env var (comma-separated
    # Enrichr library names).
    DEFAULT_GENE_LIBRARY = 'DisGeNET'  # legacy single-library reference
    ENRICHMENT_LIBRARIES = [
        lib.strip() for lib in os.environ.get(
            'ENRICHMENT_LIBRARIES',
            'DisGeNET'
        ).split(',') if lib.strip()
    ]
    # short, human-friendly labels for the UI (full Enrichr name -> short)
    ENRICHMENT_LIBRARY_LABELS = {
        'KEGG_2021_Human': 'KEGG',
        'Reactome_2022': 'Reactome',
        'GO_Biological_Process_2023': 'GO BP',
        'GO_Molecular_Function_2023': 'GO MF',
        'GO_Cellular_Component_2023': 'GO CC',
        'WikiPathway_2023_Human': 'WikiPathways',
        'DisGeNET': 'DisGeNET',
    }
    ENRICHR_MAX_RETRIES = int(os.environ.get('ENRICHR_MAX_RETRIES', '3'))
    EXTERNAL_API_VERIFY_SSL = os.environ.get('EXTERNAL_API_VERIFY_SSL', 'true').lower() not in ('0', 'false', 'no')
    
    # Open Targets API Settings
    OPENTARGETS_API_URL = os.environ.get(
        'OPENTARGETS_API_URL',
        'https://api.platform.opentargets.org/api/v4/graphql'
    )
    OPENTARGETS_TIMEOUT_SECONDS = int(os.environ.get('OPENTARGETS_TIMEOUT_SECONDS', '15'))
    
    # UMLS terminology normalization. UMLS is only a terminology bridge;
    # Open Targets remains the source for disease IDs, genes, and scores.
    UMLS_API_KEY = os.environ.get('UMLS_API_KEY')
    UMLS_BASE_URL = os.environ.get('UMLS_BASE_URL', 'https://uts-ws.nlm.nih.gov/rest')
    UMLS_TIMEOUT_SECONDS = int(os.environ.get('UMLS_TIMEOUT_SECONDS', '20'))
    UMLS_CACHE_TTL_DAYS = int(os.environ.get('UMLS_CACHE_TTL_DAYS', '30'))
    UMLS_SABS = os.environ.get(
        'UMLS_SABS',
        'SNOMEDCT_US,MSH,ICD10CM,HPO,OMIM,NCI'
    )
    UMLS_SEMANTIC_TYPES = os.environ.get(
        'UMLS_SEMANTIC_TYPES',
        'T047|T046|T184|T033|T048|T191'
    )
    
    # Search and analysis settings
    MAX_SUGGESTIONS = 50
    MAX_ENRICHMENT_RESULTS = 15
    ADJUSTED_PVALUE_THRESHOLD = 0.05
    # Minimum number of genes required to run a meaningful enrichment. Lists
    # smaller than this produce single-gene noise, so they are skipped (the
    # genes still appear in the gene-overlap panel).
    MIN_ENRICHMENT_GENES = 3
    
    # LLM Settings (Gemini API)
    # IMPORTANT: Set GEMINI_API_KEY as environment variable
    # - Local: Use .env file
    # - Production: Set in server environment variables
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    # Primary model is tried first (gemini-3.5-flash, preferred). If it is ever
    # overloaded/limited (503/429), get_gemini_response automatically falls back
    # to the alternates. Override either via env vars.
    GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-3.5-flash')
    GEMINI_FALLBACK_MODELS = [
        m.strip() for m in os.environ.get(
            'GEMINI_FALLBACK_MODELS', 'gemini-2.5-flash,gemini-2.0-flash'
        ).split(',') if m.strip()
    ]

    # Demo Login Credentials (for professor access)
    # You can change these or set via environment variables
    DEMO_USERNAME = os.environ.get('DEMO_USERNAME', 'professor')
    DEMO_PASSWORD = os.environ.get('DEMO_PASSWORD', 'kiom2026')

    @classmethod
    def engine_options(cls):
        """Shared SQLAlchemy create_engine kwargs for every module's engine.

        Each module builds its own engine (routes/services/opentargets/umls),
        so this keeps them identical: pool_pre_ping recycles dead connections
        (important for Postgres in prod after an idle/restart), pool_recycle
        caps connection age, and check_same_thread=False lets the threaded dev
        server share a SQLite connection across threads.
        """
        opts = {'pool_pre_ping': True, 'pool_recycle': 300}
        if cls.SQLALCHEMY_DATABASE_URI.startswith('sqlite'):
            opts['connect_args'] = {'check_same_thread': False}
        return opts
