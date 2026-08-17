# ADR 0004: Make the public demo synthetic

- Status: Accepted
- Date: 2026-08-16

## Context

Real trip logs can reveal home/work locations, schedules, identifiers, and
vehicle history. A reviewer should be able to use the project without receiving
personal data.

## Decision

All checked-in fixtures and public demo values are fabricated and labeled as
synthetic/sample data. Real logs remain local. Only sanitized aggregate evidence
may be published after explicit review.

## Consequences

The public experience is reproducible and safer to share. Synthetic data is not
proof of real-world accuracy, so data/model cards and resume bullets must keep
that distinction visible.

## Alternatives considered

- Publishing a blurred or truncated raw trip still risks re-identification and
  git-history retention.
- An empty demo would protect privacy but make the project difficult to review.
