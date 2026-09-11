from flask import Flask, request, jsonify, make_response
import re
import os
import hashlib
import json
import urllib.request
import urllib.error
import base64
from datetime import datetime

app = Flask(__name__)

# PDF Library
try:
    import fitz
    PDF_LIBRARY = 'pymupdf'
except ImportError:
    PDF_LIBRARY = None

def extract_text_from_pdf_bytes(pdf_bytes):
    if PDF_LIBRARY == 'pymupdf':
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text() + "\n"
            doc.close()
            return text.strip()
        except Exception as e:
            print(f"PDF error: {e}")
    return None

def get_password():
    return os.environ.get('APP_PASSWORD', '')

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_ai_config():
    groq_key = os.environ.get('GROQ_API_KEY', '')
    if groq_key:
        return {
            'provider': 'groq',
            'api_key': groq_key,
            'base_url': 'https://api.groq.com/openai/v1/chat/completions',
            'model': 'llama-3.1-8b-instant'
        }
    openai_key = os.environ.get('OPENAI_API_KEY', '')
    if openai_key:
        return {
            'provider': 'openai',
            'api_key': openai_key,
            'base_url': 'https://api.openai.com/v1/chat/completions',
            'model': 'gpt-3.5-turbo'
        }
    return None

def call_ai(prompt, max_tokens=1500):
    config = get_ai_config()
    if not config:
        return None

    try:
        data = json.dumps({
            "model": config['model'],
            "messages": [
                {"role": "system", "content": "You are a resume parser. Extract information accurately. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
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

        with urllib.request.urlopen(req, timeout=25) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            content = result['choices'][0]['message']['content'].strip()
            print(f"AI OK: {len(content)} chars")
            return content
    except Exception as e:
        print(f"AI Error: {e}")
        return None

def parse_ai_json(response):
    if not response:
        return None
    try:
        # Clean markdown
        content = re.sub(r'^```(?:json)?\s*', '', response.strip())
        content = re.sub(r'\s*```$', '', content)
        return json.loads(content)
    except:
        try:
            match = re.search(r'\{[\s\S]*\}', response)
            if match:
                return json.loads(match.group(0))
        except:
            pass
    return None

# ===== SMART EXTRACTION =====

def extract_name(text, lines):
    """Extract candidate name from first few lines"""
    for line in lines[:8]:
        line = line.strip()
        if not line or len(line) < 3 or len(line) > 45:
            continue
        # Skip lines with contact info or headers
        if re.search(r'@|http|www\.|phone|mobile|email|resume|cv|address|linkedin|github|\d{6,}', line, re.I):
            continue
        # Skip job titles appearing at top
        if re.search(r'engineer|developer|manager|analyst|designer|consultant|intern|executive|specialist', line, re.I):
            continue
        words = line.split()
        if 2 <= len(words) <= 4:
            # Check if words look like names (capitalized)
            if all(w[0].isupper() for w in words if w and len(w) > 1):
                return line
    return "Unknown"

def extract_email(text):
    match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    return match.group(0) if match else ""

def extract_phone(text):
    # Indian format
    match = re.search(r'\+91[\s\-]?\d{10}|\+91[\s\-]?\d{5}[\s\-]?\d{5}', text)
    if match:
        return re.sub(r'[\s\-]', '', match.group(0))
    # General 10 digit
    match = re.search(r'[6-9]\d{9}', text)
    if match:
        return match.group(0)
    return ""

def extract_location(_text):
    """Let AI handle location extraction - return empty for regex fallback"""
    # AI will intelligently determine current location vs education location
    # No hardcoded logic here
    return ""

def extract_current_role(text, lines):
    """Extract current job title from experience section"""
    in_exp = False

    for i, line in enumerate(lines):
        line_clean = line.strip()
        line_lower = line_clean.lower()

        # Detect experience section
        if re.match(r'^(professional\s+experience|work\s+experience|employment|experience)$', line_lower):
            in_exp = True
            continue

        # Exit on other sections
        if re.match(r'^(education|skills|technical\s+skills|projects|certifications|achievements)', line_lower):
            if in_exp:
                break
            continue

        if in_exp and line_clean:
            # Skip bullet points
            if line_clean.startswith(('•', '-', '*', '–')):
                continue

            # Look for "Role | Company" or "Role at Company" patterns
            role_match = re.match(r'^([A-Za-z][A-Za-z\s\-/]+?)\s*[|–\-]\s*[A-Za-z]', line_clean)
            if role_match:
                role = role_match.group(1).strip()
                # Validate it looks like a job title
                if 3 < len(role) < 50 and not re.search(r'\d{4}|present|current', role, re.I):
                    return role

            # Look for standalone role (next line might be company)
            if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*\s*(?:Engineer|Developer|Manager|Analyst|Designer|Specialist|Executive|Consultant|Intern|Lead|Director|Officer|Coordinator|Assistant)', line_clean):
                return line_clean.split('|')[0].split('–')[0].strip()

    return ""

def extract_experience_years(text):
    """Calculate years of experience from job dates in EXPERIENCE section only"""
    lines = text.split('\n')
    current_year = datetime.now().year

    # First check for explicit mention
    exp_match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)[\s\-]*(?:of\s+)?(?:experience|exp)', text, re.I)
    if exp_match:
        years = int(exp_match.group(1))
        if 0 < years <= 30:
            return years

    # Find the EXPERIENCE section only
    exp_section = ""
    in_exp = False
    for line in lines:
        line_lower = line.lower().strip()
        # Start of experience section
        if re.match(r'^(professional\s+experience|work\s+experience|employment\s+history|experience)$', line_lower):
            in_exp = True
            continue
        # End on other major sections
        if re.match(r'^(education|skills|technical\s+skills|projects|certifications|achievements|key\s+projects)', line_lower):
            if in_exp:
                break
        if in_exp:
            exp_section += line + "\n"

    if not exp_section:
        exp_section = text  # Fallback to full text if no section found

    # Find date ranges like "Sep 2025 - Present" or "2020 - 2022"
    date_pattern = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*(\d{4})\s*[-–]\s*(?:Present|Current|Now|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*(\d{4}))'

    matches = re.findall(date_pattern, exp_section, re.I)

    if not matches:
        return 0

    # Calculate total experience (handle potential overlaps by taking min-max range)
    start_years = []
    end_years = []

    for match in matches:
        start_year = int(match[0])
        if match[1] and match[1].isdigit():
            end_year = int(match[1])
        else:
            end_year = current_year

        if 1990 <= start_year <= current_year and start_year <= end_year <= current_year + 1:
            start_years.append(start_year)
            end_years.append(end_year)

    if start_years and end_years:
        # Total span from earliest start to latest end
        total_years = max(end_years) - min(start_years)
        return min(max(total_years, 1), 30)

    return 0

def extract_education(text):
    patterns = [
        r"(B\.?Tech|M\.?Tech|Bachelor(?:'s)?(?:\s+of\s+[A-Za-z]+)?|Master(?:'s)?(?:\s+of\s+[A-Za-z]+)?|MBA|BCA|MCA|B\.?E\.?|M\.?E\.?|B\.?Com|M\.?Com|B\.?Sc|M\.?Sc|PhD|Ph\.?D\.?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1)
    return ""

def extract_skills(text, lines):
    """Extract skills from resume - handles multiple formats including Category: skill1, skill2"""
    skills = []
    in_skills = False
    skills_lines = []

    for line in lines:
        line_lower = line.lower().strip()

        # Detect skills section
        if re.match(r'^(technical\s+skills?|skills?|key\s+skills?|core\s+competenc|areas?\s+of\s+expertise)', line_lower):
            in_skills = True
            continue

        # Exit on other sections
        if re.match(r'^(professional\s+experience|work\s+experience|employment|education|projects|certifications|achievements|experience|summary|objective)', line_lower):
            if in_skills:
                break
            continue

        if in_skills and line.strip():
            skills_lines.append(line.strip())

    # Parse each line - handle "Category: skill1, skill2, skill3" format
    for line in skills_lines:
        # Check if line has "Category: values" format
        if ':' in line:
            # Split by colon and take the values part
            parts = line.split(':', 1)
            if len(parts) > 1:
                values_part = parts[1].strip()
                # Split values by comma
                items = re.split(r'[,;]+', values_part)
                for item in items:
                    item = item.strip()
                    if 2 <= len(item) <= 40:
                        skills.append(item)
        else:
            # No colon - split by common delimiters
            items = re.split(r'[,;|•]+', line)
            for item in items:
                item = item.strip()
                item = re.sub(r'^[\-\*\s•]+', '', item)
                if 2 <= len(item) <= 40:
                    skills.append(item)

    # Also try inline format if no skills found
    if not skills:
        # Look for "Skills: Python, Java, SQL" anywhere
        inline_match = re.search(r'(?:skills?|competencies)[:\s]+([^\n]{10,300})', text, re.I)
        if inline_match:
            items = re.split(r'[,;|•]+', inline_match.group(1))
            for item in items:
                item = item.strip()
                if 2 <= len(item) <= 40:
                    skills.append(item)

    # Clean up and deduplicate
    cleaned = []
    seen = set()
    for s in skills:
        s = s.strip()
        s_lower = s.lower()

        # Skip empty, too short, or duplicates
        if len(s) >= 2 and s_lower not in seen and len(s.split()) <= 5:
            seen.add(s_lower)
            cleaned.append(s)

    return cleaned[:20]

def extract_all_regex(text):
    """Extract all fields using regex"""
    lines = text.split('\n')

    return {
        "name": extract_name(text, lines),
        "email": extract_email(text),
        "phone": extract_phone(text),
        "location": extract_location(text),
        "experience_years": extract_experience_years(text),
        "current_role": extract_current_role(text, lines),
        "education": extract_education(text),
        "skills": extract_skills(text, lines)
    }

def analyze_with_ai(resume_text, job_description):
    """Use AI to analyze resume"""
    prompt = f"""Parse this resume and match against the job.

RESUME:
{resume_text[:5000]}

JOB:
{job_description[:1500]}

Extract these fields ACCURATELY:

1. name: Full name (usually at very top)
2. email: Email address
3. phone: Phone number
4. location: Extract the candidate's CURRENT city/location. Use your intelligence to determine:
   - Look for location near the contact info (name, email, phone) at the top of resume
   - Cities mentioned alongside university/college names are EDUCATION locations, NOT current address
   - If someone studied at "XYZ University, Dehradun" that's where they studied, not where they live now
   - Only return a location if you're confident it's their current residence/city
   - If unsure or only education locations found, return empty string ""
5. experience_years: Calculate from work experience dates. Return as NUMBER.
6. current_role: The JOB TITLE of current/most recent position (like "AI Engineer", "Financial Analyst")
7. education: Highest degree (B.Tech, MBA, etc.)
8. skills: Array of 10-15 actual skills from the Skills/Technical Skills section. Include ALL skills listed there.
9. matched_skills: Which candidate skills match the job requirements
10. missing_skills: Key job requirements candidate doesn't have
11. score: Match score 0-100 based on how well candidate fits the job
12. recommendation: "Best" (80+), "Good" (65-79), "Average" (50-64), "Poor" (<50)

IMPORTANT:
- For skills, extract ALL skills from the skills section, not just a few.
- For location, use context to distinguish current address from education location. Be intelligent about this.

Return ONLY valid JSON, no explanation:"""

    response = call_ai(prompt)
    return parse_ai_json(response)

def calculate_score(resume_data, job_text):
    """Calculate match score"""
    job_lower = job_text.lower()
    skills = resume_data.get('skills', [])
    role = resume_data.get('current_role', '').lower()
    exp = resume_data.get('experience_years', 0)

    matched = [s for s in skills if s.lower() in job_lower]

    # Base score
    if skills:
        score = int((len(matched) / len(skills)) * 50) + 20
    else:
        score = 30

    # Experience bonus
    if exp >= 5:
        score += 15
    elif exp >= 2:
        score += 10
    elif exp >= 1:
        score += 5

    # Role relevance
    if role:
        role_words = [w for w in role.split() if len(w) > 3]
        if any(w in job_lower for w in role_words):
            score += 15

    score = min(95, max(20, score))

    if score >= 80:
        rec = "Best"
    elif score >= 65:
        rec = "Good"
    elif score >= 50:
        rec = "Average"
    else:
        rec = "Poor"

    return {"score": score, "matched_skills": matched, "recommendation": rec}

def process_resume(resume_text, job_text, frontend_data):
    """Process single resume"""
    # Try AI first
    ai_result = analyze_with_ai(resume_text, job_text)

    if ai_result and ai_result.get('name') and len(ai_result.get('name', '')) > 2:
        print(f"AI: {ai_result.get('name')} - {ai_result.get('current_role')} - Score: {ai_result.get('score')}")

        # Validate AI results
        score = ai_result.get('score', 50)
        if not isinstance(score, (int, float)):
            score = 50
        score = max(0, min(100, int(score)))

        # Get all skills and matched skills
        all_skills = ai_result.get('skills', [])
        matched_skills = ai_result.get('matched_skills', [])

        # Use all skills for display, matched for highlighting
        display_skills = all_skills[:15] if all_skills else matched_skills[:10]

        return {
            "name": ai_result.get('name') or frontend_data.get('name', 'Unknown'),
            "email": ai_result.get('email') or frontend_data.get('email', ''),
            "phone": ai_result.get('phone') or frontend_data.get('phone', ''),
            "location": ai_result.get('location', ''),  # AI decides location - no fallback
            "experience": ai_result.get('experience_years', 0),
            "currentRole": ai_result.get('current_role') or frontend_data.get('currentRole', ''),
            "currentCompany": ai_result.get('current_company', ''),
            "education": ai_result.get('education', ''),
            "skills": display_skills,
            "coveredSkills": matched_skills,
            "missingSkills": ai_result.get('missing_skills', []),
            "score": score,
            "recommendation": ai_result.get('recommendation', 'Average'),
            "analyzedBy": "ai"
        }

    # Fallback to regex
    print("Using regex fallback")
    extracted = extract_all_regex(resume_text)
    score_data = calculate_score(extracted, job_text)

    # Get all extracted skills
    all_skills = extracted.get('skills', [])
    matched_skills = score_data.get('matched_skills', [])

    return {
        "name": extracted.get('name') or frontend_data.get('name', 'Unknown'),
        "email": extracted.get('email') or frontend_data.get('email', ''),
        "phone": extracted.get('phone') or frontend_data.get('phone', ''),
        "location": extracted.get('location', ''),  # No fallback - empty if not found
        "experience": extracted.get('experience_years', 0),
        "currentRole": extracted.get('current_role') or frontend_data.get('currentRole', ''),
        "currentCompany": "",
        "education": extracted.get('education', ''),
        "skills": all_skills[:15] if all_skills else matched_skills[:10],
        "coveredSkills": matched_skills,
        "missingSkills": [],
        "score": score_data.get('score', 40),
        "recommendation": score_data.get('recommendation', 'Poor'),
        "analyzedBy": "regex"
    }

def analyze_resumes(job_text, candidates):
    ranking = []

    for c in candidates:
        resume_text = c.get("resume", "")

        # PDF extraction
        pdf_data = c.get("pdfData", "")
        if pdf_data and PDF_LIBRARY:
            try:
                pdf_bytes = base64.b64decode(pdf_data)
                extracted = extract_text_from_pdf_bytes(pdf_bytes)
                if extracted and len(extracted) > 50:
                    resume_text = extracted
            except:
                pass

        if not resume_text or len(resume_text.strip()) < 50:
            continue

        result = process_resume(resume_text, job_text, c)
        result["linkedin"] = c.get("linkedin", "")
        result["title"] = result.get("currentRole", "")
        ranking.append(result)

    ranking.sort(key=lambda x: x.get("score", 0), reverse=True)
    return ranking

# Routes
@app.route('/api/test-ai', methods=['GET', 'POST', 'OPTIONS'])
def test_ai():
    if request.method == 'OPTIONS':
        resp = make_response()
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return resp

    config = get_ai_config()
    if not config:
        resp = jsonify({"success": False, "error": "No API key"})
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp

    test = call_ai("Reply with: OK", max_tokens=10)
    resp = jsonify({
        "success": test is not None,
        "provider": config['provider'],
        "model": config['model'],
        "response": test
    })
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp

@app.route('/api', methods=['GET', 'POST', 'OPTIONS'])
@app.route('/api/', methods=['GET', 'POST', 'OPTIONS'])
@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'OPTIONS'])
@app.route('/<path:path>', methods=['GET', 'POST', 'OPTIONS'])
def main_route(path=''):
    if request.method == 'OPTIONS':
        resp = make_response()
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return resp

    if request.method == 'GET':
        config = get_ai_config()
        resp = jsonify({
            "api": "Smart Screener ATS",
            "version": "4.0",
            "ai_enabled": config is not None,
            "ai_provider": config['provider'] if config else None,
            "pdf_library": PDF_LIBRARY
        })
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp

    try:
        data = request.get_json(force=True) or {}
    except:
        data = {}

    # Auth
    if 'password' in data and 'jobDescription' not in data:
        submitted = data.get("password", "")
        correct = get_password()
        if not correct:
            resp = jsonify({"success": False, "error": "Set APP_PASSWORD"})
            resp.status_code = 500
        elif submitted == correct:
            token = hash_password(correct + "smart-screener-session")
            resp = jsonify({"success": True, "token": token})
        else:
            resp = jsonify({"success": False, "error": "Invalid password"})
            resp.status_code = 401
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp

    # Analysis
    job_text = data.get("jobDescription", "")
    uploaded = data.get("resumes", [])

    if not job_text:
        resp = jsonify({"error": "Job description required", "ranking": []})
        resp.status_code = 400
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp

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

    resp = jsonify({
        "ranking": ranking,
        "candidateCount": len(ranking),
        "bestCandidate": ranking[0] if ranking else None,
        "ai_provider": config['provider'] if config else "basic"
    })
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp
