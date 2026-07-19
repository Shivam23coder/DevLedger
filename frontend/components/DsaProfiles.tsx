"use client";

type LeetCodeStats = {
  username: string;
  solved_count: number;
  difficulty_solved: Record<string, number>;
  languages: string[];
};

type CodeforcesStats = {
  username: string;
  rating: number | null;
  rank: string | null;
  max_rating: number | null;
  max_rank: string | null;
  solved_count: number;
  languages: string[];
  tags: string[];
};

type CodeChefStats = {
  username: string;
  rating: number | null;
  stars: string | null;
  global_rank: string | null;
  country_rank: string | null;
  solved_count: number;
};

type Props = {
  leetcodeStats: LeetCodeStats | null;
  codeforcesStats: CodeforcesStats | null;
  codechefStats: CodeChefStats | null;
};

function ProfileLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="font-mono text-xs text-accent hover:underline flex items-center gap-1 opacity-70 hover:opacity-100 transition-opacity"
    >
      {children}
      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
      </svg>
    </a>
  );
}

function StatBlock({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-mono text-[10px] uppercase tracking-widest text-muted">{label}</span>
      <span className="text-xl font-bold text-ink leading-none">{value}</span>
      {sub && <span className="font-mono text-[10px] text-muted capitalize mt-0.5">{sub}</span>}
    </div>
  );
}

function LangBadge({ lang }: { lang: string }) {
  return (
    <span className="font-mono text-[11px] px-2 py-0.5 rounded border border-border text-muted bg-canvas/40 leading-snug">
      {lang}
    </span>
  );
}

