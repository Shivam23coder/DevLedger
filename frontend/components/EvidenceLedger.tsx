import { Gap } from "@/lib/api";

type Props = {
  claimedSkills: string[];
  gaps: Gap[];
  unverifiedSkills: string[];
};

type Status = "evidenced" | "gap" | "unverified";

const STYLES: Record<Status, { symbol: string; text: string; bg: string }> = {
  evidenced: { symbol: "+", text: "text-evidenced", bg: "bg-evidenced/5" },
  gap: { symbol: "−", text: "text-gap", bg: "bg-gap/10" },
  unverified: { symbol: "~", text: "text-unverified", bg: "bg-unverified/5" },
};

/**
 * The signature visual for this product: resume claims rendered like a
 * git diff / PR review, because that's literally what the tool does -
 * reviews a claim against evidence.
 *
 * Three states, not two:
 *   "+" evidenced   - a rule exists in EVIDENCE_MAP and a repo satisfies it
 *   "-" gap         - a rule exists but no repo satisfies it
 *   "~" unverified  - no rule exists yet for this skill (see find_unverified
 *                     in gap_detector.py). This is NOT the same as evidenced -
 *                     it means the tool has no opinion, and must look visually
 *                     distinct so it's never mistaken for a pass.
 */
export default function EvidenceLedger({ claimedSkills, gaps, unverifiedSkills }: Props) {
  const gapMap = new Map(gaps.map((g) => [g.skill, g]));
  const unverifiedSet = new Set(unverifiedSkills);

  function statusFor(skill: string): Status {
    if (gapMap.has(skill)) return "gap";
    if (unverifiedSet.has(skill)) return "unverified";
    return "evidenced";
  }

  return (
    <div className="rounded-md border border-border bg-surface overflow-hidden">
      <div className="px-4 py-2.5 border-b border-border">
        <h2 className="font-mono text-xs uppercase tracking-wider text-muted">
          Evidence Ledger
        </h2>
      </div>

      <div className="font-mono text-sm">
        {claimedSkills.map((skill) => {
          const status = statusFor(skill);
          const style = STYLES[status];
          const gapInfo = gapMap.get(skill);

          return (
            <div
              key={skill}
              className={`px-4 py-2.5 border-b border-border last:border-b-0 ${style.bg}`}
            >
              <div className="flex items-start gap-3">
                <span className={style.text}>{style.symbol}</span>
                <div className="flex-1 min-w-0">
                  <span className={style.text}>{skill}</span>
                  {status === "gap" && gapInfo?.suggestion && (
                    <p className="mt-1 font-sans text-xs text-muted leading-relaxed">
                      {gapInfo.suggestion}
                    </p>
                  )}
                  {status === "unverified" && (
                    <p className="mt-1 font-sans text-xs text-muted leading-relaxed">
                      No verification rule defined yet for this skill - neither confirmed nor flagged.
                    </p>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {claimedSkills.length === 0 && (
          <p className="px-4 py-6 font-sans text-sm text-muted text-center">
            No recognized skills found in this resume.
          </p>
        )}
      </div>
    </div>
  );
}
