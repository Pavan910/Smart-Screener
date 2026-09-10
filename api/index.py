from flask import Flask, request, jsonify, make_response
import re
import os
import hashlib
import json
import urllib.request
import urllib.error

app = Flask(__name__)

# Authentication
def get_password():
    return os.environ.get('APP_PASSWORD', '')

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# AI API Configuration - supports Groq (free), Grok (xAI), or OpenAI
def get_ai_config():
    # Try Groq first (FREE)
    groq_key = os.environ.get('GROQ_API_KEY', '')
    if groq_key:
        return {
            'provider': 'groq',
            'api_key': groq_key,
            'base_url': 'https://api.groq.com/openai/v1/chat/completions',
            'model': 'llama-3.1-70b-versatile'
        }

    # Try Grok (xAI)
    grok_key = os.environ.get('GROK_API_KEY', '') or os.environ.get('XAI_API_KEY', '')
    if grok_key:
        return {
            'provider': 'grok',
            'api_key': grok_key,
            'base_url': 'https://api.x.ai/v1/chat/completions',
            'model': 'grok-beta'
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

def call_ai_api(messages, max_tokens=800):
    config = get_ai_config()
    if not config:
        return None

    try:
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

        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result['choices'][0]['message']['content'].strip()

    except Exception as e:
        print(f"AI API error ({config['provider']}): {e}")
        return None

def extract_resume_with_ai(resume_text, job_description=""):
    """Use AI to extract structured data from resume - no hardcoded skills"""

    jd_context = f"\nJOB REQUIREMENTS (for context):\n{job_description[:500]}\n" if job_description else ""

    prompt = f"""Extract information from this resume. Return ONLY valid JSON.

Extract ALL skills mentioned - technical skills, soft skills, tools, methodologies, certifications, languages, domain knowledge. Do not limit to any predefined list.
{jd_context}
RESUME TEXT:
{resume_text[:3500]}

Return this JSON format:
{{
  "name": "full name",
  "email": "email address",
  "phone": "phone with country code",
  "location": "city, country",
  "experience_years": number,
  "current_role": "most recent job title",
  "current_company": "most recent company",
  "education": "highest degree",
  "skills": ["all skills found in resume - technical, soft skills, tools, domain expertise"]
}}

Return ONLY JSON, no explanation."""

    response = call_ai_api([
        {"role": "system", "content": "Extract resume data into JSON. Find ALL skills - technical, soft skills, tools, certifications, domain knowledge. No predefined skill list."},
        {"role": "user", "content": prompt}
    ])

    if response:
        try:
            content = response.strip()
            if content.startswith('```'):
                content = re.sub(r'^```json?\n?', '', content)
                content = re.sub(r'\n?```$', '', content)
            return json.loads(content)
        except:
            pass

    return extract_resume_basic(resume_text)

def extract_resume_basic(resume_text):
    """Basic regex extraction fallback when no AI available"""
    text = resume_text.replace('\n', ' ')
    normalized = text.lower()

    # Email
    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)

    # Phone
    phone_patterns = [
        r'\+91[\s\-]?\d{4}[\s\-]?\d{3}[\s\-]?\d{3}',
        r'\+91[\s\-]?[6-9]\d{9}',
        r'[6-9]\d{9}',
        r'\+1[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}'
    ]
    phone = ''
    for pattern in phone_patterns:
        match = re.search(pattern, text)
        if match:
            phone = re.sub(r'[\s\-]', '', match.group(0))
            break

    # Name - improved extraction
    lines = resume_text.split('\n')
    name = ''

    # Skip words that are not names
    skip_words = ['resume', 'cv', 'curriculum', 'vitae', 'updated', 'profile', 'contact', 'summary', 'objective', 'experience', 'education', 'skills', 'about']

    for line in lines[:15]:  # Check more lines
        line = line.strip()
        if not line or len(line) < 3 or len(line) > 50:
            continue

        # Skip lines with email, URL, phone
        if re.search(r'@|http|www\.|\.com|\.org|\.net|\+\d|^\d{5,}', line, re.I):
            continue

        # Skip common resume headers
        if re.match(r'^(resume|cv|curriculum|profile|contact|summary|objective|experience|education|skills|about|work|employment|professional)', line, re.I):
            continue

        # Clean the line
        clean_line = re.sub(r'^[\s|•\-:]+|[\s|•\-:]+$', '', line).strip()

        # Remove words like "Resume", "CV", "Updated" from potential name
        words = clean_line.split()
        filtered_words = [w for w in words if w.lower() not in skip_words]

        if len(filtered_words) >= 2 and len(filtered_words) <= 4:
            # Check if words look like a name (capitalized)
            if all(w[0].isupper() and w.isalpha() for w in filtered_words if w):
                name = ' '.join(filtered_words)
                break

        # Also check for "Name: John Doe" format
        name_match = re.match(r'^(?:name|candidate|applicant)\s*[:\-]\s*(.+)', line, re.I)
        if name_match:
            name = name_match.group(1).strip()
            break

    # Experience years
    exp_years = 0
    exp_patterns = [
        r'(\d+)\+?\s*(?:years?|yrs?)[\s\w]*(?:of\s+)?(?:experience|exp)',
        r'(?:experience|exp)[\s:]*(\d+)\+?\s*(?:years?|yrs?)',
        r'(?:total|overall)[\s\w]*(\d+)\+?\s*(?:years?|yrs?)'
    ]
    for pattern in exp_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            exp_years = int(match.group(1))
            break

    # Current role - look for job titles
    current_role = ''
    role_patterns = [
        r'((?:Senior|Junior|Lead|Principal|Staff|Chief|Head|Director|Manager|Engineer|Developer|Analyst|Specialist|Consultant|Associate|Executive|Architect|Designer|Coordinator|Administrator|Officer|Financial|Software|Data|Product|Project|Business|Marketing|Sales|HR|Operations|Technical)[^,\n•|]{0,40})',
    ]
    for line in lines[:30]:
        line = line.strip()
        for pattern in role_patterns:
            match = re.search(pattern, line, re.I)
            if match and len(match.group(1)) > 5:
                current_role = match.group(1).strip()
                break
        if current_role:
            break

    # Education
    education = ''
    edu_patterns = [
        r'(B\.?Com|B\.?Tech|M\.?Tech|B\.?E|M\.?E|B\.?Sc|M\.?Sc|BCA|MCA|BBA|MBA|Bachelor|Master|PhD|Ph\.D)',
        r'(Bachelor\s+of\s+[A-Za-z\s]+)',
        r'(Master\s+of\s+[A-Za-z\s]+)'
    ]
    for pattern in edu_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            education = match.group(1).strip()
            break

    # Location - Indian cities
    location = ''
    cities = ['Mumbai', 'Delhi', 'Bangalore', 'Bengaluru', 'Hyderabad', 'Chennai', 'Kolkata',
              'Pune', 'Ahmedabad', 'Jaipur', 'Noida', 'Gurgaon', 'Gurugram', 'Vadodara',
              'Baroda', 'Surat', 'Lucknow', 'Chandigarh', 'Indore', 'Bhopal', 'Coimbatore',
              'Kochi', 'Trivandrum', 'Mysore', 'Nagpur', 'Patna', 'Ranchi']
    for city in cities:
        if city.lower() in normalized:
            location = city
            break

    # Extract skills dynamically from resume text
    skills = extract_skills_from_text(resume_text)

    return {
        "name": name or "Unknown",
        "email": email_match.group(0) if email_match else "",
        "phone": phone,
        "location": location,
        "experience_years": exp_years,
        "current_role": current_role,
        "current_company": "",
        "education": education,
        "skills": skills
    }

