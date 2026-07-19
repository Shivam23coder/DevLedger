"""
Resume agent: parses a PDF resume for (1) claimed skills via context-aware
keyword matching and (2) social/profile links - including links hidden behind
hyperlinked text like "GitHub", which plain text extraction misses.

Uses PyMuPDF (fitz) because it exposes link annotations (page.get_links()),
not just the visible text layer. pypdf/PyPDF2 alone cannot do this.

Auto-Verify (no LLM): each detected skill is scored 0-100 based purely on
*where* it appears in the resume (Skills section, Experience, Projects,
Education, or nowhere prominent). This confidence score travels downstream
so the gap detector and frontend can prioritise which gaps actually matter.
"""
import re
from collections import defaultdict

import fitz  # PyMuPDF

# ---------------------------------------------------------------------------
# Skill vocabulary
# Kept flat deliberately: a v2 would use an embedding-based taxonomy, but
# keyword matching is transparent and easy to debug for v1.
# ---------------------------------------------------------------------------
SKILL_KEYWORDS = [
    "python", "java", "javascript", "typescript", "c++", "go", "rust",
    "react", "next.js", "node.js", "django", "flask", "fastapi", "spring boot",
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "docker", "kubernetes", "aws", "gcp", "azure", "terraform",
    "ci/cd", "github actions", "jenkins",
    "machine learning", "tensorflow", "pytorch", "nlp",
    "graphql", "rest api", "microservices", "kafka", "rabbitmq",
    "competitive programming", "algorithms", "data structures",
]

# ---------------------------------------------------------------------------
# Profile link patterns
# ---------------------------------------------------------------------------
LINK_PATTERNS = {
    "github": re.compile(r"github\.com/[\w\-]+", re.I),
    "linkedin": re.compile(r"linkedin\.com/in/[\w\-]+", re.I),
    "leetcode": re.compile(r"leetcode\.com/(?:u/)?[\w\-]+", re.I),
    "codeforces": re.compile(r"codeforces\.com/(?:profile|submissions)/[\w\-]+", re.I),
    "codechef": re.compile(r"codechef\.com/users/[\w\-]+", re.I),
}

# ---------------------------------------------------------------------------
# Section detection
# ---------------------------------------------------------------------------

# Known header titles mapped to canonical section names.
# Order matters: first match wins per line.
_SECTION_HEADERS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(technical\s+skills?|skills?|technologies|tech\s+stack|core\s+competencies|expertise)\b", re.I), "skills"),
    (re.compile(r"\b(work\s+experience|experience|employment|professional\s+experience|career)\b", re.I), "experience"),
    (re.compile(r"\b(projects?|personal\s+projects?|side\s+projects?|open.?source)\b", re.I), "projects"),
    (re.compile(r"\b(education|academic|university|college|degree|schooling)\b", re.I), "education"),
    (re.compile(r"\b(certifications?|awards?|achievements?|publications?|research)\b", re.I), "other"),
]


def _is_section_header(line: str) -> bool:
    """Heuristic: a line is a section header if it's short, has no sentence-ending
    punctuation, is all-caps or title-case, or ends with a colon."""
    stripped = line.strip()
    if not stripped or len(stripped) > 60:
        return False
    if stripped.endswith(":"):
        return True
    if stripped.isupper() and len(stripped) > 2:
        return True
    # Title-case check: most words start with uppercase, no lowercase runs
    words = stripped.split()
    if len(words) <= 4 and sum(w[0].isupper() for w in words if w) >= len(words) * 0.75:
        return True
    return False


def detect_resume_sections(text: str) -> dict[str, str]:
    """Split raw PDF text into named sections.

    Returns a dict mapping section name → concatenated text for that section.
    Unclassified lines go into "other". If no section headers are found at all
    (e.g., a heavily-visual PDF), everything lands in "other".
    """
    sections: dict[str, list[str]] = defaultdict(list)
    current_section = "other"

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # Try to classify as a header
        if _is_section_header(stripped):
            matched = False
            for pattern, section_name in _SECTION_HEADERS:
                if pattern.search(stripped):
                    current_section = section_name
                    matched = True
                    break
            if not matched:
                # It looks like a header but we don't recognise the name —
                # treat it as an "other" section so the previous context ends.
                current_section = "other"
            continue  # don't add the header text itself to the section body

        sections[current_section].append(stripped)

    return {k: "\n".join(v) for k, v in sections.items()}


# ---------------------------------------------------------------------------
# Skill scoring
# ---------------------------------------------------------------------------

# Points awarded per section in which a skill appears
_SECTION_SCORES: dict[str, int] = {
    "skills": 40,
    "experience": 35,
    "projects": 25,
    "education": 10,
    "other": 5,
}

# Confidence bands
_CONFIDENCE_HIGH = 60
_CONFIDENCE_MEDIUM = 30


def _skill_pattern(skill: str) -> re.Pattern:
    """Boundary-safe regex for a skill keyword.
    Uses lookaround instead of \\b because \\b breaks on skills like
    'c++' where the boundary character isn't a word character."""
    return re.compile(
        r'(?<![a-zA-Z0-9])' + re.escape(skill) + r'(?![a-zA-Z0-9])',
        re.IGNORECASE,
    )


