"use client";
import HistoryChart from "@/components/HistoryChart";
// import { analyzeProfile, fetchProfileHistory, ProfileAnalysis, HistoryEntry } from "@/lib/api";
import { useState } from "react";
import UploadForm from "@/components/UploadForm";
import EvidenceLedger from "@/components/EvidenceLedger";
import RepoGrid from "@/components/RepoGrid";
import SkillBreakdownChart from "@/components/SkillBreakdownChart";
import NarrativeAdvice from "@/components/NarrativeAdvice";
import DsaProfiles from "@/components/DsaProfiles";
import { analyzeProfile, fetchProfileHistory, ProfileAnalysis, HistoryEntry } from "@/lib/api";

export default function Home() {
  const [result, setResult] = useState<ProfileAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);

  async function handleSubmit(githubUsername: string, resumeFile: File) {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await analyzeProfile(githubUsername, resumeFile);
      setResult(data);

      try {
        const historyData = await fetchProfileHistory(githubUsername);
        setHistory(historyData);
      } catch {
        setHistory([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  const gapCount = result?.gaps.length ?? 0;
  const unverifiedCount = result?.unverified_skills.length ?? 0;
  const evidencedCount = (result?.claimed_skills.length ?? 0) - gapCount - unverifiedCount;

  return (
    <main className="min-h-screen bg-canvas">
      <div className="max-w-[53rem] mx-auto px-8 py-16">
        <header className="mb-10">
          <p className="font-mono text-xs uppercase tracking-wider text-accent mb-2">
            EngineerOS
          </p>
          <h1 className="text-2xl font-semibold text-ink">
            Does your resume match your repos?
          </h1>
          <p className="mt-2 text-sm text-muted leading-relaxed">
            Enter a GitHub username and upload a resume. Every claimed skill gets checked
            against actual evidence in the analyzed repositories.
          </p>
        </header>

        <div className="mb-10 rounded-lg border border-border bg-surface p-6">
          <UploadForm onSubmit={handleSubmit} loading={loading} />
        </div>

        {error && (
          <div className="mb-8 rounded-md border border-gap/40 bg-gap/10 px-4 py-3">
            <p className="font-mono text-sm text-gap">{error}</p>
          </div>
        )}

        {result && (
          <div className="flex flex-col gap-8">
            <NarrativeAdvice advice={result.narrative_advice} />
            <div className="flex gap-6 font-mono text-sm">
              <span className="text-evidenced">{evidencedCount} evidenced</span>
              <span className="text-gap">{gapCount} gaps</span>
              <span className="text-unverified">{unverifiedCount} unverified</span>
              <span className="text-muted">{result.repositories.length} repos analyzed</span>
            </div>

            <SkillBreakdownChart
              evidencedCount={evidencedCount}
              gapCount={gapCount}
              unverifiedCount={unverifiedCount}
            />

            <DsaProfiles
              leetcodeStats={result.leetcode_stats}
              codeforcesStats={result.codeforces_stats}
              codechefStats={result.codechef_stats}
            />

            <section>
              <h2 className="font-mono text-xs uppercase tracking-wider text-muted mb-3">
                Repositories
              </h2>
              <RepoGrid repositories={result.repositories} />
            </section>

            <section>
              <EvidenceLedger
                claimedSkills={result.claimed_skills}
                gaps={result.gaps}
                unverifiedSkills={result.unverified_skills}
              />
            </section>
          </div>
        )}
      </div>
    </main>
  );
}
