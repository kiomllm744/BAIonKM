"""
Flask routes for the Disease Portal application.
"""
import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from sqlalchemy import func, desc
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from models import Disease, Herb, AnalysisResult
from services import analyze_prescriptions
from config import Config
from llm_service import generate_full_ai_analysis

# Create blueprint
main_bp = Blueprint('main', __name__)

# Create engine and session
engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
Session = sessionmaker(bind=engine)

# Ensure the analysis_results table exists
def init_results_table():
    """Create the analysis_results table if it doesn't exist."""
    from sqlalchemy import MetaData, Table, Column, Integer, Text, DateTime
    metadata = MetaData()
    
    analysis_results = Table(
        'analysis_results', metadata,
        Column('id', Integer, primary_key=True, autoincrement=True),
        Column('disease_name', Text, nullable=False),
        Column('prescriptions', Text, nullable=False),
        Column('results_json', Text, nullable=False),
        Column('common_genes_count', Integer, default=0),
        Column('created_at', DateTime, default=datetime.utcnow)
    )
    
    metadata.create_all(engine)

# Initialize table on import
init_results_table()


@main_bp.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')


@main_bp.route('/database')
def database():
    """Render the database explorer page."""
    return render_template('database.html')


@main_bp.route('/results')
def results():
    """Render the results history page."""
    return render_template('results_history.html')


@main_bp.route('/about')
def about():
    """Render the about page."""
    return render_template('about.html')


@main_bp.route('/api/database/diseases')
def get_diseases_paginated():
    """API endpoint to get paginated diseases data."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    search = request.args.get('search', '').strip()
    
    session = Session()
    try:
        query = session.query(
            Disease.diseaseName,
            func.count(Disease.geneName).label('gene_count')
        ).group_by(Disease.diseaseName)
        
        if search:
            query = query.filter(Disease.diseaseName.ilike(f'%{search}%'))
        
        total = query.count()
        
        diseases = query.order_by(Disease.diseaseName)\
            .offset((page - 1) * per_page)\
            .limit(per_page)\
            .all()
        
        return jsonify({
            'data': [{'name': d[0], 'gene_count': d[1]} for d in diseases],
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })
    finally:
        session.close()


@main_bp.route('/api/database/herbs')
def get_herbs_paginated():
    """API endpoint to get paginated herbs data."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    search = request.args.get('search', '').strip()
    
    session = Session()
    try:
        query = session.query(
            Herb.herbName,
            func.count(Herb.Genes).label('gene_count'),
            func.count(func.distinct(Herb.Compound)).label('compound_count')
        ).group_by(Herb.herbName)
        
        if search:
            query = query.filter(Herb.herbName.ilike(f'%{search}%'))
        
        total = query.count()
        
        herbs = query.order_by(Herb.herbName)\
            .offset((page - 1) * per_page)\
            .limit(per_page)\
            .all()
        
        return jsonify({
            'data': [{'name': h[0], 'gene_count': h[1], 'compound_count': h[2]} for h in herbs],
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })
    finally:
        session.close()


