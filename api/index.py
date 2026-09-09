from http.server import BaseHTTPRequestHandler
import json
import os
import re

# Initialize Groq client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = None
try:
    from groq import Groq
    groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
except ImportError:
    pass

skill_library = {
    "python": ["python", "pandas", "numpy", "scikit-learn", "jupyter"],
    "sql": ["sql", "postgres", "mysql", "database", "query"],
    "dashboard": ["dashboard", "tableau", "power bi", "bi", "reporting"],
    "business communication": ["business communication", "business stakeholder", "stakeholder management", "communication", "executive"],
    "analytics": ["analytics", "data analysis", "kpi", "insights"],
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
        exp_score = min(14, max((c.get("experience") or 4) - 2, 0) * 2)
        score = min(96, max(55, int(skill_score + exp_score + 10)))

        ranking.append({
            "name": c.get("name", "Unknown"),
            "title": c.get("title", "Resume"),
            "experience": c.get("experience", 4),
            "email": c.get("email", "unknown@example.com"),
            "skills": c.get("skills", []) + custom_skills,
            "coveredSkills": covered,
            "missingSkills": missing,
            "score": score,
            "resumeText": resume_text[:180],
            "analyzedBy": "keyword-matching"
        })

    ranking.sort(key=lambda x: x["score"], reverse=True)
    return ranking


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        job_text = sample_job_description()
        ranking = analyze_resumes(job_text, sample_candidates)

        response = json.dumps({"ranking": ranking})

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response.encode())

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        job_text = data.get("jobDescription") or sample_job_description()
        uploaded = data.get("resumes") or []

        candidates = list(sample_candidates)

        for i, item in enumerate(uploaded):
            if isinstance(item, dict):
                resume_text = item.get("resume") or item.get("text") or ""
                name = item.get("name") or f"Uploaded {i+1}"
            else:
                resume_text = str(item)
                name = f"Uploaded {i+1}"

            candidates.append({
                "name": name,
                "title": "Uploaded Resume",
                "experience": 4,
                "email": f"uploaded{i+1}@example.com",
                "skills": [],
                "resume": resume_text
            })

        ranking = analyze_resumes(job_text, candidates)

        response = json.dumps({
            "ranking": ranking,
            "jobDescription": job_text,
            "candidateCount": len(ranking),
            "bestCandidate": ranking[0] if ranking else None
        })

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response.encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
