"""
Data models for Smart-Screener v5.0
Defines structured data classes for type safety and clarity.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class JobLevel(Enum):
    """Experience level classification"""
    INTERN = "intern"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    PRINCIPAL = "principal"
    EXECUTIVE = "executive"


class CareerTrajectory(Enum):
    """Career progression pattern"""
    RISING = "rising"          # Clear upward movement
    LATERAL = "lateral"        # Same-level moves
    MIXED = "mixed"            # Combination
    DECLINING = "declining"    # Downward movement (red flag)
    EARLY_CAREER = "early_career"  # Too early to determine


class Recommendation(Enum):
    """Hiring recommendation"""
    STRONG_HIRE = "Strong Hire"
    HIRE = "Hire"
    MAYBE = "Maybe"
    WEAK_MAYBE = "Weak Maybe"
    PASS = "Pass"


@dataclass
class ContactInfo:
    """Candidate contact information"""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    location: str = ""
    github: str = ""


@dataclass
class WorkExperience:
    """Single work experience entry"""
    company: str = ""
    title: str = ""
    start_date: str = ""  # YYYY-MM or YYYY
    end_date: str = ""    # YYYY-MM or "Present"
    duration_months: int = 0
    is_current: bool = False
    is_relevant: bool = False
    key_achievements: List[str] = field(default_factory=list)
    technologies_used: List[str] = field(default_factory=list)


@dataclass
class Education:
    """Education entry"""
    degree: str = ""
    field_of_study: str = ""
    institution: str = ""
    graduation_year: Optional[int] = None
    gpa: Optional[float] = None


@dataclass
class Skills:
    """Categorized skills"""
    technical: List[str] = field(default_factory=list)  # Programming languages, frameworks
    tools: List[str] = field(default_factory=list)      # Tools, platforms, software
    soft_skills: List[str] = field(default_factory=list)  # Communication, leadership
    certifications: List[str] = field(default_factory=list)

    def all_skills(self) -> List[str]:
        """Get all skills as flat list"""
        return self.technical + self.tools + self.soft_skills

    def all_normalized(self) -> List[str]:
        """Get all skills normalized to lowercase"""
        return [s.lower().strip() for s in self.all_skills()]


@dataclass
class JDRequirements:
    """Parsed job description requirements"""
    job_title: str = ""
    required_skills: List[str] = field(default_factory=list)
    preferred_skills: List[str] = field(default_factory=list)
    min_experience_years: Optional[int] = None
    max_experience_years: Optional[int] = None
    experience_level: JobLevel = JobLevel.MID
    education_required: str = ""
    certifications_preferred: List[str] = field(default_factory=list)
    industry_keywords: List[str] = field(default_factory=list)
    key_responsibilities: List[str] = field(default_factory=list)
    red_flags_to_watch: List[str] = field(default_factory=list)
    location_preference: str = ""
    remote_friendly: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "job_title": self.job_title,
            "required_skills": self.required_skills,
            "preferred_skills": self.preferred_skills,
            "min_experience_years": self.min_experience_years,
            "max_experience_years": self.max_experience_years,
            "experience_level": self.experience_level.value,
            "education_required": self.education_required,
            "certifications_preferred": self.certifications_preferred,
            "industry_keywords": self.industry_keywords,
            "key_responsibilities": self.key_responsibilities,
            "location_preference": self.location_preference,
            "remote_friendly": self.remote_friendly
        }


@dataclass
class CandidateProfile:
    """Complete candidate profile extracted from resume"""
    filename: str = ""
    name: str = ""
    contact: ContactInfo = field(default_factory=ContactInfo)
    professional_summary: str = ""
    work_history: List[WorkExperience] = field(default_factory=list)
    total_experience_years: float = 0.0
    relevant_experience_years: float = 0.0
    current_role: str = ""
    current_company: str = ""
    skills: Skills = field(default_factory=Skills)
    education: List[Education] = field(default_factory=list)
    career_trajectory: CareerTrajectory = CareerTrajectory.EARLY_CAREER
    red_flags: List[str] = field(default_factory=list)
    raw_text: str = ""  # Original resume text

    def highest_education(self) -> str:
        """Get highest education degree"""
        degree_rank = {
            'phd': 6, 'ph.d': 6, 'doctorate': 6,
            'master': 5, 'mba': 5, 'm.tech': 5, 'mtech': 5, 'ms': 5, 'mca': 5, 'm.com': 5,
            'bachelor': 4, 'b.tech': 4, 'btech': 4, 'be': 4, 'b.e': 4, 'bca': 4, 'b.com': 4, 'bs': 4,
            'diploma': 3,
            'associate': 2,
            'certificate': 1
        }

        highest = ""
        highest_rank = 0

        for edu in self.education:
            degree_lower = edu.degree.lower()
            for key, rank in degree_rank.items():
                if key in degree_lower and rank > highest_rank:
                    highest = edu.degree
                    highest_rank = rank

        return highest


@dataclass
class ScoreBreakdown:
    """Detailed score breakdown"""
    overall: int = 0
    skills: int = 0
    experience: int = 0
    education: int = 0
    career_fit: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "overall": self.overall,
            "skills": self.skills,
            "experience": self.experience,
            "education": self.education,
            "career_fit": self.career_fit
        }


@dataclass
class MatchResult:
    """Result of matching candidate to job"""
    scores: ScoreBreakdown = field(default_factory=ScoreBreakdown)
    matched_skills: List[str] = field(default_factory=list)
    missing_required_skills: List[str] = field(default_factory=list)
    missing_preferred_skills: List[str] = field(default_factory=list)
    bonus_skills: List[str] = field(default_factory=list)  # Skills beyond requirements
    experience_fit: str = ""  # "under", "perfect", "over"
    education_fit: str = ""   # "meets", "exceeds", "below"


@dataclass
class CandidateReport:
    """Recruiter-style candidate assessment"""
    summary: str = ""
    strengths: List[str] = field(default_factory=list)
    gaps: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    interview_focus: List[str] = field(default_factory=list)
    recommendation: Recommendation = Recommendation.MAYBE
    recommendation_confidence: str = "Medium"  # High, Medium, Low
    recommendation_reason: str = ""


@dataclass
class AnalyzedCandidate:
    """Final analyzed candidate with all data"""
    profile: CandidateProfile = field(default_factory=CandidateProfile)
    match_result: MatchResult = field(default_factory=MatchResult)
    report: CandidateReport = field(default_factory=CandidateReport)
    analyzed_by: str = "ai"  # "ai" or "regex"

    def to_response_dict(self) -> Dict[str, Any]:
        """Convert to API response format"""
        return {
            "filename": self.profile.filename,
            "name": self.profile.name,
            "email": self.profile.contact.email,
            "phone": self.profile.contact.phone,
            "linkedin": self.profile.contact.linkedin,
            "location": self.profile.contact.location,
            "experience": self.profile.total_experience_years,
            "relevantExperience": self.profile.relevant_experience_years,
            "currentRole": self.profile.current_role,
            "currentCompany": self.profile.current_company,
            "education": self.profile.highest_education(),
            "skills": self.profile.skills.all_skills()[:20],
            "careerTrajectory": self.profile.career_trajectory.value,
            "scores": self.match_result.scores.to_dict(),
            "score": self.match_result.scores.overall,
            "coveredSkills": self.match_result.matched_skills,
            "missingSkills": self.match_result.missing_required_skills,
            "missingPreferredSkills": self.match_result.missing_preferred_skills,
            "bonusSkills": self.match_result.bonus_skills,
            "experienceFit": self.match_result.experience_fit,
            "report": {
                "summary": self.report.summary,
                "strengths": self.report.strengths,
                "gaps": self.report.gaps,
                "risks": self.report.risks,
                "interviewFocus": self.report.interview_focus,
            },
            "recommendation": self.report.recommendation.value,
            "recommendationConfidence": self.report.recommendation_confidence,
            "recommendationReason": self.report.recommendation_reason,
            "redFlags": self.profile.red_flags,
            "analyzedBy": self.analyzed_by
        }


@dataclass
class AnalysisMetadata:
    """Metadata about the analysis process"""
    total_candidates: int = 0
    successful_analyses: int = 0
    ai_analyses: int = 0
    regex_fallbacks: int = 0
    processing_time_ms: int = 0
    ai_calls_made: int = 0
    cached_results: int = 0
