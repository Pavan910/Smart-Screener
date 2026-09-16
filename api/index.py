"""
Smart-Screener API v5.0
Main Flask application - refactored to use modular architecture.

This is the entry point for the Vercel serverless deployment.
"""

from flask import Flask, request, jsonify, make_response
import os
import hashlib
import base64
import time
from typing import List, Dict, Any, Optional

# PDF Library
try:
    import fitz
    PDF_LIBRARY = 'pymupdf'
except ImportError:
    PDF_LIBRARY = None

# Import our modules - handle both local and Vercel deployment
try:
    # Try relative imports first (when running as package)
    from .models import AnalyzedCandidate, AnalysisMetadata
    from .utils import get_ai_config, clean_text
    from .jd_parser import parse_job_description
    from .resume_parser import parse_resume, parse_resumes_batch
    from .matching_engine import calculate_match, rank_candidates
    from .report_generator import generate_report
except ImportError:
    # Fall back to absolute imports (for Vercel serverless)
    from models import AnalyzedCandidate, AnalysisMetadata
    from utils import get_ai_config, clean_text
    from jd_parser import parse_job_description
    from resume_parser import parse_resume, parse_resumes_batch
    from matching_engine import calculate_match, rank_candidates
    from report_generator import generate_report

app = Flask(__name__)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> Optional[str]:
    """Extract text from PDF bytes using PyMuPDF."""
    if PDF_LIBRARY != 'pymupdf':
        return None

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
        return text.strip() if text else None
    except Exception as e:
        print(f"[PDF] Extraction error: {e}")
        return None


def get_password() -> str:
    """Get app password from environment."""
    return os.environ.get('APP_PASSWORD', '')


def hash_password(password: str) -> str:
    """Hash password for session token."""
    return hashlib.sha256(password.encode()).hexdigest()


def add_cors_headers(response):
    """Add CORS headers to response."""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


# ============================================================================
# MAIN ANALYSIS FUNCTION
# ============================================================================