def score_skill_in_resume(skill: str, sections: dict[str, str]) -> tuple[int, list[str]]:
    """Score a skill 0-100 based purely on resume text context.

    Returns (score, contexts) where contexts is a list of up to 2 example
    sentences in which the skill was found.
    """
    pattern = _skill_pattern(skill)
    score = 0
    contexts: list[str] = []
    total_hits = 0

    for section_name, section_text in sections.items():
        section_points = _SECTION_SCORES.get(section_name, 5)
        hits_in_section = pattern.findall(section_text)
        if not hits_in_section:
            continue

        score += section_points
        total_hits += len(hits_in_section)

        # Collect up to 2 context sentences across all sections
        if len(contexts) < 2:
            for sentence in re.split(r'[.\n]', section_text):
                if pattern.search(sentence):
                    ctx = sentence.strip()
                    if ctx and ctx not in contexts:
                        contexts.append(ctx)
                    if len(contexts) >= 2:
                        break

    # Bonus: skill mentioned in multiple sections or more than twice
    sections_hit = sum(
        1 for st in sections.values() if pattern.search(st)
    )
    if sections_hit > 1 or total_hits > 2:
        score += 10

    # Penalty: appeared exactly once in a low-prominence area
    if total_hits == 1 and score <= _SECTION_SCORES["other"] + 10:
        score -= 10

    score = max(0, min(100, score))  # clamp to [0, 100]
    return score, contexts


def _confidence_band(score: int) -> str:
    if score >= _CONFIDENCE_HIGH:
        return "high"
    if score >= _CONFIDENCE_MEDIUM:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

def extract_text_and_links(pdf_bytes: bytes) -> tuple[str, list[str]]:
    """Returns (full_text, list_of_hyperlink_uris) from annotation links,
    which is where 'GitHub' as clickable text actually stores its URL."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    full_text = ""
    hyperlinks: list[str] = []

    for page in doc:
        full_text += page.get_text()
        for link in page.get_links():
            uri = link.get("uri")
            if uri:
                hyperlinks.append(uri)

    return full_text, hyperlinks


# ---------------------------------------------------------------------------
# Link detection
# ---------------------------------------------------------------------------

def detect_profile_links(text: str, hyperlinks: list[str]) -> dict[str, str | None]:
    """Finds github/linkedin/leetcode links two ways:
    1. Embedded hyperlink annotations (e.g. "GitHub" text linked to a URL)
    2. Plain-text URLs typed directly (e.g. "github.com/username" as visible text)
    Hyperlink annotations take priority since they're less error-prone."""
    detected: dict[str, str | None] = {
        "github": None, "linkedin": None,
        "leetcode": None, "codeforces": None, "codechef": None,
    }

    search_spaces = hyperlinks + [text]

    for platform, pattern in LINK_PATTERNS.items():
        for space in search_spaces:
            match = pattern.search(space)
            if match:
                url = match.group(0)
                if not url.startswith("http"):
                    url = "https://" + url
                detected[platform] = url
                break

    return detected


# ---------------------------------------------------------------------------
# Skill extraction (with auto-verification)
# ---------------------------------------------------------------------------

def extract_claimed_skills(
    text: str,
    sections: dict[str, str],
) -> tuple[list[str], list[dict]]:
    """Detect skills present in the resume text and score each one.

    Returns:
        claimed_skills  — flat list[str] for backward-compatibility with
                          gap_detector.py and the DB layer (unchanged callers).
        skill_details   — list[dict] with per-skill confidence metadata:
                          {skill, score, resume_confidence, contexts}
    """
    claimed_skills: list[str] = []
    skill_details: list[dict] = []

    # If no sections were detected (purely visual PDF), fall back to scoring
    # against full text treated as "other" — gives a medium baseline.
    effective_sections = sections if sections else {"other": text}

    for skill in SKILL_KEYWORDS:
        # First check presence in full text (cheap)
        if not _skill_pattern(skill).search(text):
            continue

        score, contexts = score_skill_in_resume(skill, effective_sections)

        # A skill that scored 0 after the penalty pass was a truly incidental
        # hit — don't include it as a genuine claim.
        if score <= 0:
            continue

        claimed_skills.append(skill)
        skill_details.append({
            "skill": skill,
            "score": score,
            "resume_confidence": _confidence_band(score),
            "contexts": contexts,
        })

    # Sort by score descending so the most prominent skills come first
    skill_details.sort(key=lambda d: d["score"], reverse=True)
    # Keep claimed_skills in the same order as skill_details
    claimed_skills = [d["skill"] for d in skill_details]

    return claimed_skills, skill_details


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_resume(pdf_bytes: bytes) -> dict:
    """Parse a PDF resume and return skills + links.

    Return shape:
        claimed_skills  list[str]  — flat skill list (backward-compat)
        skill_details   list[dict] — per-skill confidence metadata (new)
        detected_links  dict       — platform → URL
    """
    text, hyperlinks = extract_text_and_links(pdf_bytes)
    sections = detect_resume_sections(text)
    claimed_skills, skill_details = extract_claimed_skills(text, sections)

    return {
        "claimed_skills": claimed_skills,
        "skill_details": skill_details,
        "detected_links": detect_profile_links(text, hyperlinks),
    }
