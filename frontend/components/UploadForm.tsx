"use client";

import { useState, FormEvent } from "react";

type Props = {
  onSubmit: (githubUsername: string, resumeFile: File) => void;
  loading: boolean;
};

export default function UploadForm({ onSubmit, loading }: Props) {
  const [githubUsername, setGithubUsername] = useState("");
  const [resumeFile, setResumeFile] = useState<File | null>(null);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!githubUsername.trim() || !resumeFile) return;
    onSubmit(githubUsername.trim(), resumeFile);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div>
        <label htmlFor="github" className="block font-mono text-xs uppercase tracking-wider text-muted mb-1.5">
          GitHub username
        </label>
        <input
          id="github"
          type="text"
          value={githubUsername}
          onChange={(e) => setGithubUsername(e.target.value)}
          placeholder="octocat"
          className="w-full rounded-md border border-border bg-canvas px-3 py-2 font-mono text-sm text-ink placeholder:text-muted/60 focus:border-accent"
          required
        />
      </div>

      <div>
        <label htmlFor="resume" className="block font-mono text-xs uppercase tracking-wider text-muted mb-1.5">
          Resume (PDF)
        </label>
        <input
          id="resume"
          type="file"
          accept="application/pdf"
          onChange={(e) => setResumeFile(e.target.files?.[0] ?? null)}
          className="w-full text-sm text-muted file:mr-3 file:rounded-md file:border file:border-border file:bg-surface file:px-3 file:py-1.5 file:font-mono file:text-xs file:text-ink file:cursor-pointer"
          required
        />
      </div>

      <button
        type="submit"
        disabled={loading}
        className="mt-2 rounded-md bg-accent px-4 py-2 font-mono text-sm text-canvas font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:bg-accent/90 transition-colors"
      >
        {loading ? "Analyzing…" : "Run analysis"}
      </button>
    </form>
  );
}
