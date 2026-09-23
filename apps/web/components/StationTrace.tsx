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

import type { Observation } from "@/lib/api";
import { formatAtlantic } from "@/lib/format";


export function StationTrace({ observations }: { observations: Observation[] }) {
  if (observations.length < 2) {
    return <div className="station-trace-empty">Waiting for enough observations to draw the trace.</div>;
  }

  const data = observations.map((observation) => ({
    timestamp: observation.observed_at_utc,
    value: observation.value,
  }));

  return (
    <div className="station-trace">
      <ResponsiveContainer width="100%" height={170}>
        <LineChart data={data} margin={{ top: 15, right: 5, bottom: 0, left: 5 }}>
          <CartesianGrid stroke="#ccd8cf" strokeDasharray="2 6" vertical={false} />
          <XAxis dataKey="timestamp" hide />
          <YAxis domain={["dataMin - 0.25", "dataMax + 0.25"]} hide />
          <Tooltip
            labelFormatter={(value) => formatAtlantic(String(value))}
            formatter={(value) => [`${Number(value).toFixed(2)} m³/s`, "Measured discharge"]}
            contentStyle={{
              background: "#fbfaf5",
              border: "1px solid #aebcaf",
              borderRadius: 2,
              boxShadow: "none",
              fontSize: 12,
            }}
          />
          <Line
            type="linear"
            dataKey="value"
            stroke="#1f6b4f"
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 4, fill: "#d88039", stroke: "#fbfaf5", strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
      <div className="trace-axis" aria-hidden="true">
        <span>{formatAtlantic(observations[0].observed_at_utc, false)}</span>
        <span>{formatAtlantic(observations[observations.length - 1].observed_at_utc, false)}</span>
      </div>
    </div>
  );
}
