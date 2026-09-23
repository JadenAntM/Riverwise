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

import { formatAtlantic } from "@/lib/format";
import type { Observation } from "@/lib/api";


type Point = { timestamp: string; value: number | null };

function withVisibleGaps(observations: Observation[]): Point[] {
  const points: Point[] = [];
  observations.forEach((observation, index) => {
    const previous = observations[index - 1];
    if (previous) {
      const delta = new Date(observation.observed_at_utc).getTime() - new Date(previous.observed_at_utc).getTime();
      if (delta > 90 * 60 * 1000) {
        points.push({ timestamp: new Date(new Date(previous.observed_at_utc).getTime() + delta / 2).toISOString(), value: null });
      }
    }
    points.push({ timestamp: observation.observed_at_utc, value: observation.value });
  });
  return points;
}


export function FlowChart({ observations }: { observations: Observation[] }) {
  if (observations.length < 2) {
    return <div className="chart-empty">Not enough recent observations to draw the chart.</div>;
  }
  const data = withVisibleGaps(observations);
  return (
    <div className="chart-wrap" aria-label="48-hour measured discharge chart">
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 12, right: 10, left: -14, bottom: 0 }}>
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
            tick={{ fill: "#667064", fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            width={48}
            unit=" m³/s"
          />
          <Tooltip
            labelFormatter={(value) => formatAtlantic(String(value))}
            formatter={(value) => [`${Number(value).toFixed(2)} m³/s`, "Measured flow"]}
            contentStyle={{ border: "1px solid #c7d0c5", borderRadius: 12, boxShadow: "0 12px 30px rgba(28, 49, 38, .12)" }}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke="#1f6b4f"
            strokeWidth={3}
            dot={false}
            activeDot={{ r: 5, fill: "#f0a653", stroke: "#fff", strokeWidth: 2 }}
            connectNulls={false}
          />
        </LineChart>
      </ResponsiveContainer>
      <p className="chart-note">Gaps are left open when readings are more than 90 minutes apart.</p>
    </div>
  );
}
