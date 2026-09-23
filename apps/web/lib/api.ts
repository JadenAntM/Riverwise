export type Observation = {
  observed_at_utc: string;
  value: number;
  unit: string;
  qualifier: string | null;
  approval: string | null;
};

export type Weather = {
  valid_at_utc: string;
  kind: "historical_or_modelled" | "forecast";
  air_temp_c: number | null;
  precip_mm: number | null;
  cloud_cover_pct: number | null;
  pressure_hpa: number | null;
};

export type ScoreComponent = {
  key: string;
  label: string;
  points: number | null;
  maximum: number;
  reason: string;
};

export type Score = {
  value: number | null;
  status: "available" | "stale" | "insufficient_history" | "insufficient_data";
  confidence: "complete" | "partial" | "unavailable";
  earned_points: number;
  available_points: number;
  rules_version: string;
  reasons: string[];
  components: ScoreComponent[];
};

export type StationSummary = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  province: string;
  source_url: string;
  latest_flow: Observation | null;
  score: Score;
};

export type StationDetail = StationSummary & {
  baseline_median_m3s: number | null;
  six_hour_change_pct: number | null;
  precipitation_12h_mm: number | null;
  current_weather: Weather | null;
};

export type History = {
  station_id: string;
  hours: number;
  observations: Observation[];
};

export type IngestSourceStatus = {
  source: string;
  station_id: string | null;
  status: "success" | "failed";
  last_attempt_at_utc: string;
  last_success_at_utc: string | null;
  fetched_count: number;
  upserted_count: number;
  duration_ms: number | null;
  error: string | null;
};

export type StationFreshness = {
  id: string;
  name: string;
  latest_observed_at_utc: string | null;
  age_minutes: number | null;
};

export type IngestionStatus = {
  generated_at_utc: string;
  schedule: string;
  sources: IngestSourceStatus[];
  stations: StationFreshness[];
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(response.status === 404 ? "That station was not found." : "River data could not be loaded.");
  }
  return response.json() as Promise<T>;
}

export function getStations(): Promise<StationSummary[]> {
  return request("/api/v1/stations");
}

export function getStation(id: string): Promise<StationDetail> {
  return request(`/api/v1/stations/${encodeURIComponent(id)}`);
}

export function getHistory(id: string): Promise<History> {
  return request(`/api/v1/stations/${encodeURIComponent(id)}/history?hours=48`);
}

export function getIngestionStatus(): Promise<IngestionStatus> {
  return request("/api/v1/ingestion");
}
