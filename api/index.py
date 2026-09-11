from flask import Flask, request, jsonify, make_response
import re
import os
import hashlib
import json
import urllib.request
import urllib.error
import base64

app = Flask(__name__)

# Try to import PDF libraries
try:
    import fitz  # PyMuPDF - best for text extraction
    PDF_LIBRARY = 'pymupdf'
except ImportError:
    try:
        from PyPDF2 import PdfReader
        PDF_LIBRARY = 'pypdf2'
    except ImportError:
        PDF_LIBRARY = None

def extract_text_from_pdf_bytes(pdf_bytes):
    """Extract text from PDF bytes using available library"""
    if PDF_LIBRARY == 'pymupdf':
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text() + "\n"
            doc.close()
            return text.strip()
        except Exception as e:
            print(f"PyMuPDF extraction error: {e}")
            return None
    elif PDF_LIBRARY == 'pypdf2':
        try:
            import io
            reader = PdfReader(io.BytesIO(pdf_bytes))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            print(f"PyPDF2 extraction error: {e}")
            return None
    return None

# Authentication
def get_password():
    return os.environ.get('APP_PASSWORD', '')

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# AI Configuration
def get_ai_config():
    """Get AI provider configuration"""
    # Try Groq first (FREE and fast)
    groq_key = os.environ.get('GROQ_API_KEY', '')
    if groq_key:
        return {
            'provider': 'groq',
            'api_key': groq_key,
            'base_url': 'https://api.groq.com/openai/v1/chat/completions',
            'model': 'llama-3.1-8b-instant'  # Fast and reliable
        }

    # Try OpenAI
    openai_key = os.environ.get('OPENAI_API_KEY', '')
    if openai_key:
        return {
            'provider': 'openai',
            'api_key': openai_key,
            'base_url': 'https://api.openai.com/v1/chat/completions',
            'model': 'gpt-3.5-turbo'
        }

    return None

def call_ai_api(prompt, system_prompt="You are an expert resume analyzer and recruiter.", max_tokens=2000):
    """Make AI API call with proper error handling"""
    config = get_ai_config()
    if not config:
        print("AI API: No API key configured")
        return None

    print(f"AI API: Calling {config['provider']} model {config['model']}")

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        data = json.dumps({
            "model": config['model'],
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": max_tokens
        }).encode('utf-8')

        req = urllib.request.Request(
            config['base_url'],
            data=data,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {config["api_key"]}'
            }
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            content = result['choices'][0]['message']['content'].strip()
            print(f"AI API: Success - {len(content)} chars")
            return content

    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode('utf-8')
        except:
            pass
        print(f"AI API Error: HTTP {e.code} - {error_body[:200]}")
        return None
    except Exception as e:
        print(f"AI API Error: {type(e).__name__}: {e}")
        return None

def parse_json_response(response):
    """Robustly parse JSON from AI response"""
    if not response:
        return None

    content = response.strip()

    # Remove markdown code blocks
    content = re.sub(r'^```(?:json)?\s*\n?', '', content, flags=re.MULTILINE)
    content = re.sub(r'\n?```\s*$', '', content)

    # Try direct parse
    try:
        return json.loads(content)
    except:
        pass

    # Try to find JSON object
    try:
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            return json.loads(match.group(0))
    except:
        pass

    return None

