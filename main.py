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

from flask import Flask, request, jsonify # Import Flask for web application
import argparse # Import argparse for command-line argument parsing

# --- NLTK Downloads (Ensuring they are available) ---
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

# Pre-compute static soft skill embeddings at boot to save calculation cycle resources
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
        return {
            'uid': 'mock_uid_123',
            'email': 'user@example.com',
            'name': 'Mock User',
            'admin': False
        }
    elif id_token == "FAKE_FIREBASE_ADMIN_ID_TOKEN_FOR_DEMO":
        return {
            'uid': 'mock_admin_uid',
            'email': 'admin@example.com',
            'name': 'Mock Admin',
            'admin': True
        }
    else:
        raise ValueError("Invalid or expired token (mocked error).")

auth_mock.verify_id_token.side_effect = mock_verify_id_token

try:
    if not firebase_admin._apps:
        cred = credentials.Certificate({
            "type": "service_account", "project_id": "dummy-project",
            "private_key_id": "dummy-key-id", "private_key": "-----BEGIN PRIVATE KEY-----\nFAKE_PRIVATE_KEY_CONTENTS\n-----END PRIVATE KEY-----\n",
            "client_email": "dummy-client@dummy-project.iam.gserviceaccount.com",
            "client_id": "dummy-client-id",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/dummy-client%40dummy-project.iam.gserviceaccount.com"
        })
        firebase_admin.initialize_app(cred)
except Exception as e:
    pass

def verify_firebase_token(id_token):
    try:
        if firebase_admin._apps and hasattr(firebase_admin.auth, 'verify_id_token'):
            return firebase_admin.auth.verify_id_token(id_token)
        else:
            return auth_mock.verify_id_token(id_token)
    except Exception as e:
        return None

authorized_users = ['admin@example.com', 'user@example.com', 'user1@example.com', 'user2@example.com']
admin_users = ['admin@example.com']

def is_admin_user(user_email):
    return user_email.lower() in [email.lower() for email in admin_users]

def firebase_auth_required(allow_admin_only=False):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')
            form_token = request.form.get('demo_auth_token')

            if auth_header and auth_header.startswith('Bearer '):
                id_token = auth_header.split('Bearer ') # FIXED: Correct string index isolation
            elif form_token:
                id_token = form_token
            else:
                return jsonify({'error': 'Unauthorized', 'message': 'Authorization token missing'}), 401
            
            decoded_token = verify_firebase_token(id_token)

            if decoded_token is None:
                return jsonify({'error': 'Unauthorized', 'message': 'Invalid or expired authentication token'}), 401

            user_email = decoded_token.get('email', 'anonymous@example.com')

            if user_email.lower() not in [u.lower() for u in authorized_users]:
                return jsonify({'error': 'Forbidden', 'message': f'User {user_email} is not authorized to access this resource'}), 403

            if allow_admin_only:
                if not is_admin_user(user_email):
                    return jsonify({'error': 'Forbidden', 'message': f'User {user_email} is not an administrator'}), 403

            request.user = decoded_token
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Utility Functions ---

def extract_text_from_docx(docx_path):
    try:
        from docx import Document
        document = Document(docx_path)
        text = []
        for paragraph in document.paragraphs:
            text.append(paragraph.text)
        return '\n'.join(text)
    except Exception as e:
        return f"Error reading DOCX file: {e}"

def extract_text_from_pdf(pdf_path):
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(pdf_path)
        text = []
        for page in reader.pages:
            text.append(page.extract_text())
        return '\n'.join(text)
    except Exception as e:
        return f"Error reading PDF file: {e}"

def parse_resume(file_path):
    file_extension = os.path.splitext(file_path).lower()
    if file_extension == '.docx':
        return extract_text_from_docx(file_path)
    elif file_extension == '.pdf':
        return extract_text_from_pdf(file_path)
    else:
        return "Unsupported file format. Please provide a .docx or .pdf file."

