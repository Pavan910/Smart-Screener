from http.server import BaseHTTPRequestHandler
import json
import re
import os
import hashlib

# Authentication - Password stored in Vercel environment variable
def get_password():
    return os.environ.get('APP_PASSWORD', '')

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

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
        "resume": "Olivia Johnson is a Senior Data Analyst with 7 years of experience in Python, SQL, business intelligence dashboards, and stakeholder communication. Built executive reports for product and supply chain teams and translated data into growth insights. Strong experience with data storytelling, KPI design, and dashboard design."
    },
    {
        "name": "Harper Lee",
        "title": "Business Intelligence Lead",
        "experience": 6,
        "email": "harper.lee@example.com",
        "skills": ["sql", "dashboard", "business communication"],
        "resume": "Harper Lee brings 6 years of analytics experience in dashboard design and SQL analytics. Strong communication with business stakeholders and experience delivering weekly dashboards for leadership. Skilled in sales insights, KPI frameworks, and business performance analysis."
    },
    {
        "name": "Sophia Brown",
        "title": "Analytics Manager",
        "experience": 5,
        "email": "sophia.brown@example.com",
        "skills": ["sql", "dashboard", "business communication"],
        "resume": "Sophia Brown has 5 years of analytics experience with dashboard delivery and business data storytelling. Comfortable in SQL reporting and working with operations teams. Experience with business commitment, cross-functional product reporting, and stakeholder reviews."
    },
    {
        "name": "Evelyn Smith",
        "title": "Data Science Specialist",
        "experience": 4,
        "email": "evelyn.smith@example.com",
        "skills": ["python", "machine learning", "sql"],
        "resume": "Evelyn Smith has 4 years of work in Python, data science, classification, and SQL modeling. Experience working with customer data pipelines and forecasting. Has strong technical background but less emphasis on stakeholder communication and executive dashboard design."
    }
]

def sample_job_description():
    return "Senior Data Analyst with strong business communication, SQL, Python, dashboard design, stakeholder management, and experience translating source data into measurable insights for executive decision-making."

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
        keyword_score = min(16, sum(1 for word in re.findall(r"[a-z0-9]+", normalize_text(job_text)) if word and len(word) >= 3 and word in normalized_resume))
        score = min(96, max(55, int(skill_score + exp_score + keyword_score)))

        ranking.append({
            "name": c.get("name", "Unknown"),
            "title": c.get("title", "Resume"),
            "experience": c.get("experience", 4),
            "email": c.get("email", "unknown@example.com"),
            "skills": list(set(c.get("skills", []) + custom_skills)),
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

        response = json.dumps({"ranking": ranking, "candidateCount": len(ranking)})

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

        # Handle authentication endpoint
        if '/auth' in self.path:
            self.handle_auth(data)
            return

        job_text = data.get("jobDescription") or sample_job_description()
        uploaded = data.get("resumes") or []

        candidates = list(sample_candidates)

        for i, item in enumerate(uploaded):
            if isinstance(item, dict):
                resume_text = item.get("resume") or item.get("text") or item.get("content") or ""
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

    def handle_auth(self, data):
        submitted_password = data.get("password", "")
        correct_password = get_password()

        # Check if password is configured
        if not correct_password:
            response = json.dumps({
                "success": False,
                "error": "Password not configured. Set APP_PASSWORD in Vercel."
            })
            self.send_response(500)
        elif submitted_password == correct_password:
            token = hash_password(correct_password + "smart-screener-session")
            response = json.dumps({
                "success": True,
                "token": token
            })
            self.send_response(200)
        else:
            response = json.dumps({
                "success": False,
                "error": "Invalid password"
            })
            self.send_response(401)

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
