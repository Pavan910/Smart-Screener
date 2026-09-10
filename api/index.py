from flask import Flask, request, jsonify, make_response
import re
import os
import hashlib

app = Flask(__name__)

# Authentication - Password stored in Vercel environment variable
def get_password():
    return os.environ.get('APP_PASSWORD', '')

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Common words to ignore when extracting keywords
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "as", "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "must",
    "shall", "can", "need", "dare", "ought", "used", "it", "its", "this", "that", "these",
    "those", "i", "you", "he", "she", "we", "they", "what", "which", "who", "whom", "whose",
    "where", "when", "why", "how", "all", "each", "every", "both", "few", "more", "most",
    "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
    "very", "just", "also", "now", "here", "there", "then", "once", "if", "any", "about",
    "into", "through", "during", "before", "after", "above", "below", "between", "under",
    "over", "out", "up", "down", "off", "again", "further", "able", "our", "your", "their",
    "etc", "including", "work", "working", "experience", "years", "year", "strong", "good",
    "excellent", "preferred", "required", "requirements", "responsibilities", "role", "position",
    "job", "candidate", "looking", "seeking", "must", "ability", "skills", "skill"
}

def normalize_text(text):
    return re.sub(r"[^a-z0-9\s-]", " ", text.lower())

def extract_keywords_from_text(text, min_length=3):
    """Extract meaningful keywords from any text (job description or resume)"""
    normalized = normalize_text(text)
    words = re.findall(r'\b[a-z][a-z0-9+#.-]*\b', normalized)

    # Filter out stop words and short words
    keywords = []
    for word in words:
        if len(word) >= min_length and word not in STOP_WORDS:
            keywords.append(word)

    # Also extract multi-word phrases (2-3 words)
    phrases = re.findall(r'\b([a-z]+\s+[a-z]+(?:\s+[a-z]+)?)\b', normalized)
    for phrase in phrases:
        words_in_phrase = phrase.split()
        # Keep phrase if it's not all stop words
        if not all(w in STOP_WORDS for w in words_in_phrase):
            keywords.append(phrase.replace(' ', '_'))

    return list(set(keywords))

def extract_name_from_resume(text):
    """Extract candidate name from resume text - usually at the top"""
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    for i, line in enumerate(lines[:5]):
        # Skip common headers
        if re.match(r'^(resume|curriculum|cv|profile|summary|objective|contact|address|phone|email|linkedin)', line, re.I):
            continue
        # Skip emails, URLs, phone numbers
        if re.search(r'@|http|www\.|\.com|\.org|\.net', line, re.I):
            continue
        if re.match(r'^\+?\d[\d\s\-().]{8,}', line):
            continue
        if len(line) > 50 or len(line) < 3:
            continue

        # Check for name pattern (2-4 capitalized words)
        match = re.match(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})$', line)
        if match:
            return match.group(1)

        # First line with 2-4 capitalized words
        if i == 0:
            words = line.split()
            if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
                return line

    return None

def extract_email_from_resume(text):
    """Extract email from resume text"""
    match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    return match.group(0) if match else ''

