"use client";

import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { HistoryEntry } from "@/lib/api";

const COLORS = {
    evidenced: "#3FB950",
    gap: "#F85149",
    unverified: "#D29922",
};

function formatDate(iso: string): string {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function HistoryChart({ history }: { history: HistoryEntry[] }) {
    if (history.length < 2) return null;

    const data = history.map((entry) => ({
        date: formatDate(entry.created_at),
        Evidenced: entry.evidenced_count,
        Gaps: entry.gap_count,
        Unverified: entry.unverified_count,
    }));

    return (
        <div className="rounded-md border border-border bg-surface p-4">
            <h2 className="font-mono text-xs uppercase tracking-wider text-muted mb-3">
                Gap Closure Over Time
            </h2>
            <div style={{ width: "100%", height: 220 }}>
                <ResponsiveContainer>
                    <LineChart data={data} margin={{ top: 5, right: 10, bottom: 0, left: -10 }}>
                        <CartesianGrid stroke="#30363D" strokeDasharray="3 3" vertical={false} />
                        <XAxis
                            dataKey="date"
                            stroke="#7D8590"
                            tick={{ fill: "#7D8590", fontSize: 11, fontFamily: "var(--font-plex-mono)" }}
                            axisLine={{ stroke: "#30363D" }}
                            tickLine={false}
                        />
                        <YAxis
                            stroke="#7D8590"
                            tick={{ fill: "#7D8590", fontSize: 11, fontFamily: "var(--font-plex-mono)" }}
                            axisLine={{ stroke: "#30363D" }}
                            tickLine={false}
                            allowDecimals={false}
                        />
                        <Tooltip
                            contentStyle={{ backgroundColor: "#161B22", border: "1px solid #30363D", borderRadius: 6, fontFamily: "var(--font-plex-mono)", fontSize: 12 }}
                            labelStyle={{ color: "#E6EDF3" }}
                        />
                        <Line type="monotone" dataKey="Evidenced" stroke={COLORS.evidenced} strokeWidth={2} dot={{ r: 3 }} />
                        <Line type="monotone" dataKey="Gaps" stroke={COLORS.gap} strokeWidth={2} dot={{ r: 3 }} />
                        <Line type="monotone" dataKey="Unverified" stroke={COLORS.unverified} strokeWidth={2} dot={{ r: 3 }} />
                    </LineChart>
                </ResponsiveContainer>
            </div>
            <div className="flex gap-4 mt-2 font-mono text-xs">
                <span style={{ color: COLORS.evidenced }}>● Evidenced</span>
                <span style={{ color: COLORS.gap }}>● Gaps</span>
                <span style={{ color: COLORS.unverified }}>● Unverified</span>
            </div>
        </div>
    );
}