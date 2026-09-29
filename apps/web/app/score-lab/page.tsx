"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { StatusPill } from "@/components/StatusPill";
import {
  getScoreComparison,
  type Score,
  type ScoreComparison,
} from "@/lib/api";
import { formatAtlantic, formatNumber, formatStationName } from "@/lib/format";


export default function ScoreLabPage() {
  const [rows, setRows] = useState<ScoreComparison[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    getScoreComparison()
      .then((data) => {
        if (active) setRows(data);
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : "Score comparison could not be loaded.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="shell score-lab-main">
      <Link className="back-link" href="/">← Station index</Link>
      <header className="score-lab-header">
        <p className="eyebrow">Rule comparison</p>
        <h1>Score lab</h1>
        <p>
          Version 1.0 remains the dashboard score. Versions 1.1 and 1.2 run beside it as
          shadow experiments; different numbers are not evidence of better catch prediction.
        </p>
      </header>

      <section className="rule-comparison" aria-labelledby="rules-heading">
        <div className="status-section-heading">
          <h2 id="rules-heading">What changed</h2>
          <span>All versions are deterministic and inspectable</span>
        </div>
        <div className="rule-columns">
          <article>
            <div><span>Current</span><strong>v1.0</strong></div>
            <h3>Recent flow and nearby weather</h3>
            <ul>
              <li>Flow versus the previous 14-day median · 4 points</li>
              <li>Six-hour flow change · 2 points</li>
              <li>Previous 12-hour modeled precipitation · 2 points</li>
              <li>Nearby modeled cloud cover · 2 points</li>
            </ul>
          </article>
          <article>
            <div><span>Shadow candidate</span><strong>v1.1</strong></div>
            <h3>Seasonal flow and measured temperature</h3>
            <ul>
              <li>Flow percentile for this time of year · 4 points</li>
              <li>Absolute six-hour flow stability · 2 points</li>
              <li>Measured water temperature when available · 4 points</li>
              <li>Rain and cloud remain context, not score points</li>
            </ul>
          </article>
          <article>
            <div><span>Shadow experiment</span><strong>v1.2</strong></div>
            <h3>Station-month flow and multi-window context</h3>
            <ul>
              <li>Station-month discharge percentile · 3 points</li>
              <li>One- and six-hour flow trends · 2 points</li>
              <li>Complete 6-, 24-, and 72-hour modeled precipitation · 3 points</li>
              <li>Measured water temperature, when fresh · 2 points</li>
              <li>Unusually rapid one-hour rise · up to 1 point removed</li>
              <li>Daylight and pressure trend are context only</li>
            </ul>
          </article>
        </div>
      </section>

      <section className="lab-results" aria-labelledby="results-heading">
        <div className="status-section-heading">
          <h2 id="results-heading">Live station comparison</h2>
          <span>Not validated against catch records</span>
        </div>
        {loading && <div className="loading-card" role="status"><span className="spinner" />Loading rule versions…</div>}
        {error && <div className="error-card" role="alert"><strong>Comparison unavailable</strong><span>{error}</span></div>}
        {!loading && !error && (
          <div className="lab-station-list">
            {rows.map((row) => <ComparisonCard row={row} key={row.station_id} />)}
          </div>
        )}
      </section>

      <aside className="lab-note">
        <strong>How to read this page</strong>
        <p>
          These factor weights and bands are hypotheses, not biological findings. Pressure and
          daylight are shown without score points until there is evidence for a relationship.
          Accuracy claims require effort-normalized observations, including zero-catch trips.
        </p>
      </aside>
    </main>
  );
}


function ComparisonCard({ row }: { row: ScoreComparison }) {
  const context = row.experiment_context;
  return (
    <article className="lab-station-card">
      <header>
        <div>
          <span className="station-id">WSC {row.station_id}</span>
          <h3>{formatStationName(row.station_name)}</h3>
        </div>
        <Link href={`/stations/${row.station_id}`}>Station details →</Link>
      </header>
      <div className="score-pair">
        <ScoreColumn label="Current dashboard" score={row.current_score} />
        <ScoreColumn label="v1.1 shadow" score={row.candidate_score} />
        {row.experiment_score
          ? <ScoreColumn label="v1.2 shadow" score={row.experiment_score} />
          : <section aria-label="v1.2 shadow score"><p>Waiting for the v1.2 API deployment.</p></section>}
      </div>
      <dl className="lab-inputs">
        <div>
          <dt>Measured water temperature</dt>
          <dd>
            {row.latest_water_temperature
              ? `${row.latest_water_temperature.value.toFixed(1)} °C · ${formatAtlantic(row.latest_water_temperature.observed_at_utc)}`
              : "Not reported by this station"}
          </dd>
        </div>
        <div>
          <dt>Seasonal flow position</dt>
          <dd>
            {row.seasonal_flow_percentile === null
              ? "Insufficient historical daily flow"
              : `${row.seasonal_flow_percentile.toFixed(0)}th percentile · median ${formatNumber(row.seasonal_median_m3s, " m³/s", 2)}`}
          </dd>
        </div>
        <div>
          <dt>Historical coverage</dt>
          <dd>{row.seasonal_sample_count} daily values across {row.seasonal_year_count} years</dd>
        </div>
        {context && <>
        <div>
          <dt>Station-month reference</dt>
          <dd>{context.monthly_sample_count} daily values across {context.monthly_year_count} prior years</dd>
        </div>
        <div>
          <dt>Measured discharge trend</dt>
          <dd>{formatSigned(context.scoring_inputs?.one_hour_change_pct, "% over 1h")} · {formatSigned(context.scoring_inputs?.twenty_four_hour_change_pct, "% over 24h")}</dd>
        </div>
        <div>
          <dt>Nearby modeled precipitation</dt>
          <dd>{formatRain(context.scoring_inputs?.precipitation_6h_mm, 6)} · {formatRain(context.scoring_inputs?.precipitation_24h_mm, 24)} · {formatRain(context.scoring_inputs?.precipitation_72h_mm, 72)}</dd>
        </div>
        <div>
          <dt>Approximate daylight at gauge</dt>
          <dd>{context.is_daylight ? "Daylight" : "Dark"} · sunrise {formatAtlantic(context.sunrise_at_utc)} · sunset {formatAtlantic(context.sunset_at_utc)}</dd>
        </div>
        <div>
          <dt>Nearby modeled surface pressure</dt>
          <dd>{context.pressure_hpa === null ? "Unavailable" : `${context.pressure_hpa.toFixed(1)} hPa`} · 6h trend {formatSigned(context.pressure_change_6h_hpa, " hPa")}</dd>
        </div>
        </>}
      </dl>
    </article>
  );
}


function ScoreColumn({ label, score }: { label: string; score: Score }) {
  return (
    <section aria-label={`${label} score`}>
      <div className="score-column-topline">
        <span>{label}</span>
        <StatusPill status={score.confidence} />
      </div>
      <div className="lab-score-number">{score.value?.toFixed(1) ?? "—"}<small>{score.value === null ? "" : "/10"}</small></div>
      <p>{score.rules_version}</p>
      <p>{score.available_points}/10 points available · {score.earned_points} earned</p>
      <ul>
        {score.components.length > 0
          ? score.components.map((component) => (
            <li key={component.key}>
              {component.points === null ? "Omitted" : component.points < 0 ? `${component.points} point` : `+${component.points}/${component.maximum}`} · {component.reason}
            </li>
          ))
          : score.reasons.map((reason) => <li key={reason}>{reason}</li>)}
      </ul>
    </section>
  );
}


function formatSigned(value: number | null | undefined, suffix: string): string {
  return value === null || value === undefined ? "Unavailable" : `${value > 0 ? "+" : ""}${value.toFixed(1)}${suffix}`;
}


function formatRain(value: number | null | undefined, hours: number): string {
  return `${hours}h ${value === null || value === undefined ? "unavailable" : `${value.toFixed(1)} mm`}`;
}
