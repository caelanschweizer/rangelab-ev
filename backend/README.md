# RangeLab EV API

The backend imports read-only EV telemetry, derives trip-level energy metrics,
and produces an explainable trip-energy forecast. It can mask coordinates
inside caller-configured privacy zones, round remaining coordinates, and shift
timestamps before persistence. The default has no privacy zones, so it does
**not** automatically remove sensitive trip endpoints. It never sends commands
to a vehicle.

## Run locally

```powershell
cd backend
python -m pip install -e ".[dev]"
uvicorn rangelab.api:app --reload --port 8000
```

Open `http://localhost:8000/docs` for the generated OpenAPI explorer. SQLite is
used by default and creates `rangelab.db` in the current directory.

The multipart importer accepts the CSV in `file`, an optional `Idempotency-Key`
header, and JSON form fields named `privacy_options` and
`segmentation_options`. Home/work coordinates therefore stay in the request
body rather than appearing in URLs or ordinary access logs. Plain HTTP is not
encrypted; keep this API on loopback. Any future network transport would need
TLS as well as authentication. For example, `privacy_options` can contain:

```json
{
  "enabled": true,
  "zones": [{"name": "home", "latitude": 43.9, "longitude": -78.8, "radius_m": 500}],
  "coordinate_precision": 4,
  "mask_coordinates_in_zones": true,
  "shift_timestamps": true
}
```

When timestamp shifting is enabled, a cryptographically random, per-import
offset obscures both date and clock time. The offset is not returned or logged.
Sampling intervals are retained, but calendar date, season, and time-of-day
must be treated as anonymized.

Import matching uses a server-secret HMAC over the canonical CSV and every
privacy, segmentation, and power-sign option. Those internal digests are stored
only for matching and are absent from API responses and OpenAPI schemas, so
they cannot act as a public coordinate-guessing oracle. Public import and trip
IDs are independent random UUIDv4 values. Replaying the same request is safe;
reusing an explicit idempotency key for different input returns HTTP `409
Conflict`.

> The API has no authentication or multi-user isolation. Uvicorn's command
> above binds to loopback by default; keep it local. CORS restricts browser
> origins but does not prevent non-browser clients from reaching an exposed
> API.

Configuration is environment-based:

| Variable | Default | Purpose |
| --- | --- | --- |
| `RANGELAB_DATABASE_URL` | `sqlite:///./rangelab.db` | SQLAlchemy database URL |
| `RANGELAB_CORS_ORIGINS` | `http://localhost:3000` | Comma-separated browser origins |
| `RANGELAB_MAX_UPLOAD_BYTES` | `10000000` | CSV upload limit |
| `RANGELAB_TRIP_GAP_MINUTES` | `15` | Gap that starts a new trip |
| `RANGELAB_IDENTITY_SECRET` | Random per process | HMAC key; at least 32 bytes |

For PostgreSQL, install `.[postgres]` and set (for example)
`RANGELAB_DATABASE_URL=postgresql+psycopg://user:password@localhost/rangelab`.

The random identity-secret default is appropriate for a disposable,
single-process local demo. Set a stable, high-entropy
`RANGELAB_IDENTITY_SECRET` to preserve content-based replay across restarts or
multiple workers. Explicit idempotency-key bindings are persisted in the
database; if the secret changes, the service safely refuses an old key rather
than assuming a newly computed request is equivalent.

## Privacy behavior

Privacy processing is enabled by default, but the default only rounds supplied
coordinates to four decimal places. Rounding is not anonymization. Configure a
home/sensitive zone to mask matching points and optionally shift timestamps
before importing a real log. The service persists normalized telemetry, import
metadata, the source filename, and secret-keyed internal matching digests; it
does not persist the raw CSV body. See the root
privacy guide before handling personal data: [Privacy design](../docs/PRIVACY.md).

## Forecast interval semantics

With no eligible trip history, the engineering fallback uses an illustrative
error scale of `0.45 kWh`; it is not a historical residual estimate and its
band is not labelled as an 80% confidence interval. The response sets
`interval.confidence_pct` to `null`, `interval.calibrated` to `false`, and
explains the heuristic in `interval.basis`. A trained model reports a nominal
`80` percent normal-approximation band, still with `calibrated: false`, because
empirical coverage calibration is not claimed.

## Generate deterministic demo data

```powershell
rangelab-generate --output ../data/synthetic_bolt_trips.csv --trips 16 --seed 2018
rangelab-evaluate ../data/synthetic_bolt_trips.csv
```

The generator models plausible—not manufacturer-certified—2018 Chevrolet Bolt
telemetry. Synthetic data is clearly labelled and must not be presented as
measurements from a real vehicle. The evaluator prints exact trip totals, model
sample size, chronological backtest MAE, and distance-only baseline MAE so
published synthetic claims are reproducible.

## Test

```powershell
pytest
```
