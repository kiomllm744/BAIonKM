"""
Database models for the Disease Portal Flask application.
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Herb(db.Model):
    """Model representing herb-gene associations from BATMAN-TCM."""
    __tablename__ = 'herbs'
    
    Serial_Number_H = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Compound = db.Column(db.Text)
    TCMID_ID = db.Column(db.Text)
    Genes = db.Column(db.Text)
    GeneId = db.Column(db.Text)
    herbName = db.Column(db.Text)
    
    def __repr__(self):
        return f'<Herb {self.herbName} - Gene {self.Genes}>'


class Disease(db.Model):
    """Local index of Open Targets diseases/phenotypes for browsing the full
    catalogue. Populated by build_disease_index.py. Genes are still fetched
    live from Open Targets at analysis time -- this is only the name/ID list."""
    __tablename__ = 'diseases'

    efo_id = db.Column(db.Text, primary_key=True)  # EFO_/MONDO_/Orphanet_/HP_...
    name = db.Column(db.Text, nullable=False, index=True)

    def __repr__(self):
        return f'<Disease {self.efo_id} {self.name}>'


class AnalysisResult(db.Model):
    """Model for storing analysis results history."""
    __tablename__ = 'analysis_results'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    disease_name = db.Column(db.Text, nullable=False)
    prescriptions = db.Column(db.Text, nullable=False)  # JSON string of herb lists
    results_json = db.Column(db.Text, nullable=False)   # Full results as JSON
    ai_analysis_json = db.Column(db.Text, nullable=True)  # AI analysis results (Gemini)
    common_genes_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<AnalysisResult {self.disease_name} - {self.created_at}>'


class ExternalLookupCache(db.Model):
    """Cache for external API lookups (Open Targets autocomplete/gene results)."""
    __tablename__ = 'external_lookup_cache'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    provider = db.Column(db.Text, nullable=False)
    cache_key = db.Column(db.Text, nullable=False, unique=True)
    query = db.Column(db.Text, nullable=False)
    response_json = db.Column(db.Text, nullable=False)
    source = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)


class User(db.Model):
    """Registered user account (email + password) for login."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.Text, nullable=False, unique=True)
    password_hash = db.Column(db.Text, nullable=False)
    ai_provider = db.Column(db.Text, nullable=True)            # saved AI model: gemini|claude|gpt
    enrichment_libraries = db.Column(db.Text, nullable=True)   # saved libraries (JSON list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<User {self.email}>'
