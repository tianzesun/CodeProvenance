"""
Simple Web GUI for CodeProvenance
MOSS-like interface: upload files, view results
"""

import sys
import os
import atexit

# Add parent directory to path for imports
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from werkzeug.utils import secure_filename
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Any
import json
from datetime import datetime
from itertools import combinations

# Import core modules
from src.core.parser.base_parser import ParserFactory
from src.engines.similarity.base_similarity import SimilarityEngine, register_builtin_algorithms
from src.engines.similarity.deep_analysis import analyze_code_deep, compare_codes_deep

# Import all parsers to register them
import src.core.parser.python_parser
import src.core.parser.java_parser
import src.core.parser.c_parser
import src.core.parser.cpp_parser
import src.core.parser.javascript_parser
import src.core.parser.typescript_parser
import src.core.parser.csharp_parser
import src.core.parser.go_parser
import src.core.parser.rust_parser
import src.core.parser.ruby_parser
import src.core.parser.perl_parser
import src.core.parser.scala_parser
import src.core.parser.haskell_parser
import src.core.parser.sql_parser
import src.core.parser.julia_parser
import src.core.parser.ocaml_parser
import src.core.parser.pascal_parser
import src.core.parser.arduino_parser
import src.core.parser.scheme_parser
import src.core.parser.blaise_parser
import src.core.parser.forth_parser

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload

# Upload folder setup
UPLOAD_FOLDER = tempfile.mkdtemp(prefix='codeprovenance_')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Supported languages
LANGUAGES = {
    'python': 'Python',
    'java': 'Java',
    'c': 'C',
    'cpp': 'C++',
    'javascript': 'JavaScript',
    'typescript': 'TypeScript',
    'csharp': 'C#',
    'go': 'Go',
    'rust': 'Rust',
    'ruby': 'Ruby',
    'php': 'PHP',
    'swift': 'Swift',
    'kotlin': 'Kotlin',
    'scala': 'Scala',
    'haskell': 'Haskell',
    'sql': 'SQL',
    'html': 'HTML',
    'css': 'CSS',
    'plaintext': 'Plain Text'
}

ALLOWED_EXTENSIONS = {
    'py', 'java', 'c', 'cpp', 'cc', 'cxx', 'h', 'hpp',
    'js', 'ts', 'jsx', 'tsx', 'cs',
    'go', 'rs', 'rb', 'php', 'swift', 'kt', 'scala',
    'hs', 'sql', 'html', 'htm', 'css', 'txt'
}


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def detect_language(filename: str) -> str:
    """Auto-detect language from file extension."""
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    mapping = {
        'py': 'python', 'java': 'java', 'c': 'c', 'cpp': 'cpp',
        'cc': 'cpp', 'cxx': 'cpp', 'h': 'c', 'hpp': 'cpp',
        'js': 'javascript', 'ts': 'typescript', 'jsx': 'javascript',
        'tsx': 'typescript', 'cs': 'csharp', 'go': 'go', 'rs': 'rust',
        'rb': 'ruby', 'php': 'php', 'swift': 'swift', 'kt': 'kotlin',
        'scala': 'scala', 'hs': 'haskell', 'sql': 'sql',
        'html': 'html', 'htm': 'html', 'css': 'css', 'txt': 'plaintext'
    }
    return mapping.get(ext, 'plaintext')