def analyze_candidates(
    job_description: str,
    resume_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Main analysis function - processes JD and resumes through the new pipeline.

    Args:
        job_description: Raw job description text
        resume_data: List of resume data dicts from frontend

    Returns:
        Analysis results with rankings and reports
    """
    start_time = time.time()
    metadata = AnalysisMetadata()

    # -------------------------------------------------------------------------
    # STEP 1: Parse Job Description
    # -------------------------------------------------------------------------
    print("[Analysis] Step 1: Parsing job description...")
    jd_requirements = parse_job_description(job_description)
    print(f"[Analysis] JD parsed: {len(jd_requirements.required_skills)} required, "
          f"{len(jd_requirements.preferred_skills)} preferred skills")
    metadata.ai_calls_made += 1

    # -------------------------------------------------------------------------
    # STEP 2: Prepare Resumes
    # -------------------------------------------------------------------------
    print(f"[Analysis] Step 2: Processing {len(resume_data)} resumes...")
    resumes_to_process = []

    for item in resume_data:
        resume_text = item.get("resume", "") or item.get("text", "")

        # Try PDF extraction if available
        pdf_data = item.get("pdfData", "")
        if pdf_data and PDF_LIBRARY:
            try:
                pdf_bytes = base64.b64decode(pdf_data)
                extracted = extract_text_from_pdf_bytes(pdf_bytes)
                if extracted and len(extracted) > 50:
                    resume_text = extracted
            except Exception as e:
                print(f"[PDF] Decode error: {e}")

        # Skip invalid resumes
        if not resume_text or len(resume_text.strip()) < 50:
            print(f"[Analysis] Skipping invalid resume: {item.get('name', 'unknown')}")
            continue

        resumes_to_process.append({
            "filename": item.get("name", "") or item.get("filename", ""),
            "text": clean_text(resume_text)
        })

    if not resumes_to_process:
        return {
            "ranking": [],
            "jd_analysis": jd_requirements.to_dict(),
            "candidateCount": 0,
            "bestCandidate": None,
            "ai_provider": get_ai_config()['provider'] if get_ai_config() else "none",
            "metadata": {
                "total_candidates": 0,
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }
        }

    metadata.total_candidates = len(resumes_to_process)

    # -------------------------------------------------------------------------
    # STEP 3: Parse Resumes (Batch or Individual)
    # -------------------------------------------------------------------------
    print(f"[Analysis] Step 3: Parsing {len(resumes_to_process)} resumes...")

    # Use batch processing for efficiency (fewer AI calls)
    if len(resumes_to_process) > 3:
        # Batch process in groups of 5
        all_profiles = []
        batch_size = 5
        for i in range(0, len(resumes_to_process), batch_size):
            batch = resumes_to_process[i:i + batch_size]
            profiles = parse_resumes_batch(batch, jd_requirements)
            all_profiles.extend(profiles)
            metadata.ai_calls_made += 1
    else:
        # Individual processing for small batches
        all_profiles = []
        for resume in resumes_to_process:
            profile = parse_resume(
                resume['text'],
                resume['filename'],
                jd_requirements
            )
            all_profiles.append(profile)
            metadata.ai_calls_made += 1

    print(f"[Analysis] Parsed {len(all_profiles)} candidate profiles")
    metadata.successful_analyses = len(all_profiles)

    # -------------------------------------------------------------------------
    # STEP 4: Match and Score Candidates
    # -------------------------------------------------------------------------
    print("[Analysis] Step 4: Matching candidates to requirements...")
    analyzed_candidates: List[AnalyzedCandidate] = []

    for profile in all_profiles:
        # Calculate match
        match_result = calculate_match(profile, jd_requirements)

        # Generate report
        report = generate_report(profile, jd_requirements, match_result)

        # Create analyzed candidate
        analyzed = AnalyzedCandidate(
            profile=profile,
            match_result=match_result,
            report=report,
            analyzed_by="ai"
        )
        analyzed_candidates.append(analyzed)

    # -------------------------------------------------------------------------
    # STEP 5: Rank and Format Results
    # -------------------------------------------------------------------------
    print("[Analysis] Step 5: Ranking candidates...")

    # Sort by overall score
    analyzed_candidates.sort(
        key=lambda x: x.match_result.scores.overall,
        reverse=True
    )

    # Convert to response format
    ranking = [c.to_response_dict() for c in analyzed_candidates]

    # Calculate processing time
    processing_time = int((time.time() - start_time) * 1000)

    print(f"[Analysis] Complete! {len(ranking)} candidates ranked in {processing_time}ms")

    config = get_ai_config()

    return {
        "ranking": ranking,
        "jd_analysis": jd_requirements.to_dict(),
        "candidateCount": len(ranking),
        "bestCandidate": ranking[0] if ranking else None,
        "ai_provider": config['provider'] if config else "basic",
        "metadata": {
            "total_candidates": metadata.total_candidates,
            "successful_analyses": metadata.successful_analyses,
            "ai_calls_made": metadata.ai_calls_made,
            "processing_time_ms": processing_time
        }
    }


# ============================================================================
# API ROUTES
# ============================================================================

@app.route('/api/test-ai', methods=['GET', 'POST', 'OPTIONS'])
def test_ai():
    """Test AI connectivity endpoint."""
    if request.method == 'OPTIONS':
        return add_cors_headers(make_response())

    config = get_ai_config()
    if not config:
        resp = jsonify({"success": False, "error": "No API key configured"})
        return add_cors_headers(resp)

    # Import call_ai with fallback for Vercel
    try:
        from .utils import call_ai
    except ImportError:
        from utils import call_ai

    test_response = call_ai("Reply with exactly: OK", max_tokens=10)

    resp = jsonify({
        "success": test_response is not None,
        "provider": config['provider'],
        "model": config['model'],
        "response": test_response
    })
    return add_cors_headers(resp)


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    config = get_ai_config()
    resp = jsonify({
        "status": "healthy",
        "version": "5.0",
        "ai_enabled": config is not None,
        "ai_provider": config['provider'] if config else None,
        "pdf_library": PDF_LIBRARY
    })
    return add_cors_headers(resp)


@app.route('/api', methods=['GET', 'POST', 'OPTIONS'])
@app.route('/api/', methods=['GET', 'POST', 'OPTIONS'])
@app.route('/api/analyze', methods=['GET', 'POST', 'OPTIONS'])
@app.route('/api/rank', methods=['POST', 'OPTIONS'])
def main_route():
    """Main API endpoint for analysis."""
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return add_cors_headers(make_response())

    # Handle GET request - return API info
    if request.method == 'GET':
        config = get_ai_config()
        resp = jsonify({
            "api": "Smart Screener ATS",
            "version": "5.0",
            "description": "AI-powered resume screening with recruiter-level analysis",
            "ai_enabled": config is not None,
            "ai_provider": config['provider'] if config else None,
            "pdf_library": PDF_LIBRARY,
            "endpoints": {
                "POST /api/": "Main analysis endpoint",
                "POST /api/analyze": "Alias for main analysis",
                "POST /api/rank": "Alias for main analysis",
                "GET /api/test-ai": "Test AI connectivity",
                "GET /api/health": "Health check"
            }
        })
        return add_cors_headers(resp)

    # Handle POST request - perform analysis
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        data = {}

    # Authentication check
    if 'password' in data and 'jobDescription' not in data:
        submitted = data.get("password", "")
        correct = get_password()

        if not correct:
            resp = jsonify({"success": False, "error": "Password not configured"})
            resp.status_code = 500
        elif submitted == correct:
            token = hash_password(correct + "smart-screener-v5")
            resp = jsonify({"success": True, "token": token})
        else:
            resp = jsonify({"success": False, "error": "Invalid password"})
            resp.status_code = 401

        return add_cors_headers(resp)

    # Validate input
    job_description = data.get("jobDescription", "")
    if not job_description:
        resp = jsonify({
            "error": "Job description is required",
            "ranking": []
        })
        resp.status_code = 400
        return add_cors_headers(resp)

    # Get resume data
    resume_data = data.get("resumes", [])
    if not resume_data:
        resp = jsonify({
            "error": "At least one resume is required",
            "ranking": []
        })
        resp.status_code = 400
        return add_cors_headers(resp)

    # Run analysis
    try:
        result = analyze_candidates(job_description, resume_data)
        resp = jsonify(result)
    except Exception as e:
        print(f"[API] Analysis error: {type(e).__name__}: {e}")
        resp = jsonify({
            "error": f"Analysis failed: {str(e)}",
            "ranking": []
        })
        resp.status_code = 500

    return add_cors_headers(resp)


# Catch-all route for Vercel
@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'OPTIONS'])
@app.route('/<path:path>', methods=['GET', 'POST', 'OPTIONS'])
def catch_all(path=''):
    """Catch-all route - redirects to main API."""
    return main_route()


# ============================================================================
# LOCAL DEVELOPMENT
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True, port=5000)