def analyze_resume_complete(resume_text, job_description):
    """Single AI call to extract all data AND score the resume"""

    # Clean text
    clean_text = resume_text.replace('\x00', '').strip()
    clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)

    prompt = f"""Analyze this resume against the job description. Extract candidate information and provide a match score.

=== RESUME ===
{clean_text[:6000]}

=== JOB DESCRIPTION ===
{job_description[:2000]}

=== TASK ===
Extract the following information and score how well this candidate matches the job:

1. CANDIDATE INFO:
- name: Full name (usually at top of resume)
- email: Email address
- phone: Phone number
- location: City/location
- experience_years: Total years of work experience (number)
- current_role: Their CURRENT or MOST RECENT job title (e.g., "Software Engineer", "HR Manager", "Data Analyst"). Look at the first job in Work Experience section.
- current_company: Company name for current/recent job
- education: Highest degree (e.g., "B.Tech", "MBA", "Bachelor's")
- skills: Array of 10-15 key skills from the resume

2. JOB MATCH ANALYSIS:
- matched_skills: Skills from resume that match job requirements
- missing_skills: Key job requirements the candidate lacks
- score: Match score 0-100 based on:
  * How many job requirements the candidate meets
  * Experience level fit
  * Role relevance
  * Skills alignment
- recommendation: Based on score:
  * "Best" (80-100): Excellent fit
  * "Good" (65-79): Strong candidate
  * "Average" (50-64): Partial match
  * "Poor" (0-49): Not suitable

Return ONLY this JSON (no other text):
{{
  "name": "",
  "email": "",
  "phone": "",
  "location": "",
  "experience_years": 0,
  "current_role": "",
  "current_company": "",
  "education": "",
  "skills": [],
  "matched_skills": [],
  "missing_skills": [],
  "score": 0,
  "recommendation": ""
}}"""

    response = call_ai_api(
        prompt,
        "You are an expert ATS (Applicant Tracking System). Analyze resumes accurately. Extract real data from the resume - do not make up information. Return only valid JSON.",
        max_tokens=1500
    )

    result = parse_json_response(response)

    if result and result.get('name'):
        print(f"AI Analysis: {result.get('name')} - Score: {result.get('score')} - Role: {result.get('current_role')}")
        return result

    print("AI analysis failed, using fallback extraction")
    return None

def extract_with_regex(text):
    """Fallback regex-based extraction"""
    lines = text.split('\n')

    # Email
    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    email = email_match.group(0) if email_match else ""

    # Phone
    phone = ""
    phone_match = re.search(r'(\+\d{1,3}[\s\-]?)?\d{10}|(\+\d{1,3}[\s\-]?)?\d{4,5}[\s\-]\d{4,5}', text)
    if phone_match:
        phone = re.sub(r'[\s\-]', '', phone_match.group(0))

    # Name - look at first few lines
    name = ""
    for line in lines[:10]:
        line = line.strip()
        if not line or len(line) < 3 or len(line) > 40:
            continue
        if re.search(r'@|http|www\.|phone|email|resume|cv|\d{5,}', line, re.I):
            continue
        words = line.split()
        if 2 <= len(words) <= 4:
            if all(w[0].isupper() for w in words if w and w[0].isalpha()):
                name = line
                break

    # Experience years
    exp = 0
    exp_match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp)', text, re.I)
    if exp_match:
        exp = int(exp_match.group(1))

    # Education
    education = ""
    edu_match = re.search(r'(B\.?Tech|M\.?Tech|B\.?E|M\.?E|BCA|MCA|MBA|B\.?Com|M\.?Com|B\.?Sc|M\.?Sc|Bachelor|Master|PhD)', text, re.I)
    if edu_match:
        education = edu_match.group(1)

    # Location - look for city names near "Location:" or at start
    location = ""
    loc_match = re.search(r'(?:location|city|address)[:\s]+([A-Za-z][A-Za-z\s,]{2,25})', text, re.I)
    if loc_match:
        location = loc_match.group(1).strip().split(',')[0].strip()

    # Current role - find in work experience section
    current_role = ""
    in_exp_section = False
    for line in lines:
        line_lower = line.lower().strip()
        if re.match(r'^(work\s*experience|professional\s*experience|employment)', line_lower):
            in_exp_section = True
            continue
        if re.match(r'^(education|skills|projects|certifications)', line_lower):
            in_exp_section = False
            continue
        if in_exp_section and not current_role:
            # Look for job title patterns
            if line.strip() and not line.strip().startswith(('•', '-', '*')):
                role_match = re.match(r'^([A-Za-z][A-Za-z\s\-]+?)(?:\s*[-–|@]\s*|\s+at\s+|\s*$)', line.strip())
                if role_match:
                    potential = role_match.group(1).strip()
                    if 3 < len(potential) < 50:
                        current_role = potential
                        break

    # Skills - extract from skills section
    skills = []
    skills_match = re.search(r'(?:skills|technical\s+skills|key\s+skills)[:\s]*\n?([\s\S]{20,800}?)(?:\n\s*\n|education|experience|$)', text, re.I)
    if skills_match:
        section = skills_match.group(1)
        items = re.split(r'[,;•|\n]+', section)
        for item in items:
            item = item.strip()
            if 2 <= len(item) <= 35 and not item.isdigit():
                skills.append(item)
        skills = skills[:15]

    return {
        "name": name or "Unknown",
        "email": email,
        "phone": phone,
        "location": location,
        "experience_years": exp,
        "current_role": current_role,
        "current_company": "",
        "education": education,
        "skills": skills
    }