def extract_phone_from_resume(text):
    """Extract phone from resume text"""
    patterns = [
        r'(?:\+91[\s-]?)?[6-9]\d{9}',  # Indian mobile
        r'(?:\+1[\s-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}',  # US format
        r'\+\d{1,3}[\s-]?\d{6,14}'  # International
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return re.sub(r'\s+', '', match.group(0))
    return ''

def extract_experience_from_resume(text):
    """Extract years of experience from resume text"""
    patterns = [
        r'(\d+)\+?\s*(?:years?|yrs?)[\s\w]*(?:of\s+)?(?:experience|exp|in)',
        r'(?:experience|exp)[\s:]*(\d+)\+?\s*(?:years?|yrs?)',
        r'(?:total|overall)[\s\w]*(\d+)\+?\s*(?:years?|yrs?)'
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return int(match.group(1))
    return 0

def analyze_resumes(job_text, candidates):
    """
    Analyze resumes against job description using dynamic keyword matching.
    Works for ANY type of job - technical, non-technical, or mixed.
    """
    # Extract keywords from job description
    job_keywords = extract_keywords_from_text(job_text)

    ranking = []
    for c in candidates:
        resume_text = c.get("resume", "")
        normalized_resume = normalize_text(resume_text)

        # Extract keywords from resume
        resume_keywords = extract_keywords_from_text(resume_text)

        # Find matching keywords between job and resume
        matched_keywords = []
        missing_keywords = []

        for keyword in job_keywords:
            # Check both exact match and word presence
            keyword_clean = keyword.replace('_', ' ')
            if keyword in resume_keywords or keyword_clean in normalized_resume:
                matched_keywords.append(keyword_clean)
            else:
                missing_keywords.append(keyword_clean)

        # Calculate match percentage
        total_job_keywords = len(job_keywords) if job_keywords else 1
        match_percentage = len(matched_keywords) / total_job_keywords

        # Score breakdown:
        # - Keyword match: up to 70 points (main factor)
        # - Experience bonus: up to 15 points
        # - Content length/depth: up to 15 points

        keyword_score = round(match_percentage * 70)

        exp = c.get("experience") or 0
        exp_score = min(15, exp * 2) if exp > 0 else 0

        # Content depth score (longer, more detailed resumes score slightly higher)
        content_length = len(resume_text)
        depth_score = min(15, content_length // 500)  # 1 point per 500 chars, max 15

        total_score = min(100, max(0, keyword_score + exp_score + depth_score))

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
            "skills": matched_keywords[:10],  # Top 10 matched skills
            "coveredSkills": matched_keywords,
            "missingSkills": missing_keywords[:10],  # Top 10 missing
            "score": total_score,
            "matchPercentage": round(match_percentage * 100),
            "resumeText": resume_text[:180],
            "analyzedBy": "dynamic-keyword-matching"
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

    # Handle GET - API info endpoint
    if request.method == 'GET':
        response = jsonify({
            "api": "Smart Screener",
            "version": "1.0",
            "message": "Use POST to analyze resumes"
        })
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
        job_text = data.get("jobDescription") or ""
        uploaded = data.get("resumes") or []

        # Validate inputs
        if not job_text:
            response = jsonify({"error": "Job description is required", "ranking": []})
            response.status_code = 400
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response

        if not uploaded:
            response = jsonify({"error": "No resumes provided", "ranking": []})
            response.status_code = 400
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response

        # Process uploaded resumes
        candidates = []
        for i, item in enumerate(uploaded):
            if isinstance(item, dict):
                resume_text = item.get("resume") or item.get("text") or item.get("content") or ""

                # Use frontend extraction, but fallback to server-side extraction
                name = item.get("name") or extract_name_from_resume(resume_text) or f"Candidate {i+1}"
                email = item.get("email") or extract_email_from_resume(resume_text)
                phone = item.get("phone") or extract_phone_from_resume(resume_text)
                experience = item.get("experience") or extract_experience_from_resume(resume_text)

                candidates.append({
                    "name": name,
                    "title": item.get("currentRole") or item.get("title") or "",
                    "experience": experience,
                    "email": email,
                    "phone": phone,
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
                    "name": extract_name_from_resume(resume_text) or f"Candidate {i+1}",
                    "title": "",
                    "experience": extract_experience_from_resume(resume_text),
                    "email": extract_email_from_resume(resume_text),
                    "phone": extract_phone_from_resume(resume_text),
                    "skills": [],
                    "resume": resume_text
                })

        ranking = analyze_resumes(job_text, candidates)
        response = jsonify({
            "ranking": ranking,
            "jobDescription": job_text,
            "candidateCount": len(ranking),
            "bestCandidate": ranking[0] if ranking else None
        })
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
