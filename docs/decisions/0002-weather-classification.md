# ADR 0002: Separate model history from forecast hours

## Status

Accepted for the MVP.

## Context

Open-Meteo returns hourly model values around the current time. A timestamp from the weather response must not replace a hydrometric observation time, and future values must not affect a current conditions score.

## Decision

Store weather hours at or before the ingestion evaluation time as `historical_or_modelled`. Store later hours as `forecast`. Only `historical_or_modelled` rows are eligible for scoring. Label air temperature as nearby modeled air temperature, never measured water temperature.

## Consequences

The MVP remains honest about its data type and can add a separate forecast surface later without changing the meaning of current scores.
