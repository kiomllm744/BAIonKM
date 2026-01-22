"""
Database models for the Disease Portal application.
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Disease(db.Model):
    """Model representing disease-gene associations from DisGeNET."""
    __tablename__ = 'diseases'
    
    Serial_Number_D = db.Column(db.INTEGER, primary_key=True, autoincrement=True)
    geneNID = db.Column(db.TEXT)
    diseaseNID = db.Column(db.TEXT)
    diseaseId = db.Column(db.TEXT)
    geneId = db.Column(db.TEXT)
    diseaseName = db.Column(db.TEXT)
    geneName = db.Column(db.TEXT)
    score = db.Column(db.TEXT)
    
    def __repr__(self):
        return f'<Disease {self.diseaseName} - Gene {self.geneName}>'


class Herb(db.Model):
    """Model representing herb-gene associations from BATMAN-TCM."""
    __tablename__ = 'herbs'
    
    Serial_Number_H = db.Column(db.INTEGER, primary_key=True, autoincrement=True)
    Compound = db.Column(db.TEXT)
    TCMID_ID = db.Column(db.TEXT)
    Genes = db.Column(db.TEXT)
    GeneId = db.Column(db.TEXT)
    herbName = db.Column(db.TEXT)
    
    def __repr__(self):
        return f'<Herb {self.herbName} - Gene {self.Genes}>'


class AnalysisResult(db.Model):
    """Model for storing analysis results history."""
    __tablename__ = 'analysis_results'
    
    id = db.Column(db.INTEGER, primary_key=True, autoincrement=True)
    disease_name = db.Column(db.TEXT, nullable=False)
    prescriptions = db.Column(db.TEXT, nullable=False)  # JSON string of herb lists
    results_json = db.Column(db.TEXT, nullable=False)  # Full results as JSON
    common_genes_count = db.Column(db.INTEGER, default=0)
    created_at = db.Column(db.DATETIME, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<AnalysisResult {self.disease_name} - {self.created_at}>'
