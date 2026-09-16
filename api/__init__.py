"""
Smart-Screener API v5.0
AI-powered resume screening with recruiter-level analysis.
"""

__version__ = "5.0.0"
__author__ = "Smart-Screener"

# Re-export main components for convenience
from .models import (
    JDRequirements,
    CandidateProfile,
    MatchResult,
    CandidateReport,
    AnalyzedCandidate,
    JobLevel,
    CareerTrajectory,
    Recommendation
)

from .jd_parser import parse_job_description
from .resume_parser import parse_resume, parse_resumes_batch
from .matching_engine import calculate_match, rank_candidates
from .report_generator import generate_report
from .skill_taxonomy import normalize_skill, normalize_skills, match_skills
from .utils import get_ai_config, call_ai
