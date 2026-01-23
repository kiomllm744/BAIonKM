"""
Database models for the Disease Portal application.
Supports both Flask-SQLAlchemy and pure SQLAlchemy for flexibility.
"""
from datetime import datetime
import os

# Database path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "diseaseportal.db")
DATABASE_URI = f'sqlite:///{DATABASE_PATH}'

# Try Flask-SQLAlchemy first (for Flask app), fall back to pure SQLAlchemy (for Streamlit)
try:
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()
    USING_FLASK = True
    
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
        prescriptions = db.Column(db.Text, nullable=False)
        results_json = db.Column(db.Text, nullable=False)
        common_genes_count = db.Column(db.Integer, default=0)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        
        def __repr__(self):
            return f'<AnalysisResult {self.disease_name} - {self.created_at}>'

except ImportError:
    # Pure SQLAlchemy models (for Streamlit or when Flask is not installed)
    from sqlalchemy import Column, Integer, Text, DateTime, create_engine
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker
    
    db = None
    USING_FLASK = False
    Base = declarative_base()
    
    class Disease(Base):
        __tablename__ = 'diseases'
        Serial_Number_D = Column(Integer, primary_key=True, autoincrement=True)
        geneNID = Column(Text)
        diseaseNID = Column(Text)
        diseaseId = Column(Text)
        geneId = Column(Text)
        diseaseName = Column(Text)
        geneName = Column(Text)
        score = Column(Text)

    class Herb(Base):
        __tablename__ = 'herbs'
        Serial_Number_H = Column(Integer, primary_key=True, autoincrement=True)
        Compound = Column(Text)
        TCMID_ID = Column(Text)
        Genes = Column(Text)
        GeneId = Column(Text)
        herbName = Column(Text)

    class AnalysisResult(Base):
        __tablename__ = 'analysis_results'
        id = Column(Integer, primary_key=True, autoincrement=True)
        disease_name = Column(Text, nullable=False)
        prescriptions = Column(Text, nullable=False)
        results_json = Column(Text, nullable=False)
        common_genes_count = Column(Integer, default=0)
        created_at = Column(DateTime, default=datetime.utcnow)


def get_engine():
    """Get SQLAlchemy engine (for non-Flask usage)."""
    from sqlalchemy import create_engine
    return create_engine(
        DATABASE_URI,
        pool_pre_ping=True,
        connect_args={'check_same_thread': False}
    )


def get_session():
    """Get a new database session (for non-Flask usage)."""
    from sqlalchemy.orm import sessionmaker
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()
