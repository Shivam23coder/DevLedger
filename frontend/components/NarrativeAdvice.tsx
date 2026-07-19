export default function NarrativeAdvice({ advice }: { advice: string | null }) {
  if (!advice) return null;

  return (
    <div className="rounded-md border-l-2 border-accent bg-surface pl-4 pr-4 py-4">
      <p className="font-mono text-xs uppercase tracking-wider text-accent mb-2">
        Mentor note
      </p>
      <p className="text-sm text-ink leading-relaxed">{advice}</p>
    </div>
  );
}
