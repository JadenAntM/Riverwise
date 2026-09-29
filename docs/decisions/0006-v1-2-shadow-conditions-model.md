# ADR 0006: Keep v1.2 as a measurable shadow conditions experiment

Date: 2026-09-29

## Context

The canonical specification keeps `v1.0.0` on the dashboard and introduced `v1.1.0-shadow` for a season-matched flow and measured-temperature comparison. Phase 2 asks for longer rainfall windows, short- and long-term discharge trends, station-specific context, rapid rises, daylight, pressure trend, reproducible inputs, and outcome evaluation. The user has no trip observations this season. These factors therefore cannot be called more accurate or given biological meaning on the basis of score differences alone.

## Decision

Add `v1.2.0-shadow` to the Score Lab and stored snapshots, while leaving `v1.0.0` as the sole production dashboard score. This is a deliberate extension of the specification's two-version Score Lab; no production ranking changes. Existing snapshots are not backfilled or relabeled.

The provisional 10-point model is:

| Input | Raw points | Provisional rule and reason to test |
| --- | ---: | --- |
| Station-month discharge percentile | 3 | Compare the latest measured discharge with prior-year daily discharge in the same calendar month. Require 21 values across three years; score 3 for the 25th–75th percentile, 1 for the 10th–<25th or >75th–90th, 0 outside. This gives station-specific seasonal context, not evidence of fishing quality. |
| One-hour discharge trend | 1 | Score 1 for −5% through +5%, 0 otherwise. Require an observed endpoint within ±30 minutes and a prior value above 0.001 m³/s. |
| Six-hour discharge trend | 1 | Score 1 for −20% through +10%, 0 otherwise. Six-hour history is required; a missing one-hour endpoint makes coverage partial. |
| Nearby modeled precipitation over 6, 24, and 72 complete hours | 1 each | Provisional middle bands are 0.5–5, 1–15, and 2–30 mm inclusive. Each window requires every non-forecast hourly value. These bands are hypotheses from the earlier moderate-precipitation rule; longer windows capture antecedent conditions but do not prove favorable fishing. |
| Fresh measured water temperature | 2 | Reuse v1.1's 12–16°C central, 6–<12°C and >16–18°C outer, and other bands, scaled to 2/1/0 points. Omit if older than three hours or unreported; never substitute air temperature. |
| Rapid-rise penalty | −1 raw point | If the latest one-hour rise exceeds the station's 90th percentile of positive one-hour rises in the previous 14 days, remove one raw point. Require at least 24 positive comparison rises and seven days of history. This describes an unusually fast change at that gauge, not a safety determination. |

Available raw points are rescaled to 0–10 as in v1.0/v1.1; when an input is missing, the result is visibly `partial` with available and earned points. The rapid-rise penalty is applied before rescaling, so its effect on a partial 0–10 score can exceed one displayed score point. No score is returned when flow is stale (>3 hours), the station-month reference or six-hour comparison is absent, or all three rainfall windows are absent. These choices avoid manufacturing a complete score from missing measurements.

The 24-hour discharge change, approximate sunrise/sunset and daylight state, current nearby modeled surface pressure, and six-hour pressure change are retained as unscored context. A pressure trend can only be judged more useful than absolute pressure by comparison against an external outcome, not by comparing the two pressure series or their correlation with this heuristic score. Daylight likewise receives no points without outcome evidence. Sunrise/sunset use an approximate NOAA solar calculation at the official gauge coordinates and Atlantic local date; they are astronomical estimates, not weather forecasts or observed light conditions.

Open-Meteo defines hourly `precipitation` as the **preceding hour's sum**. At an evaluation time within UTC hour `H`, the newest completed interval is labeled `H`; a six-hour total uses labels `H` through `H−5`. The previous v1.0 12-hour window remains unchanged to preserve its production meaning; its existing `[H−12, H)` logic is one hour earlier than this interpretation, a known semantic difference to review separately before any production-score revision. The ingestion request now retrieves four past UTC days, enough for a 72-hour window around day boundaries, while scoring filters out `forecast` rows. [Open-Meteo hourly parameter definitions](https://open-meteo.com/en/docs/historical-weather-api).

