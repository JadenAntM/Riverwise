import stationSeeds from "../../../data/stations.json";
import type { StationSummary } from "@/lib/api";

// Broad location groups for these verified gauges, not watershed/access boundaries.
const regions: Record<string, string> = {
  "01FB001": "Cape Breton",
  "01FB003": "Cape Breton",
  "01FC002": "Cape Breton",
  "01EO001": "Eastern mainland",
  "01EF001": "South Shore",
  "01ED005": "South Shore",
};

export const configuredStations = stationSeeds;
export const stationRegion = (id: string) => regions[id] ?? "Other configured stations";
export type StationSort = "score" | "freshness" | "completeness" | "name";

export function flowState(station: StationSummary): string {
  // Older APIs do not supply measured freshness. Do not infer it from score confidence.
  return station.flow_state ?? (station.latest_flow ? "Age not assessed" : "missing");
}

export function scoreCoverage(station: StationSummary): string {
  if (station.score.value === null) return `Score unavailable: ${station.score.status.replaceAll("_", " ")}`;
  return `${station.score.confidence === "partial" ? "Partial" : "Complete"} score · ${station.score.available_points}/10 points available`;
}

export function discoverStations(stations: StationSummary[], query: string, region: string, sort: StationSort) {
  const terms = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  const confidenceRank = { complete: 0, partial: 1, unavailable: 2 };
  const tier = (station: StationSummary) => station.score.value === null ? 2 : confidenceRank[station.score.confidence];
  const flowRank = (station: StationSummary) => ({ current: 0, stale: 1, missing: 3 }[flowState(station)] ?? 2);
  return stations.filter((station) => {
    const text = `${station.id} ${station.name} ${stationRegion(station.id)}`.toLocaleLowerCase();
    return (region === "all" || stationRegion(station.id) === region) && terms.every((term) => text.includes(term));
  }).sort((a, b) => {
    let order = 0;
    if (sort === "score") order = tier(a) - tier(b) || (b.score.value ?? -1) - (a.score.value ?? -1);
    if (sort === "completeness") order = tier(a) - tier(b) || b.score.available_points - a.score.available_points;
    if (sort === "freshness") order = flowRank(a) - flowRank(b) ||
      Date.parse(b.latest_flow?.observed_at_utc ?? "1970-01-01") - Date.parse(a.latest_flow?.observed_at_utc ?? "1970-01-01");
    return order || a.name.localeCompare(b.name) || a.id.localeCompare(b.id);
  });
}
