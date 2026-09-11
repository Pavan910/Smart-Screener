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
    # Try Groq first (FREE) - using mixtral for reliable performance
    groq_key = os.environ.get('GROQ_API_KEY', '')
    if groq_key:
        return {
            'provider': 'groq',
            'api_key': groq_key,
            'base_url': 'https://api.groq.com/openai/v1/chat/completions',
            'model': 'mixtral-8x7b-32768'
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

    # Clean the resume text - handle PDF extraction issues
    clean_text = resume_text.replace('\x00', '').strip()
    # Normalize whitespace
    clean_text = re.sub(r'\s+', ' ', clean_text)
    # Try to preserve line breaks for structure
    resume_lines = resume_text.split('\n')
    first_lines = '\n'.join([l.strip() for l in resume_lines[:20] if l.strip()])

    jd_context = f"\nJOB DESCRIPTION (use this to identify relevant skills):\n{job_description[:800]}\n" if job_description else ""

    prompt = f"""Parse this resume and extract candidate information. The text may have formatting issues from PDF extraction.

FIRST 20 LINES (check here for NAME):
{first_lines}

FULL RESUME TEXT:
{clean_text[:4500]}
{jd_context}
EXTRACTION INSTRUCTIONS:
1. NAME: The person's full name (first + last). Usually the FIRST prominent text. Look for 2-3 capitalized words at the top that form a name. NEVER return "Unknown" - find the actual name.

2. EMAIL: Email address from the resume

3. PHONE: Phone number with country code

4. LOCATION: City where the person is located

5. EXPERIENCE: Total years of work experience (as number)

6. CURRENT ROLE: Their CURRENT or MOST RECENT job title. Must be a proper title like:
   - "HR Executive", "Software Engineer", "Data Analyst", "Recruitment Specialist"
   - Look in Work Experience section for the first/most recent position
   - Extract the TITLE, not the job description

7. CURRENT COMPANY: Name of current/most recent employer

8. EDUCATION: Highest degree (e.g., B.Tech, MBA, B.Com)

9. SKILLS: List ALL skills found in the resume - technical, soft skills, tools, software, certifications. Extract 8-15 skills minimum.

Return ONLY this JSON (no other text):
{{"name":"","email":"","phone":"","location":"","experience_years":0,"current_role":"","current_company":"","education":"","skills":[]}}"""

    response = call_ai_api([
        {"role": "system", "content": "Extract resume data accurately. Return valid JSON only. For name, find the actual person's name at the top of the resume. For current_role, extract the job title not description. For skills, list actual skills not action verbs."},
        {"role": "user", "content": prompt}
    ], max_tokens=1200)

    if response:
        try:
            content = response.strip()
            # Remove markdown code blocks if present
            content = re.sub(r'^```json?\s*\n?', '', content)
            content = re.sub(r'\n?\s*```\s*$', '', content)
            # Try to find JSON object in the response
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content)
            if json_match:
                content = json_match.group(0)
            parsed = json.loads(content)

            # Ensure name is not empty
            if not parsed.get('name') or parsed.get('name') == 'Unknown':
                # Try to find name from first lines
                lines = resume_text.split('\n')
                for line in lines[:10]:
                    line = line.strip()
                    if line and len(line) < 40 and not re.search(r'@|http|www\.|phone|email|resume|cv|profile|\d{5,}', line, re.I):
                        words = line.split()
                        if 2 <= len(words) <= 4 and all(w[0].isupper() if w else False for w in words):
                            parsed['name'] = line
                            break

            # Clean current_role
            if parsed.get('current_role'):
                role = parsed['current_role']
                if len(role) > 50:
                    role = re.split(r'[,\-–|]', role)[0].strip()
                parsed['current_role'] = role

            # Clean skills - remove action verbs
            if parsed.get('skills') and isinstance(parsed['skills'], list):
                action_verbs = {'maintain', 'maintained', 'maintaining', 'manage', 'managed', 'managing',
                               'develop', 'developed', 'developing', 'handle', 'handled', 'handling',
                               'support', 'supported', 'supporting', 'work', 'worked', 'working',
                               'create', 'created', 'creating', 'build', 'built', 'building',
                               'ensure', 'ensured', 'ensuring', 'responsible', 'responsibilities'}
                cleaned_skills = []
                for skill in parsed['skills']:
                    if isinstance(skill, str):
                        skill_lower = skill.lower().strip()
                        if skill_lower not in action_verbs and len(skill) >= 2:
                            cleaned_skills.append(skill)
                parsed['skills'] = cleaned_skills[:20]

            print(f"AI extracted: name={parsed.get('name')}, role={parsed.get('current_role')}, skills={len(parsed.get('skills', []))}")
            return parsed
        except Exception as e:
            print(f"AI response parsing error: {e}")
            print(f"Response was: {response[:500] if response else 'None'}")

    # Fallback to basic extraction if AI fails
    print("AI extraction failed, using basic extraction")
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

    # Current role - try AI extraction first, then pattern matching
    current_role = ''

    # Try AI to extract current role
    config = get_ai_config()
    if config:
        role_prompt = f"""What is the CURRENT or MOST RECENT job title of this candidate?

Look in the Work Experience section for the first/most recent position.
Return ONLY the job title (e.g., "HR Executive", "Software Engineer", "Data Analyst").
Do NOT return job descriptions or responsibilities.

Resume text:
{resume_text[:3000]}

Return ONLY the job title, nothing else:"""

        role_response = call_ai_api([
            {"role": "system", "content": "Extract the current job title from resumes. Return only the title."},
            {"role": "user", "content": role_prompt}
        ], max_tokens=50)

        if role_response:
            role = role_response.strip().strip('"').strip("'")
            # Basic validation
            if 3 < len(role) < 60 and not role.startswith(('I ', 'The ', 'This ')):
                current_role = role

    # Fallback to pattern matching if AI failed
    if not current_role:
        in_work_section = False
        for line in lines[:50]:
            line_clean = line.strip()
            line_lower = line_clean.lower()

            # Detect work experience section
            if re.match(r'^(work\s*experience|professional\s*experience|employment|career)', line_lower):
                in_work_section = True
                continue

            # Exit work section on other headers
            if re.match(r'^(education|skills|certifications|projects|achievements|summary)', line_lower):
                if in_work_section and current_role:
                    break
                in_work_section = False
                continue

            if in_work_section and not current_role:
                if not line_clean or line_clean.startswith('•') or line_clean.startswith('-'):
                    continue

                # Look for role with date pattern: "HR Executive | Jan 2020 - Present"
                role_date_match = re.match(r'^([A-Za-z][A-Za-z\s\-]+)\s*[|–\-]\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4}|Present)', line_clean, re.I)
                if role_date_match:
                    potential_role = role_date_match.group(1).strip()
                    if len(potential_role) > 3 and len(potential_role) < 50:
                        current_role = potential_role
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

