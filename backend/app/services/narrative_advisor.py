"""
Narrative advisor: the LLM reasoning half of the recommendation engine.
Uses Groq's OpenAI-compatible chat completions endpoint via httpx -
no extra SDK dependency needed.
"""
import httpx

from app.config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"  # llama-3.3-70b-versatile was deprecated June 17, 2026


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

Write 2-4 sentences of direct, specific, actionable advice for this developer, in the voice
of an experienced engineering mentor. Reference their actual repos and gaps by name. Do not
restate the raw data back at them - synthesize it into one clear recommendation about what to
build or learn next and why it matters. No preamble, no bullet points, just the advice."""


def generate_narrative_advice(gaps: list[dict], repos: list[dict], claimed_skills: list[str]) -> str | None:
    if not settings.groq_api_key:
        return None  # no key configured - feature silently unavailable, not broken

    try:
        response = httpx.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": _build_prompt(gaps, repos, claimed_skills)}],
                "max_tokens": 300,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Narrative advisor failed: {e}")  # remove/comment out once confirmed working
        return None