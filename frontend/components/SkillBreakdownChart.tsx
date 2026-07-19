"use client";

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";

type Props = {
  evidencedCount: number;
  gapCount: number;
  unverifiedCount: number;
};

// Same three colors as EvidenceLedger - one visual language across the app,
// not a chart-specific palette.
const COLORS = {
  evidenced: "#3FB950",
  gap: "#F85149",
  unverified: "#D29922",
};

export default function SkillBreakdownChart({ evidencedCount, gapCount, unverifiedCount }: Props) {
  const total = evidencedCount + gapCount + unverifiedCount;

  const data = [
    { name: "Evidenced", value: evidencedCount, color: COLORS.evidenced },
    { name: "Gaps", value: gapCount, color: COLORS.gap },
    { name: "Unverified", value: unverifiedCount, color: COLORS.unverified },
  ].filter((d) => d.value > 0);

  if (total === 0) return null;

  return (
    <div className="rounded-md border border-border bg-surface p-4">
      <h2 className="font-mono text-xs uppercase tracking-wider text-muted mb-3">
        Skill Breakdown
      </h2>
      <div className="flex items-center gap-6">
        <div style={{ width: 140, height: 140 }}>
          <ResponsiveContainer>
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                nameKey="name"
                innerRadius={40}
                outerRadius={65}
                strokeWidth={0}
              >
                {data.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: "#161B22",
                  border: "1px solid #30363D",
                  borderRadius: 6,
                  fontFamily: "var(--font-plex-mono)",
                  fontSize: 12,
                }}
                itemStyle={{ color: "#E6EDF3" }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="flex flex-col gap-2 font-mono text-sm">
          {data.map((entry) => (
            <div key={entry.name} className="flex items-center gap-2">
              <span
                className="inline-block w-2.5 h-2.5 rounded-sm"
                style={{ backgroundColor: entry.color }}
              />
              <span style={{ color: entry.color }}>
                {entry.name} — {entry.value}
              </span>
              <span className="text-muted">
                ({Math.round((entry.value / total) * 100)}%)
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
