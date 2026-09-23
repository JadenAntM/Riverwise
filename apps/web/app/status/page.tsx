"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { StatusPill } from "@/components/StatusPill";
import {
  getIngestionStatus,
  type IngestionStatus,
  type StationFreshness,
} from "@/lib/api";
import { formatAtlantic, sentenceCase } from "@/lib/format";


export default function StatusPage() {
  const [data, setData] = useState<IngestionStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    setLoading(true);
    setError(null);
    getIngestionStatus()
      .then(setData)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Status could not be loaded."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    let active = true;
    getIngestionStatus()
      .then((status) => {
        if (active) setData(status);
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
  }, []);

  return (
    <main className="shell status-main">
      <Link className="back-link" href="/">← Station index</Link>
      <header className="status-header">
        <div>
          <p className="eyebrow">Ingestion monitoring</p>
          <h1>Data status</h1>
          <p>Riverwise imports each station and provider independently on an hourly schedule.</p>
        </div>
        <button className="refresh-button" type="button" onClick={refresh} disabled={loading}>
          {loading ? "Checking…" : "Refresh status"}
        </button>
      </header>

      {error && <div className="error-card" role="alert"><strong>Status unavailable</strong><span>{error}</span></div>}
      {loading && !data && <div className="loading-card" role="status"><span className="spinner" />Loading ingestion records…</div>}
      {data && (
        <>
          <section className="freshness-section" aria-labelledby="freshness-heading">
            <div className="status-section-heading">
              <h2 id="freshness-heading">Station freshness</h2>
              <span>Generated {formatAtlantic(data.generated_at_utc)}</span>
            </div>
            <div className="freshness-grid">
              {data.stations.map((station) => <FreshnessCard station={station} key={station.id} />)}
            </div>
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
                        <td>{run.fetched_count} fetched / {run.upserted_count} written</td>
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


function FreshnessCard({ station }: { station: StationFreshness }) {
  const status = station.age_minutes === null ? "unavailable" : station.age_minutes <= 180 ? "current" : "stale";
  return (
    <article className="freshness-card">
      <div><span className="station-id">WSC {station.id}</span><StatusPill status={status} /></div>
      <h3>{station.name}</h3>
      <p>{station.latest_observed_at_utc ? `Latest discharge: ${formatAtlantic(station.latest_observed_at_utc)}` : "No discharge observation stored"}</p>
      <small>{station.age_minutes === null ? "Age unavailable" : `${station.age_minutes} minutes old`}</small>
    </article>
  );
}
