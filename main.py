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
    return '''<form action="/analyze" method="post" enctype="multipart/form-data">
                <input type="text" name="demo_auth_token" value="FAKE_FIREBASE_ID_TOKEN_FOR_DEMO">
                <input type="file" name="resume_file">
                <textarea name="job_description"></textarea>
                <button type="submit">Analyze</button>
              </form>'''

@app.route('/analyze', methods=['POST'])
@firebase_auth_required
def analyze():
    file = request.files.get('resume_file')
    jd = request.form.get('job_description')
    if not file or not jd:
        return jsonify({'error': 'Missing input'}), 400
    return jsonify(run_minimal_api(file.filename, jd))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
