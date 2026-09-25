"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { StatusPill } from "@/components/StatusPill";
import {
  getIngestionStatus,
  getReliability,
  type IngestionStatus,
  type Reliability,
  type StationFreshness,
  type StationReliability,
} from "@/lib/api";
import { formatAtlantic, formatStationName, sentenceCase } from "@/lib/format";


export default function StatusPage() {
  const [data, setData] = useState<IngestionStatus | null>(null);
  const [reliability, setReliability] = useState<Reliability | null>(null);
  const [days, setDays] = useState<7 | 30>(30);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([getIngestionStatus(), getReliability(days)])
      .then(([status, metrics]) => {
        setData(status);
        setReliability(metrics);
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Status could not be loaded."))
      .finally(() => setLoading(false));
  }, [days]);

  useEffect(() => {
    let active = true;
    Promise.all([getIngestionStatus(), getReliability(days)])
      .then(([status, metrics]) => {
        if (active) {
          setData(status);
          setReliability(metrics);
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : "Status could not be loaded.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [days]);

  return (
    <main className="shell status-main">
      <Link className="back-link" href="/">← Station index</Link>
      <header className="status-header">
        <div>
          <p className="eyebrow">Ingestion monitoring</p>
          <h1>Data status</h1>
          <p>Riverwise imports each station and provider independently every 30 minutes.</p>
        </div>
        <button className="refresh-button" type="button" onClick={refresh} disabled={loading}>
          {loading ? "Checking…" : "Refresh status"}
        </button>
      </header>

      {error && <div className="error-card" role="alert"><strong>Status unavailable</strong><span>{error}</span></div>}
      {loading && !data && <div className="loading-card" role="status"><span className="spinner" />Loading ingestion records…</div>}
      {data && reliability && (
        <>
          <ReliabilitySummary reliability={reliability} days={days} onDaysChange={setDays} />

          <section className="freshness-section" aria-labelledby="freshness-heading">
            <div className="status-section-heading">
              <h2 id="freshness-heading">Station coverage</h2>
              <span>Generated {formatAtlantic(data.generated_at_utc)}</span>
            </div>
            <div className="freshness-grid">
              {data.stations.map((station) => (
                <FreshnessCard
                  days={days}
                  key={station.id}
                  reliability={reliability.stations.find((item) => item.id === station.id)}
                  station={station}
                />
              ))}
            </div>
          </section>

          <section className="runs-section" aria-labelledby="reliability-runs-heading">
            <div className="status-section-heading">
              <h2 id="reliability-runs-heading">Provider reliability</h2>
              <span>{days}-day measured window</span>
            </div>
            {reliability.providers.length === 0 ? (
              <div className="empty-state">No provider attempts are stored in this window.</div>
            ) : (
              <div className="runs-table-wrap">
                <table className="runs-table">
                  <thead><tr><th>Provider</th><th>Station</th><th>Success</th><th>Attempts</th><th>Rows</th><th>Changed values</th><th>Last success</th></tr></thead>
                  <tbody>
                    {reliability.providers.map((provider) => (
                      <tr key={`${provider.source}-${provider.station_id}`}>
                        <td>{sentenceCase(provider.source)}</td>
                        <td>{provider.station_id}</td>
                        <td>{provider.success_rate_pct.toFixed(1)}%</td>
                        <td>{provider.successes} / {provider.attempts}</td>
                        <td>{provider.inserted_count} new / {provider.updated_count} refreshed</td>
                        <td>{provider.revision_count}</td>
                        <td>{provider.last_success_at_utc ? formatAtlantic(provider.last_success_at_utc) : "None recorded"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="runs-section" aria-labelledby="runs-heading">
            <div className="status-section-heading">
              <h2 id="runs-heading">Latest provider runs</h2>
              <span>Schedule: {data.schedule}</span>
            </div>
            {data.sources.length === 0 ? (
              <div className="empty-state">No ingestion runs have been recorded.</div>
            ) : (
              <div className="runs-table-wrap">
                <table className="runs-table">
                  <thead><tr><th>Provider</th><th>Station</th><th>Status</th><th>Last attempt</th><th>Last success</th><th>Rows</th><th>Duration</th></tr></thead>
                  <tbody>
                    {data.sources.map((run) => (
                      <tr key={`${run.source}-${run.station_id ?? "all"}`}>
                        <td>{sentenceCase(run.source)}</td>
                        <td>{run.station_id ?? "All"}</td>
                        <td><StatusPill status={run.status} /></td>
                        <td>{formatAtlantic(run.last_attempt_at_utc)}</td>
                        <td>{run.last_success_at_utc ? formatAtlantic(run.last_success_at_utc) : "None recorded"}</td>
                        <td>{run.inserted_count} new / {run.updated_count} refreshed / {run.revision_count} changed</td>
                        <td>{run.duration_ms === null ? "—" : `${run.duration_ms} ms`}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}


function ReliabilitySummary({
  reliability,
  days,
  onDaysChange,
}: {
  reliability: Reliability;
  days: 7 | 30;
  onDaysChange: (days: 7 | 30) => void;
}) {
  const attempts = reliability.providers.reduce((total, provider) => total + provider.attempts, 0);
  const successes = reliability.providers.reduce((total, provider) => total + provider.successes, 0);
  const revisions = reliability.providers.reduce((total, provider) => total + provider.revision_count, 0);
  const candidateSnapshots = reliability.stations.reduce(
    (total, station) => total + station.candidate_snapshot_count,
    0,
  );
  const temperatureSnapshots = reliability.stations.reduce(
    (total, station) => total + station.water_temperature_available_snapshots,
    0,
  );
  const successRate = attempts ? successes / attempts * 100 : null;
  const temperatureCoverage = candidateSnapshots
    ? temperatureSnapshots / candidateSnapshots * 100
    : null;

  return (
    <section className="reliability-summary" aria-labelledby="reliability-heading">
      <div className="status-section-heading">
        <div>
          <p className="section-kicker">Measured operations</p>
          <h2 id="reliability-heading">Reliability window</h2>
        </div>
        <div className="period-toggle" aria-label="Reliability window">
          {([7, 30] as const).map((period) => (
            <button
              aria-pressed={days === period}
              key={period}
              onClick={() => onDaysChange(period)}
              type="button"
            >
              {period} days
            </button>
          ))}
        </div>
      </div>
      <div className="reliability-metrics">
        <MetricCard
          label="Provider success"
          note={`${successes} successful of ${attempts} attempts`}
          value={successRate === null ? "Collecting" : `${successRate.toFixed(1)}%`}
        />
        <MetricCard
          label="Temperature coverage"
          note={`${temperatureSnapshots} of ${candidateSnapshots} candidate snapshots`}
          value={temperatureCoverage === null ? "Collecting" : `${temperatureCoverage.toFixed(1)}%`}
        />
        <MetricCard
          label="Changed provider values"
          note="Source-field changes tracked from this release onward"
          value={String(revisions)}
        />
        <MetricCard
          label="Verified gauges"
          note="Active WSC stations with current discharge"
          value={String(reliability.stations.length)}
        />
      </div>
    </section>
  );
}


function MetricCard({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <article>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  );
}


function FreshnessCard({
  station,
  reliability,
  days,
}: {
  station: StationFreshness;
  reliability?: StationReliability;
  days: 7 | 30;
}) {
  const status = station.age_minutes === null ? "unavailable" : station.age_minutes <= 180 ? "current" : "stale";
  return (
    <article className="freshness-card">
      <div><span className="station-id">WSC {station.id}</span><StatusPill status={status} /></div>
      <h3>{formatStationName(station.name)}</h3>
      <p>{station.latest_observed_at_utc ? `Latest discharge: ${formatAtlantic(station.latest_observed_at_utc)}` : "No discharge observation stored"}</p>
      <small>{station.age_minutes === null ? "Age unavailable" : `${station.age_minutes} minutes old`}</small>
      {reliability && (
        <dl>
          <div><dt>Discharge rows</dt><dd>{reliability.recent_discharge_observation_count} / {days}d</dd></div>
          <div><dt>Water-temperature rows</dt><dd>{reliability.recent_water_temperature_observation_count}</dd></div>
          <div><dt>Temperature snapshot coverage</dt><dd>{reliability.water_temperature_availability_pct === null ? "Collecting" : `${reliability.water_temperature_availability_pct.toFixed(1)}%`}</dd></div>
          <div><dt>Daily history</dt><dd>{reliability.historical_daily_observation_count} rows · {reliability.historical_year_count} years</dd></div>
          <div><dt>History range</dt><dd>{reliability.historical_first_date && reliability.historical_last_date ? `${reliability.historical_first_date} to ${reliability.historical_last_date}` : "Unavailable"}</dd></div>
        </dl>
      )}
    </article>
  );
}
