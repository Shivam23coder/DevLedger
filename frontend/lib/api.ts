const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Repository = {
  name: string;
  primary_language: string | null;
  languages: string[];
  topics: string[];
  has_readme: boolean;
  has_ci: boolean;
  has_tests: boolean;
  stars: number;
};

export type Gap = {
  skill: string;
  reason: string;
  suggestion: string | null;
};

export type ProfileAnalysis = {
  github_username: string;
  repositories: Repository[];
  claimed_skills: string[];
  gaps: Gap[];
  unverified_skills: string[];
  narrative_advice: string | null;
  detected_links: Record<string, string | null>;
  leetcode_stats: any;
  codeforces_stats: any;
  codechef_stats: any;
};

type JobQueuedResponse = {
  job_id: string;
  status: "queued";
};

type JobStatusResponse =
  | { status: "pending" }
  | { status: "success"; result: ProfileAnalysis }
  | { status: "failed"; error: string };

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * The pipeline now runs as a Celery task (GitHub + resume + 3 DSA sources +
 * LLM call - too slow to hold a single HTTP connection open for). This
 * function keeps the same signature/behavior from the caller's point of
 * view - still just "await analyzeProfile(...)" - but internally it's now:
 * POST to enqueue -> poll status -> return the completed result.
 */
export async function analyzeProfile(
  githubUsername: string,
  resumeFile: File,
  options?: { onStatusChange?: (status: "queued" | "pending") => void; pollIntervalMs?: number; timeoutMs?: number }
): Promise<ProfileAnalysis> {
  const pollIntervalMs = options?.pollIntervalMs ?? 1500;
  const timeoutMs = options?.timeoutMs ?? 90_000; // most analyses finish well under this

  const form = new FormData();
  form.append("github_username", githubUsername);
  form.append("resume", resumeFile);

  const enqueueRes = await fetch(`${API_URL}/profile/analyze`, {
    method: "POST",
    body: form,
  });

  if (!enqueueRes.ok) {
    const detail = await enqueueRes.json().catch(() => null);
    throw new Error(detail?.detail ?? `Analysis failed to start (${enqueueRes.status})`);
  }

  const { job_id }: JobQueuedResponse = await enqueueRes.json();
  options?.onStatusChange?.("queued");

  const startedAt = Date.now();

  while (true) {
    if (Date.now() - startedAt > timeoutMs) {
      throw new Error("Analysis timed out - it may still finish in the background. Try fetching the profile again shortly.");
    }

    await sleep(pollIntervalMs);

    const statusRes = await fetch(`${API_URL}/profile/analyze/status/${job_id}`);
    if (!statusRes.ok) {
      throw new Error(`Failed to check analysis status (${statusRes.status})`);
    }

    const statusData: JobStatusResponse = await statusRes.json();

    if (statusData.status === "success") {
      return statusData.result;
    }
    if (statusData.status === "failed") {
      throw new Error(statusData.error || "Analysis failed for an unknown reason.");
    }
    // status === "pending" - keep polling
    options?.onStatusChange?.("pending");
  }
}

export async function fetchProfile(githubUsername: string): Promise<ProfileAnalysis> {
  const res = await fetch(`${API_URL}/profile/${githubUsername}`, {
    method: "GET",
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Failed to fetch profile (${res.status})`);
  }

  return res.json();
}

export type HistoryEntry = {
  run_id: number;
  created_at: string;
  evidenced_count: number;
  gap_count: number;
  unverified_count: number;
};

export async function fetchProfileHistory(githubUsername: string): Promise<HistoryEntry[]> {
  const res = await fetch(`${API_URL}/profile/${githubUsername}/history`);

  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Failed to fetch history (${res.status})`);
  }

  return res.json();
}