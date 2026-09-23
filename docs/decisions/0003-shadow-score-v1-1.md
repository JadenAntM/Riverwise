# ADR 0003: Evaluate score v1.1 in shadow mode

## Status

Accepted as a post-MVP experiment. It does not replace the primary `v1.0.0` score.

## Context

The 14-day baseline in v1.0 describes recent conditions but not whether a flow is unusual for the season. Nearby modeled air temperature also cannot stand in for water temperature. Some WSC stations publish parameter 5 water temperature, and the WSC daily service provides historical discharge suitable for a station-specific seasonal comparison.

These additions may make the heuristic easier to reason about, but Riverwise has no effort-normalized catch outcomes with which to establish predictive accuracy.

## Decision

Run `v1.1.0-shadow` beside v1.0 and expose both through the comparison API and Score Lab. Keep v1.0 as the station-list score.

The candidate assigns four points to a season-matched flow percentile, two to absolute six-hour flow stability, and four to measured water temperature. Seasonal history uses prior years within ±7 calendar days and requires at least 21 daily values across at least three years. Temperature must be no more than three hours old. When it is missing, rescale over six available points and label the result partial; never substitute air temperature.

Ingest up to ten years of WSC daily discharge initially and refresh a 14-day overlap at most every 20 hours. Preserve provider symbols and observation dates. WSC does not apply standardized quality assurance to non-flow/level outputs, so temperature remains explicitly timestamped and qualified.

## Consequences

Users can inspect how the candidate differs without silently changing existing rankings. The historical import adds storage and one larger first-run request. Stations without measured temperature still receive a partial candidate when their flow inputs are sufficient. No score difference may be described as greater accuracy until an appropriate validation dataset and method exist.
