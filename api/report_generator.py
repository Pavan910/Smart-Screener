"""
Report Generator for Smart-Screener v5.0

Generates recruiter-style candidate assessments with actionable insights.
"""

from typing import List, Optional
from dataclasses import dataclass

try:
    from .models import (
        CandidateProfile, JDRequirements, MatchResult, CandidateReport,
        Recommendation, CareerTrajectory
    )
except ImportError:
    from models import (
        CandidateProfile, JDRequirements, MatchResult, CandidateReport,
        Recommendation, CareerTrajectory
    )


class ReportGenerator:
    """
    Generates comprehensive candidate assessment reports.

    Reports include:
    - Executive summary
    - Key strengths
    - Gaps/concerns
    - Risk factors
    - Interview focus areas
    - Hiring recommendation
    """

    def generate(
        self,
        candidate: CandidateProfile,
        jd: JDRequirements,
        match_result: MatchResult
    ) -> CandidateReport:
        """
        Generate comprehensive candidate report.

        Args:
            candidate: Candidate profile
            jd: Job requirements
            match_result: Match analysis result

        Returns:
            CandidateReport with full assessment
        """
        # Generate each section
        summary = self._generate_summary(candidate, jd, match_result)
        strengths = self._identify_strengths(candidate, jd, match_result)
        gaps = self._identify_gaps(candidate, jd, match_result)
        risks = self._assess_risks(candidate, match_result)
        interview_focus = self._suggest_interview_focus(candidate, jd, match_result, gaps, risks)
        recommendation, confidence, reason = self._get_recommendation(candidate, match_result)

        return CandidateReport(
            summary=summary,
            strengths=strengths,
            gaps=gaps,
            risks=risks,
            interview_focus=interview_focus,
            recommendation=recommendation,
            recommendation_confidence=confidence,
            recommendation_reason=reason
        )

    def _generate_summary(
        self,
        candidate: CandidateProfile,
        jd: JDRequirements,
        match_result: MatchResult
    ) -> str:
        """Generate executive summary of candidate."""
        parts = []

        # Experience context
        exp = candidate.total_experience_years
        if exp >= 10:
            exp_desc = f"Highly experienced professional with {exp:.0f} years"
        elif exp >= 5:
            exp_desc = f"Experienced professional with {exp:.0f} years"
        elif exp >= 2:
            exp_desc = f"Mid-level professional with {exp:.0f} years"
        elif exp >= 1:
            exp_desc = f"Early-career professional with {exp:.0f} year(s)"
        else:
            exp_desc = "Entry-level candidate"

        parts.append(exp_desc)

        # Current role
        if candidate.current_role:
            parts.append(f"currently working as {candidate.current_role}")
            if candidate.current_company:
                parts[-1] += f" at {candidate.current_company}"

        # Skill match context
        score = match_result.scores.overall
        if score >= 80:
            parts.append("showing strong alignment with job requirements")
        elif score >= 65:
            parts.append("with good potential fit for the role")
        elif score >= 50:
            parts.append("with partial alignment to requirements")
        else:
            parts.append("but limited alignment with core requirements")

        # Experience fit
        if match_result.experience_fit == "perfect":
            parts.append("Experience level matches expectations")
        elif match_result.experience_fit == "under":
            gap = (jd.min_experience_years or 0) - candidate.total_experience_years
            parts.append(f"Note: {gap:.0f} year(s) below minimum experience requirement")
        elif match_result.experience_fit == "over":
            parts.append("May be overqualified - verify interest in this level")

        return ". ".join(parts) + "."

    def _identify_strengths(
        self,
        candidate: CandidateProfile,
        jd: JDRequirements,
        match_result: MatchResult
    ) -> List[str]:
        """Identify candidate's key strengths relative to job."""
        strengths = []

        # Skill matches
        matched = match_result.matched_skills
        if len(matched) >= len(jd.required_skills) * 0.8:
            strengths.append(f"Strong skill coverage ({len(matched)}/{len(jd.required_skills)} required skills)")
        elif len(matched) >= len(jd.required_skills) * 0.5:
            strengths.append(f"Solid skill foundation ({len(matched)}/{len(jd.required_skills)} required skills)")

        # Highlight key matched skills
        key_matched = matched[:5]
        if key_matched:
            strengths.append(f"Key skills: {', '.join(key_matched)}")

        # Bonus skills
        if match_result.bonus_skills:
            strengths.append(f"Additional relevant skills: {', '.join(match_result.bonus_skills[:4])}")

        # Experience strengths
        exp = candidate.total_experience_years
        min_exp = jd.min_experience_years or 0
        if exp >= min_exp:
            if exp > min_exp + 2:
                strengths.append(f"Exceeds experience requirement ({exp:.0f} years vs {min_exp} required)")
            else:
                strengths.append(f"Meets experience requirement ({exp:.0f} years)")

        # Education
        if match_result.education_fit in ["meets", "exceeds"]:
            edu = candidate.highest_education()
            if edu:
                strengths.append(f"Educational qualification: {edu}")

        # Career trajectory
        if candidate.career_trajectory == CareerTrajectory.RISING:
            strengths.append("Shows consistent career growth and progression")
        elif candidate.career_trajectory == CareerTrajectory.LATERAL and exp >= 5:
            strengths.append("Demonstrated expertise through sustained contributions")

        # Current role relevance
        if candidate.current_role and jd.job_title:
            role_words = set(candidate.current_role.lower().split())
            title_words = set(jd.job_title.lower().split())
            if role_words & title_words:
                strengths.append(f"Current role ({candidate.current_role}) is directly relevant")

        return strengths[:7]  # Limit to top 7 strengths

    def _identify_gaps(
        self,
        candidate: CandidateProfile,
        jd: JDRequirements,
        match_result: MatchResult
    ) -> List[str]:
        """Identify gaps between candidate and job requirements."""
        gaps = []

        # Missing required skills
        missing_required = match_result.missing_required_skills
        if missing_required:
            if len(missing_required) >= 3:
                gaps.append(f"Missing required skills: {', '.join(missing_required[:5])}")
            else:
                for skill in missing_required:
                    gaps.append(f"Missing required skill: {skill}")

        # Missing preferred skills (only if significant)
        missing_preferred = match_result.missing_preferred_skills
        if len(missing_preferred) >= 2:
            gaps.append(f"Missing preferred skills: {', '.join(missing_preferred[:3])}")

        # Experience gaps
        if match_result.experience_fit == "under":
            exp = candidate.total_experience_years
            min_exp = jd.min_experience_years or 0
            gap = min_exp - exp
            gaps.append(f"Experience gap: {gap:.0f} year(s) below requirement")

        # Education gaps
        if match_result.education_fit == "below":
            edu = jd.education_required
            if edu:
                gaps.append(f"Education below requirement: {edu} preferred")

        # No certifications if required
        if jd.certifications_preferred and not candidate.skills.certifications:
            gaps.append("No relevant certifications listed")

        return gaps[:6]  # Limit to top 6 gaps

    def _assess_risks(
        self,
        candidate: CandidateProfile,
        match_result: MatchResult
    ) -> List[str]:
        """Assess risk factors for hiring this candidate."""
        risks = []

        # Include candidate red flags
        for flag in candidate.red_flags:
            if flag:  # Skip empty flags
                risks.append(flag)

        # Overqualification risk
        if match_result.experience_fit == "significantly_over":
            risks.append("Significantly overqualified - may leave for senior role")
        elif match_result.experience_fit == "over":
            risks.append("Overqualified - verify genuine interest in this level")

        # Career trajectory concerns
        if candidate.career_trajectory == CareerTrajectory.DECLINING:
            risks.append("Career shows declining trajectory - understand reasons")

        # Skill score concerns
        if match_result.scores.skills < 50:
            risks.append("Limited skill match - would require significant training")

        # Low overall fit
        if match_result.scores.overall < 50:
            risks.append("Below-threshold fit - high risk of poor performance")

        return risks[:5]  # Limit to top 5 risks

    def _suggest_interview_focus(
        self,
        candidate: CandidateProfile,
        jd: JDRequirements,
        match_result: MatchResult,
        gaps: List[str],
        risks: List[str]
    ) -> List[str]:
        """Suggest areas to focus on during interview."""
        focus = []

        # Missing skills - assess learning ability
        missing_skills = match_result.missing_required_skills
        if missing_skills:
            focus.append(f"Assess ability to learn: {', '.join(missing_skills[:3])}")

        # Experience gap - assess transferable skills
        if match_result.experience_fit == "under":
            focus.append("Explore depth of experience in related projects")
            focus.append("Assess problem-solving with real scenarios")

        # Overqualification - verify motivation
        if match_result.experience_fit in ["over", "significantly_over"]:
            focus.append("Understand motivation for this role level")
            focus.append("Verify long-term career expectations")

        # Red flags - get context
        if candidate.red_flags:
            if any("job" in f.lower() or "change" in f.lower() for f in candidate.red_flags):
                focus.append("Understand reasons for job transitions")
            if any("gap" in f.lower() for f in candidate.red_flags):
                focus.append("Clarify employment gaps")

        # Career trajectory concerns
        if candidate.career_trajectory == CareerTrajectory.DECLINING:
            focus.append("Understand career direction and goals")

        # Current role relevance
        if candidate.current_role:
            focus.append(f"Deep-dive on current responsibilities at {candidate.current_company or 'current role'}")

        # Technical depth
        if match_result.matched_skills:
            top_skill = match_result.matched_skills[0].replace(" (related)", "")
            focus.append(f"Technical deep-dive on {top_skill} expertise")

        return focus[:6]  # Limit to top 6 focus areas

    def _get_recommendation(
        self,
        candidate: CandidateProfile,
        match_result: MatchResult
    ) -> tuple:
        """
        Determine hiring recommendation.

        Returns: (Recommendation, confidence, reason)
        """
        score = match_result.scores.overall
        skill_score = match_result.scores.skills
        red_flags = len(candidate.red_flags)

        # Hard disqualifiers
        if skill_score < 40:
            return (
                Recommendation.PASS,
                "High",
                "Insufficient skill coverage for core requirements"
            )

        if red_flags >= 4:
            return (
                Recommendation.PASS,
                "Medium",
                f"Too many concerns ({red_flags} red flags identified)"
            )

        # Score-based recommendations with nuance
        if score >= 85:
            if red_flags == 0:
                return (
                    Recommendation.STRONG_HIRE,
                    "High",
                    "Excellent match across skills, experience, and trajectory"
                )
            else:
                return (
                    Recommendation.HIRE,
                    "Medium-High",
                    f"Strong match - address {red_flags} concern(s) in interview"
                )

        elif score >= 75:
            if red_flags <= 1:
                return (
                    Recommendation.HIRE,
                    "Medium-High",
                    "Strong candidate with solid overall alignment"
                )
            else:
                return (
                    Recommendation.MAYBE,
                    "Medium",
                    "Good potential but several areas need clarification"
                )

        elif score >= 65:
            if skill_score >= 70:
                return (
                    Recommendation.MAYBE,
                    "Medium",
                    "Good skills but experience or fit concerns - interview to confirm"
                )
            else:
                return (
                    Recommendation.MAYBE,
                    "Low-Medium",
                    "Potential fit but gaps in key areas - interview needed"
                )

        elif score >= 50:
            return (
                Recommendation.WEAK_MAYBE,
                "Low",
                "Significant gaps - consider only if candidate pipeline is limited"
            )

        else:
            return (
                Recommendation.PASS,
                "High",
                "Does not meet minimum requirements for this role"
            )


# Singleton instance
_generator_instance = None


def get_generator() -> ReportGenerator:
    """Get or create singleton generator instance."""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = ReportGenerator()
    return _generator_instance


def generate_report(
    candidate: CandidateProfile,
    jd: JDRequirements,
    match_result: MatchResult
) -> CandidateReport:
    """Convenience function to generate report."""
    return get_generator().generate(candidate, jd, match_result)
