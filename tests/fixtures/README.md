# Source fixtures

`wsc_01FB001_sample.csv` is a compact sample of official Water Survey of Canada parameter 47 observations requested on 2026-09-23. It was sampled from the five-minute response at wider intervals to keep the repository small; the last 48 hours retain extra points for chart and six-hour-change tests. Values remain unchanged.

`open_meteo_01FB001_sample.json` is a bounded subset of an Open-Meteo forecast API response requested on 2026-09-23 for the station coordinates. The API identifies the hourly values as model data. Riverwise classifies only hours at or before the ingestion evaluation time as `historical_or_modelled`; future hours are stored as `forecast` and excluded from current scoring.

`wsc_additional_stations_sample.csv` contains the recent official parameter 47 rows used to verify `01FB003` and `01FC002` on 2026-09-23. Their complete 14-day history remains a live-ingestion responsibility; the small fixture protects the discovered IDs, headers, timestamps, units, and parser behavior without adding thousands of provider rows to the repository.

These fixtures exist for deterministic parsing and integration tests and are not claims about present conditions.
