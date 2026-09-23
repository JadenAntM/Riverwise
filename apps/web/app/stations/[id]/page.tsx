"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { FlowChart } from "@/components/FlowChart";
import { StatusPill } from "@/components/StatusPill";
import { getHistory, getStation, type History, type StationDetail } from "@/lib/api";
import { formatAtlantic, formatNumber, sentenceCase } from "@/lib/format";


export default function StationPage() {
  const { id } = useParams<{ id: string }>();
  const [station, setStation] = useState<StationDetail | null>(null);
  const [history, setHistory] = useState<History | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getStation(id), getHistory(id)])
      .then(([stationData, historyData]) => {
        setStation(stationData);
        setHistory(historyData);
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "River data could not be loaded."));
  }, [id]);

  if (error) {
    return <main className="shell detail-main"><Link className="back-link" href="/">← Station index</Link><div className="error-card" role="alert"><strong>Station unavailable</strong><span>{error}</span></div></main>;
  }
  if (!station || !history) {
    return <main className="shell detail-main"><Link className="back-link" href="/">← Station index</Link><div className="loading-card" role="status"><span className="spinner" />Loading measured flow and nearby weather…</div></main>;
  }

  const displayName = station.name.replace("NORTHEAST ", "Northeast ").replace(" RIVER AT ", " River at ");
  return (
    <main className="shell detail-main">
      <Link className="back-link" href="/">← Station index</Link>
      <header className="detail-header">
        <div>
          <p className="eyebrow">WSC station {station.id}</p>
          <h1>{displayName}</h1>
          <p className="location-line">{station.latitude.toFixed(5)}, {station.longitude.toFixed(5)} · Atlantic time</p>
        </div>
        <a className="source-link" href={station.source_url} target="_blank" rel="noreferrer">Water Survey of Canada ↗</a>
      </header>

      <section className="score-panel" aria-labelledby="score-heading">
        <div className="score-value">
          <p className="section-kicker" id="score-heading">Experimental conditions score</p>
          <div className="score-number">{station.score.value?.toFixed(1) ?? "—"}<span>{station.score.value === null ? "" : "/10"}</span></div>
          <div className="score-status"><StatusPill status={station.score.status} /><StatusPill status={station.score.confidence} /></div>
        </div>
        <div className="score-explanation">
          <h2>{scoreHeading(station)}</h2>
          <ul>{station.score.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
          {station.score.available_points > 0 && <p className="coverage">{station.score.earned_points} of {station.score.available_points} rule points · version {station.score.rules_version}</p>}
        </div>
      </section>

      <p className="score-disclaimer">Experimental conditions score based on nearby weather and river flow; actual fishing conditions and local rules may differ.</p>

      <section className="metric-strip" aria-label="Latest station conditions">
        <Metric label="Measured discharge" value={station.latest_flow ? station.latest_flow.value.toFixed(2) : "—"} unit={station.latest_flow?.unit ?? "Unavailable"} note={station.latest_flow ? formatAtlantic(station.latest_flow.observed_at_utc) : "No observation"} />
        <Metric label="14-day station median" value={formatNumber(station.baseline_median_m3s, "", 2)} unit="m³/s" note="Previous valid readings" />
        <Metric label="6-hour change" value={formatNumber(station.six_hour_change_pct, "%")} unit="measured trend" note="No gap interpolation" />
        <Metric label="Nearby air temperature" value={formatNumber(station.current_weather?.air_temp_c ?? null, "°", 1)} unit="Celsius" note="Modeled, not water temperature" />
      </section>

      <section className="chart-card">
        <div className="section-heading compact">
          <div><p className="section-kicker">Measured discharge</p><h2>Previous 48 hours</h2></div>
          <p className="section-aside">m³/s · observation time</p>
        </div>
        <FlowChart observations={history.observations} />
      </section>

      <section className="detail-grid">
        <article className="info-card">
          <p className="section-kicker">Nearby modeled weather</p>
          <h2>Weather context</h2>
          <dl>
            <div><dt>Previous 12h precipitation</dt><dd>{formatNumber(station.precipitation_12h_mm, " mm")}</dd></div>
            <div><dt>Cloud cover</dt><dd>{formatNumber(station.current_weather?.cloud_cover_pct ?? null, "%", 0)}</dd></div>
            <div><dt>Surface pressure</dt><dd>{formatNumber(station.current_weather?.pressure_hpa ?? null, " hPa")}</dd></div>
            <div><dt>Classification</dt><dd>{station.current_weather ? sentenceCase(station.current_weather.kind) : "Unavailable"}</dd></div>
          </dl>
        </article>
        <article className="info-card">
          <p className="section-kicker">Data provenance</p>
          <h2>Sources and limitations</h2>
          <dl>
            <div><dt>Water source</dt><dd>Water Survey of Canada</dd></div>
            <div><dt>Approval</dt><dd>{station.latest_flow?.approval ?? "Not supplied"}</dd></div>
            <div><dt>Weather source</dt><dd>Open-Meteo at gauge coordinates</dd></div>
            <div><dt>Station scope</dt><dd>Gauge location only</dd></div>
          </dl>
        </article>
      </section>
    </main>
  );
}


function scoreHeading(station: StationDetail): string {
  if (station.score.status === "stale") return "No score: the discharge reading is stale.";
  if (station.score.status === "insufficient_history") return "No score: seven days of history are required.";
  if (station.score.status === "insufficient_data") return "No score: weather inputs are unavailable.";
  return station.score.confidence === "partial" ? "Score uses partial weather input." : "Score uses all four inputs.";
}


function Metric({ label, value, unit, note }: { label: string; value: string; unit: string; note: string }) {
  return <article><span className="metric-label">{label}</span><strong>{value}</strong><span className="metric-unit">{unit}</span><small>{note}</small></article>;
}
