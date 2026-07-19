# EngineerOS v1 — System Design

**Scope of this document:** the shipped v1 slice — GitHub Intelligence + Resume Gap Analysis.
Later modules (AI interviewer, career coach, DSA intelligence) are noted only where they
change v1's design decisions.

---

## 1. Problem Statement

Developers' skills are scattered across GitHub, resumes, LeetCode, and LinkedIn, with no
system that cross-references them. Resumes can claim skills with no supporting evidence;
recruiters have no way to verify claims without manually opening every repo.

**v1 goal:** given a GitHub username and a resume PDF, automatically detect which claimed
skills are backed by evidence in the person's public repos, and which are not.

---

## 2. Requirements

### Functional
- Analyze a public GitHub profile's repos (languages, CI presence, test presence, docs)
- Parse a PDF resume for claimed skills and embedded profile links (GitHub/LinkedIn/LeetCode),
  including links hidden behind hyperlinked text, not just plain-text URLs
- Cross-reference claims against evidence and produce a list of gaps with suggestions
- Persist analysis so it can be re-fetched without recomputation

### Non-functional
- **Correctness over completeness**: a skill with no defined evidence rule is skipped, not
  guessed at — false positives (wrongly flagging a real skill as a gap) are worse than false
  negatives for user trust
- **Resilience to third-party instability**: GitHub API is stable and documented; downstream
  integrations (LeetCode) are not, and the design must not let one unstable dependency take
  down the whole analysis
- **Idempotent re-analysis**: re-running analysis for the same user replaces prior results
  rather than duplicating them
- Single-user-request latency target: a few seconds is acceptable (this is not a real-time
  system); nothing here needs sub-second response

### Explicitly out of scope for v1
- Private repo access (needs OAuth — v1.5)
- LeetCode/Codeforces integration (v2 — see §8 for why deferred)
- LLM-generated narrative advice (rules only — see §6.3)
- Any authentication on the API itself (local/demo only)

---

## 3. Capacity Estimation (rough, order-of-magnitude)

| Factor | Estimate | Why it matters |
|---|---|---|
| GitHub API calls per user analyzed | ~1 + 3×N (N = repos, capped at 10) | ≈31 calls/user at the default limit |
| Unauthenticated GitHub rate limit | 60 req/hr | Fine for local dev, **unusable** for any real demo with >1 user |
| Authenticated (PAT) rate limit | 5,000 req/hr | Supports ~160 user-analyses/hour on this budget alone |
| Resume PDF parse time | <1s typically | PyMuPDF is fast; not a bottleneck |
| Total single request latency | 2–5s | Dominated by sequential GitHub API round-trips, not compute |

**Implication:** the GitHub rate limit, not compute or storage, is the binding constraint on
this system at any real scale. This drives the caching decision in §7.

---

## 4. High-Level Architecture

```
Client (POST github_username + resume PDF)
        │
        ▼
FastAPI router (profile.py)  — orchestrates, does no analysis itself
        │
        ├──► github_agent.py  ──► GitHub REST API (public, unauthenticated or PAT)
        │
        ├──► resume_agent.py  ──► PyMuPDF (local, no external call)
        │
        ▼
gap_detector.py  — pure in-memory rule evaluation, no I/O
        │
        ▼
SQLAlchemy models ──► Postgres  (Profile / Repository / ResumeClaim / Gap tables)
        │
        ▼
JSON response (ProfileAnalysisOut)
```

Two things worth calling out explicitly if asked:
- The two agents (GitHub, resume) have **no dependency on each other** — they're written as
  sequential awaits today for simplicity, but are safe to run concurrently
  (`asyncio.gather()`) since neither reads the other's output.
- The gap detector is **pure and stateless** — no I/O, no DB access, just dict comparisons.
  That's deliberate: it makes the core "is this claim evidenced" logic unit-testable without
  mocking a database or an HTTP client.

---

## 5. Data Model

Four tables, one profile as the anchor:

```
Profile
 ├── github_username (unique)
 ├── linkedin_url
 └── leetcode_username

Repository (N per Profile)
 ├── name, primary_language, languages[], topics[]
 ├── has_readme, has_ci, has_tests
 └── stars

ResumeClaim (N per Profile)
 ├── skill
 └── raw_context

Gap (N per Profile)
 ├── skill
 ├── reason
 └── suggestion
```

**Design decision — relational, not graph:** the pitch's original architecture proposed a
"knowledge graph." In practice, the actual query pattern here is "for profile X, get all repos
and all claims" — a straightforward join, not a graph traversal (no multi-hop queries like
"find developers similar to X via shared contributors"). A graph database would add
operational complexity with no corresponding query benefit at this stage. **If** the product
later needs similarity search ("developers like you also learned...") or multi-hop
recommendation reasoning, that's the point to introduce a vector index (pgvector extension on
the same Postgres instance, not a separate graph DB) — evolutionary, not a rewrite.

**Re-analysis behavior:** `Repository`/`ResumeClaim`/`Gap` rows are deleted and re-inserted on
each `/profile/analyze` call for an existing profile, rather than diffed. Simpler to reason
about; acceptable because analysis is infrequent per user, not a hot path.

---

## 6. Component Deep-Dives

### 6.1 GitHub Agent
- Fetches repos sorted by `updated`, capped at a configurable limit (default 10) — this cap is
  the main lever on both latency and rate-limit consumption (§3).
