"""
Resume Parser for Smart-Screener v5.0

Extracts structured candidate information from resumes using AI.
Works with ANY resume format - no hardcoded patterns.
"""

import re
from datetime import datetime
from typing import Optional, Dict, Any, List

try:
    from .models import (
        CandidateProfile, ContactInfo, WorkExperience, Education, Skills,
        CareerTrajectory, JDRequirements
    )
    from .utils import (
        call_ai, parse_ai_json, clean_text, truncate_text,
        extract_email, extract_phone, extract_linkedin, extract_github,
        calculate_months_between, safe_int, safe_float
    )
    from .skill_taxonomy import normalize_skills
except ImportError:
    from models import (
        CandidateProfile, ContactInfo, WorkExperience, Education, Skills,
        CareerTrajectory, JDRequirements
    )
    from utils import (
        call_ai, parse_ai_json, clean_text, truncate_text,
        extract_email, extract_phone, extract_linkedin, extract_github,
        calculate_months_between, safe_int, safe_float
    )
    from skill_taxonomy import normalize_skills


# AI prompt for resume extraction - optimized for GPT-4o
RESUME_EXTRACTION_PROMPT = """You are a senior technical recruiter analyzing a candidate's resume. Your task is to extract comprehensive, structured information with recruiter-level precision.

=== RESUME ===
{resume_text}
=== END RESUME ===

{jd_context}

Analyze this resume thoroughly and extract ALL information. Return a JSON object:

{{
  "candidate_name": "Full legal name (first and last name from header/top)",
  "contact": {{
    "email": "Email address",
    "phone": "Phone number with country code if present",
    "linkedin": "Full LinkedIn URL",
    "github": "Full GitHub URL",
    "portfolio": "Portfolio/personal website if present",
    "location": "Current city and state/country from CONTACT section only (ignore education locations)"
  }},
  "professional_summary": "2-3 sentence professional summary capturing their expertise, experience level, and key strengths",
  "current_role": "Most recent/current job title",
  "current_company": "Most recent/current employer",
  "work_history": [
    {{
      "company": "Company name",
      "title": "Exact job title",
      "start_date": "YYYY-MM format",
      "end_date": "YYYY-MM or 'Present'",
      "is_current": true/false,
      "duration_months": <calculated months>,
      "key_achievements": [
        "Quantified achievement with metrics if available",
        "Impact statement with numbers/percentages"
      ],
      "technologies_used": ["Specific technologies used in this role"],
      "team_context": "Led team of X / Individual contributor / Collaborated with X teams"
    }}
  ],
  "total_experience_years": <number: calculate from earliest job start to latest job end>,
  "relevant_experience_years": <number: experience in similar roles/technologies>,
  "skills": {{
    "programming_languages": ["Python", "JavaScript", etc.],
    "frameworks": ["React", "Django", "Spring", etc.],
    "databases": ["PostgreSQL", "MongoDB", etc.],
    "cloud_platforms": ["AWS", "Azure", "GCP", etc.],
    "devops_tools": ["Docker", "Kubernetes", "Jenkins", etc.],
    "other_technical": ["Other technical skills"],
    "soft_skills": ["Leadership", "Communication", etc.]
  }},
  "education": [
    {{
      "degree": "Degree type (B.Tech, MBA, MS, etc.)",
      "field_of_study": "Major/Specialization",
      "institution": "University/College name",
      "graduation_year": <year as number>,
      "gpa": <GPA if mentioned, null otherwise>,
      "honors": "Cum Laude, Dean's List, etc. if mentioned"
    }}
  ],
  "certifications": [
    {{
      "name": "Certification name",
      "issuer": "Issuing organization",
      "year": <year if mentioned>
    }}
  ],
  "projects": [
    {{
      "name": "Project name",
      "description": "Brief description",
      "technologies": ["Technologies used"],
      "impact": "Outcome/impact if mentioned"
    }}
  ],
  "career_trajectory": "rising|lateral|mixed|declining|early_career",
  "career_trajectory_evidence": "Brief explanation of trajectory assessment",
  "strengths": [
    "Key strength 1 with evidence from resume",
    "Key strength 2 with evidence from resume"
  ],
  "red_flags": [
    "Only include if actually present: job hopping, gaps, inconsistencies"
  ],
  "seniority_level": "intern|junior|mid|senior|lead|principal|executive"
}}

EXTRACTION RULES:

1. NAME EXTRACTION:
   - Look at the TOP of the resume (first 3 lines typically)
   - The name is usually the largest text or first prominent line
   - Skip "Resume", "CV", "Curriculum Vitae", email addresses, phone numbers
   - Format: First Last or First Middle Last

2. LOCATION EXTRACTION - CRITICAL:
   - ONLY extract location from the CONTACT/HEADER section (top of resume)
   - Look near email/phone for city, state/country
   - DO NOT use the location of universities or previous employers
   - If no contact location found, return empty string

3. EXPERIENCE CALCULATION:
   - Calculate from ACTUAL dates in work history
   - total_experience_years = (latest_end_date - earliest_start_date) in years
   - For "Present", use current date
   - Handle overlapping roles by using overall span

4. SKILLS EXTRACTION - BE THOROUGH:
   - Extract from dedicated "Skills" section
   - ALSO extract technologies mentioned in job descriptions
   - ALSO extract technologies from project descriptions
   - Normalize skill names (e.g., "JS" → "JavaScript")
   - Include version numbers when specified

5. ACHIEVEMENTS:
   - Prioritize quantified achievements (numbers, percentages, metrics)
   - "Increased X by Y%" or "Reduced Z from A to B"
   - Extract impact statements

6. CAREER TRAJECTORY:
   - "rising": Clear promotions, title progression, increasing scope
   - "lateral": Same-level moves, broadening experience
   - "declining": Decreasing responsibilities, lower titles
   - "early_career": <3 years experience, still establishing

7. RED FLAGS (only if ACTUALLY present):
   - Job hopping: 3+ jobs in 2 years with no apparent reason
   - Gaps: 6+ months between roles unexplained
   - Inconsistencies: Overlapping dates, vague descriptions
   - DO NOT fabricate red flags - return empty array if none found

Return ONLY the JSON object."""