def extract_skills_with_ai(text):
    """Use AI to extract skills from resume text"""
    prompt = f"""Extract ALL skills mentioned in this resume text. Include:
- Technical skills (programming languages, tools, software, frameworks)
- Domain skills (HR, Finance, Marketing, etc.)
- Professional skills (communication, leadership, etc.)
- Software proficiency (Excel, SAP, etc.)

Return ONLY a JSON array of skill names. Example: ["Python", "Excel", "Communication", "HR Management"]

Resume text:
{text[:4000]}

Return ONLY the JSON array, nothing else:"""

    response = call_ai_api([
        {"role": "system", "content": "Extract skills from resumes. Return only a JSON array of skill names."},
        {"role": "user", "content": prompt}
    ], max_tokens=500)

    if response:
        try:
            content = response.strip()
            if content.startswith('```'):
                content = re.sub(r'^```json?\s*\n?', '', content)
                content = re.sub(r'\n?\s*```$', '', content)
            # Find JSON array in response
            array_match = re.search(r'\[[\s\S]*\]', content)
            if array_match:
                skills = json.loads(array_match.group(0))
                if isinstance(skills, list):
                    return [s for s in skills if isinstance(s, str) and len(s) >= 2][:20]
        except:
            pass
    return []

def extract_skills_from_text(text):
    """Extract skills from resume - tries AI first, then simple extraction"""
    # Try AI extraction first
    config = get_ai_config()
    if config:
        skills = extract_skills_with_ai(text)
        if skills:
            return skills

    # Simple fallback: extract from skills section only (no hardcoded lists)
    skills = set()
    skills_match = re.search(r'(?:skills|technical\s+skills|competencies|expertise)[:\s]*\n?([\s\S]{30,1000}?)(?:\n\s*\n|$)', text, re.I)

    if skills_match:
        section = skills_match.group(1)
        # Split by common delimiters
        items = re.split(r'[,;•|/\n\-]+', section)
        for item in items:
            item = item.strip()
            # Basic validation: 2-40 chars, max 4 words, not a number
            if 2 <= len(item) <= 40 and len(item.split()) <= 4 and not item.isdigit():
                skills.add(format_skill(item))

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
    """Skill matching - uses AI when available for better accuracy"""

    # Try AI-based matching first
    config = get_ai_config()
    if config:
        skills_str = ', '.join(resume_data.get('skills', [])[:25])
        match_prompt = f"""Compare this candidate's skills against the job requirements.

JOB DESCRIPTION:
{job_text[:1500]}

CANDIDATE SKILLS:
{skills_str}

CANDIDATE EXPERIENCE: {resume_data.get('experience_years', 0)} years
CANDIDATE CURRENT ROLE: {resume_data.get('current_role', 'Not specified')}

Analyze the match and return a JSON with:
1. matched_skills: Skills the candidate has that match job requirements
2. missing_skills: Key job requirements the candidate lacks
3. score: Overall match score 0-100 based on skill match, experience fit, and role relevance
4. recommendation: "Best" (80-100), "Good" (65-79), "Average" (50-64), or "Poor" (0-49)

Return ONLY valid JSON:
{{"matched_skills": [], "missing_skills": [], "score": 0, "recommendation": ""}}"""

        response = call_ai_api([
            {"role": "system", "content": "Analyze job fit accurately. Return only valid JSON."},
            {"role": "user", "content": match_prompt}
        ], max_tokens=500)

        if response:
            try:
                content = response.strip()
                if content.startswith('```'):
                    content = re.sub(r'^```json?\s*\n?', '', content)
                    content = re.sub(r'\n?\s*```$', '', content)
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    result = json.loads(json_match.group(0))
                    if 'score' in result:
                        return result
            except:
                pass

    # Fallback: Simple text-based matching (no hardcoded lists)
    job_lower = job_text.lower()
    resume_skills = [s.lower() for s in resume_data.get('skills', [])]

    # Extract skills from job description using AI
    job_skills = extract_skills_from_text(job_text)

    matched = []
    missing = []

    for skill in job_skills:
        skill_lower = skill.lower()
        found = any(skill_lower in rs or rs in skill_lower for rs in resume_skills)
        if found:
            matched.append(skill)
        else:
            missing.append(skill)

    # Calculate score based on matches
    if len(job_skills) > 0:
        skill_score = int((len(matched) / len(job_skills)) * 60)
    else:
        skill_score = 40  # Default when no job skills extracted

    # Experience contribution
    exp = resume_data.get('experience_years', 0)
    exp_score = min(25, exp * 4) if exp > 0 else 5

    # Role match contribution
    role_score = 10
    current_role = resume_data.get('current_role', '').lower()
    if current_role and len(current_role) > 3:
        # Check if any word from role appears in job
        role_words = [w for w in current_role.split() if len(w) > 3]
        if any(w in job_lower for w in role_words):
            role_score = 20

    total_score = min(95, max(40, skill_score + exp_score + role_score))

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