def parse_job_description(job_description_text):
    extracted_info = {}
    job_title_match = re.search(r"(Job Title|Role|Position)[:\s]*([A-Za-z0-9\s-\&,/()]+?)(?:\n|$)", job_description_text, re.IGNORECASE)
    if job_title_match:
        extracted_info['Job Title'] = job_title_match.group(2).strip()
    else:
        first_line = job_description_text.strip().split('\n')
        if first_line and len(first_line) < 100:
            extracted_info['Job Title'] = first_line.strip() # FIXED: Referenced explicit row item index
        else:
            extracted_info['Job Title'] = 'N/A'

    skills_match = re.search(r"(Required Skills|Skills|Qualifications|Requirements)[:\s]*([\s\S]+?)(?:\n\s*(?:Responsibilities|Experience|Education|About Us|We Offer)|$)", job_description_text, re.IGNORECASE)
    if skills_match:
        skills_text = skills_match.group(2).strip()
        skills_list = [s.strip().lstrip('-').strip() for s in re.split(r'\n\s*[-*]?\s*|;|,', skills_text) if s.strip() and s.strip() != '-']
        extracted_info['Required Skills'] = [s for s in skills_list if s]
    else:
        extracted_info['Required Skills'] = []

    responsibilities_match = re.search(r"(Responsibilities|Key Responsibilities|Duties)[:\s]*([\s\S]+?)(?:\n\s*(?:Skills|Qualifications|Experience|Education|About Us|We Offer)|$)", job_description_text, re.IGNORECASE)
    if responsibilities_match:
        responsibilities_text = responsibilities_match.group(2).strip()
        responsibilities_list = [r.strip().lstrip('-').strip() for r in re.split(r'\n\s*[-*]?\s*|;|,', responsibilities_text) if r.strip() and r.strip() != '-']
        extracted_info['Responsibilities'] = [r for r in responsibilities_list if r]
    else:
        extracted_info['Responsibilities'] = []

    return extracted_info

def record_application_data(job_title, company, status_or_reason, file_name):
    current_date = datetime.now().strftime('%Y-%m-%d')
    new_record = {}

    if file_name == 'jobs_applied_to.csv':
        new_record = {
            'Job Title': job_title,
            'Company': company,
            'Date Applied': current_date,
            'Status': status_or_reason
        }
        df = pd.read_csv(file_name) if os.path.exists(file_name) else pd.DataFrame(columns=['Job Title', 'Company', 'Date Applied', 'Status'])
        df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
        df.to_csv(file_name, index=False)
    elif file_name == 'jobs_not_a_fit.csv':
        new_record = {
            'Job Title': job_title,
            'Company': company,
            'Reason Not Fit': status_or_reason,
            'Date Decided': current_date
        }
        df = pd.read_csv(file_name) if os.path.exists(file_name) else pd.DataFrame(columns=['Job Title', 'Company', 'Reason Not Fit', 'Date Decided'])
        df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
        df.to_csv(file_name, index=False)
    else:
        print(f"Warning: Unknown file_name {file_name}. Record not saved.")

def extract_phrases_and_keywords_nltk(text, n_min=1, n_max=3):
    words = word_tokenize(text.lower())
    filtered_words = [word for word in words if word.isalpha() and len(word) > 2]
    extracted_terms = set()
    if n_min <= 1:
        extracted_terms.update(filtered_words)
    for n in range(max(2, n_min), n_max + 1):
        for gram in ngrams(filtered_words, n):
            extracted_terms.add(' '.join(gram))
    return list(extracted_terms)

# --- Core Functions ---

