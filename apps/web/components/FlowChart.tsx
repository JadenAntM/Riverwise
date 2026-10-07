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


type Point = { timestamp: number; value: number | null };

function withVisibleGaps(observations: Observation[]): Point[] {
  const points: Point[] = [];
  observations.forEach((observation, index) => {
    const previous = observations[index - 1];
    if (previous) {
      const delta = new Date(observation.observed_at_utc).getTime() - new Date(previous.observed_at_utc).getTime();
      if (delta > 90 * 60 * 1000) {
        points.push({ timestamp: new Date(previous.observed_at_utc).getTime() + delta / 2, value: null });
      }
    }
    points.push({ timestamp: Date.parse(observation.observed_at_utc), value: observation.value });
  });
  return points;
}


export function FlowChart({ observations }: { observations: Observation[] }) {
  const ordered = [...observations].sort((a, b) => Date.parse(a.observed_at_utc) - Date.parse(b.observed_at_utc));
  const data = withVisibleGaps(ordered);
  const qualified = ordered.filter((row) => row.qualifier !== null).length;
  return (
    <div className="chart-wrap" aria-label="48-hour measured discharge chart">
      <p className="chart-summary">{ordered.length} WSC discharge readings{ordered.length > 0 ? ` · ${formatAtlantic(ordered[0].observed_at_utc)} to ${formatAtlantic(ordered[ordered.length - 1].observed_at_utc)}` : " · No measured discharge available"}. {qualified} qualified readings; qualifiers and approval are in the data table.</p>
      {ordered.length < 2 ? <div className="chart-empty">Not enough recent observations to draw the chart.</div> : (
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 12, right: 10, left: -14, bottom: 0 }}>
          <CartesianGrid stroke="#d9e0d7" strokeDasharray="3 4" vertical={false} />
          <XAxis
            dataKey="timestamp"
            type="number"
            domain={["dataMin", "dataMax"]}
            scale="time"
            minTickGap={54}
            tickFormatter={(value: number) => formatAtlantic(new Date(value).toISOString(), false)}
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
            labelFormatter={(value) => formatAtlantic(new Date(Number(value)).toISOString())}
            formatter={(value) => [`${Number(value).toFixed(2)} m³/s`, "Measured flow"]}
            contentStyle={{ border: "1px solid #c7d0c5", borderRadius: 12, boxShadow: "0 12px 30px rgba(28, 49, 38, .12)" }}
          />
          <Line
            type="linear"
            dataKey="value"
            stroke="#1f6b4f"
            strokeWidth={3}
            dot={false}
            activeDot={{ r: 5, fill: "#f0a653", stroke: "#fff", strokeWidth: 2 }}
            connectNulls={false}
          />
        </LineChart>
      </ResponsiveContainer>
      )}
      <p className="chart-note">Gaps are left open when readings are more than 90 minutes apart.</p>
      <p className="chart-note">Discharge is the volume of water passing the gauge each second, in m³/s. Lines join available readings; they do not create new measurements. All times are Atlantic (AST/ADT).</p>
      <details className="data-details">
        <summary>View discharge readings, qualifiers, and approval</summary>
        {ordered.length === 0 ? <p>No readings in this window.</p> : <div className="data-table-scroll" role="region" aria-label="Discharge readings table" tabIndex={0}>
          <table className="data-table"><caption>Measured Water Survey of Canada discharge · Atlantic observation time</caption>
            <thead><tr><th scope="col">Observed</th><th scope="col">Discharge</th><th scope="col">Qualifier</th><th scope="col">Approval</th></tr></thead>
            <tbody>{ordered.map((row) => <tr key={row.observed_at_utc}><th scope="row">{formatAtlantic(row.observed_at_utc)}</th><td>{row.value.toFixed(2)} {row.unit}</td><td>{row.qualifier ?? "None supplied"}</td><td>{row.approval ?? "Not supplied"}</td></tr>)}</tbody>
          </table>
        </div>}
      </details>
    </div>
  );
}