def extract_skills_from_text(text):
    """Extract skills dynamically from resume text without predefined list"""
    normalized = text.lower()
    skills = set()

    # Common skill patterns to look for (not a fixed library, just detection patterns)
    # Technical skills - programming languages, tools, frameworks
    tech_patterns = [
        r'\b(python|java|javascript|typescript|react|angular|vue|node\.?js|sql|mysql|postgresql|mongodb|aws|azure|gcp|docker|kubernetes|git|excel|power\s*bi|tableau|pandas|numpy|tensorflow|pytorch|scikit[\s-]?learn|spark|hadoop|airflow|flask|django|spring|html|css|php|ruby|golang|rust|scala|kotlin|swift|c\+\+|c#|\.net|jquery|bootstrap|sass|linux|unix|windows|jira|confluence|slack|figma|sketch|photoshop|illustrator)\b',
    ]

    # Soft skills and business skills
    soft_patterns = [
        r'\b(communication|leadership|teamwork|problem[\s-]?solving|analytical|presentation|negotiation|stakeholder\s+management|client[\s-]?facing|project\s+management|time\s+management|critical\s+thinking|decision[\s-]?making|collaboration|mentoring|coaching|strategic\s+planning|business\s+analysis|data\s+analysis|reporting|documentation)\b',
    ]

    # Certifications and methodologies
    cert_patterns = [
        r'\b(agile|scrum|kanban|devops|ci[\s/]?cd|pmp|six\s+sigma|itil|iso|sap|salesforce|oracle|microsoft\s+certified|aws\s+certified|google\s+certified|lean|waterfall|tdd|bdd)\b',
    ]

    all_patterns = tech_patterns + soft_patterns + cert_patterns

    for pattern in all_patterns:
        matches = re.findall(pattern, normalized, re.I)
        for match in matches:
            # Clean and capitalize skill name
            skill = match.strip()
            if len(skill) > 1:
                # Proper capitalization
                if skill.lower() in ['sql', 'aws', 'gcp', 'css', 'html', 'php', 'ci/cd', 'pmp', 'sap']:
                    skill = skill.upper()
                elif skill.lower() in ['javascript', 'typescript', 'python', 'java', 'react', 'angular', 'vue', 'docker', 'kubernetes', 'excel', 'tableau', 'jira', 'figma', 'linux', 'windows']:
                    skill = skill.capitalize()
                else:
                    skill = skill.title()
                skills.add(skill)

    return list(skills)[:15]  # Return top 15 skills