def assess_candidate_fit_semantic(parsed_resume, parsed_jd, model, fit_weights):
    fit_score = 0
    rationale_points = []
    category_scores = {
        'semantic_skills': 0,
        'semantic_responsibilities': 0,
        'soft_skills': 0,
        'keyword_skills': 0,
        'keyword_responsibilities': 0,
        'job_title_match': 0
    }

    jd_skills = [skill.lower() for skill in parsed_jd.get('Required Skills', [])]
    jd_responsibilities = [resp.lower() for resp in parsed_jd.get('Responsibilities', [])]

    resume_skills = [skill.lower() for skill in parsed_resume.get('Skills', [])]
    resume_experience_sentences = [exp.lower() for exp in parsed_resume.get('Experience', [])]

    resume_combined_text = " ".join(resume_skills + resume_experience_sentences)

    if jd_skills and resume_combined_text:
        jd_skill_embeddings = model.encode(jd_skills, convert_to_tensor=True)
        resume_skill_embeddings = model.encode(resume_skills, convert_to_tensor=True)

        matched_semantic_skills = []
        for i, jd_s_emb in enumerate(jd_skill_embeddings):
            if resume_skill_embeddings.numel() > 0:
                cosine_scores_skills = util.pytorch_cos_sim(jd_s_emb, resume_skill_embeddings)
                if torch.max(cosine_scores_skills) > 0.6:
                    matched_semantic_skills.append(jd_skills[i])
                    score_to_add = fit_weights['semantic_skills_weight']
                    fit_score += score_to_add
                    category_scores['semantic_skills'] += score_to_add

        if matched_semantic_skills:
            rationale_points.append(f"Candidate semantically matches key skills: {', '.join(set(matched_semantic_skills))}.")

    if jd_responsibilities and resume_combined_text:
        jd_responsibility_embeddings = model.encode(jd_responsibilities, convert_to_tensor=True)
        resume_experience_embeddings = model.encode(resume_experience_sentences, convert_to_tensor=True)

        matched_semantic_responsibilities = []
        for i, jd_r_emb in enumerate(jd_responsibility_embeddings):
            if resume_experience_embeddings.numel() > 0:
                cosine_scores_resps = util.pytorch_cos_sim(jd_r_emb, resume_experience_embeddings)
                if torch.max(cosine_scores_resps) > 0.5:
                    matched_semantic_responsibilities.append(jd_responsibilities[i])
                    score_to_add = fit_weights['semantic_responsibilities_weight']
                    fit_score += score_to_add
                    category_scores['semantic_responsibilities'] += score_to_add

        if matched_semantic_responsibilities:
            rationale_points.append(f"Candidate's experience semantically aligns with key responsibilities: {', '.join(set(matched_semantic_responsibilities))}.")

    resume_lower_text = resume_combined_text.lower()
    matched_semantic_soft_skills_categories = set()

    if resume_combined_text:
        resume_embedding = model.encode(resume_combined_text, convert_to_tensor=True)

        for category, embed_tensors in soft_skills_embeddings.items():
            max_cosine_score_soft_skill = 0.0
            if embed_tensors.numel() > 0 and resume_embedding.numel() > 0:
                cosine_scores_for_category = util.pytorch_cos_sim(resume_embedding, embed_tensors)
                max_cosine_score_soft_skill = torch.max(cosine_scores_for_category).item()

            soft_skill_threshold = 0.1

            if max_cosine_score_soft_skill > soft_skill_threshold:
                matched_semantic_soft_skills_categories.add(category)
                score_to_add = fit_weights['soft_skills_weight']
                fit_score += score_to_add
                category_scores['soft_skills'] += score_to_add

    if matched_semantic_soft_skills_categories:
        rationale_points.append(f"Candidate demonstrates strong semantic soft skills in categories like: {', '.join(set(matched_semantic_soft_skills_categories))}.")

    matched_keywords_skills = []
    for skill in jd_skills:
        if any(skill in rs for rs in resume_skills) or any(skill in rexp for rexp in resume_experience_sentences):
            if skill not in matched_semantic_skills:
                matched_keywords_skills.append(skill)
                score_to_add = fit_weights['keyword_skills_weight']
                fit_score += score_to_add
                category_scores['keyword_skills'] += score_to_add

    if matched_keywords_skills:
        rationale_points.append(f"Candidate possesses additional keyword-matched skills: {', '.join(matched_keywords_skills)}.")

    matched_keywords_responsibilities = []
    for jd_resp in jd_responsibilities:
        jd_resp_keywords = set(jd_resp.split())
        if any(any(keyword in rexp for keyword in jd_resp_keywords) for rexp in resume_experience_sentences):
            if jd_resp not in matched_semantic_responsibilities:
                matched_keywords_responsibilities.append(jd_resp)
                score_to_add = fit_weights['keyword_responsibilities_weight']
                fit_score += score_to_add
                category_scores['keyword_responsibilities'] += score_to_add
    if matched_keywords_responsibilities:
        rationale_points.append(f"Candidate's experience includes additional keyword-matched responsibilities: {', '.join(matched_keywords_responsibilities)}.")

    if 'Job Title' in parsed_jd and 'Job Title' in parsed_resume:
        if parsed_jd['Job Title'].lower() in parsed_resume['Job Title'].lower():
            score_to_add = fit_weights['job_title_weight']
            fit_score += score_to_add
            category_scores['job_title_match'] += score_to_add
            rationale_points.append(f"Candidate's previous job title '{parsed_resume['Job Title']}' directly matches the job description.")

    if not rationale_points:
        rationale_points.append("Further analysis needed; limited direct matches found between resume and job description.")

    return {
        'fit_score': fit_score,
        'rationale': '\n'.join(rationale_points),
        'category_scores': category_scores
    }

def predict_fit_score_ml(parsed_resume, parsed_jd):
    jd_skills = set(skill.lower() for skill in parsed_jd.get('Required Skills', []))
    resume_skills = set(skill.lower() for skill in parsed_resume.get('Skills', []))
    common_skills = jd_skills.intersection(resume_skills)
    score = len(common_skills) * 5
    score += 15
    return min(score, 100)

def optimize_resume(parsed_resume, parsed_jd, original_resume_text):
    optimized_sections = []
    jd_skills = [skill.lower() for skill in parsed_jd.get('Required Skills', [])]
    jd_responsibilities =
