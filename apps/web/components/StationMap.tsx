"use client";

import Link from "next/link";
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";

import type { StationSummary } from "@/lib/api";


function displayName(name: string): string {
  return name
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .replace("At", "at")
    .replace("Near", "near")
    .replace("Above", "above");
}


export function StationMap({ stations }: { stations: StationSummary[] }) {
  const latitude = stations.reduce((sum, station) => sum + station.latitude, 0) / stations.length;
  const longitude = stations.reduce((sum, station) => sum + station.longitude, 0) / stations.length;

  return (
    <section className="map-section" aria-labelledby="map-heading">
      <div className="section-heading compact">
        <div>
          <p className="section-kicker">Station locations</p>
          <h2 id="map-heading">Cape Breton gauges</h2>
        </div>
        <p className="section-aside">Map is supplementary; every station is listed above.</p>
      </div>
      <div className="map-frame" role="region" aria-label="Interactive map of configured river gauges">
        <MapContainer
          center={[latitude, longitude]}
          zoom={9}
          scrollWheelZoom={false}
          className="station-map-canvas"
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {stations.map((station) => (
            <CircleMarker
              key={station.id}
              center={[station.latitude, station.longitude]}
              radius={10}
              pathOptions={{
                color: "#fbfaf5",
                fillColor: station.latest_flow ? "#1f6b4f" : "#68736b",
                fillOpacity: 1,
                weight: 3,
              }}
            >
              <Popup>
                <strong>{displayName(station.name)}</strong><br />
                WSC {station.id}<br />
                <Link href={`/stations/${station.id}`}>Open station details</Link>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>
      <ul className="map-key" aria-label="Map station links">
        {stations.map((station) => (
          <li key={station.id}>
            <span className={station.latest_flow ? "map-dot active" : "map-dot"} aria-hidden="true" />
            <Link href={`/stations/${station.id}`}>{station.id} · {displayName(station.name)}</Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
