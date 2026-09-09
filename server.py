from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import json
import mimetypes
import os
import tempfile
import uuid
from pypdf import PdfReader
from docx import Document
import re
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

DATA_DIR = Path("data")
UPLOAD_DIR = DATA_DIR / "uploads"
RESUME_DIR = DATA_DIR / "resumes"

DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
RESUME_DIR.mkdir(exist_ok=True)

# Initialize Groq client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

STATIC_FILES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/app.js": "app.js",
    "/styles.css": "styles.css",
}

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

class ResumeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self.send_json({"status": "ok", "candidates": len(sample_candidates)})
            return

        if parsed.path == "/api/rank":
            job_text = "Senior Data Analyst with strong business communication, SQL, Python, dashboard design, stakeholder management, and experience translating source data into measurable insights for executive decision-making."
            ranking = analyze_resumes(job_text, sample_candidates)
            self.send_json({"ranking": ranking})
            return

        if parsed.path in STATIC_FILES:
            file_path = Path(STATIC_FILES[parsed.path])
            self.serve_static(file_path)
            return

        if parsed.path == "/favicon.ico":
            self.serve_static(Path("favicon.ico"))
            return

        self.send_error(404, "Not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/rank":
            content_type = self.headers.get("Content-Type", "")
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)

            try:
                if "application/json" in content_type:
                    data = json.loads(body.decode("utf-8"))
                else:
                    data = parse_qs(body.decode("utf-8"))
            except Exception:
                data = {}

            job_text = data.get("jobDescription") or data.get("job_text") or sample_job_description()
            uploaded_text = data.get("resumes") or []
            files = []

            # allow frontend to send a list of filename/text resume strings
            if isinstance(uploaded_text, list):
                files = uploaded_text
            elif isinstance(uploaded_text, str):
                files = [uploaded_text]

            candidates = []
            for candidate in sample_candidates:
                candidates.append(candidate)

            # If uploaded resumes are provided as text fragments, build transparent text candidates.
            for index, item in enumerate(files):
                if isinstance(item, dict):
                    resume_text = item.get("resume") or item.get("text") or item.get("content") or ""
                    name = item.get("name") or f"Uploaded Candidate {index+1}"
                else:
                    resume_text = str(item)
                    name = f"Uploaded Candidate {index+1}"

                candidates.append({
                    "name": name,
                    "title": "Uploaded Resume",
                    "experience": 4,
                    "email": f"uploaded{index+1}@example.com",
                    "skills": [],
                    "resume": resume_text
                })

            ranking = analyze_resumes(job_text, candidates)
            self.send_json({
                "ranking": ranking,
                "jobDescription": job_text,
                "candidateCount": len(ranking),
                "bestCandidate": ranking[0] if ranking else None
            })
            return

        if parsed.path == "/api/upload":
            try:
                self.handle_resume_upload()
            except Exception as exc:
                self.send_json({"error": str(exc)}, 400)
            return

        self.send_error(404, "Not found")

    def handle_resume_upload(self):
        # parse multipart upload
        boundary = self.headers.get("Content-Type", "").split("boundary=")[-1]
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length)

        # Very small browser-friendly multipart parser for text and docs
        parts = raw.decode("utf-8", errors="ignore").split("--" + boundary)
        candidates = []
        for part in parts:
            if "Content-Disposition" not in part or "filename" not in part:
                continue
            name_match = re.search(r'name="(.*?)"', part)
            file_match = re.search(r'filename="(.*?)"', part)
            if not file_match:
                continue

            filename = file_match.group(1)
            content = part.split("\r\n\r\n", 1)[1].split("\r\n", 1)[0]
            filepath = UPLOAD_DIR / filename
            filepath.write_text(content, encoding="utf-8")

            candidates.append({
                "name": Path(filename).stem,
                "title": "Uploaded Resume",
                "experience": 4,
                "email": "uploaded@example.com",
                "skills": [],
                "resume": content
            })

        job_description = sample_job_description()
        ranking = analyze_resumes(job_description, sample_candidates + candidates)
        self.send_json({"ranking": ranking, "candidateCount": len(ranking)})

    def serve_static(self, file_path):
        path = Path(file_path)
        full_path = Path.cwd() / path
        if not full_path.exists():
            self.send_error(404, "Static file not found")
            return

        content = full_path.read_bytes()
        guess = mimetypes.guess_type(str(full_path))
        self.send_response(200)
        self.send_header("Content-Type", guess[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        return


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


def extract_resume_text(file_path):
    path = Path(file_path)
    suffix = path.suffix.lower()
    try:
        if suffix == ".pdf":
            reader = PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(pages)
            return text
        if suffix == ".docx":
            doc = Document(str(path))
            return "\n".join(p[0].text if hasattr(p[0], 'text') else "" for p in [paragraph for paragraph in doc.paragraphs])
        if suffix in [".txt", ".md"]:
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".html":
            return re.sub(r"<[^>]+>", " ", path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return path.read_text(encoding="utf-8", errors="ignore")
    return ""


def analyze_with_llm(job_text, candidate):
    """Use Groq LLM to analyze a single resume against job description"""
    if not groq_client:
        return None

    try:
        prompt = f"""You are an expert recruiter. Analyze this candidate's resume against the job description and provide a detailed scoring.

Job Description:
{job_text}

Candidate Resume:
{candidate.get('resume', '')}

Analyze the candidate and provide:
1. Overall fit score (0-100)
2. Covered skills (list skills from job description that candidate has)
3. Missing skills (list skills from job description that candidate lacks)
4. A brief 1-2 sentence fit summary

Respond in JSON format:
{{
    "score": <number 0-100>,
    "covered_skills": ["skill1", "skill2"],
    "missing_skills": ["skill3", "skill4"],
    "fit_summary": "Brief summary here"
}}"""

        response = groq_client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an expert recruitment analyst. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )

        result_text = response.choices[0].message.content.strip()

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()

        result = json.loads(result_text)
        return result
    except Exception as e:
        print(f"LLM analysis error: {e}")
        return None


def analyze_resumes(job_text, candidates):
    skills = extract_skills(job_text)
    ranking = []

    for c in candidates:
        resume_text = c.get("resume", "")
        normalized_resume = normalize_text(resume_text)
        custom_skills = []

        # Try LLM analysis first
        llm_result = None
        if groq_client:
            llm_result = analyze_with_llm(job_text, c)

        if llm_result and "score" in llm_result:
            # Use LLM analysis
            covered = llm_result.get("covered_skills", [])
            missing = llm_result.get("missing_skills", [])
            score = int(llm_result.get("score", 70))
            fit_summary = llm_result.get("fit_summary", "")

            # Extract skills from resume for display
            for skill_key, synonyms in skill_library.items():
                if any(s in normalized_resume for s in synonyms):
                    custom_skills.append(skill_key)

            ranking.append({
                "name": c.get("name", "Unknown Candidate"),
                "title": c.get("title", "Resume"),
                "experience": c.get("experience", 4),
                "email": c.get("email", "unknown@example.com"),
                "skills": c.get("skills", []) + custom_skills,
                "coveredSkills": covered,
                "missingSkills": missing,
                "score": score,
                "resumeText": resume_text[:180],
                "fitSummary": fit_summary,
                "analyzedBy": "LLM"
            })
        else:
            # Fallback to keyword-based analysis
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
                "name": c.get("name", "Unknown Candidate"),
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


def main():
    server = ThreadingHTTPServer(("0.0.0.0", 8000), ResumeHandler)
    print("Resume Agent server running on http://127.0.0.1:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()
