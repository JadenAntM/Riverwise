"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ScoreHistory, ScoreSnapshot } from "@/lib/api";
import { formatAtlantic } from "@/lib/format";


type Point = {
  timestamp: string;
  current: number | null;
  candidate: number | null;
};

type VersionSummary = {
  total: number;
  complete: number;
  partial: number;
  stale: number;
  unavailable: number;
};


export function ScoreHistoryChart({
  history,
  days,
  loading,
  onDaysChange,
}: {
  history: ScoreHistory | null;
  days: 7 | 30;
  loading: boolean;
  onDaysChange: (days: 7 | 30) => void;
}) {
  const points = history ? chartPoints(history.snapshots) : [];
  const current = summarize(history?.snapshots ?? [], "v1.0.0");
  const candidate = summarize(history?.snapshots ?? [], "v1.1.0-shadow");

  return (
    <>
      <div className="history-toolbar" aria-label="Score history window">
        <div className="period-toggle">
          {([7, 30] as const).map((period) => (
            <button
              aria-pressed={days === period}
              disabled={loading}
              key={period}
              onClick={() => onDaysChange(period)}
              type="button"
            >
              {period} days
            </button>
          ))}
        </div>
        <div className="score-history-legend" aria-label="Chart series">
          <span className="current">v1.0 current</span>
          <span className="candidate">v1.1 shadow</span>
        </div>
      </div>

      {loading && !history ? (
        <div className="chart-empty" role="status">Loading stored score history…</div>
      ) : points.length === 0 ? (
        <div className="chart-empty">
          No score snapshots are stored in this window yet. History starts with the next hourly import.
        </div>
      ) : (
        <div className="chart-wrap" aria-label={`${days}-day experimental score history chart`}>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={points} margin={{ top: 12, right: 10, left: -14, bottom: 0 }}>
              <CartesianGrid stroke="#d9e0d7" strokeDasharray="3 4" vertical={false} />
              <XAxis
                dataKey="timestamp"
                minTickGap={54}
                tickFormatter={(value: string) => formatAtlantic(value, false)}
                tick={{ fill: "#667064", fontSize: 12 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                domain={[0, 10]}
                ticks={[0, 2, 4, 6, 8, 10]}
                tick={{ fill: "#667064", fontSize: 12 }}
                tickLine={false}
                axisLine={false}
                width={32}
              />
              <Tooltip
                labelFormatter={(value) => formatAtlantic(String(value))}
                formatter={(value, name) => [
                  `${Number(value).toFixed(1)}/10`,
                  name === "current" ? "v1.0 current" : "v1.1 shadow",
                ]}
                contentStyle={{ border: "1px solid #c7d0c5", borderRadius: 3 }}
              />
              <Line
                type="monotone"
                dataKey="current"
                stroke="#1f6b4f"
                strokeWidth={3}
                dot={{ r: 3, fill: "#1f6b4f" }}
                connectNulls={false}
              />
              <Line
                type="monotone"
                dataKey="candidate"
                stroke="#d88039"
                strokeWidth={3}
                strokeDasharray="6 4"
                dot={{ r: 3, fill: "#d88039" }}
                connectNulls={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="history-coverage" aria-label="Stored score status summary">
        <HistorySummary label="v1.0 current" summary={current} />
        <HistorySummary label="v1.1 shadow" summary={candidate} />
      </div>
      <p className="chart-note">
        One snapshot is stored after each hourly import. Missing points preserve stale or unavailable
        score states instead of drawing a continuous value.
      </p>
    </>
  );
}


function chartPoints(snapshots: ScoreSnapshot[]): Point[] {
  const grouped = new Map<string, Point>();
  snapshots.forEach((snapshot) => {
    const point = grouped.get(snapshot.computed_at_utc) ?? {
      timestamp: snapshot.computed_at_utc,
      current: null,
      candidate: null,
    };
    if (snapshot.rules_version === "v1.0.0") point.current = snapshot.value;
    if (snapshot.rules_version === "v1.1.0-shadow") point.candidate = snapshot.value;
    grouped.set(snapshot.computed_at_utc, point);
  });
  return [...grouped.values()].sort((left, right) => left.timestamp.localeCompare(right.timestamp));
}


function summarize(snapshots: ScoreSnapshot[], rulesVersion: string): VersionSummary {
  const rows = snapshots.filter((snapshot) => snapshot.rules_version === rulesVersion);
  const complete = rows.filter((snapshot) => snapshot.confidence === "complete").length;
  const partial = rows.filter((snapshot) => snapshot.confidence === "partial").length;
  const stale = rows.filter((snapshot) => snapshot.status === "stale").length;
  return {
    total: rows.length,
    complete,
    partial,
    stale,
    unavailable: rows.length - complete - partial - stale,
  };
}


function HistorySummary({ label, summary }: { label: string; summary: VersionSummary }) {
  return (
    <article>
      <strong>{label}</strong>
      <span>{summary.total} snapshots</span>
      <small>
        {summary.complete} complete · {summary.partial} partial · {summary.stale} stale · {summary.unavailable} unavailable
      </small>
    </article>
  );
}