def validate_and_clean(value, field_type="text"):
    """Validate and clean extracted data"""
    if not value:
        return "" if field_type == "text" else 0

    if field_type == "text":
        value = str(value).strip()
        # Remove common prefixes/suffixes that shouldn't be in data
        value = re.sub(r'^[\-•*:,\s]+|[\-•*:,\s]+$', '', value)
        return value
    elif field_type == "number":
        try:
            return int(value)
        except:
            return 0
    return value

def analyze_resumes(job_text, candidates):
    """Analyze resumes against job description using AI"""
    ranking = []
    config = get_ai_config()

    for c in candidates:
        resume_text = c.get("resume", "")

        if not resume_text or len(resume_text.strip()) < 50:
            continue  # Skip empty or too short resumes

        # Extract with AI
        extracted = extract_resume_with_ai(resume_text, job_text)

        # Merge frontend data with AI extraction - prefer AI data when available
        name = validate_and_clean(extracted.get("name") or c.get("name") or "Unknown")
        email = validate_and_clean(extracted.get("email") or c.get("email"))
        phone = validate_and_clean(extracted.get("phone") or c.get("phone"))
        location = validate_and_clean(extracted.get("location") or c.get("location"))
        experience = validate_and_clean(extracted.get("experience_years") or c.get("experience") or 0, "number")
        current_role = validate_and_clean(extracted.get("current_role") or c.get("currentRole"))
        current_company = validate_and_clean(extracted.get("current_company") or c.get("currentCompany"))
        education = validate_and_clean(extracted.get("education") or c.get("education"))
        skills = extracted.get("skills") or []

        # Clean skills list
        if skills:
            skills = [validate_and_clean(s) for s in skills if s and len(str(s).strip()) >= 2]

        # Match against job description
        match_result = analyze_match_with_ai({
            "name": name,
            "experience_years": experience,
            "current_role": current_role,
            "skills": skills,
            "education": education
        }, job_text)

        # Get matched and missing skills
        matched_skills = match_result.get("matched_skills", skills[:10])
        missing_skills = match_result.get("missing_skills", [])
        score = match_result.get("score", 50)
        recommendation = match_result.get("recommendation", "Review")

        # Ensure score is valid
        if not isinstance(score, (int, float)):
            try:
                score = int(score)
            except:
                score = 50
        score = max(0, min(100, score))

        ranking.append({
            "name": name,
            "email": email,
            "phone": phone,
            "location": location,
            "experience": experience,
            "currentRole": current_role,
            "currentCompany": current_company,
            "education": education,
            "skills": matched_skills if matched_skills else skills[:10],
            "coveredSkills": matched_skills,
            "missingSkills": missing_skills,
            "score": score,
            "recommendation": recommendation,
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
