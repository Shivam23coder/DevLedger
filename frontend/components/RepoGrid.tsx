import { Repository } from "@/lib/api";

export default function RepoGrid({ repositories }: { repositories: Repository[] }) {
  if (repositories.length === 0) {
    return <p className="text-sm text-muted">No public repositories analyzed.</p>;
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {repositories.map((repo) => (
        <div
          key={repo.name}
          className="rounded-md border border-border bg-surface p-4"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-sm text-ink truncate">{repo.name}</span>
            {repo.stars > 0 && (
              <span className="font-mono text-xs text-muted shrink-0">★ {repo.stars}</span>
            )}
          </div>

          {repo.primary_language && (
            <span className="mt-1 inline-block font-mono text-xs text-accent">
              {repo.primary_language}
            </span>
          )}

          <div className="mt-3 flex flex-wrap gap-1.5">
            <Signal ok={repo.has_readme} label="docs" />
            <Signal ok={repo.has_ci} label="ci" />
            <Signal ok={repo.has_tests} label="tests" />
          </div>
        </div>
      ))}
    </div>
  );
}

function Signal({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={`font-mono text-xs px-1.5 py-0.5 rounded border ${
        ok
          ? "border-evidenced/40 text-evidenced"
          : "border-border text-muted"
      }`}
    >
      {label}
    </span>
  );
}