- Per repo: one call for language breakdown (bytes per language, not just the `primary_language`
  field, which only reports one language per repo even for polyglot projects), and two
  existence-checks (`README.md`, `.github/workflows`) via the contents API rather than cloning
  the repo — cheaper than a full clone for signals this shallow.
- No pagination handling beyond the `limit` param yet — a user with 200 repos still only gets
  their 10 most recently updated analyzed. Acceptable for v1; would need cursor-based pagination
  if "analyze everything" becomes a requirement.

### 6.2 Resume Agent
- **Why PyMuPDF over pypdf/PyPDF2:** the latter only extracts the text layer. A resume's
  "GitHub" text is often a hyperlink annotation with the URL stored separately from the visible
  text — `page.get_links()` is required to read that, and pypdf doesn't expose it.
- **Two-pass link detection:** hyperlink annotations checked first, then a regex fallback over
  plain text, because some resume builders (Canva exports, older Word versions) don't preserve
  link annotations reliably. This dual-path is the single most failure-prone part of the
  pipeline and the first place to add test coverage against real-world resume exports.
- **Skill extraction is a flat keyword list**, not an ML model or embedding match. Deliberate
  trade-off: fully deterministic and debuggable ("why was 'Kubernetes' not detected? because
  it's not in SKILL_KEYWORDS" is a one-line answer) versus a model-based extractor that would
  need its own evaluation harness before v1 could trust it.

### 6.3 Gap Detector
- Each skill maps to an `EVIDENCE_MAP` entry describing what would count as proof (a GitHub
  language, a repo topic, a `has_ci` flag, or a keyword in the repo description/name).
- **Skills with no `EVIDENCE_MAP` entry are skipped, not flagged.** This is the single most
  important correctness decision in the system: the alternative (flag anything unverifiable)
  produces false positives that erode trust in every other gap the tool reports.
- The commented-out `generate_narrative_advice()` stub marks where an LLM call would sit to
  turn a structured gap list into the conversational advice from the original pitch ("you've
  built 3 backend projects but never used caching"). Kept as a separate function so the
  deterministic rules stay testable independent of any LLM's non-determinism.

---

## 7. Scaling & Reliability Considerations

- **GitHub rate limit is the real bottleneck** (§3), not the database or compute. The
  authenticated PAT is a stopgap; a production version would need either a GitHub App
  (higher limits, per-installation tokens) or a caching layer (Redis, already in
  `docker-compose.yml` but unused by the app code today) that skips re-fetching a repo's
  language breakdown if it hasn't changed since the last analysis — checked via the repo's
  `updated_at` timestamp before making the 3 extra per-repo calls.
- **Async job queue (Celery/BullMQ), not implemented yet:** today `/profile/analyze` blocks
  the HTTP request for the full 2–5s pipeline. At any real traffic, this should be:
  client request → enqueue job → return job ID immediately → client polls or gets a webhook
  when analysis completes. Straightforward to add without touching the agent/detector logic —
  it's a wrapper around the existing `analyze_profile()` body.
- **No retry/backoff on GitHub API calls.** A transient GitHub API hiccup currently fails the
  whole request. Cheap fix: wrap `httpx` calls with exponential backoff (e.g. `tenacity`).

---

## 8. Failure Modes & Third-Party Dependency Risk

| Dependency | Stability | Mitigation in place / planned |
|---|---|---|
| GitHub REST API | Official, stable, documented | Optional PAT for rate limit; no retry logic yet (gap) |
| PyMuPDF | Local library, no external dependency | N/A — most reliable part of the system |
| LeetCode (v2) | **Unofficial GraphQL endpoint, can break without notice** | Planned: manual username/CSV import fallback so demo doesn't die if the endpoint changes |
| Codeforces (v2) | Official, documented API | Preferred over LeetCode for the first non-GitHub integration for exactly this reason |

This table is worth having memorized for an interview: it shows the design explicitly
accounts for *which* dependencies are contractual versus scraped, and routes around the
unstable one rather than pretending it's equally reliable.

---

## 9. Security & Privacy Notes

- Current v1 only touches **public** data (public repos, user-uploaded resume) — no OAuth
  scopes, no access to private code.
- Resume PDFs are processed in-memory and not persisted as files — only the extracted
  structured fields (skills, links) are written to Postgres. Worth stating explicitly to a
  recruiter/interviewer: raw resume bytes never touch disk.
- CORS is currently wide open (`allow_origins=["*"]`) — explicitly flagged in code comments as
  a "tighten before real deployment" item, not an oversight.
- No API authentication yet — anyone with network access to the service can trigger analysis
  for any GitHub username. Acceptable for local demo; would need API keys or session auth
  before any public deployment.

---

## 10. What Changes at v1.5 / v2 (and why the design already supports it)

- **v1.5 — LLM reasoning layer:** slots in as `generate_narrative_advice()` consuming
  `find_gaps()` output — no change to the rule engine or data model.
- **v1.5 — Private repos:** GitHub OAuth adds a token per profile; `github_agent.py`'s
  `_headers()` function already centralizes auth header construction, so this is a
  per-user-token swap, not a rewrite.
- **v2 — Codeforces/LeetCode:** a third agent module (`dsa_agent.py`) following the same
  shape as the existing two — fetch, shape into evidence, feed into `EVIDENCE_MAP`-style rules.
  The `Profile.leetcode_username` field already exists in the schema for this.
- **v2 — AI Interviewer:** needs repo *content* (not just metadata) as RAG context — the
  natural extension point is inside `github_agent.py`'s per-repo analysis, adding a step that
  fetches README/key file contents for embedding, not a new architectural layer.
