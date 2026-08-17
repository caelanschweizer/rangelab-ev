# Roadmap

The roadmap protects the project's credibility by separating a complete,
reviewable v1 from attractive but unnecessary infrastructure.

## v1 — portfolio release

- Standalone synthetic web demo plus an OpenAPI-driven API workflow, both usable
  without a vehicle
- CSV file/text ingestion with validation and aggregate rejection diagnostics
- Trip segmentation, energy, regeneration, and efficiency summaries
- Versioned FastAPI endpoints and generated OpenAPI documentation
- Transparent arrival-charge forecast plus baseline diagnostics
- Responsive Vinext/React interface with clear sample-data labeling
- SQLite local default and PostgreSQL Docker Compose path
- Unit/integration checks, frontend checks, and container builds in CI
- Data card, model card, privacy design, safety boundary, and PID attribution
- One-command local setup and a tagged GitHub release

The checkbox for a release item belongs in GitHub Issues or Projects. This file
describes scope and should not claim completion merely because code exists on a
working branch.

## v1.1 — evidence from private real-world use

- Import several sanitized logs from the owner's 2018 Bolt
- Add an importer compatibility report for the chosen mobile logger
- Expand dropout, clock-shift, duplicate, and temperature edge-case tests
- Record trip count, sample count, rejection rate, and test count
- Evaluate forecasts chronologically against the distance-only baseline
- Publish only aggregate metrics that pass privacy review

## v1.2 — product depth

- Saved comparison views for cold versus mild conditions
- Capacity-trend experiment with uncertainty and prominent non-diagnostic label
- Exportable sanitized trip summary
- Accessibility audit and performance budget
- Database migrations and deletion workflow if persistent hosted use is added

## Later research

- Route elevation and forecast-weather features with caching and provenance
- Read-only direct adapter prototype behind an explicit experimental boundary
- Additional EV formats through adapter-specific import modules
- Broader, consented evaluation across vehicles and seasons

## Explicit non-goals

- Sending vehicle/CAN commands or clearing trouble codes
- Scraping unofficial OnStar endpoints
- Claiming battery diagnosis or guaranteed remaining range
- Kafka, Kubernetes, microservices, or a custom mobile app for résumé optics
- Publishing raw personal telemetry

New work should be accepted because it improves user value, evidence, safety,
or maintainability—not because it adds another technology name.
