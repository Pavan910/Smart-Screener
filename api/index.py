from flask import Flask, request, jsonify, make_response
import json
import re
import os
import hashlib

app = Flask(__name__)

# Authentication - Password stored in Vercel environment variable
def get_password():
    return os.environ.get('APP_PASSWORD', '')

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

skill_library = {
    "python": ["python", "pandas", "numpy", "scikit-learn", "jupyter", "flask", "django", "fastapi"],
    "sql": ["sql", "postgres", "postgresql", "mysql", "database", "query", "oracle", "sqlite", "mongodb", "nosql"],
    "dashboard": ["dashboard", "tableau", "power bi", "powerbi", "bi", "reporting", "looker", "metabase", "superset"],
    "business communication": ["business communication", "business stakeholder", "stakeholder management", "communication", "executive", "presentation", "client facing"],
    "analytics": ["analytics", "data analysis", "kpi", "insights", "metrics", "statistical analysis", "data-driven"],
    "machine learning": ["machine learning", "ml", "deep learning", "neural network", "tensorflow", "pytorch", "keras", "nlp", "computer vision"],
    "excel": ["excel", "spreadsheet", "pivot table", "vlookup", "macro", "vba"],
    "data visualization": ["visualization", "charts", "graphs", "data viz", "matplotlib", "seaborn", "plotly", "d3"],
    "cloud": ["aws", "azure", "gcp", "google cloud", "cloud computing", "s3", "ec2", "lambda"],
    "etl": ["etl", "data pipeline", "data engineering", "airflow", "spark", "hadoop", "data warehouse"],
    "leadership": ["leadership", "team lead", "manager", "managed", "mentored", "supervised", "coordinated"],
    "agile": ["agile", "scrum", "sprint", "kanban", "jira", "product owner"],
    "java": ["java", "spring", "spring boot", "hibernate", "maven"],
    "javascript": ["javascript", "react", "angular", "vue", "node", "nodejs", "typescript"],
    "project management": ["project management", "pmp", "program management", "roadmap", "milestone"],
}

sample_candidates = [
    {
        "name": "Olivia Johnson",
        "title": "Senior Data Analyst",
        "experience": 7,
        "email": "olivia.johnson@example.com",
        "skills": ["python", "sql", "dashboard", "business communication"],
        "resume": "Olivia Johnson is a Senior Data Analyst with 7 years of experience in Python, SQL, business intelligence dashboards, and stakeholder communication."
    },
    {
        "name": "Harper Lee",
        "title": "Business Intelligence Lead",
        "experience": 6,
        "email": "harper.lee@example.com",
        "skills": ["sql", "dashboard", "business communication"],
        "resume": "Harper Lee brings 6 years of analytics experience in dashboard design and SQL analytics."
    },
    {
        "name": "Sophia Brown",
        "title": "Analytics Manager",
        "experience": 5,
        "email": "sophia.brown@example.com",
        "skills": ["sql", "dashboard", "business communication"],
        "resume": "Sophia Brown has 5 years of analytics experience with dashboard delivery and business data storytelling."
    },
    {
        "name": "Evelyn Smith",
        "title": "Data Science Specialist",
        "experience": 4,
        "email": "evelyn.smith@example.com",
        "skills": ["python", "machine learning", "sql"],
        "resume": "Evelyn Smith has 4 years of work in Python, data science, classification, and SQL modeling."
    }
]

def sample_job_description():
    return "Senior Data Analyst with strong business communication, SQL, Python, dashboard design, stakeholder management."

def normalize_text(text):
    return re.sub(r"[^a-z0-9\s-]", " ", text.lower())

def extract_skills(job_text):
    normalized = normalize_text(job_text)
    found = []
    for key, synonyms in skill_library.items():
        if any(s in normalized for s in synonyms):
            found.append(key)
    return found