Every new snapshot stores the exact direct scoring-function inputs in `components_json.inputs`, along with point-level components and unscored context. New v1.0 and v1.1 snapshots also store their direct inputs. This reproduces the score from those feature values, but not necessarily the entire upstream aggregation after providers revise source rows. Existing snapshots predating this change have no input payload. The read API exposes stored inputs and components for audit; no database migration is required because `components_json` is already JSON.

## Evidence and limits

The comparison script, [`scripts/analyze_score_models.py`](../../scripts/analyze_score_models.py), recomputes all three versions at the same sampled UTC times in a separate local database restored from a verified production export. It reports availability and score differences, not fishing accuracy. Historical provider revisions can change a replayed score from its original snapshot. No trip observations were supplied; outcome evaluation is therefore explicitly unavailable. Future evaluation should collect consented, effort-normalized trips, including zero-catch trips, with enough coverage to compare high and low conditions by station and season. Do not turn either a score difference or an environmental association into a catch-prediction claim.

On 2026-09-29, a read-only replay of the verified production export sampled 36 evenly spaced stored evaluation times from 2026-09-24 15:05 to 2026-09-29 21:02 UTC across all six stations (216 station-time comparisons). The mean scores were 6.491 for v1.0, 8.831 for v1.1, and 6.095 for v1.2. Compared with v1.0, v1.2 differed by at least one point in 139/216 pairs; its mean absolute difference was 1.631 points. All 216 sampled v1.2 calculations returned a score, but 184 were partial because at least one optional scoring input was unavailable; this run did not tabulate missingness by factor. Both current absolute pressure and its six-hour change were calculable in 216/216 sampled cases. This is a **difference and input-coverage measurement**, not a validation result; it is also biased toward times present in the historical snapshot table. The exact command used was:

```sh
DATABASE_URL='postgresql://riverwise:riverwise@localhost:5432/LOCAL_RESTORE_DB' \
  .venv/bin/python scripts/analyze_score_models.py --max-times 36
```

`LOCAL_RESTORE_DB` is a placeholder for a separate local restore. The script rejects non-local database hosts and never writes to the database. The original restored backup was exported on 2026-09-29; later provider revisions and a wider evaluation window can produce different numbers.

The solar calculation is based on [NOAA's published equations](https://gml.noaa.gov/grad/solcalc/solareqns.PDF); NOAA cautions that calculated sunrise/sunset may differ from observed times owing to atmospheric conditions. Water temperature remains [WSC-measured where reported](https://wateroffice.ec.gc.ca/services/) and is not available at every gauge. All scoring thresholds are portfolio experiment assumptions, not validated brook trout criteria.

The deployed [seven-day reliability API](https://api-production-f376.up.railway.app/api/v1/reliability?days=7) showed 667 recent measured water-temperature observations and 100% candidate-snapshot temperature availability at `01FB001` on 2026-09-29; the other five stations showed zero observations and 0% availability. The existing WSC parameter-5 ingestion already checks these gauges. We did not fill those gaps with modeled air temperature or an unverified nearby sensor; adding a new source would require confirming its location, timestamp, unit, quality flags, license, and relevance to the gauge first.

Railway reported successful web, API, and scheduled-ingestion deployments of commit `f9f309b2d4d9b537aee777ad0490f2dd2a8a6201` on 2026-09-29. The 22:31 UTC production ingestion completed all 12 WSC/Open-Meteo station-source imports and wrote 18 score snapshots (three versions for each of six stations). Public `scores/compare` and score-history responses exposed a `v1.2.0-shadow` result and stored direct inputs for all six stations; the public Score Lab displayed the third version. This establishes deployment and calculation coverage, not score accuracy or a completed seven-day reliability window.

A search for public catch observations did not identify a suitable station-time, effort-normalized dataset. Nova Scotia's [Sportfish Angler Records](https://data.novascotia.ca/Fishing-and-Aquaculture/Nova-Scotia-Sportfish-Angler-Records/7rxg-qfam) list record holders, not ordinary trips or zero-catch effort. Historical provincial [creel-survey reports](https://novascotia.ca/fish/documents/special-management-areas-reports/Sea_Run_Trout_Fisheries_in_Northumberland_Strait_Rivers_2002.pdf) summarize other rivers and seasons; they cannot validate these six gauges' current hourly scores. No records from either source were converted into synthetic outcome labels.
