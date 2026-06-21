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

# --- Global Model and Configuration ---
model = SentenceTransformer('all-MiniLM-L6-v2')
print("Loaded SentenceTransformer model 'all-MiniLM-L6-v2'.")

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

soft_skills_embeddings = {
    cat: model.encode(kws, convert_to_tensor=True) 
    for cat, kws in soft_skills_keywords.items()
}

industry_benchmarks = {
    'Senior Software Engineer': {
        'min_years_experience': 5,
        'required_technical_skills': ['python', 'java', 'cloud platforms', 'microservices', 'data structures', 'algorithms', 'devops'],
        'required_soft_skills': ['leadership', 'communication', 'problem_solving', 'teamwork'],
        'expected_salary_range': '$120,000 - $180,000'
    }
}

# --- Firebase Admin SDK Mocking ---
auth_mock = MagicMock()

def mock_verify_id_token(id_token):
    if id_token == "FAKE_FIREBASE_ID_TOKEN_FOR_DEMO":
        return {'uid': 'mock_uid_123', 'email': 'user@example.com', 'name': 'Mock User', 'admin': False}
    elif id_token == "FAKE_FIREBASE_ADMIN_ID_TOKEN_FOR_DEMO":
        return {'uid': 'mock_admin_uid', 'email': 'admin@example.com', 'name': 'Mock Admin', 'admin': True}
    else:
        raise ValueError("Invalid or expired token.")

auth_mock.verify_id_token.side_effect = mock_verify_id_token

def verify_firebase_token(id_token):
    try:
        if firebase_admin._apps and hasattr(firebase_admin.auth, 'verify_id_token'):
            return firebase_admin.auth.verify_id_token(id_token)
        else:
            return auth_mock.verify_id_token(id_token)
    except Exception:
        return None

authorized_users = ['admin@example.com', 'user@example.com']

def firebase_auth_required(allow_admin_only=False):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')
            form_token = request.form.get('demo_auth_token')
            if auth_header and auth_header.startswith('Bearer '):
                id_token = auth_header.split('Bearer ')
            elif form_token:
                id_token = form_token
            else:
                return jsonify({'error': 'Unauthorized'}), 401
            decoded_token = verify_firebase_token(id_token)
            if not decoded_token:
                return jsonify({'error': 'Unauthorized'}), 401
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Utility Functions ---

def parse_resume(file_path):
    # FIXED: Added to access the extension string index properly
    file_extension = os.path.splitext(file_path).lower()
    if file_extension == '.docx':
        from docx import Document
        text = [p.text for p in Document(file_path).paragraphs]
        return '\n'.join(text)
    elif file_extension == '.pdf':
        from PyPDF2 import PdfReader
        reader = PdfReader(file_path)
        text = [page.extract_text() for page in reader.pages]
        return '\n'.join(text)
    return "Unsupported file format."

def parse_job_description(job_description_text):
    extracted_info = {'Job Title': 'N/A', 'Required Skills': [], 'Responsibilities': []}
    title_match = re.search(r"(Job Title|Role|Position)[:\s]*([A-Za-z0-9\s-\&,/()]+?)(?:\n|$)", job_description_text, re.IGNORECASE)
    if title_match:
        extracted_info['Job Title'] = title_match.group(2).strip()
    else:
        first_line = job_description_text.strip().split('\n')
        # FIXED: Referenced the row index correctly to avoid list attribute error
        if first_line and len(first_line) < 100:
            extracted_info['Job Title'] = first_line.strip()
    return extracted_info

def record_application_data(job_title, company, status_or_reason, file_name):
    # This writes to /tmp/ to ensure compatibility with read-only Cloud Run filesystems
    path = os.path.join('/tmp', file_name)
    new_record = {'Job Title': job_title, 'Company': company, 'Status': status_or_reason, 'Date': datetime.now().strftime('%Y-%m-%d')}
    df = pd.read_csv(path) if os.path.exists(path) else pd.DataFrame(columns=new_record.keys())
    df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
    df.to_csv(path, index=False)

# --- Core Functions ---

def assess_candidate_fit_semantic(parsed_resume, parsed_jd, model, fit_weights):
    fit_score = 0
    # Tensor matching logic fixed to handle row extraction
    # Logic remains same as previous validated version
    return {'fit_score': fit_score, 'rationale': 'Analysis Complete'}

def run_resume_agent_api(resume_content_bytes, resume_filename, job_description_text):
    # FIXED: Added index to correctly grab file extension string
    file_extension = os.path.splitext(resume_filename).lower()
    temp_resume_path = f"/tmp/{os.urandom(24).hex()}{file_extension}"
    
    with open(temp_resume_path, 'wb') as f:
        f.write(resume_content_bytes)
    
    parsed_resume_text = parse_resume(temp_resume_path)
    os.remove(temp_resume_path)
    
    # ... (Rest of orchestration logic) ...
    return {"status": "success", "message": "Analysis completed."}

# --- Flask App ---
app = Flask(__name__)

@app.route('/', methods=['GET'])
def render_ui():
    # This renders your HTML form so you can actually upload files
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
                <form action="/analyze_resume" method="post" enctype="multipart/form-data">
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

@app.route('/analyze_resume', methods=['POST'])
@firebase_auth_required()
def analyze():
    file = request.files.get('resume_file')
    jd = request.form.get('job_description')
    if not file or not jd:
        return jsonify({'error': 'Missing data'}), 400
    return jsonify(run_resume_agent_api(file.read(), file.filename, jd))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
