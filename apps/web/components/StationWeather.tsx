"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { StationWeather as WeatherData, WeatherSample } from "@/lib/api";
import { formatAtlantic, formatNumber } from "@/lib/format";

type Hour = { timestamp: string; sample: WeatherSample | null; precip_mm: number | null };

function hoursEndingAt(end: string, count: number, samples: WeatherSample[]): Hour[] {
  const byTime = new Map(samples.map((sample) => [Date.parse(sample.valid_at_utc), sample]));
  return Array.from({ length: count }, (_, index) => {
    const time = Date.parse(end) - (count - index - 1) * 3_600_000;
    const sample = byTime.get(time) ?? null;
    return { timestamp: new Date(time).toISOString(), sample, precip_mm: sample?.precip_mm ?? null };
  });
}

export function StationWeather({ data, error, loading }: { data: WeatherData | null; error: string | null; loading: boolean }) {
  if (loading) return <section className="chart-card" role="status">Loading nearby weather history and forecast preview…</section>;
  if (error || !data) return <section className="chart-card"><h2>Nearby weather</h2><p className="inline-error" role="status">Weather history and forecast preview are unavailable. Measured river data and the current score remain above.</p></section>;
  const history = hoursEndingAt(data.history_end_at_utc, data.history_hours, data.history);
  const forecast = hoursEndingAt(data.forecast_end_at_utc, data.forecast_hours, data.forecast);
  const precipitationCount = history.filter((hour) => hour.precip_mm !== null).length;
  const forecastCount = forecast.filter((hour) => hour.sample && [hour.sample.air_temp_c, hour.sample.precip_mm, hour.sample.cloud_cover_pct].some((value) => value !== null)).length;
  const staleForecasts = forecast.filter((hour) => hour.sample?.retrieval_state === "stale").length;
  const retrievals = data.forecast.map((row) => row.retrieved_at_utc).sort();
  return (
    <>
      <section className="chart-card" aria-labelledby="weather-history-heading">
        <div className="section-heading compact"><div><p className="section-kicker">Nearby modeled / historical weather</p><h2 id="weather-history-heading">Previous {data.history_hours} hours of precipitation</h2></div></div>
        <p className="chart-summary">{precipitationCount}/{data.history_hours} hourly precipitation values available. Missing values stay unavailable; a blank bar can also be a reported zero—use the table to distinguish them.</p>
        {precipitationCount === 0 ? <p className="chart-empty">No nearby precipitation history is available.</p> : (
          <div aria-label="Nearby modeled hourly precipitation chart">
            <ResponsiveContainer width="100%" height={230}><BarChart data={history} margin={{ left: -10, right: 12 }}>
              <CartesianGrid stroke="#d9e0d7" strokeDasharray="3 4" vertical={false} />
              <XAxis dataKey="timestamp" tickFormatter={(value: string) => formatAtlantic(value, false)} minTickGap={60} tick={{ fontSize: 12 }} />
              <YAxis unit=" mm" width={60} tick={{ fontSize: 12 }} />
              <Tooltip labelFormatter={(value) => `Hour ending ${formatAtlantic(String(value))}`} formatter={(value) => [`${Number(value).toFixed(1)} mm`, "Modeled precipitation"]} />
              <Bar dataKey="precip_mm" fill="#1f6b4f" isAnimationActive={false} />
            </BarChart></ResponsiveContainer>
          </div>
        )}
        <p className="chart-note">Precipitation includes rain and snow water equivalent. Each timestamp ends the preceding one-hour accumulation. Air temperature and cloud cover are instantaneous at that hour. These are model values near the gauge, not measured river or watershed-wide rainfall.</p>
        <details className="data-details"><summary>View hourly weather history and missing values</summary><WeatherTable hours={history} forecast={false} /></details>
        <p className="chart-note">Source: <a href={data.source_url} target="_blank" rel="noreferrer">{data.source}</a>. The current score&apos;s 12-hour precipitation total ends one hour earlier than this history.</p>
      </section>
      <section className="chart-card forecast-preview" aria-labelledby="forecast-heading">
        <div className="section-heading compact"><div><p className="section-kicker">Future weather · forecast only</p><h2 id="forecast-heading">Next {data.forecast_hours} hours near the gauge</h2></div></div>
        <p className="forecast-boundary">Forecast weather does not enter the current experimental conditions score. This preview does not predict river flow or fishing outcomes.</p>
        <p className="chart-summary">{forecastCount}/{data.forecast_hours} future hours have at least one preview value. {staleForecasts > 0 && `${staleForecasts} ${staleForecasts === 1 ? "hour uses" : "hours use"} a stale retrieval (over ${data.retrieval_stale_after_minutes} minutes old). `}The existing import may cover only part of this window.</p>
        <p className="chart-note">{retrievals.length > 0 ? `Stored forecast retrievals: ${formatAtlantic(retrievals[0])} to ${formatAtlantic(retrievals[retrievals.length - 1])}.` : "No future forecast is stored."} Provider issue/model-run time is not supplied in this storage. Retrieval time is not issue time.</p>
        <ul className="forecast-hours" aria-label="Next six forecast hours">{forecast.slice(0, 6).map((hour) => <li key={hour.timestamp}>
          <time dateTime={hour.timestamp}>{formatAtlantic(hour.timestamp)}</time>
          <strong>{formatNumber(hour.sample?.air_temp_c ?? null, " °C")}</strong>
          <span>Air temperature forecast</span>
          <span>Precipitation: {formatNumber(hour.precip_mm, " mm")}</span>
          <span>{hour.sample ? `${hour.sample.retrieval_state === "stale" ? "Stale retrieval" : "Retrieved"}: ${formatAtlantic(hour.sample.retrieved_at_utc)}` : "Forecast hour missing"}</span>
        </li>)}</ul>
        <p className="chart-note">Precipitation is the accumulation during the hour ending at each displayed time. Valid times and retrieval times use Atlantic time (AST/ADT).</p>
        <details className="data-details"><summary>View all {data.forecast_hours} forecast hours and retrieval times</summary><WeatherTable hours={forecast} forecast /></details>
        <p className="chart-note">Source: <a href={data.source_url} target="_blank" rel="noreferrer">{data.source}</a>. Latest stored versions only; past forecast issues are not retained for forecast-error analysis.</p>
      </section>
    </>
  );
}

function WeatherTable({ hours, forecast }: { hours: Hour[]; forecast: boolean }) {
  return <div className="data-table-scroll" role="region" aria-label={forecast ? "Forecast hours table" : "Weather history table"} tabIndex={0}>
    <table className="data-table"><caption>{forecast ? "Open-Meteo forecast" : "Open-Meteo modeled / historical weather"} · Atlantic valid times; precipitation is for the preceding hour</caption>
      <thead><tr><th scope="col">Valid time</th><th scope="col">Air °C</th><th scope="col">Precip. mm</th><th scope="col">Cloud %</th><th scope="col">Retrieval</th></tr></thead>
      <tbody>{hours.map((hour) => <tr key={hour.timestamp}><th scope="row">{formatAtlantic(hour.timestamp)}</th>
        <td>{formatNumber(hour.sample?.air_temp_c ?? null)}</td><td>{formatNumber(hour.precip_mm)}</td><td>{formatNumber(hour.sample?.cloud_cover_pct ?? null, "", 0)}</td>
        <td>{hour.sample ? `${formatAtlantic(hour.sample.retrieved_at_utc)}${forecast && hour.sample.retrieval_state === "stale" ? " · stale" : ""}` : "Hour missing"}</td></tr>)}</tbody>
    </table>
  </div>;
}
