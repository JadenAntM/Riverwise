import { expect, test, type Page } from "@playwright/test";

const observedAt = "2026-09-24T14:40:00Z";
const generatedAt = "2026-09-24T15:06:12Z";

const availableScore = {
  value: 7,
  status: "available",
  confidence: "complete",
  earned_points: 7,
  available_points: 10,
  rules_version: "v1.0.0",
  reasons: [
    "Flow is within this station's recent range.",
    "Flow has been stable over six hours.",
  ],
  components: [],
};

const candidateScore = {
  ...availableScore,
  value: 6,
  confidence: "partial",
  earned_points: 6,
  rules_version: "v1.1.0-shadow",
  reasons: ["Seasonal flow is typical.", "Measured water temperature is unavailable."],
};

const stations = [
  {
    id: "01FB001",
    name: "NORTHEAST MARGAREE RIVER AT MARGAREE VALLEY",
    latitude: 46.36897,
    longitude: -60.97528,
    province: "NS",
    source_url: "https://wateroffice.ec.gc.ca/report/real_time_e.html?stn=01FB001",
    latest_flow: {
      observed_at_utc: observedAt,
      value: 7.42,
      unit: "m³/s",
      qualifier: null,
      approval: "Provisional/Provisoire",
    },
    score: availableScore,
  },
  {
    id: "01EF001",
    name: "LAHAVE RIVER AT WEST NORTHFIELD",
    latitude: 44.44722,
    longitude: -64.59111,
    province: "NS",
    source_url: "https://wateroffice.ec.gc.ca/report/real_time_e.html?stn=01EF001",
    latest_flow: {
      observed_at_utc: "2026-09-24T14:35:00Z",
      value: 17,
      unit: "m³/s",
      qualifier: null,
      approval: "Provisional/Provisoire",
    },
    score: { ...availableScore, value: 5 },
  },
];

const stationDetail = {
  ...stations[0],
  candidate_score: candidateScore,
  baseline_median_m3s: 6.9,
  seasonal_median_m3s: 7.1,
  seasonal_flow_percentile: 54,
  seasonal_sample_count: 240,
  seasonal_year_count: 8,
  six_hour_change_pct: -1.2,
  precipitation_12h_mm: 0.4,
  latest_water_temperature: null,
  current_weather: {
    valid_at_utc: observedAt,
    kind: "historical_or_modelled",
    air_temp_c: 16.2,
    precip_mm: 0,
    cloud_cover_pct: 68,
    pressure_hpa: 1009.4,
  },
};

const observations = [
  {
    observed_at_utc: "2026-09-24T12:40:00Z",
    value: 7.55,
    unit: "m³/s",
    qualifier: null,
    approval: "Provisional/Provisoire",
  },
  {
    observed_at_utc: "2026-09-24T13:40:00Z",
    value: 7.48,
    unit: "m³/s",
    qualifier: null,
    approval: "Provisional/Provisoire",
  },
  stations[0].latest_flow,
];

const scoreSnapshots = [
  ["2026-09-24T13:06:12Z", "v1.0.0", 6.5, "complete"],
  ["2026-09-24T13:06:12Z", "v1.1.0-shadow", 5.5, "partial"],
  [generatedAt, "v1.0.0", 7, "complete"],
  [generatedAt, "v1.1.0-shadow", 6, "partial"],
].map(([computed_at_utc, rules_version, value, confidence]) => ({
  computed_at_utc,
  hydro_observed_at_utc: observedAt,
  value,
  status: "available",
  confidence,
  available_points: 10,
  earned_points: value,
  rules_version,
}));

type MockOptions = {
  failStationList?: boolean;
  missingStation?: boolean;
};

