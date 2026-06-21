import os
import re
from flask import Flask, request, jsonify
from functools import wraps

app = Flask(__name__)

# --- Auth Helper ---
def firebase_auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # We check for a token, but do not split if it doesn't exist
        auth_header = request.headers.get('Authorization')
        if auth_header and 'Bearer ' in auth_header:
            return f(*args, **kwargs)
        if request.form.get('demo_auth_token'):
            return f(*args, **kwargs)
        return jsonify({'error': 'Unauthorized'}), 401
    return decorated_function

# --- Minimal Logic ---
def run_minimal_api(filename, jd_text):
    # Safe splitting: only split if '.' exists
    if '.' in filename:
        # Access the extension string at index [-1], then call lower()
        ext = filename.rsplit('.', 1)[-1].lower()
    else:
        ext = ''
    return {"status": "success", "extension": ext, "job_title": jd_text[:20]}

# --- Routes ---
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
                    <div class="mb-3">
                        <label class="form-label fw-bold">Auth Token</label>
                        <input type="text" name="demo_auth_token" class="form-control" value="FAKE_FIREBASE_ID_TOKEN_FOR_DEMO" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label fw-bold">1. Upload Resume</label>
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
@firebase_auth_required
def analyze():
    file = request.files.get('resume_file')
    jd = request.form.get('job_description')
    if not file or not jd:
        return jsonify({'error': 'Missing input'}), 400
    
    # Run your logic
    results = run_minimal_api(file.filename, jd)
    
    # Return a clean HTML dashboard instead of raw JSON
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/css/bootstrap.min.css">
    </head>
    <body class="bg-light py-5">
        <div class="container" style="max-width: 600px;">
            <div class="card shadow p-4">
                <h3 class="text-success">✅ Analysis Complete</h3>
                <hr>
                <p><strong>Detected File Type:</strong> {results['extension'].upper()}</p>
                <p><strong>Job Title Found:</strong> {results['job_title']}</p>
                <br>
                <a href="/" class="btn btn-outline-primary w-100">Analyze Another</a>
            </div>
        </div>
    </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
