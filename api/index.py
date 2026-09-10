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
    """Use AI to extract structured data from resume with high accuracy"""

    jd_context = f"\nJOB DESCRIPTION (match skills against this):\n{job_description[:800]}\n" if job_description else ""

    prompt = f"""You are an expert HR resume parser. Extract information from this resume with high accuracy.

IMPORTANT RULES:
1. NAME: Extract the candidate's full name (usually at the top). Do NOT include words like "Resume", "CV", "Updated" in the name.
2. LOCATION: Extract the city/location where the candidate is based. Look for city names in contact section or address.
3. EXPERIENCE: Calculate total years of professional experience from work history dates. If explicit "X years experience" is mentioned, use that.
4. CURRENT ROLE: Extract the EXACT job title from the MOST RECENT job position. This should be a proper job title like "Software Engineer", "HR Manager", "Data Analyst" - NOT descriptive text.
5. SKILLS: Extract ALL skills mentioned in the resume - programming languages, tools, frameworks, soft skills, domain expertise, certifications. Read the entire resume carefully.
{jd_context}
RESUME TEXT:
{resume_text[:4000]}

Return ONLY this JSON (no explanation, no markdown):
{{
  "name": "candidate full name only",
  "email": "email@example.com",
  "phone": "+91XXXXXXXXXX or similar",
  "location": "City name",
  "experience_years": number (integer),
  "current_role": "exact job title from most recent position",
  "current_company": "most recent company name",
  "education": "highest degree (e.g., B.Tech, MBA, etc.)",
  "skills": ["skill1", "skill2", "skill3", ...]
}}"""

    response = call_ai_api([
        {"role": "system", "content": "You are a precise resume parser. Extract data exactly as it appears in the resume. For current_role, extract the actual job title, not descriptive text. For skills, list ALL skills found including technical, soft skills, tools, and certifications."},
        {"role": "user", "content": prompt}
    ], max_tokens=1000)

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
    """Smart regex extraction fallback when no AI available - no hardcoded lists"""
    text = resume_text.replace('\n', ' ')
    normalized = text.lower()
    lines = resume_text.split('\n')

    # Email - standard pattern
    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)

    # Phone - international patterns
    phone_patterns = [
        r'\+\d{1,3}[\s\-]?\d{4,5}[\s\-]?\d{3,4}[\s\-]?\d{3,4}',  # International
        r'\+\d{1,3}[\s\-]?\d{10}',  # +XX XXXXXXXXXX
        r'[6-9]\d{9}',  # Indian mobile
        r'\(\d{3}\)[\s\-]?\d{3}[\s\-]?\d{4}'  # US format
    ]
    phone = ''
    for pattern in phone_patterns:
        match = re.search(pattern, text)
        if match:
            phone = re.sub(r'[\s\-\(\)]', '', match.group(0))
            break

    # Name extraction - smart approach
    name = ''
    skip_words = ['resume', 'cv', 'curriculum', 'vitae', 'updated', 'profile', 'contact',
                  'summary', 'objective', 'experience', 'education', 'skills', 'about',
                  'new', 'final', 'latest', 'version', 'draft']

    for line in lines[:15]:
        line = line.strip()
        if not line or len(line) < 3 or len(line) > 50:
            continue

        # Skip lines with email, URL, phone
        if re.search(r'@|http|www\.|\.com|\.org|\.net|\+\d|^\d{5,}', line, re.I):
            continue

        # Skip section headers
        if re.match(r'^(resume|cv|curriculum|profile|contact|summary|objective|experience|education|skills|about|work|employment|professional|technical)', line, re.I):
            continue

        # Clean and filter
        clean_line = re.sub(r'^[\s|•\-:]+|[\s|•\-:]+$', '', line).strip()
        words = clean_line.split()
        filtered_words = [w for w in words if w.lower() not in skip_words and len(w) > 1]

        # Check if looks like a name (2-4 capitalized words)
        if 2 <= len(filtered_words) <= 4:
            if all(w[0].isupper() and w.replace('.', '').isalpha() for w in filtered_words if w):
                name = ' '.join(filtered_words)
                break

        # Check "Name: John Doe" format
        name_match = re.match(r'^(?:name|candidate|applicant)\s*[:\-]\s*(.+)', line, re.I)
        if name_match:
            name = name_match.group(1).strip()
            break

    # Experience - calculate from dates if not explicitly mentioned
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

    # If not found, calculate from work history
    if exp_years == 0:
        current_year = 2024
        years_found = re.findall(r'\b(19\d{2}|20[0-2]\d)\b', text)
        years_found = [int(y) for y in years_found if 1990 <= int(y) <= current_year]
        if years_found:
            exp_years = current_year - min(years_found)
            if exp_years > 40:  # Sanity check
                exp_years = 0

    # Current role - look for job title patterns near "Present" or recent dates
    current_role = ''
    role_keywords = ['engineer', 'developer', 'analyst', 'manager', 'lead', 'specialist',
                     'consultant', 'designer', 'architect', 'coordinator', 'executive',
                     'officer', 'director', 'head', 'associate', 'scientist', 'recruiter',
                     'administrator', 'representative', 'accountant']

    for i, line in enumerate(lines[:40]):
        line_lower = line.lower().strip()
        # Check if line contains a role keyword and is near dates or "present"
        for keyword in role_keywords:
            if keyword in line_lower and len(line.strip()) < 80:
                # Check if this looks like a job title (not a bullet point or sentence)
                if not line.strip().startswith('•') and not line.strip().startswith('-'):
                    # Extract potential title
                    title_match = re.match(r'^([A-Z][A-Za-z\s\-]+(?:Engineer|Developer|Analyst|Manager|Lead|Specialist|Consultant|Designer|Architect|Coordinator|Executive|Officer|Director|Associate|Scientist|Recruiter|Administrator|Representative|Accountant))', line.strip(), re.I)
                    if title_match:
                        current_role = title_match.group(1).strip()
                        break
        if current_role:
            break

    # Education - find degree patterns
    education = ''
    edu_patterns = [
        r'(B\.?Tech|M\.?Tech|B\.?E\.?|M\.?E\.?|B\.?Com|M\.?Com|B\.?Sc|M\.?Sc|BCA|MCA|BBA|MBA|B\.?A\.?|M\.?A\.?|PhD|Ph\.?D\.?|Bachelor|Master)',
        r'(Bachelor\s+of\s+[A-Za-z\s]{3,30})',
        r'(Master\s+of\s+[A-Za-z\s]{3,30})'
    ]
    for pattern in edu_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            education = match.group(1).strip()
            break

    # Location - look for labeled location or common patterns
    location = ''
    loc_patterns = [
        r'(?:Location|Address|City|Based in|residing)\s*[:\-]\s*([A-Za-z][A-Za-z\s,]{2,30})',
        r'(?:^|\n)\s*([A-Z][a-z]+(?:,\s*[A-Z][a-z]+)?)\s*(?:\n|$)'  # City on its own line
    ]
    for pattern in loc_patterns:
        match = re.search(pattern, resume_text, re.I)
        if match:
            loc = match.group(1).strip().split('\n')[0].split(',')[0].strip()
            # Validate it looks like a city (not a section header)
            if 2 < len(loc) < 25 and not re.match(r'^(Summary|Experience|Education|Skills|Projects|Contact|Profile)', loc, re.I):
                location = loc
                break

    # Extract skills dynamically
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
    """Extract skills dynamically from resume text using intelligent patterns"""
    text_lower = text.lower()
    skills = set()

    # Look for explicit skills section
    skills_section = ""
    skills_match = re.search(r'(?:skills|technical\s+skills|core\s+competencies|expertise|technologies)[:\s]*\n?([\s\S]{50,800}?)(?:\n\s*\n|\n[A-Z]|$)', text, re.I)
    if skills_match:
        skills_section = skills_match.group(1)

    # Extract from skills section if found
    if skills_section:
        # Split by common delimiters and extract
        potential_skills = re.split(r'[,;•|\n\-]+', skills_section)
        for skill in potential_skills:
            skill = skill.strip()
            # Valid skill: 2-40 chars, not just numbers, not a sentence
            if 2 <= len(skill) <= 40 and not skill.isdigit():
                # Skip if looks like a sentence (too many words)
                if len(skill.split()) <= 4:
                    skills.add(format_skill(skill))

    # Also look for common skill patterns in entire text
    # Technical terms often follow patterns like "proficient in X", "experience with X", "knowledge of X"
    skill_context_patterns = [
        r'(?:proficient|experienced|skilled|expertise|knowledge|familiar)\s+(?:in|with)\s+([A-Za-z0-9\s\+\#\.]{2,30})',
        r'(?:worked|working)\s+(?:on|with)\s+([A-Za-z0-9\s\+\#\.]{2,30})',
        r'(?:using|used)\s+([A-Za-z0-9\s\+\#\.]{2,30})',
    ]

    for pattern in skill_context_patterns:
        matches = re.findall(pattern, text, re.I)
        for match in matches:
            skill = match.strip()
            if 2 <= len(skill) <= 30 and len(skill.split()) <= 3:
                skills.add(format_skill(skill))

    # Look for capitalized technical terms (often tools/technologies)
    tech_terms = re.findall(r'\b([A-Z][a-zA-Z0-9]*(?:\.[a-zA-Z]+)?)\b', text)
    common_words = {'the', 'and', 'for', 'with', 'this', 'that', 'from', 'have', 'been', 'were', 'are', 'was', 'will', 'can', 'may', 'should', 'would', 'could', 'their', 'your', 'our', 'his', 'her', 'its'}
    for term in tech_terms:
        if len(term) >= 2 and term.lower() not in common_words:
            # Check if it appears multiple times (likely a skill/tool)
            if text_lower.count(term.lower()) >= 2:
                skills.add(format_skill(term))

    return list(skills)[:20]

