"""
Gap detector: the deterministic half of the recommendation engine
(see architecture diagram - 'Rules + LLM reasoning'). This module only
does the rules part: does a claimed skill have supporting evidence in
the GitHub repos? The LLM reasoning layer (turning a gap into a
personalized suggestion) is a clean seam to add next - see the
NotImplemented stub at the bottom.
"""

# Maps a resume skill keyword to the evidence signals that would support it.
# A skill "counts as evidenced" if ANY of its mapped signals is found in ANY repo.
EVIDENCE_MAP: dict[str, dict] = {
    "docker": {"dependencies": ["dockerfile"], "topics": ["docker"], "keywords": ["docker"]},
    "kubernetes": {"languages": [], "topics": ["kubernetes", "k8s"], "keywords": ["kubernetes", "k8s"]},
    "ci/cd": {"has_ci": True},
    "github actions": {"has_ci": True},
    "redis": {"dependencies": ["redis", "aioredis"], "topics": ["redis"], "keywords": ["redis"]},
    "postgresql": {"dependencies": ["psycopg2", "psycopg", "asyncpg", "pg"], "topics": ["postgresql", "postgres"], "keywords": ["postgres"]},
    "mongodb": {"dependencies": ["pymongo", "mongoose", "motor"], "topics": ["mongodb"], "keywords": ["mongo"]},
    "react": {"dependencies": ["react", "react-dom"], "languages": ["JavaScript", "TypeScript"], "topics": ["react"], "keywords": ["react"]},
    "next.js": {"dependencies": ["next"], "topics": ["nextjs", "next.js"], "keywords": ["nextjs", "next"]},
    "graphql": {"dependencies": ["graphql", "apollo-server", "graphene-python"], "topics": ["graphql"], "keywords": ["graphql"]},
    "microservices": {"topics": ["microservices"], "keywords": ["microservice"]},
    # Languages map directly to the GitHub "languages" field or LeetCode/Codeforces languages
    "python": {"languages": ["Python"]},
    "java": {"languages": ["Java"]},
    "javascript": {"languages": ["JavaScript"]},
    "typescript": {"languages": ["TypeScript"]},
    "go": {"languages": ["Go"]},
    "rust": {"languages": ["Rust"]},
    "c++": {"languages": ["C++"]},
    "flask": {"dependencies": ["flask"], "languages": ["Python"], "keywords": ["flask"]},
    "fastapi": {"dependencies": ["fastapi", "uvicorn"], "languages": ["Python"], "keywords": ["fastapi"]},
    "django": {"dependencies": ["django"], "languages": ["Python"], "keywords": ["django"]},
    "authentication": {"dependencies": ["pyjwt", "python-jose", "passlib", "bcrypt", "jsonwebtoken", "passport", "next-auth", "auth0", "firebase-admin"], "topics": ["auth", "authentication", "jwt", "oauth"], "keywords": ["auth", "jwt", "oauth", "login"]},
    "machine learning": {"dependencies": ["torch", "pytorch", "tensorflow", "scikit-learn", "sklearn", "transformers", "openai", "langchain", "pandas", "numpy"], "topics": ["machine-learning", "deep-learning", "ml", "ai"], "keywords": ["machine learning", "neural network", "transformer"]},
    "sqlalchemy": {"dependencies": ["sqlalchemy"], "topics": ["sqlalchemy", "orm"], "keywords": ["sqlalchemy"]},
    "celery": {"dependencies": ["celery"], "topics": ["celery"], "keywords": ["celery"]},
    "kafka": {"dependencies": ["kafka-python", "confluent-kafka"], "topics": ["kafka"], "keywords": ["kafka"]},
    "node.js": {"dependencies": ["express", "nest", "fastify"], "languages": ["JavaScript", "TypeScript"], "keywords": ["node"]},
    # DSA and Competitive Programming Evidence
    "competitive programming": {"codeforces": True, "codechef": True},
    "algorithms": {"codeforces_solved": 5, "leetcode_solved": 10, "codechef_solved": 5, "topics": ["algorithms"], "keywords": ["algorithm"]},
    "data structures": {"codeforces_solved": 5, "leetcode_solved": 10, "codechef_solved": 5, "topics": ["data-structures"], "keywords": ["data-structure"]},
}

SUGGESTIONS: dict[str, str] = {
    "kubernetes": "Deploy one existing project on Kubernetes before listing it prominently on your resume.",
    "docker": "Add a Dockerfile to one of your active repos to back this claim with evidence.",
    "ci/cd": "Add a GitHub Actions workflow to a repo - even a simple lint/test-on-push pipeline counts as evidence.",
    "redis": "Use Redis for caching in one project so there's a repo that backs this up.",
    "fastapi": "Add FastAPI to a project repo along with a simple route handler to demonstrate REST API experience.",
    "authentication": "Implement JWT or OAuth2 authentication in one of your project repos to verify auth experience.",
    "machine learning": "Build a simple ML model using PyTorch or Scikit-Learn in a repository to back up your ML claims.",
    "competitive programming": "Create a Codeforces or CodeChef profile and participate in contests to demonstrate competitive programming skills.",
    "algorithms": "Solve at least 10 problems on LeetCode, 5 on Codeforces, or 5 on CodeChef to demonstrate active algorithmic problem solving.",
    "data structures": "Solve problems involving key data structures (trees, graphs, heaps) on LeetCode, Codeforces, or CodeChef to demonstrate practical understanding.",
}


