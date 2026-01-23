"""
Database models for the Disease Portal application.
Uses pure SQLAlchemy (no Flask dependency) for Streamlit compatibility.
"""
from sqlalchemy import Column, Integer, Text, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# Create base class for models
Base = declarative_base()

# Database path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "diseaseportal.db")
DATABASE_URI = f'sqlite:///{DATABASE_PATH}'


class Disease(Base):
    """Model representing disease-gene associations from DisGeNET."""
    __tablename__ = 'diseases'
    
    Serial_Number_D = Column(Integer, primary_key=True, autoincrement=True)
    geneNID = Column(Text)
    diseaseNID = Column(Text)
    diseaseId = Column(Text)
    geneId = Column(Text)
    diseaseName = Column(Text)
    geneName = Column(Text)
    score = Column(Text)
    
    def __repr__(self):
        return f'<Disease {self.diseaseName} - Gene {self.geneName}>'


class Herb(Base):
    """Model representing herb-gene associations from BATMAN-TCM."""
    __tablename__ = 'herbs'
    
    Serial_Number_H = Column(Integer, primary_key=True, autoincrement=True)
    Compound = Column(Text)
    TCMID_ID = Column(Text)
    Genes = Column(Text)
    GeneId = Column(Text)
    herbName = Column(Text)
    
    def __repr__(self):
        return f'<Herb {self.herbName} - Gene {self.Genes}>'


class AnalysisResult(Base):
    """Model for storing analysis results history."""
    __tablename__ = 'analysis_results'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    disease_name = Column(Text, nullable=False)
    prescriptions = Column(Text, nullable=False)  # JSON string of herb lists
    results_json = Column(Text, nullable=False)  # Full results as JSON
    common_genes_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<AnalysisResult {self.id} - {self.disease_name}>'


# Create engine and session factory
def get_engine():
    """Get SQLAlchemy engine."""
    return create_engine(
        DATABASE_URI,
        pool_pre_ping=True,
        connect_args={'check_same_thread': False}
    )


def get_session():
    """Get a new database session."""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


# For backwards compatibility with Flask code
db = None  # Placeholder