def calculate_basic_score(resume_data, job_text):
    """Calculate score without AI"""
    job_lower = job_text.lower()
    skills = resume_data.get('skills', [])
    exp = resume_data.get('experience_years', 0)
    role = resume_data.get('current_role', '').lower()

    # Count skill matches
    matched = []
    for skill in skills:
        if skill.lower() in job_lower:
            matched.append(skill)

    # Base score from skill matches
    if skills:
        match_ratio = len(matched) / len(skills)
        score = int(match_ratio * 50) + 25  # 25-75 range
    else:
        score = 35

    # Bonus for experience
    if exp >= 5:
        score += 15
    elif exp >= 3:
        score += 10
    elif exp >= 1:
        score += 5

    # Bonus for relevant role
    if role:
        role_words = [w for w in role.split() if len(w) > 3]
        if any(w in job_lower for w in role_words):
            score += 10

    score = min(95, max(20, score))

    if score >= 80:
        rec = "Best"
    elif score >= 65:
        rec = "Good"
    elif score >= 50:
        rec = "Average"
    else:
        rec = "Poor"

    return {
        "score": score,
        "matched_skills": matched[:10],
        "missing_skills": [],
        "recommendation": rec
    }

def process_single_resume(resume_text, job_description, frontend_data=None):
    """Process a single resume - extract data and score"""
    frontend_data = frontend_data or {}

    # Try AI analysis first (single call for everything)
    ai_result = analyze_resume_complete(resume_text, job_description)

    if ai_result:
        # Use AI results, fill in any blanks from frontend
        return {
            "name": ai_result.get('name') or frontend_data.get('name', 'Unknown'),
            "email": ai_result.get('email') or frontend_data.get('email', ''),
            "phone": ai_result.get('phone') or frontend_data.get('phone', ''),
            "location": ai_result.get('location') or frontend_data.get('location', ''),
            "experience": ai_result.get('experience_years', 0) or frontend_data.get('experience', 0),
            "currentRole": ai_result.get('current_role') or frontend_data.get('currentRole', ''),
            "currentCompany": ai_result.get('current_company') or frontend_data.get('currentCompany', ''),
            "education": ai_result.get('education') or frontend_data.get('education', ''),
            "skills": ai_result.get('matched_skills', []) or ai_result.get('skills', [])[:10],
            "coveredSkills": ai_result.get('matched_skills', []),
            "missingSkills": ai_result.get('missing_skills', []),
            "score": ai_result.get('score', 50),
            "recommendation": ai_result.get('recommendation', 'Average'),
            "analyzedBy": "ai"
        }

    # Fallback to regex extraction
    print("Using fallback regex extraction")
    extracted = extract_with_regex(resume_text)
    score_result = calculate_basic_score(extracted, job_description)

    return {
        "name": extracted.get('name') or frontend_data.get('name', 'Unknown'),
        "email": extracted.get('email') or frontend_data.get('email', ''),
        "phone": extracted.get('phone') or frontend_data.get('phone', ''),
        "location": extracted.get('location') or frontend_data.get('location', ''),
        "experience": extracted.get('experience_years', 0) or frontend_data.get('experience', 0),
        "currentRole": extracted.get('current_role') or frontend_data.get('currentRole', ''),
        "currentCompany": extracted.get('current_company') or frontend_data.get('currentCompany', ''),
        "education": extracted.get('education') or frontend_data.get('education', ''),
        "skills": score_result.get('matched_skills', []) or extracted.get('skills', [])[:10],
        "coveredSkills": score_result.get('matched_skills', []),
        "missingSkills": score_result.get('missing_skills', []),
        "score": score_result.get('score', 40),
        "recommendation": score_result.get('recommendation', 'Poor'),
        "analyzedBy": "fallback"
    }

