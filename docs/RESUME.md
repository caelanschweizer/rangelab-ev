# Resume and interview evidence

This file prevents the project from turning into unsupported résumé claims.
Replace every bracketed value only after a command, release, or report makes it
reproducible.

## Evidence ledger

| Claim | Evidence to record | Where to find it |
| --- | --- | --- |
| Telemetry scale | `[N]` accepted samples, `[K]` trips, rejected-row count | Versioned import summary on a sanitized evaluation set |
| Forecast result | Enhanced and baseline MAE on `[K]` chronological holdout trips | Model diagnostics/report tied to a commit |
| Test coverage | 46 passing automated tests: 42 backend + 4 frontend; 89% backend branch coverage | [v1.0.0 CI run](https://github.com/caelanschweizer/rangelab-ev/actions/runs/31988801525) |
| Reliability | Import edge cases and API/container checks | Test names and CI workflow |
| Delivery | Tagged release and standalone public synthetic demo | [v1.0.0 release](https://github.com/caelanschweizer/rangelab-ev/releases/tag/v1.0.0) and [live demo](https://rangelab.caelanschweizer.com) |

Do not count generated or synthetic trips as real Chevrolet Bolt trips. Do not
quote a test count that includes failed, skipped, or unrelated generated checks
without saying so.

The [v1.0.0 release](https://github.com/caelanschweizer/rangelab-ev/releases/tag/v1.0.0)
evidence is 42 passing backend tests at 89% branch-aware coverage plus 4/4
passing frontend `node:test` cases; frontend lint, type-check, production build,
PostgreSQL integration, and both container builds also pass in the
[matching GitHub Actions run](https://github.com/caelanschweizer/rangelab-ev/actions/runs/31988801525).

The seed-2018 synthetic report currently provides a reproducibility example—
1,908 generated samples, 16 generated trips, and 0.3414 versus 0.3480 kWh
walk-forward MAE—but those values must stay labeled **synthetic** and should not
replace the real-trip placeholders below.

## Resume bullet templates

- Built a privacy-first EV telemetry platform with **FastAPI, SQLAlchemy,
  PostgreSQL, React, and TypeScript**, processing **[N] samples across [K]
  sanitized real trips** with schema validation and trip-level energy analysis.
- Evaluated an arrival-charge estimator on **[K] chronologically held-out
  trips**, achieving **[X] kWh energy MAE** and **[Y]% lower error** than a
  distance-only baseline.
- Shipped a one-command Docker Compose environment and GitHub Actions pipeline
  with **46 automated tests** across backend and frontend, plus data/model cards
  documenting privacy, uncertainty, and failure modes.

If real-trip/model evidence is not ready, use this honest release
bullet:

- Built a locally reproducible EV telemetry platform with a versioned FastAPI
  API, PostgreSQL/SQLite persistence, Docker Compose, and 46 automated tests;
  deployed its standalone synthetic React/TypeScript dashboard
  ([live demo](https://rangelab.caelanschweizer.com)).

The public synthetic web experience is now deployed. Do not imply that the v1
dashboard uploads to or reads from the API; API workflows are demonstrated
separately through OpenAPI.

## One-line project description

RangeLab EV turns read-only Bolt-style CSV telemetry into explainable trip
energy analysis and an uncertainty-aware arrival-charge estimate.

## Interview story

Use a four-part explanation:

1. **Problem:** EV logs are noisy and personally sensitive, while range numbers
   are easy to overstate.
2. **Decision:** An import-first modular monolith made the project safer,
   repeatable to demo, and realistic for one developer.
3. **Engineering:** Describe validation, units, trip segmentation, persistence,
   API contracts, frontend states, tests, and container delivery.
4. **Judgment:** Explain why the demo is synthetic, the forecast is compared to
   a simple baseline, and direct vehicle control is excluded.

Strong follow-up material includes one rejected-row test, one model limitation,
one privacy threat, one architecture tradeoff, and one feature deliberately
left out.

## GitHub portfolio checklist

- Repository is public and every README link works in a signed-out browser.
- The description, topics, social image, and actual demo URL are set.
- Default branch CI is green and branch protection requires it.
- The [v1.0.0 release](https://github.com/caelanschweizer/rangelab-ev/releases/tag/v1.0.0)
  points to the demo and evidence ledger.
- Issues/milestones show intentional future work rather than an abandoned TODO
  dump.
- Commit history does not contain secrets or real telemetry.