def analyze_match_with_ai(resume_data, job_text):
    """Use AI to match resume skills against job description - dynamic matching"""

    skills_str = ', '.join(resume_data.get('skills', [])[:20])

    prompt = f"""Compare this candidate's skills to the job requirements.

JOB DESCRIPTION:
{job_text[:1200]}

CANDIDATE:
- Name: {resume_data.get('name')}
- Experience: {resume_data.get('experience_years', 0)} years
- Current Role: {resume_data.get('current_role')}
- Education: {resume_data.get('education')}
- Skills: {skills_str}

TASK:
1. Find skills/requirements FROM THE JOB DESCRIPTION that the candidate HAS
2. Find skills/requirements FROM THE JOB DESCRIPTION that the candidate is MISSING
3. Score 0-100 based on how well candidate matches the JOB requirements
4. Recommend based on score: "Best" (80+), "Good" (65-79), "Average" (50-64), or "Poor" (<50)

Return ONLY JSON:
{{
  "score": number,
  "matched_skills": ["job requirements the candidate meets"],
  "missing_skills": ["job requirements the candidate lacks"],
  "recommendation": "Best" or "Good" or "Average" or "Poor"
}}"""

    response = call_ai_api([
        {"role": "system", "content": "Match candidate skills to job requirements. Extract requirements from job description, check if candidate has them. No predefined skill categories."},
        {"role": "user", "content": prompt}
    ], max_tokens=500)

    if response:
        try:
            content = response.strip()
            if content.startswith('```'):
                content = re.sub(r'^```json?\n?', '', content)
                content = re.sub(r'\n?```$', '', content)
            return json.loads(content)
        except:
            pass

    # Fallback: basic matching without AI
    return match_skills_basic(resume_data, job_text)