def analyze_resumes(job_text, candidates):
    skills = extract_skills(job_text)
    ranking = []
    for c in candidates:
        resume_text = c.get("resume", "")
        normalized_resume = normalize_text(resume_text)
        custom_skills = []
        for skill_key, synonyms in skill_library.items():
            if any(s in normalized_resume for s in synonyms):
                custom_skills.append(skill_key)
        covered = [s for s in skills if s in custom_skills]
        missing = [s for s in skills if s not in custom_skills]
        skill_score = round((len(covered) / max(len(skills), 1)) * 60)
        exp = c.get("experience") or 0
        exp_score = min(14, max(exp - 2, 0) * 2) if exp > 0 else 0
        keyword_score = min(16, sum(1 for word in re.findall(r"[a-z0-9]+", normalize_text(job_text)) if word and len(word) >= 3 and word in normalized_resume))
        score = min(96, max(40, int(skill_score + exp_score + keyword_score)))
        ranking.append({
            "name": c.get("name", "Unknown"),
            "title": c.get("title") or c.get("currentRole") or "",
            "experience": exp,
            "email": c.get("email") or "",
            "phone": c.get("phone") or "",
            "location": c.get("location") or "",
            "linkedin": c.get("linkedin") or "",
            "currentRole": c.get("currentRole") or c.get("title") or "",
            "currentCompany": c.get("currentCompany") or "",
            "education": c.get("education") or "",
            "skills": list(set(c.get("skills", []) + custom_skills)),
            "coveredSkills": covered,
            "missingSkills": missing,
            "score": score,
            "resumeText": resume_text[:180],
            "analyzedBy": "keyword-matching"
        })
    ranking.sort(key=lambda x: x["score"], reverse=True)
    return ranking

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'OPTIONS'])
@app.route('/<path:path>', methods=['GET', 'POST', 'OPTIONS'])
def catch_all(path):
    # Handle CORS
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    # Handle GET
    if request.method == 'GET':
        job_text = sample_job_description()
        ranking = analyze_resumes(job_text, sample_candidates)
        response = jsonify({"ranking": ranking, "candidateCount": len(ranking)})
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    # Handle POST
    if request.method == 'POST':
        try:
            data = request.get_json(force=True) or {}
        except:
            data = {}

        # Auth request
        if 'password' in data and 'jobDescription' not in data:
            submitted_password = data.get("password", "")
            correct_password = get_password()

            if not correct_password:
                response = jsonify({"success": False, "error": "Password not configured. Set APP_PASSWORD in Vercel."})
                response.status_code = 500
            elif submitted_password == correct_password:
                token = hash_password(correct_password + "smart-screener-session")
                response = jsonify({"success": True, "token": token})
            else:
                response = jsonify({"success": False, "error": "Invalid password"})
                response.status_code = 401
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response

        # Ranking request
        job_text = data.get("jobDescription") or sample_job_description()
        uploaded = data.get("resumes") or []

        # Only use uploaded resumes if provided, otherwise fall back to sample data
        if uploaded:
            candidates = []
            for i, item in enumerate(uploaded):
                if isinstance(item, dict):
                    resume_text = item.get("resume") or item.get("text") or item.get("content") or ""
                    name = item.get("name") or f"Candidate {i+1}"
                    # Use metadata from frontend extraction
                    candidates.append({
                        "name": name,
                        "title": item.get("currentRole") or item.get("title") or "",
                        "experience": item.get("experience") or 0,
                        "email": item.get("email") or "",
                        "phone": item.get("phone") or "",
                        "location": item.get("location") or "",
                        "linkedin": item.get("linkedin") or "",
                        "currentRole": item.get("currentRole") or "",
                        "currentCompany": item.get("currentCompany") or "",
                        "education": item.get("education") or "",
                        "skills": item.get("skills") or [],
                        "resume": resume_text
                    })
                else:
                    resume_text = str(item)
                    candidates.append({
                        "name": f"Candidate {i+1}",
                        "title": "",
                        "experience": 0,
                        "email": "",
                        "skills": [],
                        "resume": resume_text
                    })
        else:
            # Only use sample data if no resumes uploaded (for demo/testing)
            candidates = list(sample_candidates)

        ranking = analyze_resumes(job_text, candidates)
        response = jsonify({
            "ranking": ranking,
            "jobDescription": job_text,
            "candidateCount": len(ranking),
            "bestCandidate": ranking[0] if ranking else None
        })
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