# Prompt variation for batch processing
BATCH_RESUME_PROMPT = """You are an expert resume analyst. Analyze these {count} resumes against the job requirements.

=== JOB REQUIREMENTS ===
{jd_summary}
=== END REQUIREMENTS ===

=== RESUMES ===
{resumes_text}
=== END RESUMES ===

For EACH resume, extract and return a JSON array with objects containing:
{{
  "resume_index": <0-based index>,
  "candidate_name": "Full name",
  "email": "Email",
  "phone": "Phone",
  "location": "City from contact section only",
  "total_experience_years": <number>,
  "current_role": "Most recent job title",
  "current_company": "Most recent company",
  "education": "Highest degree",
  "skills": ["All skills mentioned"],
  "career_trajectory": "rising/lateral/mixed/declining/early_career",
  "red_flags": ["Any concerns"],
  "professional_summary": "1-2 sentence summary"
}}

Return ONLY a valid JSON array with {count} objects."""


class ResumeParser:
    """
    Parses resumes to extract structured candidate profiles.

    Uses AI for intelligent extraction - works with any resume format.
    """

    def __init__(self):
        self.current_year = datetime.now().year
        self.current_month = datetime.now().month

    def parse(
        self,
        resume_text: str,
        filename: str = "",
        jd_requirements: Optional[JDRequirements] = None
    ) -> CandidateProfile:
        """
        Parse a single resume and extract candidate profile.

        Args:
            resume_text: Raw resume text
            filename: Original filename (for fallback name extraction)
            jd_requirements: Optional JD context for relevance detection

        Returns:
            CandidateProfile object with extracted data
        """
        if not resume_text or len(resume_text.strip()) < 50:
            print(f"[Resume Parser] Text too short: {len(resume_text)} chars")
            return CandidateProfile(filename=filename, name="Invalid Resume")

        # Clean text
        text_clean = clean_text(resume_text)
        text_truncated = truncate_text(text_clean, max_length=5000)

        # Build JD context string
        jd_context = ""
        if jd_requirements:
            jd_context = f"""
For context, the job requires:
- Role: {jd_requirements.job_title}
- Required Skills: {', '.join(jd_requirements.required_skills[:10])}
- Experience Level: {jd_requirements.experience_level.value}

Mark skills/experience as relevant if they match these requirements."""

        # Try AI extraction
        ai_result = self._extract_with_ai(text_truncated, jd_context)
        if ai_result:
            ai_result.filename = filename
            ai_result.raw_text = resume_text
            return ai_result

        # Fallback to regex extraction
        print("[Resume Parser] AI failed, using regex fallback")
        return self._extract_with_regex(text_clean, filename)

    def parse_batch(
        self,
        resumes: List[Dict[str, str]],
        jd_requirements: Optional[JDRequirements] = None
    ) -> List[CandidateProfile]:
        """
        Parse multiple resumes in a single AI call (cost optimization).

        Args:
            resumes: List of {"filename": str, "text": str} dicts
            jd_requirements: Optional JD context

        Returns:
            List of CandidateProfile objects
        """
        if not resumes:
            return []

        # For small batches, use individual parsing
        if len(resumes) <= 2:
            return [
                self.parse(r.get('text', ''), r.get('filename', ''), jd_requirements)
                for r in resumes
            ]

        # Build combined prompt
        jd_summary = ""
        if jd_requirements:
            jd_summary = f"""
Role: {jd_requirements.job_title}
Required: {', '.join(jd_requirements.required_skills[:8])}
Preferred: {', '.join(jd_requirements.preferred_skills[:5])}
Experience: {jd_requirements.min_experience_years or 0}-{jd_requirements.max_experience_years or 10} years"""

        # Combine resumes with markers
        resumes_text = ""
        for i, r in enumerate(resumes):
            text = truncate_text(clean_text(r.get('text', '')), max_length=2500)
            resumes_text += f"\n--- RESUME {i}: {r.get('filename', f'resume_{i}')} ---\n{text}\n"

        prompt = BATCH_RESUME_PROMPT.format(
            count=len(resumes),
            jd_summary=jd_summary,
            resumes_text=resumes_text
        )

        response = call_ai(
            prompt=prompt,
            system_prompt="You are an expert resume analyst. Extract information accurately and return valid JSON array.",
            max_tokens=3000,
            temperature=0.1
        )

        results = parse_ai_json(response)

        if results and isinstance(results, list):
            profiles = []
            for i, r in enumerate(resumes):
                # Find matching result
                result_data = next(
                    (x for x in results if x.get('resume_index') == i),
                    results[i] if i < len(results) else {}
                )
                profile = self._build_profile_from_ai(result_data, r.get('filename', ''))
                profile.raw_text = r.get('text', '')
                profiles.append(profile)
            return profiles

        # Fallback to individual parsing
        print("[Resume Parser] Batch failed, falling back to individual parsing")
        return [
            self.parse(r.get('text', ''), r.get('filename', ''), jd_requirements)
            for r in resumes
        ]

    def _extract_with_ai(self, resume_text: str, jd_context: str) -> Optional[CandidateProfile]:
        """Extract candidate profile using AI."""
        prompt = RESUME_EXTRACTION_PROMPT.format(
            resume_text=resume_text,
            jd_context=jd_context
        )

        response = call_ai(
            prompt=prompt,
            system_prompt="You are an expert resume analyst. Extract information accurately and return valid JSON only.",
            max_tokens=2500,
            temperature=0.1
        )

        data = parse_ai_json(response)
        if not data:
            return None

        return self._build_profile_from_ai(data, "")

    def _build_profile_from_ai(self, data: Dict[str, Any], filename: str) -> CandidateProfile:
        """Build CandidateProfile from AI response data."""
        try:
            # Contact info
            contact_data = data.get('contact', {})
            if isinstance(contact_data, str):
                contact_data = {}

            contact = ContactInfo(
                email=contact_data.get('email', '') or data.get('email', ''),
                phone=contact_data.get('phone', '') or data.get('phone', ''),
                linkedin=contact_data.get('linkedin', '') or data.get('linkedin', ''),
                github=contact_data.get('github', ''),
                location=contact_data.get('location', '') or data.get('location', '')
            )

            # Work history
            work_history = []
            for job in data.get('work_history', []):
                if isinstance(job, dict):
                    work_history.append(WorkExperience(
                        company=job.get('company', ''),
                        title=job.get('title', ''),
                        start_date=str(job.get('start_date', '')),
                        end_date=str(job.get('end_date', '')),
                        is_current=job.get('is_current', False),
                        key_achievements=job.get('key_achievements', [])[:5],
                        technologies_used=job.get('technologies_used', [])
                    ))

            # Skills - handle expanded format from GPT-4o
            skills_data = data.get('skills', {})
            if isinstance(skills_data, list):
                # Handle flat list
                skills = Skills(
                    technical=normalize_skills(skills_data),
                    tools=[],
                    soft_skills=[]
                )
            elif isinstance(skills_data, dict):
                # Combine all technical skill categories
                all_technical = []
                for key in ['programming_languages', 'frameworks', 'databases',
                           'cloud_platforms', 'devops_tools', 'other_technical', 'technical']:
                    all_technical.extend(skills_data.get(key, []))

                skills = Skills(
                    technical=normalize_skills(all_technical),
                    tools=normalize_skills(skills_data.get('tools', [])),
                    soft_skills=skills_data.get('soft_skills', [])
                )
            else:
                skills = Skills()

            # Education
            education = []
            for edu in data.get('education', []):
                if isinstance(edu, dict):
                    education.append(Education(
                        degree=edu.get('degree', ''),
                        field_of_study=edu.get('field_of_study', ''),
                        institution=edu.get('institution', ''),
                        graduation_year=safe_int(edu.get('graduation_year'))
                    ))
                elif isinstance(edu, str):
                    education.append(Education(degree=edu))

            # Career trajectory
            trajectory_str = data.get('career_trajectory', 'early_career').lower()
            try:
                trajectory = CareerTrajectory(trajectory_str)
            except ValueError:
                trajectory = CareerTrajectory.EARLY_CAREER

            # Current role
            current_role = data.get('current_role', '')
            current_company = data.get('current_company', '')
            if not current_role and work_history:
                current_role = work_history[0].title
                current_company = work_history[0].company

            # Experience years
            total_exp = safe_float(data.get('total_experience_years', 0))
            if total_exp == 0 and work_history:
                total_exp = self._calculate_experience(work_history)

            profile = CandidateProfile(
                filename=filename,
                name=data.get('candidate_name', '') or data.get('name', ''),
                contact=contact,
                professional_summary=data.get('professional_summary', ''),
                work_history=work_history,
                total_experience_years=total_exp,
                relevant_experience_years=total_exp,  # Will be updated by matching engine
                current_role=current_role,
                current_company=current_company,
                skills=skills,
                education=education,
                career_trajectory=trajectory,
                red_flags=data.get('red_flags', [])
            )

            # Add certifications to skills
            certs = data.get('certifications', [])
            if certs:
                profile.skills.certifications = certs

            print(f"[Resume Parser] AI extracted: {profile.name} | {current_role} | {total_exp}yrs")
            return profile

        except Exception as e:
            print(f"[Resume Parser] Error building profile: {e}")
            return CandidateProfile(filename=filename)

    def _extract_with_regex(self, text: str, filename: str) -> CandidateProfile:
        """Fallback regex extraction when AI fails."""
        lines = text.split('\n')

        # Extract contact info
        contact = ContactInfo(
            email=extract_email(text),
            phone=extract_phone(text),
            linkedin=extract_linkedin(text),
            github=extract_github(text),
            location=self._extract_location_regex(text, lines)
        )

        # Extract name
        name = self._extract_name_regex(lines, filename)

        # Extract current role
        current_role, current_company = self._extract_current_role_regex(lines)

        # Extract experience years
        exp_years = self._extract_experience_regex(text, lines)

        # Extract skills
        skills_list = self._extract_skills_regex(lines)
        skills = Skills(technical=normalize_skills(skills_list))

        # Extract education
        education = self._extract_education_regex(text)

        return CandidateProfile(
            filename=filename,
            name=name,
            contact=contact,
            total_experience_years=exp_years,
            relevant_experience_years=exp_years,
            current_role=current_role,
            current_company=current_company,
            skills=skills,
            education=[Education(degree=education)] if education else [],
            career_trajectory=CareerTrajectory.EARLY_CAREER,
            raw_text=text
        )

    def _extract_name_regex(self, lines: List[str], filename: str) -> str:
        """Extract candidate name from resume."""
        for line in lines[:10]:
            line = line.strip()
            if not line or len(line) < 3 or len(line) > 50:
                continue

            # Skip lines with contact info or headers
            if re.search(r'@|http|www\.|phone|mobile|email|resume|cv|address|linkedin|github|\d{6,}', line, re.I):
                continue

            # Skip job titles at top
            if re.search(r'engineer|developer|manager|analyst|designer|consultant|intern|executive|specialist|architect', line, re.I):
                continue

            words = line.split()
            if 2 <= len(words) <= 4:
                # Check if words look like names
                if all(w[0].isupper() for w in words if w and len(w) > 1):
                    return line

        # Fallback to filename
        if filename:
            name = re.sub(r'[_\-\.]', ' ', filename)
            name = re.sub(r'\.(pdf|docx?|txt|html)$', '', name, flags=re.I)
            name = re.sub(r'resume|cv', '', name, flags=re.I)
            name = name.strip()
            if name:
                return name.title()

        return "Unknown"

    def _extract_location_regex(self, text: str, lines: List[str]) -> str:
        """Extract location from contact section only."""
        # Look in first 10 lines for location patterns
        header_text = '\n'.join(lines[:10])

        # City, State/Country patterns
        patterns = [
            r'([A-Z][a-zA-Z\s]+),\s*([A-Z]{2,})\b',  # City, STATE
            r'([A-Z][a-zA-Z\s]+),\s*([A-Z][a-zA-Z]+)(?:\s|$)',  # City, Country
            r'Location[:\s]+([A-Z][a-zA-Z\s,]+)',  # Location: City
        ]

        for pattern in patterns:
            match = re.search(pattern, header_text)
            if match:
                return match.group(0).replace('Location:', '').strip()

        return ""

    def _extract_current_role_regex(self, lines: List[str]) -> tuple:
        """Extract current role and company."""
        in_exp = False

        for line in lines:
            line_clean = line.strip()
            line_lower = line_clean.lower()

            # Detect experience section
            if re.match(r'^(professional\s+experience|work\s+experience|employment|experience)$', line_lower):
                in_exp = True
                continue

            # Exit on other sections
            if re.match(r'^(education|skills|technical\s+skills|projects|certifications)', line_lower):
                if in_exp:
                    break
                continue

            if in_exp and line_clean:
                # Skip bullets
                if line_clean.startswith(('•', '-', '*', '–')):
                    continue

                # Pattern: Role | Company or Role at Company
                match = re.match(r'^([A-Za-z][A-Za-z\s\-/]+?)\s*[|–\-@]\s*([A-Za-z][A-Za-z\s\-/&\.]+)', line_clean)
                if match:
                    role = match.group(1).strip()
                    company = match.group(2).strip()
                    if 3 < len(role) < 60 and not re.search(r'\d{4}', role):
                        return role, company

        return "", ""

    def _extract_experience_regex(self, text: str, lines: List[str]) -> float:
        """Extract years of experience."""
        # Check for explicit mention
        exp_match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)[\s\-]*(?:of\s+)?(?:experience|exp)', text, re.I)
        if exp_match:
            years = int(exp_match.group(1))
            if 0 < years <= 40:
                return float(years)

        # Calculate from date ranges
        date_pattern = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,]*(\d{4})\s*[-–]\s*(?:Present|Current|Now|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,]*(\d{4}))'

        matches = re.findall(date_pattern, text, re.I)
        if matches:
            start_years = []
            end_years = []
            for match in matches:
                start_year = int(match[0])
                end_year = int(match[1]) if match[1] else self.current_year

                if 1990 <= start_year <= self.current_year:
                    start_years.append(start_year)
                    end_years.append(end_year)

            if start_years and end_years:
                return float(max(end_years) - min(start_years))

        return 0.0

    def _extract_skills_regex(self, lines: List[str]) -> List[str]:
        """Extract skills from resume."""
        skills = []
        in_skills = False

        for line in lines:
            line_lower = line.lower().strip()

            # Detect skills section
            if re.match(r'^(technical\s+skills?|skills?|key\s+skills?|core\s+competenc)', line_lower):
                in_skills = True
                continue

            # Exit on other sections
            if re.match(r'^(experience|work|employment|education|projects|certifications|summary)', line_lower):
                if in_skills:
                    break
                continue

            if in_skills and line.strip():
                # Parse skills line
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        items = re.split(r'[,;|•]+', parts[1])
                        for item in items:
                            item = item.strip()
                            if 2 <= len(item) <= 40:
                                skills.append(item)
                else:
                    items = re.split(r'[,;|•]+', line)
                    for item in items:
                        item = re.sub(r'^[\-\*\s•]+', '', item).strip()
                        if 2 <= len(item) <= 40:
                            skills.append(item)

        return skills[:25]

    def _extract_education_regex(self, text: str) -> str:
        """Extract highest education degree."""
        patterns = [
            r"(Ph\.?D\.?|Doctorate)",
            r"(M\.?Tech|Master'?s?|MBA|M\.?S\.?|M\.?E\.?|MCA|M\.?Com)",
            r"(B\.?Tech|Bachelor'?s?|B\.?S\.?|B\.?E\.?|BCA|B\.?Com)",
            r"(Diploma|Associate)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return match.group(1)

        return ""

    def _calculate_experience(self, work_history: List[WorkExperience]) -> float:
        """Calculate total experience from work history."""
        if not work_history:
            return 0.0

        start_years = []
        end_years = []

        for job in work_history:
            start_match = re.search(r'(\d{4})', job.start_date)
            if start_match:
                start_years.append(int(start_match.group(1)))

            if job.end_date.lower() in ['present', 'current', 'now', '']:
                end_years.append(self.current_year)
            else:
                end_match = re.search(r'(\d{4})', job.end_date)
                if end_match:
                    end_years.append(int(end_match.group(1)))

        if start_years and end_years:
            return float(max(end_years) - min(start_years))

        return 0.0


# Singleton instance
_parser_instance: Optional[ResumeParser] = None


def get_parser() -> ResumeParser:
    """Get or create singleton parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = ResumeParser()
    return _parser_instance


def parse_resume(
    resume_text: str,
    filename: str = "",
    jd_requirements: Optional[JDRequirements] = None
) -> CandidateProfile:
    """
    Convenience function to parse a single resume.

    Args:
        resume_text: Raw resume text
        filename: Original filename
        jd_requirements: Optional JD context

    Returns:
        CandidateProfile object
    """
    return get_parser().parse(resume_text, filename, jd_requirements)


def parse_resumes_batch(
    resumes: List[Dict[str, str]],
    jd_requirements: Optional[JDRequirements] = None
) -> List[CandidateProfile]:
    """
    Convenience function to parse multiple resumes.

    Args:
        resumes: List of {"filename": str, "text": str} dicts
        jd_requirements: Optional JD context

    Returns:
        List of CandidateProfile objects
    """
    return get_parser().parse_batch(resumes, jd_requirements)
