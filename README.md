# EngineerOS — v1

**Scope:** GitHub Intelligence + Resume Gap Analysis + DSA Integrations (LeetCode / Codeforces / CodeChef) + LLM Narrative Advice.

> [!NOTE]
> For the full technical architecture, DB schema, and integration specs, see [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md).

---

## What's Done ✅

### Backend (FastAPI + PostgreSQL + Redis)

| Area | Status | Details |
|---|---|---|
| **GitHub Agent** | ✅ Done | Scrapes up to 10 public repos: languages, CI presence (`.github/workflows/`), test folders, topics, stars, README. Redis-cached. |
| **Resume Agent** | ✅ Done | PyMuPDF-based PDF parser. Extracts plain text _and_ hyperlinked anchor text (e.g. `"GitHub"` → URL). Detects LeetCode, Codeforces, CodeChef, LinkedIn, GitHub profile links. |
| **DSA Agent — LeetCode** | ✅ Done | GraphQL scraper (`leetcode.com/graphql`). Returns total solved, Easy/Medium/Hard split, and languages used. |
| **DSA Agent — Codeforces** | ✅ Done | REST API (`user.info` + `user.status`). Returns rating, rank, max rating, solved count, top problem tags, and normalized languages from last 100 submissions. |
| **DSA Agent — CodeChef** | ✅ Done | HTML scraper. Parses rating, stars, global/country rank, solved count from profile page. |
| **Gap Detector** | ✅ Done | Rule-based `EVIDENCE_MAP` covering 25+ skills (languages, frameworks, infra, DSA). A skill is evidenced if ANY signal is satisfied across repos or DSA profiles. Also surfaces "unverified" skills outside the known vocabulary. |
| **Narrative Advisor** | ✅ Done | Calls Groq's OpenAI-compatible endpoint (`openai/gpt-oss-120b`). Generates 2-4 sentences of mentor-style advice referencing actual repos and gaps. Gracefully returns `null` if `GROQ_API_KEY` is not set. |
| **Profile Router** | ✅ Done | `POST /profile/analyze` — full pipeline (GitHub + resume + DSA + gaps + LLM advice), persisted to Postgres. `GET /profile/{username}` — fetch cached result without re-running. |
| **GitHub Router** | ✅ Done | `GET /github/analyze/{username}` — GitHub evidence only, no DB write. |
| **Resume Router** | ✅ Done | `POST /resume/parse` — resume-only endpoint, returns claimed skills + detected links. |
| **Database Models** | ✅ Done | SQLAlchemy ORM: `Profile`, `Repository`, `ResumeClaim`, `Gap`. Re-analysis truncates and replaces previous rows (no duplicates). |
| **Docker Compose** | ✅ Done | Postgres + Redis services, ready for `docker compose up -d`. |

### Frontend (Next.js + Tailwind)

| Component | Status | Details |
|---|---|---|
| **UploadForm** | ✅ Done | GitHub username input + PDF drag-drop. Calls `POST /profile/analyze`. |
| **EvidenceLedger** | ✅ Done | Diff-style list — green for evidenced, red for gaps, amber for unverified. |
| **SkillBreakdownChart** | ✅ Done | Pie chart visualizing evidenced vs. gap percentages. |
| **RepoGrid** | ✅ Done | Card layout per repo — language, CI/test signals, stars. |
| **DsaProfiles** | ✅ Done | Panels for LeetCode (difficulty meters), Codeforces (rating + rank + tags), CodeChef (stars + ranks). |
| **NarrativeAdvice** | ✅ Done | Renders LLM-generated mentor advice block; hidden when no advice is returned. |

---

## What's Still Pending 🔜

- **GitHub OAuth / Private Repo Access** — currently reads only public repos. Clean v1.5 addition via GitHub App or OAuth flow.
- **Skill vocabulary** — flat keyword list (`SKILL_KEYWORDS`). Embedding-based taxonomy is a good v2 upgrade once the rule-based approach proves the concept.
- **No auth on the API** — fine for local dev/demo; needs auth before any real deployment.
- **CodeChef scraper is fragile** — depends on raw HTML structure; a proper API or Selenium-based approach is the robust path.

---

## Setup

```bash
# 1. Start Postgres + Redis
docker compose up -d

# 2. Install backend deps
cd backend
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# GITHUB_TOKEN  → Settings → Developer settings → PATs (no scopes needed for public data)
# GROQ_API_KEY  → required for LLM narrative advice (optional feature)

# 4. Run the API
uvicorn app.main:app --reload
```

Interactive API docs: **http://localhost:8000/docs**

```bash
# 5. Frontend (separate terminal)
cd frontend
npm install
cp .env.local.example .env.local   # points to localhost:8000 by default
npm run dev
```

Open **http://localhost:3000** with the backend running on `:8000`.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/profile/analyze` | Full pipeline: `github_username` + resume PDF → persisted analysis + gaps |
| `GET` | `/profile/{github_username}` | Fetch a previously saved analysis (no re-run) |
| `GET` | `/github/analyze/{username}` | GitHub evidence only, no persistence |
| `POST` | `/resume/parse` | Parse a PDF → claimed skills + detected links |

---

## Architecture

```
frontend (Next.js :3000)
    └─→ POST /profile/analyze
            ├─ github_agent.py      → GitHub REST API (Redis-cached)
            ├─ resume_agent.py      → PyMuPDF PDF parser
            ├─ dsa_agent.py         → LeetCode GraphQL + Codeforces REST + CodeChef HTML
            ├─ gap_detector.py      → Rule-based EVIDENCE_MAP (25+ skills)
            ├─ narrative_advisor.py → Groq LLM (optional, degrades gracefully)
            └─ profile router       → PostgreSQL (SQLAlchemy)
```

For the full Mermaid diagram, DB schema, and integration specs, see [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md).