@main_bp.route('/api/database/disease/<disease_name>/genes')
def get_disease_genes(disease_name):
    """API endpoint to get genes for a specific disease."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    session = Session()
    try:
        query = session.query(Disease.geneName, Disease.geneId, Disease.score).filter(
            func.lower(Disease.diseaseName) == disease_name.lower()
        )
        
        total = query.count()
        
        genes = query.order_by(Disease.geneName)\
            .offset((page - 1) * per_page)\
            .limit(per_page)\
            .all()
        
        return jsonify({
            'disease': disease_name,
            'data': [{'gene': g[0], 'gene_id': g[1], 'score': g[2]} for g in genes],
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })
    finally:
        session.close()


@main_bp.route('/api/database/herb/<herb_name>/genes')
def get_herb_genes(herb_name):
    """API endpoint to get genes for a specific herb, grouped by compound."""
    session = Session()
    try:
        # Get all genes for this herb
        records = session.query(Herb.Compound, Herb.Genes, Herb.GeneId).filter(
            func.lower(Herb.herbName) == herb_name.lower()
        ).order_by(Herb.Compound, Herb.Genes).all()
        
        # Group by compound
        compounds_dict = {}
        for compound, gene, gene_id in records:
            if compound not in compounds_dict:
                compounds_dict[compound] = []
            compounds_dict[compound].append({
                'gene': gene,
                'gene_id': gene_id
            })
        
        # Convert to list format
        compounds_list = [
            {
                'compound': compound,
                'genes': genes,
                'gene_count': len(genes)
            }
            for compound, genes in compounds_dict.items()
        ]
        
        return jsonify({
            'herb': herb_name,
            'compounds': compounds_list,
            'total_compounds': len(compounds_list),
            'total_genes': len(records)
        })
    finally:
        session.close()


@main_bp.route('/api/diseases')
def get_disease_suggestions():
    """API endpoint to get disease name suggestions, sorted by relevance."""
    query = request.args.get('q', '').strip()
    
    if len(query) < 1:
        return jsonify([])
    
    session = Session()
    try:
        # Get more results than needed for better sorting
        matching_diseases = session.query(Disease.diseaseName).filter(
            Disease.diseaseName.ilike(f'%{query}%')
        ).distinct().limit(Config.MAX_SUGGESTIONS * 3).all()
        
        suggestions = [disease[0] for disease in matching_diseases]
        
        # Sort by relevance
        query_lower = query.lower()
        
        def relevance_score(name):
            name_lower = name.lower()
            # Exact match (highest priority)
            if name_lower == query_lower:
                return (0, len(name), name_lower)
            # Starts with query
            elif name_lower.startswith(query_lower):
                return (1, len(name), name_lower)
            # Word starts with query (e.g., "Type 2 Diabetes" when searching "diabetes")
            elif any(word.startswith(query_lower) for word in name_lower.split()):
                return (2, len(name), name_lower)
            # Contains query in middle
            else:
                # Earlier position = higher priority
                pos = name_lower.find(query_lower)
                return (3, pos, len(name), name_lower)
        
        suggestions.sort(key=relevance_score)
        
        # Return only the configured max
        return jsonify(suggestions[:Config.MAX_SUGGESTIONS])
    finally:
        session.close()


@main_bp.route('/api/herbs')
def get_herb_suggestions():
    """API endpoint to get herb name suggestions, sorted by relevance."""
    query = request.args.get('q', '').strip()
    
    if len(query) < 1:
        return jsonify([])
    
    session = Session()
    try:
        # Get more results for better sorting
        matching_herbs = session.query(Herb.herbName).filter(
            Herb.herbName.ilike(f'%{query}%')
        ).distinct().limit(Config.MAX_SUGGESTIONS * 3).all()
        
        suggestions = [herb[0] for herb in matching_herbs]
        
        # Sort by relevance
        query_lower = query.lower()
        
        def relevance_score(name):
            name_lower = name.lower()
            # Exact match (highest priority)
            if name_lower == query_lower:
                return (0, len(name), name_lower)
            # Starts with query
            elif name_lower.startswith(query_lower):
                return (1, len(name), name_lower)
            # Word starts with query
            elif any(word.startswith(query_lower) for word in name_lower.split()):
                return (2, len(name), name_lower)
            # Contains query in middle
            else:
                pos = name_lower.find(query_lower)
                return (3, pos, len(name), name_lower)
        
        suggestions.sort(key=relevance_score)
        
        return jsonify(suggestions[:Config.MAX_SUGGESTIONS])
    finally:
        session.close()


@main_bp.route('/api/herbs/validate')
def validate_herb():
    """API endpoint to validate if a herb exists in the database."""
    name = request.args.get('name', '').strip()
    
    if not name:
        return jsonify({'valid': False, 'name': None})
    
    session = Session()
    try:
        # Try exact match first (case-insensitive)
        herb = session.query(Herb.herbName).filter(
            func.lower(Herb.herbName) == name.lower()
        ).first()
        
        if herb:
            return jsonify({'valid': True, 'name': herb[0]})
        
        return jsonify({'valid': False, 'name': None})
    finally:
        session.close()


@main_bp.route('/api/stats')
def get_stats():
    """API endpoint to get database statistics."""
    session = Session()
    try:
        disease_count = session.query(Disease.diseaseName).distinct().count()
        herb_count = session.query(Herb.herbName).distinct().count()
        
        return jsonify({
            'diseases': disease_count,
            'herbs': herb_count
        })
    finally:
        session.close()


@main_bp.route('/analyze', methods=['POST'])
def analyze():
    """Handle form submission and perform analysis."""
    if request.method == 'POST':
        # Get form data
        disease_name = request.form.get('disease', '').strip()
        herbs_data_json = request.form.get('herbs_data', '[]')
        
        if not disease_name:
            return render_template('index.html', error="Please enter a disease name")
        
        try:
            herbs_data = json.loads(herbs_data_json)
        except json.JSONDecodeError:
            return render_template('index.html', error="Invalid herbs data format")
        
        if not herbs_data:
            return render_template('index.html', error="Please add at least one prescription with herbs")
        
        # Parse herb lists
        herb_lists = []
        for herbs_string in herbs_data:
            herbs = [herb.strip() for herb in herbs_string.split(',') if herb.strip()]
            if herbs:
                herb_lists.append(herbs)
        
        if not herb_lists:
            return render_template('index.html', error="Please add at least one herb to a prescription")
        
        # Perform analysis
        results = analyze_prescriptions(disease_name, herb_lists)
        
        # Save to history
        try:
            session = Session()
            common_genes_count = len(results.get('common_genes', []))
            
            new_result = AnalysisResult(
                disease_name=disease_name,
                prescriptions=json.dumps(herb_lists),
                results_json=json.dumps(results, default=str),
                common_genes_count=common_genes_count,
                created_at=datetime.utcnow()
            )
            session.add(new_result)
            session.commit()
            result_id = new_result.id
            session.close()
            
            # Add ID to results for linking
            results['result_id'] = result_id
        except Exception as e:
            print(f"Error saving result: {e}")
        
        return render_template('result.html', results=results)
    
    return redirect(url_for('main.index'))


@main_bp.route('/api/results/history')
def get_results_history():
    """API endpoint to get analysis results history."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    session = Session()
    try:
        query = session.query(AnalysisResult).order_by(desc(AnalysisResult.created_at))
        
        total = query.count()
        
        results = query.offset((page - 1) * per_page).limit(per_page).all()
        
        data = []
        for r in results:
            try:
                prescriptions = json.loads(r.prescriptions)
                herb_count = sum(len(p) for p in prescriptions)
            except:
                prescriptions = []
                herb_count = 0
            
            data.append({
                'id': r.id,
                'disease_name': r.disease_name,
                'prescriptions_count': len(prescriptions),
                'herbs_count': herb_count,
                'common_genes_count': r.common_genes_count,
                'created_at': r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else 'Unknown'
            })
        
        return jsonify({
            'data': data,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })
    finally:
        session.close()


