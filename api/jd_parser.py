"""
Job Description Parser for Smart-Screener v5.0

Parses job descriptions to extract structured requirements using AI.
Works with ANY job description format - no hardcoded patterns.
"""

import re
from typing import Optional, Dict, Any, List

try:
    from .models import JDRequirements, JobLevel
    from .utils import call_ai, parse_ai_json, cached, clean_text, truncate_text
    from .skill_taxonomy import normalize_skills
except ImportError:
    from models import JDRequirements, JobLevel
    from utils import call_ai, parse_ai_json, cached, clean_text, truncate_text
    from skill_taxonomy import normalize_skills


# AI prompt for JD extraction - optimized for GPT-4o
JD_EXTRACTION_PROMPT = """You are a senior technical recruiter with 15+ years of experience analyzing job descriptions. Your task is to extract structured requirements from this job posting with precision.

=== JOB DESCRIPTION ===
{jd_text}
=== END JOB DESCRIPTION ===

Analyze the job description carefully and extract ALL requirements. Return a JSON object with the following structure:

{{
  "job_title": "Exact job title from the posting",
  "required_skills": [
    "Extract EVERY skill that is marked as required, must-have, essential, mandatory, or necessary",
    "Include: programming languages, frameworks, libraries, databases, cloud platforms, tools",
    "Preserve version numbers (React 18, Python 3.11, Node.js 18+)",
    "Include methodologies (Agile, Scrum, TDD, CI/CD)"
  ],
  "preferred_skills": [
    "Skills marked as: preferred, nice-to-have, bonus, plus, advantageous, desirable",
    "Skills with: 'familiarity with', 'exposure to', 'understanding of', 'knowledge of is a plus'",
    "Any skill mentioned but not explicitly required"
  ],
  "min_experience_years": <number or null>,
  "max_experience_years": <number or null>,
  "experience_level": "intern|junior|mid|senior|lead|principal|executive",
  "education_required": "Exact education requirement or null",
  "certifications_preferred": ["AWS Certified", "PMP", etc.],
  "industry_keywords": ["Domain terms: fintech, healthcare, e-commerce, SaaS, B2B, startup, enterprise"],
  "key_responsibilities": ["Top 5-7 main job duties"],
  "location_preference": "City/Region or Remote/Hybrid",
  "remote_friendly": true|false,
  "team_size_hint": "If mentioned: 'individual contributor', 'small team', 'large team', 'lead X engineers'",
  "urgency_indicators": ["immediate", "asap", "growing team", etc. if present]
}}

EXTRACTION RULES:

1. SKILL CLASSIFICATION:
   - REQUIRED signals: "must have", "required", "essential", "mandatory", "strong experience in", "proficient in", "expert in"
   - PREFERRED signals: "nice to have", "bonus", "plus", "preferred", "desirable", "familiarity", "exposure"
   - When ambiguous: Technical core skills → required, Supplementary skills → preferred

2. EXPERIENCE PARSING:
   - "5+ years" → min: 5, max: null
   - "3-5 years" → min: 3, max: 5
   - "minimum 2 years" → min: 2, max: null
   - If only level mentioned, infer: junior(0-2), mid(2-5), senior(5-10), lead(7-15)

3. SKILL EXTRACTION DEPTH:
   - "Full-stack" → Extract implied: frontend frameworks, backend languages, databases
   - "DevOps" → Extract implied: CI/CD, containers, cloud, IaC
   - "Machine Learning" → Extract implied: Python, TensorFlow/PyTorch, data processing
   - Extract SPECIFIC tools mentioned in responsibilities section too

4. BE THOROUGH:
   - Scan the ENTIRE document including responsibilities section for hidden requirements
   - Include both hard skills (technical) and measurable soft skills (e.g., "lead standups", "mentor juniors")
   - Don't miss skills mentioned in "What you'll do" sections

Return ONLY the JSON object, no explanations."""


