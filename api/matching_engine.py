"""
Matching Engine for Smart-Screener v5.0

Implements recruiter-level matching logic with weighted scoring.
Goes beyond keyword matching to understand true fit.
"""

from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

try:
    from .models import (
        CandidateProfile, JDRequirements, MatchResult, ScoreBreakdown,
        JobLevel, CareerTrajectory
    )
    from .skill_taxonomy import match_skills, get_taxonomy
except ImportError:
    from models import (
        CandidateProfile, JDRequirements, MatchResult, ScoreBreakdown,
        JobLevel, CareerTrajectory
    )
    from skill_taxonomy import match_skills, get_taxonomy


# Score weights (must sum to 1.0)
SCORE_WEIGHTS = {
    'skills': 0.40,       # 40% - Most important
    'experience': 0.30,   # 30% - Second most important
    'education': 0.15,    # 15% - Supporting factor
    'career_fit': 0.15    # 15% - Cultural/trajectory fit
}


class MatchingEngine:
    """
    Implements recruiter-level matching logic.

    Scoring philosophy:
    - Skills matter most (40%) - Can they do the job?
    - Experience matters (30%) - Have they done similar work?
    - Education supports (15%) - Foundation knowledge
    - Career fit completes (15%) - Will they thrive?
    """

    def __init__(self):
        self.taxonomy = get_taxonomy()

    def calculate_match(
        self,
        candidate: CandidateProfile,
        jd: JDRequirements
    ) -> MatchResult:
        """
        Calculate comprehensive match between candidate and job.

        Args:
            candidate: Candidate profile from resume
            jd: Job requirements from JD

        Returns:
            MatchResult with scores and analysis
        """
        # Calculate individual scores
        skill_score, skill_details = self._calculate_skill_score(candidate, jd)
        exp_score, exp_fit = self._calculate_experience_score(candidate, jd)
        edu_score, edu_fit = self._calculate_education_score(candidate, jd)
        career_score = self._calculate_career_fit_score(candidate, jd)

        # Calculate weighted overall score
        overall = int(
            skill_score * SCORE_WEIGHTS['skills'] +
            exp_score * SCORE_WEIGHTS['experience'] +
            edu_score * SCORE_WEIGHTS['education'] +
            career_score * SCORE_WEIGHTS['career_fit']
        )

        # Clamp to valid range
        overall = max(0, min(100, overall))

        scores = ScoreBreakdown(
            overall=overall,
            skills=int(skill_score),
            experience=int(exp_score),
            education=int(edu_score),
            career_fit=int(career_score)
        )

        return MatchResult(
            scores=scores,
            matched_skills=skill_details['matched_required'],
            missing_required_skills=skill_details['missing_required'],
            missing_preferred_skills=skill_details['missing_preferred'],
            bonus_skills=skill_details['bonus_skills'],
            experience_fit=exp_fit,
            education_fit=edu_fit
        )

    def _calculate_skill_score(
        self,
        candidate: CandidateProfile,
        jd: JDRequirements
    ) -> Tuple[float, Dict[str, List[str]]]:
        """
        Calculate skill match score (0-100).

        Components:
        - Required skills coverage (0-80 points)
        - Preferred skills bonus (0-15 points)
        - Related skills bonus (0-5 points)

        Enhanced for GPT-4o extracted skills with semantic matching.
        """
        candidate_skills = candidate.skills.all_skills()
        required_skills = jd.required_skills
        preferred_skills = jd.preferred_skills

        # Handle edge cases
        if not required_skills and not preferred_skills:
            # No skills specified - give neutral score based on skill count
            if len(candidate_skills) >= 10:
                return 75.0, {'matched_required': [], 'missing_required': [],
                              'matched_preferred': [], 'missing_preferred': [],
                              'bonus_skills': candidate_skills[:10]}
            return 60.0, {'matched_required': [], 'missing_required': [],
                          'matched_preferred': [], 'missing_preferred': [],
                          'bonus_skills': candidate_skills[:10]}

        # Debug: log skills being matched
        print(f"[Matching] Candidate skills: {len(candidate_skills)} - {', '.join(candidate_skills[:5]) if candidate_skills else 'NONE'}")
        print(f"[Matching] Required skills: {len(required_skills)} - {', '.join(required_skills[:5]) if required_skills else 'NONE'}")

        # Use taxonomy for smart matching
        match_result = match_skills(
            candidate_skills,
            required_skills,
            preferred_skills
        )
        print(f"[Matching] Matched: {len(match_result.get('matched_required', []))}, Missing: {len(match_result.get('missing_required', []))}")

        # Calculate required skills score (0-80)
        # Use weighted scoring based on skill importance
        if required_skills:
            matched_count = len(match_result['matched_required'])
            total_required = len(required_skills)

            # Direct match bonus - full credit
            direct_matches = sum(1 for s in match_result['matched_required'] if '(related)' not in s)
            # Related matches - partial credit (70%)
            related_matches = sum(1 for s in match_result['matched_required'] if '(related)' in s)

            effective_coverage = (direct_matches + (related_matches * 0.7)) / total_required
            required_score = min(80, effective_coverage * 80)
        else:
            required_score = 50  # No requirements = partial score

        # Calculate preferred skills bonus (0-15)
        if preferred_skills:
            preferred_coverage = len(match_result['matched_preferred']) / len(preferred_skills)
            preferred_bonus = preferred_coverage * 15
        else:
            preferred_bonus = 5  # No preferred skills = small bonus

        # Related skills bonus (0-5) - reward breadth of knowledge
        related_count = sum(1 for s in match_result['matched_required'] if '(related)' in s)
        related_bonus = min(5, related_count * 1.5)

        # Bonus skills value (0-5) - extra skills show depth
        bonus_count = len(match_result.get('bonus_skills', []))
        bonus_skills_score = min(5, bonus_count * 0.5)

        total_score = min(100, required_score + preferred_bonus + related_bonus + bonus_skills_score)

        return total_score, match_result

    def _calculate_experience_score(
        self,
        candidate: CandidateProfile,
        jd: JDRequirements
    ) -> Tuple[float, str]:
        """
        Calculate experience match score (0-100).

        Scoring logic:
        - Perfect fit (within range): 100
        - Under-qualified: Penalty proportional to gap
        - Over-qualified (slight): 90 (might get bored)
        - Over-qualified (significant): 70-80 (likely to leave)
        """
        candidate_exp = candidate.total_experience_years
        min_exp = jd.min_experience_years or 0
        max_exp = jd.max_experience_years or 15

        # Handle no experience requirement
        if min_exp == 0 and max_exp == 0:
            return 80.0, "neutral"

        # Perfect fit - within the range
        if min_exp <= candidate_exp <= max_exp:
            return 100.0, "perfect"

        # Under-qualified
        if candidate_exp < min_exp:
            gap = min_exp - candidate_exp
            # Penalty: 15 points per year under
            penalty = min(60, gap * 15)
            score = max(40, 100 - penalty)
            return score, "under"

        # Over-qualified
        over_by = candidate_exp - max_exp
        if over_by <= 2:
            # Slightly over - minor concern
            return 90.0, "slightly_over"
        elif over_by <= 5:
            # Moderately over - might get bored
            return 80.0, "over"
        else:
            # Significantly over - likely to leave for better role
            return 70.0, "significantly_over"

    def _calculate_education_score(
        self,
        candidate: CandidateProfile,
        jd: JDRequirements
    ) -> Tuple[float, str]:
        """
        Calculate education match score (0-100).

        Scoring logic:
        - Meets requirement: 100
        - Exceeds requirement: 100 (no penalty for being better)
        - Below requirement: 60-80 based on gap
        - No requirement: 80 baseline
        """
        edu_required = jd.education_required.lower() if jd.education_required else ""
        highest_edu = candidate.highest_education().lower()

        # No education requirement
        if not edu_required:
            return 80.0, "not_required"

        # Define education hierarchy
        edu_levels = {
            'high school': 1, 'diploma': 2, 'associate': 2,
            'bachelor': 3, 'b.tech': 3, 'btech': 3, 'b.e': 3, 'be': 3,
            'b.s': 3, 'bs': 3, 'bca': 3, 'b.com': 3,
            'master': 4, 'm.tech': 4, 'mtech': 4, 'm.e': 4,
            'm.s': 4, 'ms': 4, 'mba': 4, 'mca': 4, 'm.com': 4,
            'phd': 5, 'ph.d': 5, 'doctorate': 5
        }

        # Find required level
        required_level = 3  # Default to bachelor's
        for key, level in edu_levels.items():
            if key in edu_required:
                required_level = level
                break

        # Find candidate level
        candidate_level = 0
        for key, level in edu_levels.items():
            if key in highest_edu:
                candidate_level = max(candidate_level, level)

        # Compare levels
        if candidate_level >= required_level:
            return 100.0, "meets" if candidate_level == required_level else "exceeds"

        # Below requirement
        gap = required_level - candidate_level
        if gap == 1:
            return 75.0, "slightly_below"
        else:
            return 60.0, "below"

    def _calculate_career_fit_score(
        self,
        candidate: CandidateProfile,
        jd: JDRequirements
    ) -> float:
        """
        Calculate career fit score (0-100).

        Components:
        - Career trajectory (0-30 points)
        - Red flags penalty (-10 per flag)
        - Level alignment (0-40 points)
        - Base score (30 points)
        """
        score = 30.0  # Base score

        # Career trajectory bonus/penalty
        trajectory_scores = {
            CareerTrajectory.RISING: 30,
            CareerTrajectory.LATERAL: 20,
            CareerTrajectory.MIXED: 15,
            CareerTrajectory.EARLY_CAREER: 20,
            CareerTrajectory.DECLINING: 0
        }
        score += trajectory_scores.get(candidate.career_trajectory, 15)

        # Red flags penalty
        red_flag_count = len(candidate.red_flags)
        red_flag_penalty = min(30, red_flag_count * 10)
        score -= red_flag_penalty

        # Level alignment
        level_match = self._check_level_alignment(candidate, jd)
        score += level_match * 40  # 0.0 to 1.0 multiplied by 40

        return max(0, min(100, score))

    def _check_level_alignment(
        self,
        candidate: CandidateProfile,
        jd: JDRequirements
    ) -> float:
        """
        Check alignment between candidate level and job level.

        Returns: 0.0 to 1.0 (1.0 = perfect alignment)
        """
        # Estimate candidate level from experience
        exp = candidate.total_experience_years

        if exp < 1:
            candidate_level = JobLevel.INTERN
        elif exp < 3:
            candidate_level = JobLevel.JUNIOR
        elif exp < 6:
            candidate_level = JobLevel.MID
        elif exp < 10:
            candidate_level = JobLevel.SENIOR
        elif exp < 15:
            candidate_level = JobLevel.LEAD
        else:
            candidate_level = JobLevel.PRINCIPAL

        # Level ordering for comparison
        level_order = [
            JobLevel.INTERN, JobLevel.JUNIOR, JobLevel.MID,
            JobLevel.SENIOR, JobLevel.LEAD, JobLevel.PRINCIPAL,
            JobLevel.EXECUTIVE
        ]

        try:
            candidate_idx = level_order.index(candidate_level)
            required_idx = level_order.index(jd.experience_level)
        except ValueError:
            return 0.5  # Unknown level

        diff = abs(candidate_idx - required_idx)

        if diff == 0:
            return 1.0  # Perfect match
        elif diff == 1:
            return 0.8  # Adjacent level - good
        elif diff == 2:
            return 0.5  # Two levels off - okay
        else:
            return 0.3  # Too far off

    def rank_candidates(
        self,
        candidates: List[CandidateProfile],
        jd: JDRequirements
    ) -> List[Tuple[CandidateProfile, MatchResult]]:
        """
        Rank candidates by match score.

        Args:
            candidates: List of candidate profiles
            jd: Job requirements

        Returns:
            List of (CandidateProfile, MatchResult) tuples, sorted by score
        """
        results = []

        for candidate in candidates:
            match_result = self.calculate_match(candidate, jd)
            results.append((candidate, match_result))

        # Sort by overall score descending
        results.sort(key=lambda x: x[1].scores.overall, reverse=True)

        return results

    def get_quick_recommendation(
        self,
        match_result: MatchResult,
        candidate: CandidateProfile
    ) -> Tuple[str, str, str]:
        """
        Get quick recommendation based on scores.

        Returns: (decision, confidence, reason)
        """
        score = match_result.scores.overall
        skill_coverage = match_result.scores.skills
        red_flags = len(candidate.red_flags)

        # Hard disqualifiers
        if skill_coverage < 40:
            return ("Pass", "High", "Missing too many required skills")

        if red_flags >= 4:
            return ("Pass", "Medium", "Multiple significant concerns")

        # Score-based recommendations
        if score >= 85:
            if red_flags == 0:
                return ("Strong Hire", "High", "Excellent match across all criteria")
            else:
                return ("Hire", "Medium", f"Strong match but {red_flags} concern(s) to discuss")

        elif score >= 75:
            return ("Hire", "Medium-High", "Strong candidate with minor gaps")

        elif score >= 65:
            return ("Maybe", "Medium", "Potential fit, interview to confirm")

        elif score >= 50:
            return ("Weak Maybe", "Low", "Significant gaps, consider only if pipeline is thin")

        else:
            return ("Pass", "High", "Does not meet minimum requirements")


# Singleton instance
_engine_instance = None


def get_engine() -> MatchingEngine:
    """Get or create singleton engine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = MatchingEngine()
    return _engine_instance


def calculate_match(
    candidate: CandidateProfile,
    jd: JDRequirements
) -> MatchResult:
    """Convenience function to calculate match."""
    return get_engine().calculate_match(candidate, jd)


def rank_candidates(
    candidates: List[CandidateProfile],
    jd: JDRequirements
) -> List[Tuple[CandidateProfile, MatchResult]]:
    """Convenience function to rank candidates."""
    return get_engine().rank_candidates(candidates, jd)
