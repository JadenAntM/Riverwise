# ADR 0004: Persist score history and define reliability metrics

## Status

Accepted for the six-station reliability milestone.

## Context

Current API responses describe one instant and cannot show whether scores, provider availability, or data freshness remain stable over time. A generic “uptime” label would also hide whether failures belong to a provider, a station, or a particular data type.

## Decision

After every scheduled import, persist one snapshot for `v1.0.0` and one for `v1.1.0-shadow` for every configured station. Store the explicit ingestion evaluation time, rules version, score, status, confidence, coverage, reasons, components, and nullable source-observation time. Upsert on station, evaluation time, and rules version so retries are idempotent. Preserve null scores for stale, insufficient-history, and insufficient-data states.

Report reliability over selectable seven- and 30-day windows. Provider success rate is successful stored attempts divided by all stored attempts for one provider/station pair. Row metrics distinguish new records, existing records refreshed by an overlapping fetch, and revisions where provider fields actually changed. Revision counts begin with this release and are not reconstructed retroactively.

Water-temperature availability is the number of candidate snapshots with a fresh measured temperature component divided by all candidate snapshots for that station. Data freshness is the age of the latest measured discharge. Historical coverage reports stored daily-row count, date range, and distinct years. Observation counts report stored discharge and water-temperature rows inside the selected window.

## Consequences

The station page can draw honest seven- and 30-day score histories without inventing values across unavailable periods. The status page can support portfolio claims with explicit numerators, denominators, windows, and definitions. Meaningful percentages require time to accumulate, and initial charts may contain only one point. These operational metrics do not validate the score against catches.