def parse_file(filepath: str, language: str) -> Dict[str, Any]:
    """Parse a file and return parsed representation."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    parser = ParserFactory.get_parser(language)
    if parser is None:
        # Return a basic parsed structure
        return {
            'content': content,
            'tokens': content.split(),
            'lines': content.splitlines(),
            'language': language,
            'file_path': filepath
        }
    return parser.parse(filepath, content)


def compare_files(parsed_a: Dict[str, Any], parsed_b: Dict[str, Any]) -> Dict[str, Any]:
    """Compare two parsed files using all available algorithms."""
    engine = SimilarityEngine()
    register_builtin_algorithms(engine)
    
    result = engine.compare(parsed_a, parsed_b)
    
    # Normalize result keys for the GUI
    individual = result.get('individual_scores', {})
    
    return {
        'overall_similarity': result.get('overall_score', 0) * 100,  # Convert to percentage
        'token_similarity': individual.get('token', 0) * 100,
        'ngram_similarity': individual.get('ngram', 0) * 100,
        'ast_similarity': individual.get('ast', 0) * 100,
        'winnowing_similarity': individual.get('winnowing', 0) * 100,
        'embedding_similarity': individual.get('embedding', 0) * 100,
        'deep_analysis': result.get('deep_analysis', {}),
        'ai_score': result.get('deep_analysis', {}).get('clone_score', 0) * 100
    }


@app.route('/')
def index():
    """Main page with file upload form."""
    return render_template('index.html', languages=LANGUAGES)


@app.route('/upload', methods=['POST'])
def upload_files():
    """Handle file uploads."""
    if 'files' not in request.files:
        flash('No files selected', 'error')
        return redirect(url_for('index'))
    
    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        flash('No files selected', 'error')
        return redirect(url_for('index'))
    
    # Save uploaded files
    uploaded_files = []
    job_dir = tempfile.mkdtemp(prefix='job_', dir=UPLOAD_FOLDER)
    
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(job_dir, filename)
            file.save(filepath)
            lang = detect_language(filename)
            uploaded_files.append({
                'name': filename,
                'path': filepath,
                'language': lang
            })
    
    if not uploaded_files:
        flash('No valid files uploaded', 'error')
        return redirect(url_for('index'))
    
    # Run similarity analysis
    try:
        # Parse all files
        parsed_files = []
        for f in uploaded_files:
            try:
                parsed = parse_file(f['path'], f['language'])
                parsed_files.append({
                    'file': f,
                    'parsed': parsed
                })
            except Exception as e:
                flash(f'Failed to parse {f["name"]}: {str(e)}', 'error')
                return redirect(url_for('index'))
        
        # Compare all pairs
        pairs = []
        for a, b in combinations(parsed_files, 2):
            result = compare_files(a['parsed'], b['parsed'])
            similarity = result.get('overall_similarity', 0)
            
            pairs.append({
                'file1': a['file']['name'],
                'file2': b['file']['name'],
                'similarity': round(similarity, 2),
                'metrics': {
                    'token_similarity': round(result.get('token_similarity', 0), 2),
                    'ngram_similarity': round(result.get('ngram_similarity', 0), 2),
                    'ast_similarity': round(result.get('ast_similarity', 0), 2),
                    'winnowing_similarity': round(result.get('winnowing_similarity', 0), 2),
                    'embedding_similarity': round(result.get('embedding_similarity', 0), 2)
                },
                'ai_score': round(result.get('ai_score', 0), 2),
                'matches': result.get('matches', [])[:5]
            })
        
        # Sort by similarity
        pairs.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Calculate summary
        if pairs:
            avg_sim = sum(p['similarity'] for p in pairs) / len(pairs)
            max_sim = max(p['similarity'] for p in pairs)
        else:
            avg_sim = 0
            max_sim = 0
        
        results = {
            'summary': {
                'total_files': len(uploaded_files),
                'total_pairs': len(pairs),
                'avg_similarity': round(avg_sim, 2),
                'max_similarity': round(max_sim, 2)
            },
            'pairs': pairs,
            'raw_output': generate_raw_output(pairs)
        }
        
        return render_template(
            'results.html',
            files=uploaded_files,
            results=results,
            job_id=os.path.basename(job_dir)
        )
    
    except Exception as e:
        import traceback
        flash(f'Analysis failed: {str(e)}', 'error')
        return redirect(url_for('index'))


def generate_raw_output(pairs: List[Dict]) -> str:
    """Generate MOSS-style raw output."""
    lines = []
    lines.append("=" * 60)
    lines.append("CodeProvenance Similarity Analysis Results")
    lines.append("=" * 60)
    lines.append("")
    
    for i, pair in enumerate(pairs, 1):
        lines.append(f"Pair {i}: {pair['file1']} <-> {pair['file2']}")
        lines.append(f"  Overall Similarity: {pair['similarity']}%")
        lines.append(f"  Token Similarity:   {pair['metrics']['token_similarity']}%")
        lines.append(f"  N-gram Similarity:  {pair['metrics']['ngram_similarity']}%")
        lines.append(f"  AST Similarity:     {pair['metrics']['ast_similarity']}%")
        lines.append(f"  Winnowing:          {pair['metrics']['winnowing_similarity']}%")
        if pair['ai_score'] > 0:
            lines.append(f"  AI Score:           {pair['ai_score']}%")
        lines.append("")
    
    lines.append("=" * 60)
    return "\n".join(lines)


@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    """JSON API endpoint for analysis."""
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
    
    files = request.files.getlist('files')
    job_dir = tempfile.mkdtemp(prefix='api_job_', dir=UPLOAD_FOLDER)
    
    uploaded_files = []
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(job_dir, filename)
            file.save(filepath)
            lang = detect_language(filename)
            uploaded_files.append({'path': filepath, 'language': lang})
    
    if not uploaded_files:
        return jsonify({'error': 'No valid files'}), 400
    
    # Parse files
    parsed_files = []
    for f in uploaded_files:
        parsed = parse_file(f['path'], f['language'])
        parsed_files.append(parsed)
    
    # Compare pairs
    pairs = []
    for a, b in combinations(parsed_files, 2):
        result = compare_files(a, b)
        pairs.append({
            'similarity': round(result.get('overall_similarity', 0), 2),
            'metrics': result
        })
    
    return jsonify({'pairs': pairs})


@app.route('/cleanup', methods=['POST'])
def cleanup():
    """Clean up old job directories."""
    import time
    max_age = 3600  # 1 hour
    count = 0
    for item in os.listdir(UPLOAD_FOLDER):
        path = os.path.join(UPLOAD_FOLDER, item)
        if os.path.isdir(path):
            age = time.time() - os.path.getmtime(path)
            if age > max_age:
                shutil.rmtree(path)
                count += 1
    return jsonify({'cleaned': count})


# Cleanup on shutdown
atexit.register(lambda: shutil.rmtree(UPLOAD_FOLDER, ignore_errors=True))


if __name__ == '__main__':
    # Configure Flask template folder
    app.template_folder = os.path.join(_BASE_DIR, 'templates')
    
    app.run(host='0.0.0.0', port=5000, debug=True)