def analyze_resumes(job_text, candidates):
    """Analyze all resumes against job description"""
    ranking = []

    for c in candidates:
        resume_text = c.get("resume", "")

        # Try server-side PDF extraction
        pdf_base64 = c.get("pdfData", "")
        if pdf_base64 and PDF_LIBRARY:
            try:
                pdf_bytes = base64.b64decode(pdf_base64)
                extracted = extract_text_from_pdf_bytes(pdf_bytes)
                if extracted and len(extracted) > 50:
                    print(f"Server PDF extraction: {len(extracted)} chars")
                    resume_text = extracted
            except Exception as e:
                print(f"PDF extraction error: {e}")

        if not resume_text or len(resume_text.strip()) < 50:
            continue

        # Process resume
        result = process_single_resume(resume_text, job_text, c)
        result["linkedin"] = c.get("linkedin", "")
        result["title"] = result.get("currentRole", "")

        ranking.append(result)

    # Sort by score
    ranking.sort(key=lambda x: x.get("score", 0), reverse=True)
    return ranking

# Routes
@app.route('/api/test-ai', methods=['GET', 'POST', 'OPTIONS'])
def test_ai():
    """Test if AI API is working"""
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    config = get_ai_config()
    if not config:
        response = jsonify({
            "success": False,
            "error": "No AI API key configured",
            "hint": "Set GROQ_API_KEY in environment variables"
        })
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    # Simple test
    test_result = call_ai_api("Say exactly: AI_WORKING", max_tokens=20)

    response = jsonify({
        "success": test_result is not None,
        "provider": config['provider'],
        "model": config['model'],
        "response": test_result,
        "message": "AI is working" if test_result else "AI call failed"
    })
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@app.route('/api', methods=['GET', 'POST', 'OPTIONS'])
@app.route('/api/', methods=['GET', 'POST', 'OPTIONS'])
def api_endpoint():
    """Main API endpoint"""
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    if request.method == 'GET':
        config = get_ai_config()
        response = jsonify({
            "api": "Smart Screener ATS",
            "version": "3.0",
            "ai_enabled": config is not None,
            "ai_provider": config['provider'] if config else None,
            "pdf_library": PDF_LIBRARY
        })
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    # POST - analyze resumes
    try:
        data = request.get_json(force=True) or {}
    except:
        data = {}

    # Auth check
    if 'password' in data and 'jobDescription' not in data:
        submitted = data.get("password", "")
        correct = get_password()

        if not correct:
            response = jsonify({"success": False, "error": "Set APP_PASSWORD in Vercel"})
            response.status_code = 500
        elif submitted == correct:
            token = hash_password(correct + "smart-screener-session")
            response = jsonify({"success": True, "token": token})
        else:
            response = jsonify({"success": False, "error": "Invalid password"})
            response.status_code = 401
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    # Resume analysis
    job_text = data.get("jobDescription", "")
    uploaded = data.get("resumes", [])

    if not job_text:
        response = jsonify({"error": "Job description required", "ranking": []})
        response.status_code = 400
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    candidates = []
    for item in uploaded:
        if isinstance(item, dict):
            candidates.append({
                "name": item.get("name", ""),
                "email": item.get("email", ""),
                "phone": item.get("phone", ""),
                "location": item.get("location", ""),
                "experience": item.get("experience", 0),
                "currentRole": item.get("currentRole", ""),
                "currentCompany": item.get("currentCompany", ""),
                "education": item.get("education", ""),
                "linkedin": item.get("linkedin", ""),
                "resume": item.get("resume") or item.get("text") or "",
                "pdfData": item.get("pdfData", "")
            })
        else:
            candidates.append({"resume": str(item)})

    config = get_ai_config()
    ranking = analyze_resumes(job_text, candidates)

    response = jsonify({
        "ranking": ranking,
        "candidateCount": len(ranking),
        "bestCandidate": ranking[0] if ranking else None,
        "ai_provider": config['provider'] if config else "basic"
    })
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'OPTIONS'])
@app.route('/<path:path>', methods=['GET', 'POST', 'OPTIONS'])
def catch_all(path):
    """Catch-all route"""
    # Forward to api_endpoint for API calls
    if path.startswith('api'):
        return api_endpoint()

    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    if request.method == 'GET':
        config = get_ai_config()
        response = jsonify({
            "api": "Smart Screener ATS",
            "version": "3.0",
            "ai_enabled": config is not None,
            "ai_provider": config['provider'] if config else None
        })
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    # POST requests go to api_endpoint
    return api_endpoint()