class JDParser:
    """
    Parses job descriptions to extract structured requirements.

    Uses AI for intelligent extraction - no hardcoded patterns.
    Works with any job description format from any industry.
    """

    def __init__(self):
        self._cache: Dict[str, JDRequirements] = {}

    def parse(self, jd_text: str) -> JDRequirements:
        """
        Parse a job description and extract requirements.

        Uses AI for intelligent extraction with regex fallback.

        Args:
            jd_text: Raw job description text

        Returns:
            JDRequirements object with extracted data
        """
        if not jd_text or len(jd_text.strip()) < 50:
            print("[JD Parser] Text too short, returning empty requirements")
            return JDRequirements()

        # Clean and prepare text
        jd_clean = clean_text(jd_text)
        jd_truncated = truncate_text(jd_clean, max_length=6000)

        # Try AI extraction
        ai_result = self._extract_with_ai(jd_truncated)
        if ai_result:
            return ai_result

        # Fallback to regex extraction
        print("[JD Parser] AI failed, using regex fallback")
        return self._extract_with_regex(jd_clean)

    def _extract_with_ai(self, jd_text: str) -> Optional[JDRequirements]:
        """Extract requirements using AI."""
        prompt = JD_EXTRACTION_PROMPT.format(jd_text=jd_text)

        response = call_ai(
            prompt=prompt,
            system_prompt="You are an expert technical recruiter. Extract job requirements accurately and return valid JSON only.",
            max_tokens=2000,
            temperature=0.1
        )

        data = parse_ai_json(response)
        if not data:
            return None

        try:
            # Parse experience level
            level_str = data.get('experience_level', 'mid').lower()
            try:
                level = JobLevel(level_str)
            except ValueError:
                level = self._infer_level_from_years(
                    data.get('min_experience_years'),
                    data.get('max_experience_years')
                )

            # Normalize skills
            required = normalize_skills(data.get('required_skills', []))
            preferred = normalize_skills(data.get('preferred_skills', []))

            # Parse experience years
            min_exp = self._parse_years(data.get('min_experience_years'))
            max_exp = self._parse_years(data.get('max_experience_years'))

            # Infer experience from level if not specified
            if min_exp is None and max_exp is None:
                min_exp, max_exp = self._get_level_range(level)

            result = JDRequirements(
                job_title=data.get('job_title', ''),
                required_skills=required,
                preferred_skills=preferred,
                min_experience_years=min_exp,
                max_experience_years=max_exp,
                experience_level=level,
                education_required=data.get('education_required') or '',
                certifications_preferred=data.get('certifications_preferred', []),
                industry_keywords=data.get('industry_keywords', []),
                key_responsibilities=data.get('key_responsibilities', [])[:7],
                location_preference=data.get('location_preference', ''),
                remote_friendly=data.get('remote_friendly', True)
            )

            print(f"[JD Parser] AI extracted: {len(required)} required, {len(preferred)} preferred skills")
            return result

        except Exception as e:
            print(f"[JD Parser] Error parsing AI response: {e}")
            return None

    def _extract_with_regex(self, jd_text: str) -> JDRequirements:
        """Fallback regex extraction for when AI fails."""
        jd_lower = jd_text.lower()

        # Extract skills using various patterns
        skills = self._extract_skills_regex(jd_text)

        # Try to determine experience requirements
        min_exp, max_exp = self._extract_experience_regex(jd_text)

        # Infer level
        level = self._infer_level_from_text(jd_lower)
        if min_exp is None and max_exp is None:
            min_exp, max_exp = self._get_level_range(level)

        # Extract job title (usually first substantial line)
        title = self._extract_title_regex(jd_text)

        # Try to extract education
        education = self._extract_education_regex(jd_text)

        return JDRequirements(
            job_title=title,
            required_skills=skills[:15],  # First skills as required
            preferred_skills=skills[15:25] if len(skills) > 15 else [],
            min_experience_years=min_exp,
            max_experience_years=max_exp,
            experience_level=level,
            education_required=education,
            remote_friendly='remote' in jd_lower or 'work from home' in jd_lower
        )

    def _extract_skills_regex(self, text: str) -> List[str]:
        """Extract skills using regex patterns."""
        skills = set()

        # Common skill patterns
        patterns = [
            # Direct skill mentions
            r'(?:experience with|proficiency in|knowledge of|expertise in|familiar with)\s+([A-Za-z0-9\+\#\.\-/\s]+?)(?:,|\.|;|\n|and)',
            # Skills section
            r'(?:skills?|requirements?|qualifications?)[\s:]+([^\n]+)',
            # Bullet points
            r'(?:•|-|\*)\s*([A-Z][A-Za-z0-9\+\#\.\-/]+(?:\s+[A-Za-z0-9\+\#\.]+)*)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.I)
            for match in matches:
                # Split by common delimiters
                parts = re.split(r'[,;/\|]', match)
                for part in parts:
                    skill = part.strip()
                    # Validate skill
                    if 2 <= len(skill) <= 40 and not skill.isdigit():
                        skills.add(skill)

        return list(skills)[:25]

    def _extract_experience_regex(self, text: str) -> tuple:
        """Extract experience requirements."""
        patterns = [
            r'(\d+)\+?\s*(?:to|-)\s*(\d+)\s*years?',  # 3-5 years
            r'(\d+)\+?\s*years?\s*(?:of\s+)?(?:experience|exp)',  # 5+ years experience
            r'minimum\s+(\d+)\s*years?',  # minimum 3 years
            r'at\s+least\s+(\d+)\s*years?',  # at least 3 years
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    return int(groups[0]), int(groups[1])
                elif len(groups) == 1:
                    years = int(groups[0])
                    return years, years + 3  # Assume range

        return None, None

    def _extract_title_regex(self, text: str) -> str:
        """Extract job title from text."""
        lines = text.split('\n')
        for line in lines[:5]:
            line = line.strip()
            if 10 <= len(line) <= 80:
                # Skip common header patterns
                if not re.match(r'^(about|we are|company|location|job id)', line, re.I):
                    return line
        return ""

    def _extract_education_regex(self, text: str) -> str:
        """Extract education requirements."""
        patterns = [
            r"(?:bachelor'?s?|master'?s?|ph\.?d\.?|b\.?s\.?|m\.?s\.?|mba)\s*(?:degree)?\s*(?:in\s+)?([a-zA-Z\s]+)",
            r"degree\s+in\s+([a-zA-Z\s]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return match.group(0).strip()

        return ""

    def _infer_level_from_text(self, text: str) -> JobLevel:
        """Infer experience level from job description text."""
        text = text.lower()

        if any(w in text for w in ['principal', 'staff', 'architect']):
            return JobLevel.PRINCIPAL
        elif any(w in text for w in ['lead', 'manager', 'head of']):
            return JobLevel.LEAD
        elif any(w in text for w in ['senior', 'sr.', 'sr ']):
            return JobLevel.SENIOR
        elif any(w in text for w in ['junior', 'jr.', 'jr ', 'entry level', 'entry-level']):
            return JobLevel.JUNIOR
        elif any(w in text for w in ['intern', 'internship', 'trainee']):
            return JobLevel.INTERN
        else:
            return JobLevel.MID

    def _infer_level_from_years(self, min_years: Optional[int], max_years: Optional[int]) -> JobLevel:
        """Infer experience level from years requirement."""
        if min_years is None:
            return JobLevel.MID

        if min_years >= 10:
            return JobLevel.PRINCIPAL
        elif min_years >= 7:
            return JobLevel.LEAD
        elif min_years >= 5:
            return JobLevel.SENIOR
        elif min_years >= 2:
            return JobLevel.MID
        elif min_years >= 1:
            return JobLevel.JUNIOR
        else:
            return JobLevel.INTERN

    def _get_level_range(self, level: JobLevel) -> tuple:
        """Get typical experience range for a level."""
        ranges = {
            JobLevel.INTERN: (0, 1),
            JobLevel.JUNIOR: (0, 2),
            JobLevel.MID: (2, 5),
            JobLevel.SENIOR: (5, 10),
            JobLevel.LEAD: (7, 15),
            JobLevel.PRINCIPAL: (10, 20),
            JobLevel.EXECUTIVE: (12, 30),
        }
        return ranges.get(level, (2, 5))

    def _parse_years(self, value: Any) -> Optional[int]:
        """Parse years value to integer."""
        if value is None:
            return None
        try:
            years = int(float(value))
            if 0 <= years <= 50:
                return years
        except (ValueError, TypeError):
            pass
        return None


# Singleton instance
_parser_instance: Optional[JDParser] = None


def get_parser() -> JDParser:
    """Get or create singleton parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = JDParser()
    return _parser_instance


def parse_job_description(jd_text: str) -> JDRequirements:
    """
    Convenience function to parse a job description.

    Args:
        jd_text: Raw job description text

    Returns:
        JDRequirements object with extracted requirements
    """
    return get_parser().parse(jd_text)