export default function DsaProfiles({ leetcodeStats, codeforcesStats, codechefStats }: Props) {
  if (!leetcodeStats && !codeforcesStats && !codechefStats) return null;

  return (
    <section className="flex flex-col gap-5">
      <h2 className="font-mono text-xs uppercase tracking-wider text-muted">
        DSA &amp; Competitive Programming Profiles
      </h2>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">

        {/* ── LeetCode Card ── */}
        {leetcodeStats && (
          <div className="rounded-lg border border-border bg-surface p-6 flex flex-col gap-5">
            {/* Header */}
            <div className="flex items-start justify-between">
              <div className="flex flex-col gap-0.5">
                <span className="font-mono text-sm font-semibold text-ink">LeetCode</span>
                <span className="font-mono text-xs text-muted">@{leetcodeStats.username}</span>
              </div>
              <ProfileLink href={`https://leetcode.com/${leetcodeStats.username}`}>
                Profile
              </ProfileLink>
            </div>

            {/* Big solved number */}
            <div className="flex flex-col gap-0.5">
              <span className="font-mono text-[10px] uppercase tracking-widest text-muted">Total Solved</span>
              <span className="text-4xl font-bold text-ink leading-none">{leetcodeStats.solved_count}</span>
            </div>

            {/* Difficulty breakdown */}
            {leetcodeStats.difficulty_solved && (
              <div className="flex flex-col gap-3">
                {(["Easy", "Medium", "Hard"] as const).map((diff) => {
                  const color = diff === "Easy" ? "#00B8A3" : diff === "Medium" ? "#FFC01E" : "#FF375F";
                  const count = leetcodeStats.difficulty_solved[diff] ?? 0;
                  const pct = leetcodeStats.solved_count > 0
                    ? (count / leetcodeStats.solved_count) * 100
                    : 0;
                  return (
                    <div key={diff}>
                      <div className="flex justify-between mb-1.5 font-mono text-xs">
                        <span style={{ color }}>{diff}</span>
                        <span className="text-muted">{count}</span>
                      </div>
                      <div className="w-full bg-canvas rounded-full h-1.5 overflow-hidden">
                        <div
                          className="h-1.5 rounded-full transition-all duration-500"
                          style={{ width: `${pct}%`, backgroundColor: color }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Languages */}
            {leetcodeStats.languages && leetcodeStats.languages.length > 0 && (
              <div className="flex flex-col gap-2 pt-1 border-t border-border/40">
                <span className="font-mono text-[10px] uppercase tracking-widest text-muted">Languages</span>
                <div className="flex flex-wrap gap-1.5">
                  {leetcodeStats.languages.map((lang) => (
                    <LangBadge key={lang} lang={lang} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Codeforces Card ── */}
        {codeforcesStats && (
          <div className="rounded-lg border border-border bg-surface p-6 flex flex-col gap-5">
            {/* Header */}
            <div className="flex items-start justify-between">
              <div className="flex flex-col gap-0.5">
                <span className="font-mono text-sm font-semibold text-ink">Codeforces</span>
                <span className="font-mono text-xs text-muted">@{codeforcesStats.username}</span>
              </div>
              <ProfileLink href={`https://codeforces.com/profile/${codeforcesStats.username}`}>
                Profile
              </ProfileLink>
            </div>

            {/* Rating + Max Rating */}
            <div className="grid grid-cols-2 gap-4">
              <StatBlock
                label="Rating"
                value={<span className="text-accent">{codeforcesStats.rating ?? "Unrated"}</span>}
                sub={codeforcesStats.rank ?? undefined}
              />
              <StatBlock
                label="Max Rating"
                value={codeforcesStats.max_rating ?? "—"}
                sub={codeforcesStats.max_rank ?? undefined}
              />
            </div>

            {/* Solved */}
            <div className="flex flex-col gap-0.5">
              <span className="font-mono text-[10px] uppercase tracking-widest text-muted">Solved (recent)</span>
              <span className="text-4xl font-bold text-ink leading-none">{codeforcesStats.solved_count}</span>
            </div>

            {/* Tags */}
            {codeforcesStats.tags && codeforcesStats.tags.length > 0 && (
              <div className="flex flex-col gap-2">
                <span className="font-mono text-[10px] uppercase tracking-widest text-muted">Top Tags</span>
                <div className="flex flex-wrap gap-1.5 max-h-[72px] overflow-y-auto pr-1">
                  {codeforcesStats.tags.slice(0, 10).map((tag) => (
                    <span
                      key={tag}
                      className="font-mono text-[10px] px-1.5 py-0.5 rounded border border-border/60 text-muted bg-canvas/20"
                      title={tag}
                    >
                      {tag}
                    </span>
                  ))}
                  {codeforcesStats.tags.length > 10 && (
                    <span className="font-mono text-[10px] px-1.5 py-0.5 text-muted">
                      +{codeforcesStats.tags.length - 10} more
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Languages */}
            {codeforcesStats.languages && codeforcesStats.languages.length > 0 && (
              <div className="flex flex-col gap-2 pt-1 border-t border-border/40">
                <span className="font-mono text-[10px] uppercase tracking-widest text-muted">Languages</span>
                <div className="flex flex-wrap gap-1.5">
                  {codeforcesStats.languages.map((lang) => (
                    <LangBadge key={lang} lang={lang} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── CodeChef Card ── */}
        {codechefStats && (
          <div className="rounded-lg border border-border bg-surface p-6 flex flex-col gap-5">
            {/* Header */}
            <div className="flex items-start justify-between">
              <div className="flex flex-col gap-0.5">
                <span className="font-mono text-sm font-semibold text-ink">CodeChef</span>
                <span className="font-mono text-xs text-muted">@{codechefStats.username}</span>
              </div>
              <ProfileLink href={`https://www.codechef.com/users/${codechefStats.username}`}>
                Profile
              </ProfileLink>
            </div>

            {/* Rating + stars */}
            <div className="flex flex-col gap-1">
              <span className="font-mono text-[10px] uppercase tracking-widest text-muted">Rating</span>
              <div className="flex items-end gap-2">
                <span className="text-4xl font-bold text-accent leading-none">
                  {codechefStats.rating ?? "Unrated"}
                </span>
                {codechefStats.stars && (
                  <span className="font-mono text-base text-[#F5A623] mb-0.5">{codechefStats.stars}</span>
                )}
              </div>
            </div>

            {/* Solved */}
            <div className="flex flex-col gap-0.5">
              <span className="font-mono text-[10px] uppercase tracking-widest text-muted">Solved</span>
              <span className="text-4xl font-bold text-ink leading-none">{codechefStats.solved_count}</span>
            </div>

            {/* Ranks */}
            <div className="grid grid-cols-2 gap-4 pt-1 border-t border-border/40">
              <div className="flex flex-col gap-0.5">
                <span className="font-mono text-[10px] uppercase tracking-widest text-muted">Global Rank</span>
                <span className="font-mono text-sm font-semibold text-ink">
                  {codechefStats.global_rank ?? "—"}
                </span>
              </div>
              <div className="flex flex-col gap-0.5">
                <span className="font-mono text-[10px] uppercase tracking-widest text-muted">Country Rank</span>
                <span className="font-mono text-sm font-semibold text-ink">
                  {codechefStats.country_rank ?? "—"}
                </span>
              </div>
            </div>
          </div>
        )}

      </div>
    </section>
  );
}