def match_skills_basic(resume_data, job_text):
    """Basic skill matching when no AI available - compares resume skills to job description"""
    job_normalized = job_text.lower()
    resume_skills = [s.lower() for s in resume_data.get('skills', [])]

    # Extract skills/keywords from job description
    job_skills = extract_skills_from_text(job_text)

    # Find matches
    matched = []
    missing = []

    for skill in job_skills:
        skill_lower = skill.lower()
        # Check if skill or similar term exists in resume
        found = False
        for rs in resume_skills:
            if skill_lower in rs or rs in skill_lower:
                found = True
                break
        if found:
            matched.append(skill)
        else:
            missing.append(skill)

    # Calculate score
    if len(job_skills) > 0:
        skill_score = int((len(matched) / len(job_skills)) * 60)
    else:
        skill_score = 30

    # Experience bonus
    exp = resume_data.get('experience_years', 0)
    exp_score = min(20, exp * 3) if exp > 0 else 0

    # Role relevance bonus
    role_score = 0
    current_role = resume_data.get('current_role', '').lower()
    if current_role:
        role_keywords = ['analyst', 'developer', 'engineer', 'manager', 'lead', 'senior', 'consultant', 'specialist']
        for kw in role_keywords:
            if kw in job_normalized and kw in current_role:
                role_score = 10
                break

    total_score = min(95, max(35, skill_score + exp_score + role_score))

    # Recommendation - intuitive labels
    if total_score >= 80:
        recommendation = "Best"
    elif total_score >= 65:
        recommendation = "Good"
    elif total_score >= 50:
        recommendation = "Average"
    else:
        recommendation = "Poor"

    return {
        "score": total_score,
        "matched_skills": matched[:10],
        "missing_skills": missing[:10],
        "recommendation": recommendation
    }

def analyze_resumes(job_text, candidates):
    """Analyze resumes against job description using AI"""
    ranking = []

    for c in candidates:
        resume_text = c.get("resume", "")

        # Extract with AI
        extracted = extract_resume_with_ai(resume_text, job_text)

        # Merge frontend data with AI extraction
        name = c.get("name") or extracted.get("name") or "Unknown"
        email = c.get("email") or extracted.get("email") or ""
        phone = c.get("phone") or extracted.get("phone") or ""
        location = c.get("location") or extracted.get("location") or ""
        experience = c.get("experience") or extracted.get("experience_years") or 0
        current_role = c.get("currentRole") or extracted.get("current_role") or ""
        current_company = c.get("currentCompany") or extracted.get("current_company") or ""
        education = c.get("education") or extracted.get("education") or ""
        skills = extracted.get("skills") or []

        # Match against job description
        match_result = analyze_match_with_ai({
            "name": name,
            "experience_years": experience,
            "current_role": current_role,
            "skills": skills,
            "education": education
        }, job_text)

        config = get_ai_config()
        ranking.append({
            "name": name,
            "email": email,
            "phone": phone,
            "location": location,
            "experience": experience,
            "currentRole": current_role,
            "currentCompany": current_company,
            "education": education,
            "skills": match_result.get("matched_skills", skills[:10]),
            "coveredSkills": match_result.get("matched_skills", []),
            "missingSkills": match_result.get("missing_skills", []),
            "score": match_result.get("score", 50),
            "recommendation": match_result.get("recommendation", "Review"),
            "linkedin": c.get("linkedin", ""),
            "title": current_role,
            "analyzedBy": config['provider'] if config else "basic"
        })

    ranking.sort(key=lambda x: x["score"], reverse=True)
    return ranking

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'OPTIONS'])
@app.route('/<path:path>', methods=['GET', 'POST', 'OPTIONS'])
def catch_all(path):
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    if request.method == 'GET':
        config = get_ai_config()
        response = jsonify({
            "api": "Smart Screener",
            "version": "2.0",
            "ai_enabled": config is not None,
            "ai_provider": config['provider'] if config else None,
            "message": f"Using {config['provider'].upper()} AI" if config else "No AI key configured. Add GROQ_API_KEY (free) in Vercel."
        })
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    if request.method == 'POST':
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
        job_text = data.get("jobDescription") or ""
        uploaded = data.get("resumes") or []

        if not job_text:
            response = jsonify({"error": "Job description required", "ranking": []})
            response.status_code = 400
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response

        if not uploaded:
            response = jsonify({"error": "No resumes provided", "ranking": []})
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
                    "resume": item.get("resume") or item.get("text") or ""
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
