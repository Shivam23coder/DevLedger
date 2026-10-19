"""
Narrative advisor: the LLM reasoning half of the recommendation engine.
Uses Groq's OpenAI-compatible chat completions endpoint via httpx -
no extra SDK dependency needed.
"""
import httpx

from app.config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"


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


def _generate_fallback_advice(gaps: list[dict], repos: list[dict], claimed_skills: list[str]) -> str:
    repo_names = [r["name"] for r in repos[:3]]
    repo_str = ", ".join(f"'{n}'" for n in repo_names) if repo_names else "your repositories"

    languages = list({l for r in repos for l in r.get("languages", []) if l})
    lang_str = ", ".join(languages[:3]) if languages else "software engineering"

    gap_skills = [g["skill"] for g in gaps]

    if gap_skills:
        top_gaps = ", ".join(f"'{s}'" for s in gap_skills[:2])
        target_repo = f"'{repo_names[0]}'" if repo_names else "your repositories"
        return (
            f"You have built projects in {lang_str} like {repo_str}. "
            f"However, while your resume claims skills in {top_gaps}, your public repositories "
            f"currently lack active package manifest or structural code evidence for them. "
            f"Consider integrating {top_gaps} into an active project like {target_repo} "
            f"to back up your resume claims with verifiable code."
        )
    else:
        return (
            f"Great job! Your analyzed repositories ({repo_str}) present clear code evidence "
            f"supporting your claimed skills in {lang_str}. To elevate your profile further, "
            f"consider adding automated CI/CD workflows and Docker configurations across your main projects."
        )


def generate_narrative_advice(gaps: list[dict], repos: list[dict], claimed_skills: list[str]) -> str:
    if not settings.groq_api_key:
        return _generate_fallback_advice(gaps, repos, claimed_skills)

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
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
            if content and content.strip():
                return content.strip()
    except Exception as e:
        print(f"Groq API call warning: {e}")

    return _generate_fallback_advice(gaps, repos, claimed_skills)