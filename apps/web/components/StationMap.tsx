"use client";

import Link from "next/link";
import { divIcon, latLngBounds } from "leaflet";
import { useEffect } from "react";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";

import type { StationSummary } from "@/lib/api";
import { formatAtlantic, formatStationName } from "@/lib/format";
import { flowState, scoreCoverage } from "@/lib/stations";

function markerState(station: StationSummary) {
  if (flowState(station) === "stale") return { key: "stale", label: "Stale measured flow" };
  if (!station.latest_flow) return { key: "missing", label: "Measured flow missing" };
  if (station.score.value === null) return { key: "unavailable", label: "Score unavailable" };
  if (station.score.confidence === "partial") return { key: "partial", label: "Partial score" };
  return { key: "complete", label: "Complete score" };
}

function FitStations({ stations }: { stations: StationSummary[] }) {
  const map = useMap();
  useEffect(() => {
    if (stations.length) map.fitBounds(latLngBounds(stations.map((station) => [station.latitude, station.longitude])), { padding: [35, 35], maxZoom: 10 });
  }, [map, stations]);
  useEffect(() => {
    const container = map.getContainer();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") map.closePopup();
    };
    container.addEventListener("keydown", closeOnEscape);
    return () => container.removeEventListener("keydown", closeOnEscape);
  }, [map]);
  return null;
}

export function StationMap({ stations }: { stations: StationSummary[] }) {
  if (stations.length === 0) return null;
  return (
    <section className="map-section" aria-labelledby="map-heading">
      <div className="section-heading compact">
        <div><p className="section-kicker">Station locations</p><h2 id="map-heading">Nova Scotia gauges</h2></div>
      </div>
      <p className="discovery-note">Map shows filtered stations. Numbered markers match the text list below. Tab to a marker and press Enter for details; Escape closes its popup.</p>
      <ul className="map-legend" aria-label="Map status legend">
        {[["complete", "Complete score"], ["partial", "Partial score"], ["stale", "Stale measured flow"], ["unavailable", "Score unavailable"], ["missing", "Measured flow missing"]].map(([key, label]) => <li key={key}><span aria-hidden="true" className={`map-dot ${key}`} />{label}</li>)}
      </ul>
      <div className="map-frame" role="region" aria-label="Interactive map of configured river gauges">
        <MapContainer center={[45.5, -62.5]} zoom={7} scrollWheelZoom={false} className="station-map-canvas">
          <FitStations stations={stations} />
          <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          {stations.map((station, index) => {
            const state = markerState(station);
            const label = `${index + 1}. ${formatStationName(station.name)} · ${state.label} · measured flow ${flowState(station)}`;
            return (
              <Marker key={station.id} position={[station.latitude, station.longitude]} title={label} alt={label} keyboard
                eventHandlers={{ add: (event) => { event.target.getElement()?.setAttribute("aria-label", label); } }}
                icon={divIcon({ className: `station-marker ${state.key}`, html: `<span>${index + 1}</span>`, iconSize: [32, 32], iconAnchor: [16, 16] })}>
                <Popup>
                  <strong>{formatStationName(station.name)}</strong><br />WSC {station.id}<br />
                  {state.label}<br />{scoreCoverage(station)}<br />
                  {station.latest_flow ? `${station.latest_flow.value.toFixed(2)} ${station.latest_flow.unit} · ${formatAtlantic(station.latest_flow.observed_at_utc)}` : "No measured flow available"}<br />
                  <Link href={`/stations/${station.id}`}>Open station details</Link>
                </Popup>
              </Marker>
            );
          })}
        </MapContainer>
      </div>
      <ul className="map-key" aria-label="Map station links">
        {stations.map((station, index) => (
          <li key={station.id}>
            <span className={`map-dot ${markerState(station).key}`} aria-hidden="true" />
            <div><Link href={`/stations/${station.id}`}>{index + 1}. {station.id} · {formatStationName(station.name)}</Link>
              <p>{markerState(station).label} · measured flow {flowState(station)}</p>
              <p>{scoreCoverage(station)}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
