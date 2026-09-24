"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import Image from "next/image";
import { useEffect, useState } from "react";

import { StationTrace } from "@/components/StationTrace";
import { StatusPill } from "@/components/StatusPill";
import {
  getHistory,
  getStations,
  type History,
  type StationSummary,
} from "@/lib/api";
import { formatAtlantic, formatStationName } from "@/lib/format";


const StationMap = dynamic(
  () => import("@/components/StationMap").then((module) => module.StationMap),
  { ssr: false, loading: () => <div className="map-loading">Loading station map…</div> },
);


export default function Home() {
  const [stations, setStations] = useState<StationSummary[]>([]);
  const [heroHistory, setHeroHistory] = useState<History | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getStations()
      .then(async (stationData) => {
        setStations(stationData);
        if (stationData[0]) {
          try {
            setHeroHistory(await getHistory(stationData[0].id));
          } catch {
            setHeroHistory(null);
          }
        }
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "River data could not be loaded."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main>
      <section className="hero shell">
        <div className="hero-layout">
          <div className="hero-intro">
            <div className="eyebrow">Nova Scotia hydrometric data</div>
            <h1>River conditions,<br />station by station.</h1>
            <p className="hero-copy">
              Check measured discharge at six Nova Scotia gauges, compare each reading with its
              station history, and inspect every input behind the experimental score.
            </p>
            <a
              className="github-link"
              href="https://github.com/JadenAntM/Riverwise"
              rel="noreferrer"
              target="_blank"
            >
              <Image aria-hidden="true" alt="" height={20} src="/github.svg" width={20} />
              <span>View source on GitHub</span>
              <span aria-hidden="true" className="github-link-arrow">↗</span>
            </a>
            <dl className="hero-index" aria-label="Current Riverwise coverage">
              <div><dt>Coverage</dt><dd>6 verified gauges</dd></div>
              <div><dt>Flow source</dt><dd>Water Survey of Canada</dd></div>
              <div><dt>Time shown</dt><dd>Atlantic</dd></div>
            </dl>
          </div>
          <HeroReading station={stations[0]} history={heroHistory} loading={loading} />
        </div>
      </section>

      <section className="station-section shell" aria-labelledby="stations-heading">
        <div className="section-heading">
          <div>
            <p className="section-kicker">Station index</p>
            <h2 id="stations-heading">Available gauges</h2>
          </div>
          <p className="section-aside">Complete data first, partial data second</p>
        </div>

        {loading && <LoadingCard />}
        {error && <ErrorCard message={error} />}
        {!loading && !error && stations.length === 0 && (
          <div className="empty-state">No configured stations are available yet.</div>
        )}
        <div className="station-grid">
          {stations.map((station) => (
            <Link className="station-card" href={`/stations/${station.id}`} key={station.id}>
              <div className="card-topline">
                <span className="station-id">WSC {station.id}</span>
                <StatusPill status={station.score.confidence} />
              </div>
              <h3>{formatStationName(station.name)}</h3>
              <div className="card-metrics">
                <div>
                  <span className="metric-label">Measured flow</span>
                  <strong>{station.latest_flow ? station.latest_flow.value.toFixed(2) : "—"}</strong>
                  <span className="metric-unit">{station.latest_flow?.unit ?? "Unavailable"}</span>
                </div>
                <div>
                  <span className="metric-label">Conditions score</span>
                  <strong>{station.score.value?.toFixed(1) ?? "—"}</strong>
                  <span className="metric-unit">{station.score.value === null ? "Unavailable" : "/ 10"}</span>
                </div>
              </div>
              <div className="card-footer">
                <span>
                  {station.latest_flow
                    ? `Observed ${formatAtlantic(station.latest_flow.observed_at_utc)}`
                    : "No measured flow available"}
                </span>
                <span aria-hidden="true" className="card-arrow">→</span>
              </div>
            </Link>
          ))}
        </div>
        {!loading && !error && stations.length > 0 && <StationMap stations={stations} />}
      </section>

      <section className="method shell">
        <p className="section-kicker">Reading the data</p>
        <h2>What each value means</h2>
        <div className="method-grid">
          <article><span>Gauge</span><div><h3>Discharge is measured at one location</h3><p>It does not describe every pool, tributary, or access point on the river.</p></div></article>
          <article><span>Temperature</span><div><h3>Water temperature is used only when measured</h3><p>Stations without that output keep an explicit data gap; nearby modeled air temperature is never substituted.</p></div></article>
          <article><span>Score</span><div><h3>The rules are experimental</h3><p>Version 1.0 remains current while the seasonal v1.1 candidate runs transparently in the score lab.</p></div></article>
        </div>
      </section>
    </main>
  );
}


function HeroReading({
  station,
  history,
  loading,
}: {
  station?: StationSummary;
  history: History | null;
  loading: boolean;
}) {
  if (loading) {
    return <aside className="hero-reading hero-reading-loading" aria-label="Loading station summary"><span className="spinner" />Loading station feed</aside>;
  }
  if (!station?.latest_flow) {
    return <aside className="hero-reading"><p className="trace-label">Station feed</p><strong className="trace-unavailable">Unavailable</strong><p className="trace-note">The station index below includes the current data status.</p></aside>;
  }
  return (
    <aside className="hero-reading" aria-label={`Latest reading for ${station.name}`}>
      <div className="trace-heading">
        <div>
          <p className="trace-label">WSC {station.id} · measured discharge</p>
          <p className="trace-name">{formatStationName(station.name)}</p>
        </div>
        <StatusPill status={station.score.status} />
      </div>
      <div className="trace-reading">
        <strong>{station.latest_flow.value.toFixed(2)}</strong>
        <span>{station.latest_flow.unit}</span>
      </div>
      <p className="trace-time">Observed {formatAtlantic(station.latest_flow.observed_at_utc)}</p>
      <StationTrace observations={history?.observations ?? []} />
      <div className="trace-footer">
        <span>Available 48-hour observations</span>
        <span>Score {station.score.value?.toFixed(1) ?? "—"}/10</span>
      </div>
    </aside>
  );
}


function LoadingCard() {
  return <div className="loading-card" role="status"><span className="spinner" />Loading the latest station reading…</div>;
}


function ErrorCard({ message }: { message: string }) {
  return <div className="error-card" role="alert"><strong>River data is unavailable.</strong><span>{message} Check that the API is running, then reload.</span></div>;
}
