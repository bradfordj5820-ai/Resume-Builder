import os
import re
import pandas as pd
from datetime import datetime
import torch
import nltk
from nltk.tokenize import word_tokenize
from nltk.util import ngrams
from sentence_transformers import SentenceTransformer, util
import firebase_admin
from firebase_admin import credentials, auth
import base64
from unittest.mock import MagicMock
from functools import wraps
from flask import Flask, request, jsonify
import argparse

# --- NLTK Downloads ---
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab')

# --- Configuration ---
model = SentenceTransformer('all-MiniLM-L6-v2')
fit_weights = {
    'semantic_skills_weight': 7,
    'semantic_responsibilities_weight': 4,
    'soft_skills_weight': 3,
    'keyword_skills_weight': 2,
    'keyword_responsibilities_weight': 1,
    'job_title_weight': 10
}
soft_skills_keywords = {
    'communication': ['communication', 'articulate', 'present', 'written', 'verbal', 'negotiation', 'interpersonal'],
    'teamwork': ['teamwork', 'collaborate', 'cooperate', 'team player', 'cross-functional'],
    'leadership': ['leadership', 'mentor', 'lead', 'guide', 'supervise', 'motivate', 'delegat'],
    'problem_solving': ['problem-solving', 'analytical', 'critical thinking', 'solution-oriented', 'resolve', 'troubleshoot']
}
soft_skills_embeddings = {cat: model.encode(kws, convert_to_tensor=True) for cat, kws in soft_skills_keywords.items()}

# --- Firebase Mocking ---
auth_mock = MagicMock()
def mock_verify_id_token(id_token):
    if id_token == "FAKE_FIREBASE_ID_TOKEN_FOR_DEMO":
        return {'uid': 'mock_uid_123', 'email': 'user@example.com', 'name': 'Mock User', 'admin': False}
    return {'uid': 'mock_admin_uid', 'email': 'admin@example.com', 'name': 'Mock Admin', 'admin': True}
auth_mock.verify_id_token.side_effect = mock_verify_id_token

def verify_firebase_token(id_token):
    return auth_mock.verify_id_token(id_token)

authorized_users = ['admin@example.com', 'user@example.com']

def firebase_auth_required(allow_admin_only=False):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')
            id_token = auth_header.split('Bearer ') if auth_header and auth_header.startswith('Bearer ') else request.form.get('demo_auth_token')
            if not id_token: return jsonify({'error': 'Unauthorized'}), 401
            decoded_token = verify_firebase_token(id_token)
            if not decoded_token: return jsonify({'error': 'Unauthorized'}), 401
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Utilities ---
def parse_resume(file_path):
    ext = os.path.splitext(file_path).lower()
    if ext == '.docx':
        from docx import Document
        return '\n'.join([p.text for p in Document(file_path).paragraphs])
    elif ext == '.pdf':
        from PyPDF2 import PdfReader
        return '\n'.join([p.extract_text() for p in PdfReader(file_path).pages])
    return "Unsupported format"

def parse_job_description(text):
    info = {'Job Title': 'N/A', 'Required Skills': [], 'Responsibilities': []}
    title = re.search(r"(Job Title|Role|Position)[:\s]*([A-Za-z0-9\s-\&,/()]+?)(?:\n|$)", text, re.IGNORECASE)
    info['Job Title'] = title.group(2).strip() if title else text.strip().split('\n').strip()
    return info

def record_data(job_title, company, status, file_name):
    path = os.path.join('/tmp', file_name)
    df = pd.read_csv(path) if os.path.exists(path) else pd.DataFrame(columns=['Job Title', 'Company', 'Status', 'Date'])
    new_rec = pd.DataFrame([{'Job Title': job_title, 'Company': company, 'Status': status, 'Date': datetime.now().strftime('%Y-%m-%d')}])
    pd.concat([df, new_rec]).to_csv(path, index=False)

# --- Core Logic ---
def run_resume_agent_api(file_bytes, filename, jd_text):
    ext = os.path.splitext(filename).lower()
    path = f"/tmp/{os.urandom(24).hex()}{ext}"
    with open(path, 'wb') as f: f.write(file_bytes)
    
    resume_text = parse_resume(path)
    os.remove(path)
    
    jd = parse_job_description(jd_text)
    
    return {"status": "success", "message": "Analysis Complete", "job_title": jd['Job Title']}

# --- Flask App ---
app = Flask(__name__)

@app.route('/', methods=['GET'])
def render_ui():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Resume Agent Dashboard</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/css/bootstrap.min.css">
    </head>
    <body class="bg-light py-5">
        <div class="container" style="max-width: 800px;">
            <div class="card shadow-sm p-4">
                <h2 class="mb-4 text-primary">📄 Resume Agent Optimizer</h2>
                <form action="/analyze" method="post" enctype="multipart/form-data">
                    <input type="hidden" name="demo_auth_token" value="FAKE_FIREBASE_ID_TOKEN_FOR_DEMO">
                    <div class="mb-3">
                        <label class="form-label fw-bold">1. Upload Resume (.pdf or .docx)</label>
                        <input type="file" name="resume_file" class="form-control" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label fw-bold">2. Paste Job Description</label>
                        <textarea name="job_description" class="form-control" rows="8" placeholder="Paste requirements here..." required></textarea>
                    </div>
                    <button type="submit" class="btn btn-primary btn-lg w-100">Analyze Candidate Fit</button>
                </form>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/analyze', methods=['POST'])
@firebase_auth_required()
def analyze():
    file = request.files.get('resume_file')
    jd = request.form.get('job_description')
    if not file or not jd: return jsonify({'error': 'Missing input'}), 400
    return jsonify(run_resume_agent_api(file.read(), file.filename, jd))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
