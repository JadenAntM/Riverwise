# ADR 0001: Rank complete scores ahead of partial scores

## Status

Accepted for scoring rules `v1.0.0`.

## Context

Riverwise can compute a score when exactly one of the two weather components is missing. Rescaling the earned points to ten makes the number readable, but it can make an incomplete score appear stronger than a score backed by every component.

## Decision

Show the rescaled value together with available component points and `partial` confidence. Lists sort complete scores first, partial scores second, and unavailable stations last. Score coverage is never hidden.

## Consequences

Users can still inspect a partially supported score, while list ordering does not reward missing data. Scores with different coverage should not be treated as equivalent measurements.
