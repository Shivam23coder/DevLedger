"""
Narrative advisor: the LLM reasoning half of the recommendation engine.
Uses Groq's OpenAI-compatible chat completions endpoint via httpx -
no extra SDK dependency needed.
"""
import httpx

from app.config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"


def _build_prompt(gaps: list[dict], repos: list[dict], claimed_skills: list[str]) -> str:
    repo_summary = "\n".join(
        f"- {r['name']}: {', '.join(r['languages']) or 'no languages detected'}"
        f"{' (has CI)' if r.get('has_ci') else ''}"
        for r in repos
    ) or "No repositories analyzed."

    gap_summary = "\n".join(f"- {g['skill']}: {g['reason']}" for g in gaps) or "No gaps detected."

    return f"""You are reviewing a developer's GitHub repositories against their resume's claimed skills.

Claimed skills: {', '.join(claimed_skills) or 'none detected'}

Repositories analyzed:
{repo_summary}

Gaps detected (claimed but no supporting repo evidence):
{gap_summary}

Write 4-6 lines of direct, specific, actionable advice for this developer, in the voice
of an experienced engineering mentor. Reference their actual repos and gaps by name. Do not
restate the raw data back at them - synthesize it into one clear recommendation about what to
build or learn next and why it matters. No preamble, no bullet points, just the advice."""


def _generate_fallback_advice(gaps: list[dict], repos: list[dict], claimed_skills: list[str]) -> str:
    repo_names = [r["name"] for r in repos[:3]]
    repo_str = ", ".join(f"'{n}'" for n in repo_names) if repo_names else "your repositories"

    languages = list({l for r in repos for l in r.get("languages", []) if l})
    lang_str = ", ".join(languages[:3]) if languages else "software engineering"

    gap_skills = [g["skill"] for g in gaps]

    if gap_skills:
        top_gaps = ", ".join(f"'{s}'" for s in gap_skills[:2])
        target_repo = f"'{repo_names[0]}'" if repo_names else "your primary project"
        return (
            f"You have demonstrated hands-on development in {lang_str} across repositories such as {repo_str}.\n"
            f"However, while your resume claims proficiency in {top_gaps}, your analyzed repositories currently lack manifest dependencies or code evidence for them.\n"
            f"To bridge this divide, we recommend integrating {top_gaps} directly into {target_repo} with realistic integration tests.\n"
            f"Additionally, adding a Dockerfile and GitHub Actions workflow will establish verifiable production readiness.\n"
            f"Focusing on backing these specific claims with clean commits will significantly strengthen your technical credibility."
        )
    else:
        return (
            f"Great work! Your analyzed repositories ({repo_str}) present consistent and verifiable code evidence supporting your claimed skills in {lang_str}.\n"
            f"The codebase demonstrates sound software engineering practices and clear repository structure.\n"
            f"To elevate your profile to senior engineering standards, consider implementing automated CI/CD pipelines across all repositories.\n"
            f"Furthermore, introducing containerization with Docker and end-to-end integration testing will showcase enterprise-ready engineering depth.\n"
            f"Continuing to document architecture decisions in comprehensive READMEs will make your portfolio stand out even further."
        )


async def generate_narrative_advice(
    gaps: list[dict],
    repos: list[dict],
    claimed_skills: list[str],
    client: httpx.AsyncClient | None = None,
) -> str:
    if not settings.groq_api_key:
        print("[Advisor] GROQ_API_KEY not set. Using system fallback (hardcoded) response.")
        return _generate_fallback_advice(gaps, repos, claimed_skills)

    try:
        should_close = False
        if client is None:
            client = httpx.AsyncClient()
            should_close = True

        try:
            response = await client.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                json={
                    "model": MODEL,
                    "messages": [{"role": "user", "content": _build_prompt(gaps, repos, claimed_skills)}],
                    "max_tokens": 500,
                },
                timeout=30,
            )
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                if content and content.strip():
                    print("[Advisor] Successfully generated advice using Groq LLM (llama-3.1-8b-instant).")
                    return content.strip()
            else:
                print(f"[Advisor] Groq API returned status {response.status_code}: {response.text}")
        finally:
            if should_close:
                await client.aclose()
    except Exception as e:
        print(f"[Advisor] Groq API call failed: {e}")

    print("[Advisor] Falling back to system (hardcoded) response.")
    return _generate_fallback_advice(gaps, repos, claimed_skills)