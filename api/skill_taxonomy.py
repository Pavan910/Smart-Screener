"""
Skill Taxonomy Module for Smart-Screener v5.0

This module provides skill normalization and relationship mapping.
IMPORTANT: This is NOT a filter - any skill can be extracted.
The taxonomy is used for:
1. Normalizing skill names (JS → JavaScript)
2. Finding related skills for better matching
3. Categorizing skills for analysis

Skills NOT in the taxonomy are still valid and processed normally.
"""

import os
import json
import re
from typing import List, Dict, Set, Optional, Tuple


class SkillTaxonomy:
    """
    Skill normalization and relationship manager.

    Does NOT filter skills - any skill is valid.
    Used for normalization and finding relationships.
    """

    def __init__(self, taxonomy_path: Optional[str] = None):
        """
        Initialize taxonomy from JSON file.

        Args:
            taxonomy_path: Path to skills_taxonomy.json (optional)
        """
        self.synonyms: Dict[str, List[str]] = {}
        self.reverse_synonyms: Dict[str, str] = {}  # synonym -> canonical
        self.categories: Dict[str, List[str]] = {}
        self.related_skills: Dict[str, List[str]] = {}
        self.skill_weights: Dict[str, float] = {}

        # Load taxonomy if path provided
        if taxonomy_path and os.path.exists(taxonomy_path):
            self._load_taxonomy(taxonomy_path)
        else:
            # Try default path
            default_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'data', 'skills_taxonomy.json'
            )
            if os.path.exists(default_path):
                self._load_taxonomy(default_path)

        # Build reverse synonym lookup
        self._build_reverse_synonyms()

    def _load_taxonomy(self, path: str) -> None:
        """Load taxonomy from JSON file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.synonyms = data.get('synonyms', {})
            self.categories = data.get('categories', {})
            self.related_skills = data.get('related_skills', {})
            self.skill_weights = data.get('skill_weights', {})
            print(f"[Taxonomy] Loaded {len(self.synonyms)} synonym groups")

        except Exception as e:
            print(f"[Taxonomy] Load error: {e}")

    def _build_reverse_synonyms(self) -> None:
        """Build reverse lookup: synonym -> canonical name."""
        for canonical, synonyms in self.synonyms.items():
            canonical_lower = canonical.lower()
            self.reverse_synonyms[canonical_lower] = canonical
            for syn in synonyms:
                self.reverse_synonyms[syn.lower()] = canonical

    def normalize(self, skill: str) -> str:
        """
        Normalize a skill name to its canonical form.

        If skill is not in taxonomy, returns original with proper casing.

        Args:
            skill: Raw skill name

        Returns:
            Normalized skill name
        """
        if not skill:
            return ""

        skill_clean = skill.strip()
        skill_lower = skill_clean.lower()

        # Check if it's a known synonym
        if skill_lower in self.reverse_synonyms:
            canonical = self.reverse_synonyms[skill_lower]
            # Return with proper casing from taxonomy
            return canonical.replace('_', ' ').title()

        # Not in taxonomy - return with proper casing
        # Title case but preserve acronyms (all caps)
        if skill_clean.isupper() and len(skill_clean) <= 5:
            return skill_clean  # Preserve acronyms like AWS, SQL, CSS

        # Smart title case
        words = skill_clean.split()
        result = []
        for word in words:
            if word.isupper() and len(word) <= 5:
                result.append(word)  # Preserve acronyms
            elif word.lower() in ['and', 'or', 'the', 'of', 'for', 'in', 'on']:
                result.append(word.lower())  # Keep conjunctions lowercase
            else:
                result.append(word.capitalize())

        return ' '.join(result)

    def normalize_list(self, skills: List[str]) -> List[str]:
        """
        Normalize a list of skills, removing duplicates.

        Args:
            skills: List of raw skill names

        Returns:
            List of normalized, deduplicated skills
        """
        seen: Set[str] = set()
        normalized: List[str] = []

        for skill in skills:
            norm = self.normalize(skill)
            norm_lower = norm.lower()

            if norm and norm_lower not in seen:
                seen.add(norm_lower)
                normalized.append(norm)

        return normalized

    def get_category(self, skill: str) -> Optional[str]:
        """
        Get the category for a skill if known.

        Args:
            skill: Normalized skill name

        Returns:
            Category name or None
        """
        skill_lower = skill.lower().replace(' ', '_')

        for category, skills in self.categories.items():
            if skill_lower in [s.lower() for s in skills]:
                return category

        return None

    def get_related(self, skill: str) -> List[str]:
        """
        Get skills related to the given skill.

        Useful for finding candidates who have related but not exact skills.

        Args:
            skill: Normalized skill name

        Returns:
            List of related skill names
        """
        skill_lower = skill.lower().replace(' ', '_')

        # Direct relationships
        related = self.related_skills.get(skill_lower, [])

        # Also check if this skill is in another skill's relationships
        for key, values in self.related_skills.items():
            if skill_lower in [v.lower() for v in values]:
                related.append(key.replace('_', ' ').title())

        return list(set(related))

    def match_skills(
        self,
        candidate_skills: List[str],
        required_skills: List[str],
        preferred_skills: List[str] = None
    ) -> Dict[str, List[str]]:
        """
        Match candidate skills against job requirements.

        Uses fuzzy matching and related skills for better results.
        Enhanced for GPT-4o extracted skills with semantic matching.

        Args:
            candidate_skills: List of candidate's skills
            required_skills: List of required skills from JD
            preferred_skills: List of preferred skills from JD (optional)

        Returns:
            Dictionary with matched, missing, and bonus skills
        """
        preferred_skills = preferred_skills or []

        # Normalize all skills
        candidate_norm = set(s.lower() for s in self.normalize_list(candidate_skills))
        required_norm = set(s.lower() for s in self.normalize_list(required_skills))
        preferred_norm = set(s.lower() for s in self.normalize_list(preferred_skills))

        # Build candidate lookup including related skills
        candidate_expanded = set(candidate_norm)
        for skill in list(candidate_norm):
            for related in self.get_related(skill):
                candidate_expanded.add(related.lower())

        # Match required skills with enhanced fuzzy matching
        matched_required = []
        missing_required = []
        for skill in required_skills:
            skill_norm = self.normalize(skill)
            skill_lower = skill_norm.lower()

            # Direct match
            if skill_lower in candidate_norm:
                matched_required.append(skill_norm)
            # Related skill match
            elif skill_lower in candidate_expanded:
                matched_required.append(f"{skill_norm} (related)")
            else:
                # Try fuzzy matching for close matches
                best_match = None
                best_score = 0.0
                for cand_skill in candidate_skills:
                    score = self.fuzzy_match(skill, cand_skill)
                    if score > best_score and score >= 0.7:  # Threshold for fuzzy match
                        best_score = score
                        best_match = cand_skill

                if best_match:
                    if best_score >= 0.9:
                        matched_required.append(skill_norm)
                    else:
                        matched_required.append(f"{skill_norm} (related)")
                else:
                    missing_required.append(skill_norm)

        # Match preferred skills with same logic
        matched_preferred = []
        missing_preferred = []
        for skill in preferred_skills:
            skill_norm = self.normalize(skill)
            skill_lower = skill_norm.lower()

            if skill_lower in candidate_norm:
                matched_preferred.append(skill_norm)
            elif skill_lower in candidate_expanded:
                matched_preferred.append(f"{skill_norm} (related)")
            else:
                # Try fuzzy matching
                best_match = None
                best_score = 0.0
                for cand_skill in candidate_skills:
                    score = self.fuzzy_match(skill, cand_skill)
                    if score > best_score and score >= 0.7:
                        best_score = score
                        best_match = cand_skill

                if best_match:
                    if best_score >= 0.9:
                        matched_preferred.append(skill_norm)
                    else:
                        matched_preferred.append(f"{skill_norm} (related)")
                else:
                    missing_preferred.append(skill_norm)

        # Bonus skills (candidate has but not required)
        all_required = required_norm | preferred_norm
        bonus = []
        for skill in candidate_skills:
            skill_norm = self.normalize(skill)
            skill_lower = skill_norm.lower()

            # Check if this skill wasn't matched to any requirement
            is_bonus = skill_lower not in all_required
            if is_bonus:
                # Also check fuzzy matches
                for req_skill in list(required_norm) + list(preferred_norm):
                    if self.fuzzy_match(skill_lower, req_skill) >= 0.7:
                        is_bonus = False
                        break

            if is_bonus:
                category = self.get_category(skill_norm)
                # Include technical skills as bonus
                if category in ['programming_languages', 'frontend_frameworks',
                               'backend_frameworks', 'databases', 'cloud_platforms',
                               'devops', 'tools']:
                    bonus.append(skill_norm)
                elif not category:
                    # Unknown category but still a valid skill
                    bonus.append(skill_norm)

        return {
            "matched_required": matched_required,
            "missing_required": missing_required,
            "matched_preferred": matched_preferred,
            "missing_preferred": missing_preferred,
            "bonus_skills": bonus[:15]  # Allow more bonus skills
        }

    def calculate_skill_score(
        self,
        matched_required: List[str],
        total_required: int,
        matched_preferred: List[str],
        total_preferred: int
    ) -> int:
        """
        Calculate skill match score (0-100).

        Weights:
        - Required skills: 80% of score
        - Preferred skills: 20% of score

        Args:
            matched_required: List of matched required skills
            total_required: Total number of required skills
            matched_preferred: List of matched preferred skills
            total_preferred: Total number of preferred skills

        Returns:
            Score from 0-100
        """
        if total_required == 0:
            return 50  # No requirements = neutral score

        # Required skills (80% weight)
        required_pct = len(matched_required) / total_required
        required_score = required_pct * 80

        # Preferred skills (20% weight)
        if total_preferred > 0:
            preferred_pct = len(matched_preferred) / total_preferred
            preferred_score = preferred_pct * 20
        else:
            preferred_score = 10  # No preferred = half bonus

        return int(min(100, required_score + preferred_score))

    def fuzzy_match(self, skill1: str, skill2: str) -> float:
        """
        Calculate fuzzy match score between two skills.

        Returns 1.0 for exact match, lower for partial matches.
        Enhanced for GPT-4o extracted skills with semantic understanding.

        Args:
            skill1: First skill
            skill2: Second skill

        Returns:
            Match score from 0.0 to 1.0
        """
        s1 = skill1.lower().strip()
        s2 = skill2.lower().strip()

        # Exact match
        if s1 == s2:
            return 1.0

        # Normalize and compare
        n1 = self.normalize(skill1).lower()
        n2 = self.normalize(skill2).lower()
        if n1 == n2:
            return 1.0

        # Version-agnostic matching (React 18 == React, Python 3.11 == Python)
        s1_base = re.sub(r'[\d\.\s]+$', '', s1).strip()
        s2_base = re.sub(r'[\d\.\s]+$', '', s2).strip()
        if s1_base and s2_base and s1_base == s2_base:
            return 0.95  # Very high match for version variants

        # One contains the other
        if s1 in s2 or s2 in s1:
            return 0.8

        # Handle common skill variations
        variations = {
            'js': 'javascript', 'ts': 'typescript', 'py': 'python',
            'node': 'nodejs', 'react': 'reactjs', 'vue': 'vuejs',
            'angular': 'angularjs', 'mongo': 'mongodb', 'postgres': 'postgresql',
            'k8s': 'kubernetes', 'tf': 'terraform', 'aws': 'amazon web services',
            'gcp': 'google cloud', 'azure': 'microsoft azure'
        }
        s1_var = variations.get(s1, s1)
        s2_var = variations.get(s2, s2)
        if s1_var == s2 or s2_var == s1 or s1_var == s2_var:
            return 1.0

        # Related skills
        related = [r.lower() for r in self.get_related(s1)]
        if s2 in related or n2 in related:
            return 0.6

        # Word overlap
        words1 = set(s1.replace('-', ' ').replace('.', ' ').split())
        words2 = set(s2.replace('-', ' ').replace('.', ' ').split())
        if words1 & words2:  # Any common words
            overlap = len(words1 & words2) / max(len(words1), len(words2))
            return overlap * 0.5

        return 0.0


# Singleton instance
_taxonomy_instance: Optional[SkillTaxonomy] = None


def get_taxonomy() -> SkillTaxonomy:
    """Get or create singleton taxonomy instance."""
    global _taxonomy_instance
    if _taxonomy_instance is None:
        _taxonomy_instance = SkillTaxonomy()
    return _taxonomy_instance


def normalize_skill(skill: str) -> str:
    """Convenience function to normalize a skill."""
    return get_taxonomy().normalize(skill)


def normalize_skills(skills: List[str]) -> List[str]:
    """Convenience function to normalize a list of skills."""
    return get_taxonomy().normalize_list(skills)


def match_skills(
    candidate_skills: List[str],
    required_skills: List[str],
    preferred_skills: List[str] = None
) -> Dict[str, List[str]]:
    """Convenience function to match skills."""
    return get_taxonomy().match_skills(
        candidate_skills, required_skills, preferred_skills
    )