async function mockApi(page: Page, options: MockOptions = {}) {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const { pathname } = url;

    if (pathname === "/api/v1/stations" && options.failStationList) {
      await route.fulfill({ status: 503, json: { detail: "Provider unavailable" } });
      return;
    }

    if (pathname === "/api/v1/stations") {
      await route.fulfill({ json: stations });
      return;
    }

    if (/\/api\/v1\/stations\/[^/]+\/score-history$/.test(pathname)) {
      await route.fulfill({
        json: {
          station_id: "01FB001",
          days: Number(url.searchParams.get("days") ?? 7),
          generated_at_utc: generatedAt,
          snapshots: scoreSnapshots,
        },
      });
      return;
    }

    if (/\/api\/v1\/stations\/[^/]+\/history$/.test(pathname)) {
      await route.fulfill({
        json: { station_id: "01FB001", hours: 48, observations },
      });
      return;
    }

    if (/\/api\/v1\/stations\/[^/]+$/.test(pathname)) {
      await route.fulfill(
        options.missingStation
          ? { status: 404, json: { detail: "Station not found" } }
          : { json: stationDetail },
      );
      return;
    }

    if (pathname === "/api/v1/ingestion") {
      await route.fulfill({
        json: {
          generated_at_utc: generatedAt,
          schedule: "hourly",
          sources: [
            {
              source: "wsc_realtime",
              station_id: "01FB001",
              status: "success",
              last_attempt_at_utc: generatedAt,
              last_success_at_utc: generatedAt,
              fetched_count: 12,
              upserted_count: 12,
              inserted_count: 2,
              updated_count: 10,
              revision_count: 0,
              duration_ms: 420,
              error: null,
            },
          ],
          stations: stations.map((station) => ({
            id: station.id,
            name: station.name,
            latest_observed_at_utc: station.latest_flow.observed_at_utc,
            age_minutes: 26,
          })),
        },
      });
      return;
    }

    if (pathname === "/api/v1/reliability") {
      await route.fulfill({
        json: {
          generated_at_utc: generatedAt,
          days: Number(url.searchParams.get("days") ?? 30),
          providers: [
            {
              source: "wsc_realtime",
              station_id: "01FB001",
              attempts: 24,
              successes: 24,
              success_rate_pct: 100,
              fetched_count: 288,
              inserted_count: 24,
              updated_count: 264,
              revision_count: 0,
              last_attempt_at_utc: generatedAt,
              last_success_at_utc: generatedAt,
            },
          ],
          stations: stations.map((station) => ({
            id: station.id,
            name: station.name,
            latest_discharge_at_utc: station.latest_flow.observed_at_utc,
            discharge_age_minutes: 26,
            latest_water_temperature_at_utc: null,
            water_temperature_age_minutes: null,
            water_temperature_available_snapshots: 0,
            candidate_snapshot_count: 24,
            water_temperature_availability_pct: 0,
            recent_discharge_observation_count: 288,
            recent_water_temperature_observation_count: 0,
            historical_daily_observation_count: 3400,
            historical_first_date: "2016-09-24",
            historical_last_date: "2026-09-24",
            historical_year_count: 10,
          })),
        },
      });
      return;
    }

    await route.fulfill({ status: 404, json: { detail: "Unhandled test route" } });
  });

  await page.route("https://*.tile.openstreetmap.org/**", (route) => route.abort());
}

test("loads station cards and preserves the map's text alternative", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Available gauges" })).toBeVisible();
  await expect(page.locator(".station-card")).toHaveCount(2);
  await expect(page.getByRole("region", { name: "Interactive map of configured river gauges" })).toBeVisible();

  const mapLinks = page.getByRole("list", { name: "Map station links" }).getByRole("link");
  await expect(mapLinks).toHaveCount(2);
  await expect(mapLinks.first()).toHaveAttribute("href", "/stations/01FB001");
});

test("opens a station detail and renders both chart regions", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");

  await page.locator(".station-card").first().click();

  await expect(page).toHaveURL(/\/stations\/01FB001$/);
  await expect(
    page.getByRole("heading", { name: "Northeast Margaree River at Margaree Valley" }),
  ).toBeVisible();
  await expect(page.getByLabel("7-day experimental score history chart")).toBeVisible();
  await expect(page.getByLabel("48-hour measured discharge chart")).toBeVisible();
  await expect(page.getByText("v1.1 shadow").first()).toBeVisible();
});

test("shows ingestion coverage and provider reliability", async ({ page }) => {
  await mockApi(page);
  await page.goto("/status");

  await expect(page.getByRole("heading", { name: "Data status" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Station coverage" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Provider reliability" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "100.0%" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "01FB001" }).first()).toBeVisible();
});

test("shows a useful homepage error when the API fails", async ({ page }) => {
  await mockApi(page, { failStationList: true });
  await page.goto("/");

  const alert = page.locator(".error-card[role='alert']");
  await expect(alert).toContainText("River data is unavailable.");
  await expect(alert).toContainText("Check that the API is running, then reload.");
});

test("shows a not-found error for an unknown station", async ({ page }) => {
  await mockApi(page, { missingStation: true });
  await page.goto("/stations/UNKNOWN");

  const alert = page.locator(".error-card[role='alert']");
  await expect(alert).toContainText("Station unavailable");
  await expect(alert).toContainText("That station was not found.");
});
