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

# AI API Configuration - supports Groq (free), Grok (xAI), or OpenAI
# Available Groq models (2024): llama-3.1-8b-instant, llama-3.1-70b-versatile, mixtral-8x7b-32768
GROQ_MODELS = ['llama-3.1-8b-instant', 'llama-3.1-70b-versatile', 'mixtral-8x7b-32768']
CURRENT_MODEL_INDEX = 0

def get_ai_config():
    global CURRENT_MODEL_INDEX

    # Try Groq first (FREE)
    groq_key = os.environ.get('GROQ_API_KEY', '')
    if groq_key:
        model = GROQ_MODELS[CURRENT_MODEL_INDEX % len(GROQ_MODELS)]
        return {
            'provider': 'groq',
            'api_key': groq_key,
            'base_url': 'https://api.groq.com/openai/v1/chat/completions',
            'model': model
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

def try_next_model():
    """Switch to next model if current one fails"""
    global CURRENT_MODEL_INDEX
    CURRENT_MODEL_INDEX = (CURRENT_MODEL_INDEX + 1) % len(GROQ_MODELS)
    print(f"Switching to model: {GROQ_MODELS[CURRENT_MODEL_INDEX]}")

def call_ai_api(messages, max_tokens=800, retry_count=0):
    config = get_ai_config()
    if not config:
        print("AI API: No configuration found - no API keys set")
        return None

    print(f"AI API: Calling {config['provider']} with model {config['model']}")

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
            content = result['choices'][0]['message']['content'].strip()
            print(f"AI API: Success - received {len(content)} chars")
            return content

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else 'No details'
        print(f"AI API HTTP Error ({config['provider']}): {e.code} - {e.reason}")
        print(f"AI API Error details: {error_body[:500]}")

        # If model not found or rate limited, try next model
        if e.code in [404, 429, 503] and config['provider'] == 'groq' and retry_count < len(GROQ_MODELS):
            try_next_model()
            print(f"Retrying with next model (attempt {retry_count + 1})")
            return call_ai_api(messages, max_tokens, retry_count + 1)
        return None
    except urllib.error.URLError as e:
        print(f"AI API URL Error ({config['provider']}): {e.reason}")
        return None
    except Exception as e:
        print(f"AI API Error ({config['provider']}): {type(e).__name__}: {e}")
        return None

def extract_resume_with_ai(resume_text, job_description=""):
    """Use AI to extract structured data from resume - handles any format"""
    print(f"extract_resume_with_ai: Starting extraction, text length={len(resume_text)}")

    # Clean the resume text but preserve some structure
    clean_text = resume_text.replace('\x00', '')
    # Keep newlines for structure but normalize spaces
    clean_text = re.sub(r'[ \t]+', ' ', clean_text)
    clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)

    # Add job context for skill extraction
    jd_context = f"\n\nJob being applied for: {job_description[:300]}" if job_description else ""

    prompt = f"""Extract information from this resume. Return a JSON object.

RESUME:
{clean_text[:7000]}{jd_context}

Extract these fields:
- name: Person's full name (at the top of resume)
- email: Email address
- phone: Phone number
- location: City where they live
- experience_years: Total work experience in years (number)
- current_role: Their current/most recent JOB TITLE. Look in "Work Experience" or "Employment" section. Find the FIRST listed position - extract ONLY the title like "HR Executive", "Software Engineer", "Data Analyst", "Recruitment Specialist". NOT the job description.
- current_company: Company name of current/recent job
- education: Highest degree (B.Tech, MBA, etc.)
- skills: Array of ALL skills mentioned (minimum 10 skills)

Return ONLY JSON, no other text:
{{"name":"","email":"","phone":"","location":"","experience_years":0,"current_role":"","current_company":"","education":"","skills":[]}}"""

    response = call_ai_api([
        {"role": "system", "content": "Extract resume data. Return only valid JSON. For current_role, find the job title in Work Experience section - the title of their current/most recent job. Never return job descriptions."},
        {"role": "user", "content": prompt}
    ], max_tokens=2000)

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
    print(f"analyze_match_with_ai: Matching candidate {resume_data.get('name')} with {len(resume_data.get('skills', []))} skills")

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
            result = json.loads(content)
            print(f"analyze_match_with_ai: AI returned score={result.get('score')}, recommendation={result.get('recommendation')}")
            return result
        except Exception as e:
            print(f"analyze_match_with_ai: JSON parsing failed: {e}")
            print(f"Response was: {response[:300] if response else 'None'}")

    # Fallback: basic matching without AI
    print("analyze_match_with_ai: Falling back to basic matching")
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

    # Fallback: Use extracted data for basic matching - no hardcoded lists
    print("AI scoring failed - using basic skill matching")
    job_lower = job_text.lower()
    resume_skills = resume_data.get('skills', [])

    matched = []
    missing = []

    # Simple text matching - check if each resume skill appears in job description
    for skill in resume_skills:
        skill_lower = skill.lower()
        if skill_lower in job_lower or any(word in job_lower for word in skill_lower.split() if len(word) > 3):
            matched.append(skill)

    # Calculate score dynamically based on data available
    skill_count = len(resume_skills)
    matched_count = len(matched)
    exp = resume_data.get('experience_years', 0)

    # Dynamic scoring based on available data
    if skill_count > 0:
        match_ratio = matched_count / skill_count
        base_score = int(match_ratio * 60) + 20  # 20-80 range based on skill match
    else:
        base_score = 30  # Low score when no skills extracted

    # Adjust for experience
    if exp >= 5:
        base_score += 15
    elif exp >= 2:
        base_score += 10
    elif exp > 0:
        base_score += 5

    total_score = min(95, max(20, base_score))

    if total_score >= 80:
        recommendation = "Best"
    elif total_score >= 65:
        recommendation = "Good"
    elif total_score >= 50:
        recommendation = "Average"
    else:
        recommendation = "Poor"

    print(f"Basic scoring: matched={matched_count}/{skill_count}, exp={exp}, score={total_score}")

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

        # Try server-side PDF extraction if base64 PDF data is provided
        pdf_base64 = c.get("pdfData", "")
        if pdf_base64 and PDF_LIBRARY:
            try:
                pdf_bytes = base64.b64decode(pdf_base64)
                extracted_text = extract_text_from_pdf_bytes(pdf_bytes)
                if extracted_text and len(extracted_text) > 50:
                    print(f"Server-side PDF extraction successful: {len(extracted_text)} chars")
                    resume_text = extracted_text
            except Exception as e:
                print(f"Server PDF extraction failed: {e}")

        if not resume_text or len(resume_text.strip()) < 50:
            continue  # Skip empty or too short resumes

        # Extract with AI
        extracted = extract_resume_with_ai(resume_text, job_text)

        # Merge frontend data with AI extraction
        # For name: prefer frontend extraction if AI returns empty/Unknown
        ai_name = extracted.get("name", "")
        frontend_name = c.get("name", "")
        if ai_name and ai_name != "Unknown" and len(ai_name) > 2:
            name = validate_and_clean(ai_name)
        elif frontend_name and frontend_name != "Unknown" and len(frontend_name) > 2:
            name = validate_and_clean(frontend_name)
        else:
            # Last resort: try to find name from resume text
            name = "Unknown"
            resume_lines = resume_text.split('\n')
            for line in resume_lines[:15]:
                line = line.strip()
                if line and 3 < len(line) < 40:
                    if not re.search(r'@|http|www\.|phone|email|resume|cv|profile|summary|objective|experience|education|skills|\d{5,}', line, re.I):
                        words = line.split()
                        if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
                            name = line
                            break

        # For other fields: prefer AI data, fall back to frontend
        email = validate_and_clean(extracted.get("email") or c.get("email"))
        phone = validate_and_clean(extracted.get("phone") or c.get("phone"))
        location = validate_and_clean(extracted.get("location") or c.get("location"))
        experience = validate_and_clean(extracted.get("experience_years") or c.get("experience") or 0, "number")

        # For current role: prefer AI, then frontend, then try to extract
        ai_role = extracted.get("current_role", "")
        frontend_role = c.get("currentRole", "")
        if ai_role and len(ai_role) > 2:
            current_role = validate_and_clean(ai_role)
        elif frontend_role and len(frontend_role) > 2:
            current_role = validate_and_clean(frontend_role)
        else:
            current_role = ""

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

@app.route('/api/test-ai', methods=['GET', 'OPTIONS'])
def test_ai():
    """Test endpoint to verify AI API is working"""
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    config = get_ai_config()
    if not config:
        response = jsonify({
            "success": False,
            "error": "No AI API key configured",
            "hint": "Set GROQ_API_KEY in Vercel environment variables"
        })
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    # Test with a simple prompt
    test_response = call_ai_api([
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Reply with exactly: AI_TEST_OK"}
    ], max_tokens=20)

    if test_response and 'AI_TEST_OK' in test_response:
        response = jsonify({
            "success": True,
            "provider": config['provider'],
            "model": config['model'],
            "message": "AI API is working correctly"
        })
    else:
        response = jsonify({
            "success": False,
            "provider": config['provider'],
            "model": config['model'],
            "response": test_response,
            "error": "AI API responded but not as expected"
        })

    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

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