@main_bp.route('/api/results/<int:result_id>')
def get_result_detail(result_id):
    """API endpoint to get a specific analysis result."""
    session = Session()
    try:
        result = session.query(AnalysisResult).filter(AnalysisResult.id == result_id).first()
        
        if not result:
            return jsonify({'error': 'Result not found'}), 404
        
        try:
            results_data = json.loads(result.results_json)
        except:
            results_data = {}
        
        return jsonify({
            'id': result.id,
            'disease_name': result.disease_name,
            'prescriptions': json.loads(result.prescriptions),
            'results': results_data,
            'created_at': result.created_at.strftime('%Y-%m-%d %H:%M:%S') if result.created_at else 'Unknown'
        })
    finally:
        session.close()


@main_bp.route('/results/<int:result_id>')
def view_result(result_id):
    """View a specific saved result."""
    session = Session()
    try:
        result = session.query(AnalysisResult).filter(AnalysisResult.id == result_id).first()
        
        if not result:
            return redirect(url_for('main.results'))
        
        try:
            results_data = json.loads(result.results_json)
            results_data['result_id'] = result.id
        except:
            results_data = {}
        
        return render_template('result.html', results=results_data)
    finally:
        session.close()


@main_bp.route('/api/results/<int:result_id>', methods=['DELETE'])
def delete_result(result_id):
    """Delete a specific analysis result."""
    session = Session()
    try:
        result = session.query(AnalysisResult).filter(AnalysisResult.id == result_id).first()
        
        if not result:
            return jsonify({'error': 'Result not found'}), 404
        
        session.delete(result)
        session.commit()
        
        return jsonify({'success': True})
    finally:
        session.close()


@main_bp.route('/api/ai-analysis', methods=['POST'])
def ai_analysis():
    """API endpoint to generate AI analysis for results.
    
    Returns structured JSON with:
    - summary_table: Comparison table data
    - detailed_analysis: Full markdown analysis
    - clinical_questions: Diagnostic interview questions
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    disease_name = data.get('disease_name', '')
    prescription_enrichments = data.get('prescription_enrichments', {})
    
    if not disease_name:
        return jsonify({'error': 'Disease name is required'}), 400
    
    if not Config.GEMINI_API_KEY:
        return jsonify({
            'error': 'AI analysis not configured. Please set the GEMINI_API_KEY environment variable.',
            'has_ai_analysis': False
        }), 503
    
    try:
        # Build the results structure for generate_full_ai_analysis
        analysis_results = {
            'prescription_enrichments': prescription_enrichments
        }
        
        # Generate full AI analysis (summary_table, detailed_analysis, clinical_questions)
        ai_results = generate_full_ai_analysis(disease_name, analysis_results)
        
        return jsonify(ai_results)
        
    except Exception as e:
        return jsonify({
            'error': f'AI analysis failed: {str(e)}',
            'has_ai_analysis': False,
            'summary_table': [],
            'detailed_analysis': None,
            'clinical_questions': None
        }), 500


@main_bp.route('/api/ai-analysis/status')
def ai_analysis_status():
    """Check if AI analysis is available (API key configured)."""
    return jsonify({
        'available': bool(Config.GEMINI_API_KEY),
        'message': 'AI analysis is available' if Config.GEMINI_API_KEY else 'GEMINI_API_KEY not configured'
    })
