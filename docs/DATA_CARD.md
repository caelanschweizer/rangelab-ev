# Data card

## Dataset name

RangeLab EV synthetic telemetry fixtures and user-local CSV imports.

## Purpose

The data supports demonstration and testing of CSV normalization, trip
segmentation, energy/efficiency calculations, dashboard rendering, and a
transparent arrival-charge forecast. It is not a general EV benchmark or a
representative sample of Chevrolet Bolt owners.

## Sources and provenance

| Source | Included in public repository | Intended use |
| --- | --- | --- |
| Deterministic synthetic web sample | Yes | Dashboard, screenshots, web checks |
| Deterministic synthetic CSV generator | Yes, including one generated fixture | API demo, tests, evaluation |
| Maintainer's real Bolt export | No | Optional private/local evaluation |
| Contributor/user CSV | No by default | Local import after consent and review |
| Community PID definition table | No | Configure a separate logging tool under its own terms |

The checked-in generated CSV uses seed `2018` and contains 1,908 points across
16 trips. Synthetic values imitate plausible units and relationships but were
not recorded from a physical trip. They must not be presented as measured
vehicle evidence. Reproduce it after installing the backend with:

```bash
rangelab-generate --output ../data/synthetic_bolt_trips.csv --trips 16 --seed 2018
rangelab-evaluate ../data/synthetic_bolt_trips.csv
```

## Expected measurements

The importer recognizes timestamp; speed; state of charge; pack voltage,
current, or power; latitude/longitude; ambient and battery temperature; HVAC
power; and optional distance-related fields commonly seen in Torque/OBD
Fusion-style exports. A timestamp plus either pack power or both pack voltage
and current is required. Unit-labelled imperial aliases are converted to
metric. No distance signal is assumed to be present or authoritative: each
plausible adjacent-sample delta is selected from available normalized signals,
otherwise distance remains unavailable. Exact accepted headers, types,
required fields, and plausibility checks are defined by importer and analytics
tests.

Units are part of the contract. A bare number must not be silently interpreted
as both kW and W, miles and kilometres, or Fahrenheit and Celsius.

## Processing

1. Bound and decode CSV input.
2. Normalize header aliases and units.
3. Drop rows with unusable timestamps, ignore out-of-range sensor values, and
   return aggregate warnings/counts.
4. Apply coordinate-zone masking/rounding and an optional private per-import
   timestamp offset before persistence.
5. Deduplicate, sort by timestamp, and split trips across configured time gaps.
6. Integrate energy/distance only across usable adjacent samples.
7. Persist normalized measurements and derived trip summaries, not the raw CSV
   body.

Missing readings remain missing unless a documented calculation can derive
them. The pipeline should not interpolate across large gaps merely to improve a
metric.

## Privacy characteristics

The public fixtures contain no real VIN, exact personal route, account ID,
email, or owner timestamp. The API accepts optional location because it can
improve distance calculations, but its default rounding does not make a real
route anonymous. See [Privacy design](PRIVACY.md) before handling an export.

## Known limitations and bias

- Synthetic data is cleaner and smaller than real mobile/OBD logs.
- One vehicle generation cannot represent all Bolt model years or other EVs.
- Optional sensors and alias naming differ across apps and configurations.
- Cold-weather, fast-charging, long-gap, clock-shift, and sensor-dropout cases
  may be underrepresented.
- Private maintainer trips reflect one driver, region, vehicle, tire setup, and
  battery history.
- Community-derived signals can carry formula or labeling uncertainty.

## Quality checks

Tests should cover reordered columns, alias headers, missing optional values,
duplicate/out-of-order timestamps, malformed numbers, large time gaps, unit
conversions, empty uploads, and bounded payloads. Any metric shown on a resume
must be reproduced from a versioned, sanitized evaluation command or CI output.

## Appropriate use

- Portfolio review and software demonstrations
- Teaching ingestion, validation, API, and visualization patterns
- Exploratory analysis of an owner's own local exports
- Comparing a forecast to a documented baseline

## Inappropriate use

- Diagnosing battery faults or certifying battery health
- Warranty, resale, insurance, charging, or safety decisions
- Tracking another person or uploading their data without consent
- Claiming fleet-wide accuracy or compatibility from one synthetic/vehicle set
- Training a production model without broader, consented, documented data

## Maintenance

Update this card whenever a public fixture, accepted field, transformation,
retention behavior, or evaluation set changes. Review fixtures for personal
data before every release.
