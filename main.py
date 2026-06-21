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

# --- Firebase Mocking ---
auth_mock = MagicMock()
def mock_verify_id_token(id_token):
    return {'uid': 'mock_uid_123', 'email': 'user@example.com'}
auth_mock.verify_id_token.side_effect = mock_verify_id_token

def firebase_auth_required():
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')
            # Extract Bearer token safely
            if auth_header and 'Bearer ' in auth_header:
                id_token = auth_header.split('Bearer ')
            else:
                id_token = request.form.get('demo_auth_token')
            
            if not id_token:
                return jsonify({'error': 'Unauthorized'}), 401
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Utilities ---
def parse_resume(file_path):
    # Split returns a tuple, access index to get the string, then lower()
    file_name, ext = os.path.splitext(file_path)
    ext = ext.lower()
    
    if ext == '.docx':
        from docx import Document
        return '\n'.join([p.text for p in Document(file_path).paragraphs])
    elif ext == '.pdf':
        from PyPDF2 import PdfReader
        return '\n'.join([p.extract_text() for p in PdfReader(file_path).pages])
    return "Unsupported format"

def parse_job_description(text):
    info = {'Job Title': 'N/A'}
    title_match = re.search(r"(Job Title|Role|Position)[:\s]*([A-Za-z0-9\s-\&,/()]+?)(?:\n|$)", text, re.IGNORECASE)
    
    if title_match:
        info['Job Title'] = title_match.group(2).strip()
    else:
        # Split into list, then access index to get the string, then strip()
        lines = text.strip().split('\n')
        if lines:
            info['Job Title'] = lines.strip()
            
    return info

# --- Core Logic ---
def run_resume_agent_api(file_bytes, filename, jd_text):
    # Extract extension correctly using index
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    
    path = f"/tmp/{os.urandom(24).hex()}{ext}"
    with open(path, 'wb') as f:
        f.write(file_bytes)
    
    parse_resume(path)
    os.remove(path)
    
    jd = parse_job_description(jd_text)
    
    return {"status": "success", "message": "Analysis Complete", "job_title": jd['Job Title']}

# --- Flask App ---
app = Flask(__name__)

@app.route('/', methods=['GET'])
def render_ui():
    return '''<form action="/analyze" method="post" enctype="multipart/form-data">
                <input type="hidden" name="demo_auth_token" value="FAKE_FIREBASE_ID_TOKEN_FOR_DEMO">
                <input type="file" name="resume_file" required>
                <textarea name="job_description" required></textarea>
                <button type="submit">Analyze</button>
              </form>'''

@app.route('/analyze', methods=['POST'])
@firebase_auth_required()
def analyze():
    file = request.files.get('resume_file')
    jd = request.form.get('job_description')
    if not file or not jd:
        return jsonify({'error': 'Missing input'}), 400
    return jsonify(run_resume_agent_api(file.read(), file.filename, jd))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
