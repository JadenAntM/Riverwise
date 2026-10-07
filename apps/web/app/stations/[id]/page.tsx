import type { Metadata } from "next";
import { StationDetail } from "@/components/StationDetail";
import { configuredStations, stationRegion } from "@/lib/stations";
import { formatStationName } from "@/lib/format";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const station = configuredStations.find((item) => item.id === id);
  if (!station) return { title: "Station unavailable — Riverwise", robots: { index: false, follow: false } };
  const title = `${formatStationName(station.name)} — Riverwise`;
  const description = `WSC ${id} in ${stationRegion(id)}, Nova Scotia. Measured discharge, data age, nearby modeled weather, a separate forecast preview, and an experimental conditions score at this gauge.`;
  return { title, description, openGraph: { title, description, type: "website" } };
}

export default async function StationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <StationDetail key={id} />;
}