def _repo_matches_signal(repo: dict, signal: dict) -> bool:
    if signal.get("has_ci") and (repo.get("has_ci") or repo.get("ci_status") in ["passing", "failing"]):
        return True

    # Check dependencies extracted from manifests or build_configs (Dockerfile, Makefile, etc.)
    repo_deps = [d.lower() for d in repo.get("dependencies", [])]
    build_cfgs = [b.lower() for b in repo.get("build_configs", [])]
    combined_deps = set(repo_deps + build_cfgs)

    for dep in signal.get("dependencies", []):
        dep_lower = dep.lower()
        if any(dep_lower in d for d in combined_deps):
            return True

    repo_languages_lower = [l.lower() for l in repo.get("languages", [])]
    for lang in signal.get("languages", []):
        if lang.lower() in repo_languages_lower:
            return True

    repo_topics_lower = [t.lower() for t in repo.get("topics", [])]
    for topic in signal.get("topics", []):
        if topic.lower() in repo_topics_lower:
            return True

    haystack = " ".join(filter(None, [repo.get("description"), repo.get("name")])).lower()
    for kw in signal.get("keywords", []):
        if kw.lower() in haystack:
            return True

    return False


def _dsa_matches_signal(dsa_evidence: dict | None, signal: dict, skill: str) -> bool:
    if not dsa_evidence:
        return False
        
    lc = dsa_evidence.get("leetcode")
    cf = dsa_evidence.get("codeforces")
    cc = dsa_evidence.get("codechef")
    
    # 1. Codeforces / CodeChef requirements
    if signal.get("codeforces") and cf:
        # Having a profile with rating or solved count counts as evidenced
        if cf.get("rating") or cf.get("solved_count", 0) > 0:
            return True
    if signal.get("codechef") and cc:
        if cc.get("rating") or cc.get("solved_count", 0) > 0:
            return True
            
    # 2. Minimum solved counts for DSA concepts
    if cf and signal.get("codeforces_solved"):
        if cf.get("solved_count", 0) >= signal["codeforces_solved"]:
            return True
    if lc and signal.get("leetcode_solved"):
        if lc.get("solved_count", 0) >= signal["leetcode_solved"]:
            return True
    if cc and signal.get("codechef_solved"):
        if cc.get("solved_count", 0) >= signal["codechef_solved"]:
            return True
            
    # 3. Languages check (e.g. if the skill is "python", we can check if they solved python problems in LC/CF)
    if signal.get("languages"):
        langs_lower = [l.lower() for l in signal["languages"]]
        if lc and lc.get("languages"):
            lc_langs = [l.lower() for l in lc["languages"]]
            if any(lang in lc_langs for lang in langs_lower):
                return True
        if cf and cf.get("languages"):
            cf_langs = [l.lower() for l in cf["languages"]]
            if any(lang in cf_langs for lang in langs_lower):
                return True
                
    return False


def find_gaps(claimed_skills: list[str], repos: list[dict], dsa_evidence: dict | None = None) -> list[dict]:
    """For each claimed skill, check if any analyzed repo or DSA profile provides evidence.
    Returns a list of gap dicts for skills with no supporting evidence.
    Skills not in EVIDENCE_MAP are skipped (no rule defined yet) rather
    than flagged - avoids false positives on skills we can't verify."""
    gaps = []

    for skill in claimed_skills:
        signal = EVIDENCE_MAP.get(skill)
        if signal is None:
            continue  # no rule defined for this skill yet - skip, don't guess

        has_github_evidence = any(_repo_matches_signal(repo, signal) for repo in repos)
        has_dsa_evidence = _dsa_matches_signal(dsa_evidence, signal, skill)

        if not (has_github_evidence or has_dsa_evidence):
            gaps.append({
                "skill": skill,
                "reason": f"Resume claims '{skill}' but no analyzed repository or DSA profile shows supporting evidence.",
                "suggestion": SUGGESTIONS.get(skill, f"Build or update a project that demonstrably uses {skill}."),
            })

    return gaps


def find_unverified(claimed_skills: list[str]) -> list[str]:
    """Skills claimed on the resume with no rule in EVIDENCE_MAP at all -
    distinct from a 'gap', which means a rule exists but found no evidence.
    These must never render identically to 'evidenced' in the UI."""
    return [skill for skill in claimed_skills if skill not in EVIDENCE_MAP]


# --- Next seam: LLM reasoning layer ---
# def generate_narrative_advice(gaps: list[dict], profile_context: dict) -> str:
#     """v1.5: feed the rule-based gaps + repo/resume context to an LLM
#     to produce the kind of narrative advice in the original pitch
#     ("You've built 3 backend projects but never used caching...").
#     Keep this a separate function so the deterministic rules stay
#     testable and auditable independent of the LLM call."""
#     raise NotImplementedError
