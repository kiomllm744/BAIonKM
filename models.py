"""
Database models for the Disease Portal Flask application.
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Disease(db.Model):
    """Model representing disease-gene associations from DisGeNET."""
    __tablename__ = 'diseases'
    
    Serial_Number_D = db.Column(db.Integer, primary_key=True, autoincrement=True)
    geneNID = db.Column(db.Text)
    diseaseNID = db.Column(db.Text)
    diseaseId = db.Column(db.Text)
    geneId = db.Column(db.Text)
    diseaseName = db.Column(db.Text)
    geneName = db.Column(db.Text)
    score = db.Column(db.Text)
    
    def __repr__(self):
        return f'<Disease {self.diseaseName} - Gene {self.geneName}>'


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