def format_skill(skill):
    """Format skill name with proper capitalization"""
    skill = skill.strip()
    if not skill:
        return skill

    # Common abbreviations that should be uppercase
    upper_terms = ['sql', 'aws', 'gcp', 'css', 'html', 'php', 'api', 'etl', 'qa', 'hr', 'ai', 'ml', 'nlp', 'xml', 'json', 'sap', 'erp', 'crm', 'ui', 'ux', 'it', 'bi', 'ci', 'cd']

    skill_lower = skill.lower()
    if skill_lower in upper_terms:
        return skill.upper()

    # If already has mixed case, preserve it
    if skill != skill.lower() and skill != skill.upper():
        return skill

    # Otherwise title case
    return skill.title()

def analyze_match_with_ai(resume_data, job_text):
    """Use AI to match resume skills against job description with accurate scoring"""

    skills_str = ', '.join(resume_data.get('skills', [])[:25])

    prompt = f"""You are an expert recruiter. Analyze how well this candidate matches the job requirements.

JOB DESCRIPTION:
{job_text[:1500]}

CANDIDATE PROFILE:
- Name: {resume_data.get('name')}
- Total Experience: {resume_data.get('experience_years', 0)} years
- Current Role: {resume_data.get('current_role')}
- Education: {resume_data.get('education')}
- Skills: {skills_str}

SCORING CRITERIA:
1. Extract key requirements from the job description (skills, experience, qualifications)
2. Check which requirements the candidate meets (matched_skills)
3. Check which requirements the candidate lacks (missing_skills)
4. Calculate a score 0-100 based on:
   - Skill match percentage (40% weight)
   - Experience relevance (30% weight)
   - Role/domain match (20% weight)
   - Education fit (10% weight)

5. Recommendation based on score:
   - "Best": 80-100 (excellent match, should interview)
   - "Good": 65-79 (strong candidate, worth considering)
   - "Average": 50-64 (partial match, review carefully)
   - "Poor": 0-49 (significant gaps, likely not suitable)

Return ONLY valid JSON (no markdown, no explanation):
{{
  "score": number,
  "matched_skills": ["requirement1 the candidate has", "requirement2 the candidate has"],
  "missing_skills": ["requirement1 the candidate lacks", "requirement2 the candidate lacks"],
  "recommendation": "Best" or "Good" or "Average" or "Poor"
}}"""

    response = call_ai_api([
        {"role": "system", "content": "You are a precise recruiter AI. Analyze job fit accurately. Return only valid JSON with realistic scores based on actual skill matches."},
        {"role": "user", "content": prompt}
    ], max_tokens=600)

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
