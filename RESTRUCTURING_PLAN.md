# Smart-Screener Restructuring Plan

## Executive Summary

This plan transforms Smart-Screener from a basic keyword-matching system into an **industry-standard AI-powered ATS** that operates like a skilled recruiter. The restructuring focuses on accurate skill extraction, semantic matching, experience level assessment, and detailed candidate reports—all while staying within Vercel serverless and Groq free tier constraints.

---

## Table of Contents

1. [Current State Analysis](#current-state-analysis)
2. [Target Architecture](#target-architecture)
3. [Phase 1: Foundation Restructure](#phase-1-foundation-restructure)
4. [Phase 2: Intelligent JD Parsing](#phase-2-intelligent-jd-parsing)
5. [Phase 3: Advanced Resume Parsing](#phase-3-advanced-resume-parsing)
6. [Phase 4: Recruiter-Grade Matching Engine](#phase-4-recruiter-grade-matching-engine)
7. [Phase 5: Detailed Candidate Reports](#phase-5-detailed-candidate-reports)
8. [Phase 6: Optimization & Caching](#phase-6-optimization--caching)
9. [Implementation Timeline](#implementation-timeline)
10. [File Structure](#file-structure)

---

## Current State Analysis

### Problems Identified

| Issue | Impact | Current Behavior |
|-------|--------|------------------|
| No JD parsing | Critical | JD used as raw text, no requirement extraction |
| Keyword matching only | Critical | `"python" in jd.lower()` - no semantic understanding |
| Dual extraction logic | High | Frontend & backend both extract, inconsistent results |
| Location extraction broken | High | Returns empty string if AI fails |
| No skill normalization | High | "JS" ≠ "JavaScript" ≠ "javascript" |
| Sequential API calls | Medium | 20 resumes = 20 API calls = slow |
| Oversimplified scoring | Critical | Flat bonuses, no weighted matching |
| No experience matching | High | No comparison to JD requirements |
| No detailed reports | Medium | Only score + recommendation |

### Current Data Flow

```
Upload → Frontend Extract → Send to API → AI/Regex Extract → Simple Score → Display
```

**Problem**: Extraction happens twice, matching is basic keyword search, no intelligence.

---

## Target Architecture

### New Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SMART-SCREENER v5.0                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────────────────────────────────────────┐ │
│  │   JOB DESC   │ →  │  JD PARSER MODULE                                │ │
│  │   (Input)    │    │  ├─ Extract required_skills[]                    │ │
│  └──────────────┘    │  ├─ Extract preferred_skills[]                   │ │
│                      │  ├─ Extract min_experience (years)               │ │
│                      │  ├─ Extract max_experience (years)               │ │
│                      │  ├─ Extract required_education                   │ │
│                      │  ├─ Extract job_level (junior/mid/senior/lead)  │ │
│                      │  ├─ Extract industry_keywords[]                  │ │
│                      │  └─ Extract responsibilities[]                   │ │
│                      └──────────────────────────────────────────────────┘ │
│                                        ↓                                   │
│                      ┌──────────────────────────────────────────────────┐ │
│                      │  SKILL TAXONOMY (Static JSON)                    │ │
│                      │  ├─ Skill synonyms (JS → JavaScript)            │ │
│                      │  ├─ Skill categories (Languages, Frameworks...)  │ │
│                      │  ├─ Skill relationships (React requires JS)      │ │
│                      │  └─ Industry mappings                            │ │
│                      └──────────────────────────────────────────────────┘ │
│                                        ↓                                   │
│  ┌──────────────┐    ┌──────────────────────────────────────────────────┐ │
│  │   RESUMES    │ →  │  RESUME PARSER MODULE (Single AI call)          │ │
│  │   (Upload)   │    │  ├─ Extract contact_info                        │ │
│  └──────────────┘    │  ├─ Extract skills[] (normalized)               │ │
│                      │  ├─ Extract work_history[]                       │ │
│                      │  │   └─ {company, role, duration, highlights}    │ │
│                      │  ├─ Extract total_experience (calculated)        │ │
│                      │  ├─ Extract education[]                          │ │
│                      │  ├─ Extract certifications[]                     │ │
│                      │  └─ Extract career_trajectory                    │ │
│                      └──────────────────────────────────────────────────┘ │
│                                        ↓                                   │
│                      ┌──────────────────────────────────────────────────┐ │
│                      │  MATCHING ENGINE                                 │ │
│                      │  ├─ Skill Match Score (weighted by importance)  │ │
│                      │  ├─ Experience Match Score                       │ │
│                      │  ├─ Education Match Score                        │ │
│                      │  ├─ Career Progression Score                     │ │
│                      │  ├─ Industry Relevance Score                     │ │
│                      │  └─ Final Weighted Score (0-100)                │ │
│                      └──────────────────────────────────────────────────┘ │
│                                        ↓                                   │
│                      ┌──────────────────────────────────────────────────┐ │
│                      │  CANDIDATE REPORT GENERATOR                      │ │
│                      │  ├─ Overall Fit Assessment                       │ │
│                      │  ├─ Strengths (what they bring)                  │ │
│                      │  ├─ Gaps (what's missing)                        │ │
│                      │  ├─ Risk Factors (job hopping, gaps)            │ │
│                      │  ├─ Interview Focus Areas                        │ │
│                      │  └─ Recommendation (Hire/Maybe/Pass)            │ │
│                      └──────────────────────────────────────────────────┘ │
│                                        ↓                                   │
│                      ┌──────────────────────────────────────────────────┐ │
│                      │  RANKING & DISPLAY                               │ │
│                      │  ├─ Ranked candidate list                        │ │
│                      │  ├─ Detailed profile cards                       │ │
│                      │  ├─ Comparison view                              │ │
│                      │  └─ Export (CSV/Excel/PDF)                       │ │
│                      └──────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Foundation Restructure

### 1.1 New File Structure

```
smart-screener/
├── api/
│   ├── index.py              # Main Flask app (refactored)
│   ├── jd_parser.py          # JD parsing module
│   ├── resume_parser.py      # Resume parsing module
│   ├── matching_engine.py    # Scoring & matching logic
│   ├── report_generator.py   # Candidate report generation
│   ├── skill_taxonomy.py     # Skill normalization & synonyms
│   ├── utils.py              # Shared utilities
│   └── prompts/
│       ├── jd_extraction.txt     # JD parsing prompt
│       ├── resume_extraction.txt # Resume parsing prompt
│       └── report_generation.txt # Report prompt
├── data/
│   └── skills_taxonomy.json  # Static skill database
├── app.js                    # Frontend (simplified)
├── index.html
├── styles.css
├── requirements.txt
└── vercel.json
```

### 1.2 Single Source of Truth

**Remove all frontend extraction logic.** Frontend should ONLY:
- Handle file upload & text extraction (PDF → text)
- Send raw resume text to backend
- Display results

**Backend handles ALL intelligence:**
- JD parsing
- Resume parsing
- Skill normalization
- Matching
- Scoring
- Report generation

### 1.3 New API Contract

```python
# POST /api/analyze
{
    "job_description": "string (raw JD text)",
    "resumes": [
        {
            "filename": "john_doe_resume.pdf",
            "content": "string (extracted text)",
            "file_type": "pdf"
        }
    ]
}

# Response
{
    "jd_analysis": {
        "required_skills": ["Python", "React", "AWS"],
        "preferred_skills": ["Docker", "Kubernetes"],
        "min_experience": 3,
        "max_experience": 7,
        "education_required": "Bachelor's in CS or equivalent",
        "job_level": "mid-senior",
        "key_responsibilities": [...]
    },
    "candidates": [
        {
            "filename": "john_doe_resume.pdf",
            "name": "John Doe",
            "contact": {...},
            "experience_years": 5,
            "skills_matched": [...],
            "skills_missing": [...],
            "scores": {
                "overall": 85,
                "skills": 90,
                "experience": 80,
                "education": 85,
                "career_fit": 82
            },
            "report": {
                "summary": "Strong candidate with...",
                "strengths": [...],
                "gaps": [...],
                "risks": [...],
                "interview_focus": [...],
                "recommendation": "Strong Hire"
            }
        }
    ],
    "ranking": [...],  # Sorted by score
    "analysis_metadata": {
        "total_candidates": 5,
        "processing_time_ms": 2340,
        "ai_calls_made": 6
    }
}
```

---

## Phase 2: Intelligent JD Parsing

### 2.1 JD Parser Module (`api/jd_parser.py`)

The JD parser extracts structured requirements from raw job description text.

```python
# jd_parser.py structure

class JDParser:
    """
    Parses job descriptions to extract:
    - Required skills (must-have)
    - Preferred skills (nice-to-have)
    - Experience requirements (min/max years)
    - Education requirements
    - Job level (junior/mid/senior/lead/executive)
    - Industry keywords
    - Key responsibilities
    """

    def parse(self, jd_text: str) -> JDRequirements:
        """
        Single AI call to extract all JD requirements.
        Uses structured prompt for consistent output.
        """
        pass

    def normalize_skills(self, skills: list) -> list:
        """
        Normalize skill names using taxonomy.
        "JS" → "JavaScript", "k8s" → "Kubernetes"
        """
        pass
```

### 2.2 JD Extraction Prompt

```
You are an expert technical recruiter. Analyze this job description and extract structured requirements.

JOB DESCRIPTION:
{jd_text}

Extract the following in JSON format:

{
  "required_skills": [
    // Skills explicitly marked as required, must-have, or essential
    // Normalize to standard names (e.g., "JS" → "JavaScript")
  ],
  "preferred_skills": [
    // Skills marked as preferred, nice-to-have, bonus, or plus
  ],
  "min_experience_years": <number or null>,
  "max_experience_years": <number or null>,
  "experience_level": "<junior|mid|senior|lead|executive>",
  "education_required": "<degree requirement or null>",
  "certifications_preferred": [],
  "industry_keywords": [
    // Domain-specific terms (fintech, healthcare, e-commerce, etc.)
  ],
  "key_responsibilities": [
    // Top 5 main job duties
  ],
  "red_flags_to_watch": [
    // What would disqualify a candidate
  ]
}

Rules:
1. If experience not specified, infer from level (junior=0-2, mid=2-5, senior=5-10, lead=8+)
2. Distinguish between required vs preferred carefully
3. Extract implicit requirements (e.g., "fast-paced" implies good at multitasking)
4. Normalize all skill names to standard forms
```

### 2.3 Why This Matters

**Before (Current System):**
```
JD: "Looking for a senior Python developer with React experience..."
Processing: jd.lower() contains "python" → match!
Problem: No understanding of seniority, no distinction required/preferred
```

**After (New System):**
```
JD: "Looking for a senior Python developer with React experience..."
Processing:
  - required_skills: ["Python"]
  - preferred_skills: ["React"]
  - experience_level: "senior"
  - min_experience: 5
```

---

## Phase 3: Advanced Resume Parsing

### 3.1 Resume Parser Module (`api/resume_parser.py`)

```python
# resume_parser.py structure

class ResumeParser:
    """
    Extracts structured data from resume text.
    Single AI call per resume for efficiency.
    """

    def parse(self, resume_text: str, jd_context: JDRequirements) -> CandidateProfile:
        """
        Parse resume with JD context for better relevance extraction.
        """
        pass

    def calculate_experience(self, work_history: list) -> float:
        """
        Calculate total years of relevant experience.
        Handles overlapping dates, part-time, etc.
        """
        pass

    def detect_career_trajectory(self, work_history: list) -> str:
        """
        Analyze career progression:
        - Rising: Clear upward movement
        - Lateral: Same-level moves
        - Mixed: Combination
        - Declining: Downward movement (red flag)
        """
        pass
```

### 3.2 Resume Extraction Prompt

```
You are an expert resume analyzer. Extract structured information from this resume.

RESUME:
{resume_text}

JOB CONTEXT (for relevance):
Role: {job_title}
Required Skills: {required_skills}

Extract in JSON format:

{
  "candidate_name": "<full name>",
  "contact": {
    "email": "<email or null>",
    "phone": "<phone or null>",
    "linkedin": "<linkedin url or null>",
    "location": "<city, state/country>"
  },
  "professional_summary": "<1-2 sentence summary of candidate>",
  "work_history": [
    {
      "company": "<company name>",
      "title": "<job title>",
      "start_date": "<YYYY-MM or YYYY>",
      "end_date": "<YYYY-MM or 'Present'>",
      "duration_months": <calculated months>,
      "is_relevant": <true if relevant to job>,
      "key_achievements": ["<achievement 1>", "<achievement 2>"]
    }
  ],
  "total_experience_years": <calculated from work history>,
  "relevant_experience_years": <only counting relevant roles>,
  "skills": {
    "technical": ["<normalized skill names>"],
    "tools": ["<tools and platforms>"],
    "soft_skills": ["<communication, leadership, etc.>"]
  },
  "education": [
    {
      "degree": "<degree name>",
      "field": "<field of study>",
      "institution": "<school name>",
      "year": <graduation year or null>
    }
  ],
  "certifications": ["<cert name>"],
  "career_trajectory": "<rising|lateral|mixed|declining>",
  "red_flags": [
    // Job hopping (3+ jobs in 2 years)
    // Large gaps (6+ months unexplained)
    // Declining responsibilities
    // Other concerns
  ]
}

Rules:
1. Calculate experience from actual dates, not claims
2. Normalize all skill names (JS → JavaScript, k8s → Kubernetes)
3. Mark relevance based on job context
4. Identify achievements vs responsibilities
5. Flag any concerning patterns honestly
```

### 3.3 Key Improvements

| Aspect | Before | After |
|--------|--------|-------|
| Skills | Raw list from "Skills:" section | Categorized (technical/tools/soft), normalized |
| Experience | Regex on "X years experience" | Calculated from actual work dates |
| Work History | Current role only | Full history with achievements |
| Education | First degree found | All degrees with relevance |
| Red Flags | None | Job hopping, gaps, trajectory |

---

## Phase 4: Recruiter-Grade Matching Engine

### 4.1 Matching Engine Module (`api/matching_engine.py`)

```python
class MatchingEngine:
    """
    Implements recruiter-level matching logic.
    Goes beyond keyword matching to understand fit.
    """

    def calculate_match(
        self,
        candidate: CandidateProfile,
        jd: JDRequirements
    ) -> MatchResult:
        """
        Calculate comprehensive match score.
        """
        return MatchResult(
            overall_score=self._weighted_average(scores),
            skill_score=self._skill_match(candidate, jd),
            experience_score=self._experience_match(candidate, jd),
            education_score=self._education_match(candidate, jd),
            career_fit_score=self._career_fit(candidate, jd),
            breakdown=detailed_breakdown
        )
```

### 4.2 Scoring Algorithm (Recruiter Logic)

```python
def calculate_scores(candidate, jd):
    scores = {}

    # ═══════════════════════════════════════════════════════════
    # SKILL MATCH SCORE (40% of total)
    # ═══════════════════════════════════════════════════════════
    required_skills = set(normalize(jd.required_skills))
    preferred_skills = set(normalize(jd.preferred_skills))
    candidate_skills = set(normalize(candidate.skills.all()))

    # Required skill coverage (0-100)
    required_matched = required_skills & candidate_skills
    required_coverage = len(required_matched) / len(required_skills) * 100

    # Preferred skill bonus (0-20)
    preferred_matched = preferred_skills & candidate_skills
    preferred_bonus = len(preferred_matched) / max(len(preferred_skills), 1) * 20

    # Related skills bonus (using taxonomy)
    related_bonus = calculate_related_skills_bonus(candidate_skills, required_skills)

    scores['skills'] = min(100, required_coverage + preferred_bonus + related_bonus)

    # ═══════════════════════════════════════════════════════════
    # EXPERIENCE MATCH SCORE (30% of total)
    # ═══════════════════════════════════════════════════════════
    candidate_exp = candidate.relevant_experience_years
    min_exp = jd.min_experience_years or 0
    max_exp = jd.max_experience_years or 15

    if candidate_exp < min_exp:
        # Under-qualified: penalize proportionally
        exp_score = max(0, 100 - (min_exp - candidate_exp) * 20)
    elif candidate_exp > max_exp + 3:
        # Over-qualified: slight penalty (might get bored)
        exp_score = max(70, 100 - (candidate_exp - max_exp) * 5)
    else:
        # Sweet spot
        exp_score = 100

    # Relevant experience bonus
    relevance_ratio = candidate.relevant_experience_years / max(candidate.total_experience_years, 1)
    exp_score = exp_score * (0.7 + 0.3 * relevance_ratio)

    scores['experience'] = exp_score

    # ═══════════════════════════════════════════════════════════
    # EDUCATION MATCH SCORE (15% of total)
    # ═══════════════════════════════════════════════════════════
    if not jd.education_required:
        scores['education'] = 100  # No requirement
    else:
        education_match = match_education(candidate.education, jd.education_required)
        scores['education'] = education_match

    # ═══════════════════════════════════════════════════════════
    # CAREER FIT SCORE (15% of total)
    # ═══════════════════════════════════════════════════════════
    career_score = 100

    # Career trajectory
    if candidate.career_trajectory == 'rising':
        career_score += 10
    elif candidate.career_trajectory == 'declining':
        career_score -= 20

    # Red flags penalty
    career_score -= len(candidate.red_flags) * 10

    # Job level alignment
    level_match = match_job_level(candidate.current_level, jd.experience_level)
    career_score = career_score * level_match

    scores['career_fit'] = max(0, min(100, career_score))

    # ═══════════════════════════════════════════════════════════
    # OVERALL SCORE (Weighted Average)
    # ═══════════════════════════════════════════════════════════
    weights = {
        'skills': 0.40,
        'experience': 0.30,
        'education': 0.15,
        'career_fit': 0.15
    }

    overall = sum(scores[k] * weights[k] for k in weights)

    return {
        'overall': round(overall),
        'skills': round(scores['skills']),
        'experience': round(scores['experience']),
        'education': round(scores['education']),
        'career_fit': round(scores['career_fit'])
    }
```

### 4.3 Recommendation Mapping

```python
def get_recommendation(overall_score, red_flags, skill_coverage):
    """
    Recruiter-style recommendation based on multiple factors.
    """

    # Hard disqualifiers
    if skill_coverage < 50:  # Missing too many required skills
        return {
            "decision": "Pass",
            "confidence": "High",
            "reason": "Missing critical required skills"
        }

    if len(red_flags) >= 3:  # Too many concerns
        return {
            "decision": "Pass",
            "confidence": "Medium",
            "reason": "Multiple red flags identified"
        }

    # Score-based recommendations
    if overall_score >= 85:
        return {
            "decision": "Strong Hire",
            "confidence": "High",
            "reason": "Excellent match across all criteria"
        }
    elif overall_score >= 75:
        return {
            "decision": "Hire",
            "confidence": "Medium-High",
            "reason": "Strong candidate with minor gaps"
        }
    elif overall_score >= 65:
        return {
            "decision": "Maybe",
            "confidence": "Medium",
            "reason": "Potential fit, requires interview to confirm"
        }
    elif overall_score >= 50:
        return {
            "decision": "Weak Maybe",
            "confidence": "Low",
            "reason": "Significant gaps, only if pipeline is thin"
        }
    else:
        return {
            "decision": "Pass",
            "confidence": "High",
            "reason": "Does not meet minimum requirements"
        }
```

---

## Phase 5: Detailed Candidate Reports

### 5.1 Report Generator Module (`api/report_generator.py`)

```python
class ReportGenerator:
    """
    Generates recruiter-style candidate assessments.
    """

    def generate(
        self,
        candidate: CandidateProfile,
        jd: JDRequirements,
        match_result: MatchResult
    ) -> CandidateReport:
        """
        Generate comprehensive candidate report.
        """
        return CandidateReport(
            summary=self._generate_summary(candidate, match_result),
            strengths=self._identify_strengths(candidate, jd),
            gaps=self._identify_gaps(candidate, jd),
            risks=self._assess_risks(candidate),
            interview_focus=self._suggest_interview_focus(candidate, jd),
            recommendation=self._get_recommendation(match_result)
        )
```

### 5.2 Report Structure

```python
{
    "summary": "Senior Python developer with 6 years of experience,
                strong backend skills but limited React exposure.
                Good trajectory from mid to senior roles at reputable companies.",

    "strengths": [
        "✓ Exceeds experience requirement (6 years vs 3-5 required)",
        "✓ Strong Python expertise with Django/FastAPI",
        "✓ AWS experience matches infrastructure needs",
        "✓ Led team of 4 at previous company (leadership potential)",
        "✓ Rising career trajectory with promotions"
    ],

    "gaps": [
        "△ React experience limited (2 small projects vs core requirement)",
        "△ No Kubernetes experience (preferred skill)",
        "△ E-commerce domain experience missing"
    ],

    "risks": [
        "⚠ 3 jobs in 4 years - verify reasons for changes",
        "⚠ 6-month gap in 2022 - clarify during interview"
    ],

    "interview_focus": [
        "Deep dive on React projects - assess learning curve",
        "Understand reasons for job changes",
        "Verify team leadership claims with examples",
        "Assess interest in e-commerce domain"
    ],

    "recommendation": {
        "decision": "Hire",
        "confidence": "Medium-High",
        "reason": "Strong Python skills compensate for React gap.
                   Candidate shows ability to learn. Worth interviewing."
    }
}
```

### 5.3 Report Display (Frontend)

New candidate card design:

```
┌─────────────────────────────────────────────────────────────────────┐
│  👤 John Doe                                    Score: 82/100       │
│  Senior Python Developer @ TechCorp             ⭐ STRONG HIRE      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  📊 SCORE BREAKDOWN                                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Skills      ████████████████████░░░░ 85%                    │   │
│  │ Experience  ██████████████████████░░ 90%                    │   │
│  │ Education   ████████████████░░░░░░░░ 75%                    │   │
│  │ Career Fit  ██████████████████░░░░░░ 80%                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ✅ STRENGTHS                                                       │
│  • 6 years Python experience (exceeds 3-5 requirement)             │
│  • Strong AWS and backend architecture skills                       │
│  • Team leadership experience                                       │
│                                                                     │
│  ⚠️ GAPS TO ADDRESS                                                 │
│  • Limited React experience (core requirement)                      │
│  • No Kubernetes exposure                                           │
│                                                                     │
│  🎯 INTERVIEW FOCUS                                                 │
│  • Deep dive on frontend capabilities                               │
│  • Understand job change frequency                                  │
│                                                                     │
│  📧 john.doe@email.com  📱 +1-555-0123  🔗 linkedin.com/in/johndoe │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phase 6: Optimization & Caching

### 6.1 API Call Optimization

**Current**: 1 AI call per resume = N calls for N resumes

**Optimized Strategy**:

```python
# Total AI calls for analyzing 20 resumes:
# - 1 call: JD parsing (done once)
# - 1 call: Batch resume analysis (20 resumes combined)
# - Total: 2 calls (vs current 20 calls)

# Alternative for very long resumes:
# - 1 call: JD parsing
# - 4 calls: 5 resumes per batch
# - Total: 5 calls (still 75% reduction)
```

### 6.2 Batched Resume Analysis

```python
def batch_analyze_resumes(resumes: list, jd: JDRequirements) -> list:
    """
    Analyze multiple resumes in a single AI call.
    """

    # Build combined prompt
    prompt = f"""
    Analyze these {len(resumes)} resumes against the job requirements.

    JOB REQUIREMENTS:
    {json.dumps(jd.to_dict())}

    RESUMES:
    """

    for i, resume in enumerate(resumes):
        prompt += f"""
        === RESUME {i+1}: {resume.filename} ===
        {resume.content[:3000]}  # Truncate each
        """

    prompt += """
    Return JSON array with analysis for each resume...
    """

    # Single AI call
    response = call_ai(prompt, max_tokens=4000)

    return parse_batch_response(response)
```

### 6.3 Caching Strategy

```python
# Cache JD analysis (same JD = same parsed requirements)
@cache(key=lambda jd: hash(jd), ttl=3600)
def parse_job_description(jd_text: str) -> JDRequirements:
    pass

# Cache skill taxonomy (static data)
@cache(key="taxonomy", ttl=86400)
def load_skill_taxonomy() -> dict:
    return json.load(open('data/skills_taxonomy.json'))

# Hash-based resume deduplication
def get_resume_hash(content: str) -> str:
    return hashlib.md5(content.encode()).hexdigest()

# Skip re-analysis of identical resumes
if resume_hash in analysis_cache:
    return analysis_cache[resume_hash]
```

### 6.4 Free Tier Optimization

| Strategy | API Calls Saved |
|----------|----------------|
| JD caching | ~50% (same JD reused) |
| Batched analysis | ~80% (20 → 4 calls) |
| Resume deduplication | ~10% (duplicate uploads) |
| **Total Savings** | **~90%** |

---

## Implementation Timeline

### Phase 1: Foundation (Week 1)
- [ ] Restructure file organization
- [ ] Remove frontend extraction logic
- [ ] Create new API contract
- [ ] Setup module skeleton files

### Phase 2: JD Parser (Week 1-2)
- [ ] Implement JD parser module
- [ ] Create JD extraction prompt
- [ ] Add skill normalization
- [ ] Test with various JD formats

### Phase 3: Resume Parser (Week 2)
- [ ] Implement resume parser module
- [ ] Create resume extraction prompt
- [ ] Add experience calculation
- [ ] Add red flag detection

### Phase 4: Matching Engine (Week 3)
- [ ] Implement scoring algorithm
- [ ] Add weighted matching
- [ ] Create recommendation logic
- [ ] Test accuracy

### Phase 5: Reports (Week 3-4)
- [ ] Implement report generator
- [ ] Update frontend UI
- [ ] Add detailed candidate cards
- [ ] Add comparison view

### Phase 6: Optimization (Week 4)
- [ ] Implement batched analysis
- [ ] Add caching layer
- [ ] Performance testing
- [ ] Final polish

---

## File Structure (Final)

```
smart-screener/
├── api/
│   ├── index.py                 # Main Flask app (entry point)
│   ├── jd_parser.py             # Job description parsing
│   ├── resume_parser.py         # Resume parsing & extraction
│   ├── matching_engine.py       # Scoring & matching logic
│   ├── report_generator.py      # Candidate report generation
│   ├── skill_taxonomy.py        # Skill normalization utilities
│   ├── utils.py                 # Shared utilities (AI calls, etc.)
│   ├── models.py                # Data classes / schemas
│   └── prompts/
│       ├── jd_extraction.txt
│       ├── resume_extraction.txt
│       ├── batch_analysis.txt
│       └── report_generation.txt
├── data/
│   └── skills_taxonomy.json     # Skill synonyms, categories
├── frontend/
│   ├── app.js                   # Simplified frontend logic
│   ├── components/
│   │   ├── upload.js            # File upload handling
│   │   ├── results.js           # Results display
│   │   └── report.js            # Candidate report view
│   └── utils/
│       └── pdf-extract.js       # PDF text extraction
├── index.html                   # Main HTML
├── styles.css                   # Styling
├── requirements.txt             # Python dependencies
├── vercel.json                  # Vercel config
└── README.md                    # Documentation
```

---

## Success Metrics

After implementation, measure:

1. **Skill Match Accuracy**: % of correctly identified skill matches
2. **Experience Accuracy**: Error margin in years calculation
3. **Recommendation Quality**: User feedback on hire/pass decisions
4. **Processing Speed**: Time to analyze 20 resumes
5. **API Cost**: Calls per analysis session

**Target Metrics:**
- Skill accuracy: >90%
- Experience accuracy: ±0.5 years
- Speed: <30 seconds for 20 resumes
- API calls: <5 per session (vs current 20+)

---

## Summary

This restructuring transforms Smart-Screener from a basic keyword matcher into a **recruiter-grade screening system** by:

1. **Parsing JDs intelligently** - Extracting requirements, not just text
2. **Deep resume analysis** - Work history, skills, red flags
3. **Weighted matching** - Skills matter more than education
4. **Detailed reports** - Actionable insights for hiring decisions
5. **Optimized for free tier** - Batching and caching reduce costs 90%

The result is a system that thinks like a skilled recruiter while operating within Vercel serverless and Groq free tier constraints.
