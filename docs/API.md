# API usage

The API listens on `http://localhost:8000` by default. Its stable application
prefix is `/api/v1`; operational health remains at `/health`.

> The v1 API is unauthenticated and intended for one trusted user on loopback.
> It has no accounts, authorization, or tenant separation. Do not expose it to
> a LAN or the internet. CORS limits browser origins; it is not authentication.

After starting the backend, use:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
- Health check: `http://localhost:8000/health`

The generated OpenAPI document is authoritative. The examples below are a
human-friendly walkthrough.

## Health

```bash
curl http://localhost:8000/health
```

## Import CSV text

`POST /api/v1/imports/csv-text` accepts a JSON object whose `csv_text` field is
the complete CSV string. The same object may set `source_name`, an idempotency
key, privacy options, segmentation options, and the pack-power sign convention.
Swagger UI is the easiest way to construct a schema-valid request without
shell-specific JSON escaping.

## Import a CSV file

```bash
curl -X POST http://localhost:8000/api/v1/imports/csv \
  -F "file=@data/synthetic_bolt_trips.csv;type=text/csv"
```

For a real local log, pass privacy zones in the multipart body rather than the
URL. This example masks a 500 m zone, rounds other coordinates, and privately
shifts all timestamps while preserving intervals:

```bash
curl -X POST http://localhost:8000/api/v1/imports/csv \
  -F "file=@path/to/private-trip.csv;type=text/csv" \
  -F 'privacy_options={"enabled":true,"zones":[{"name":"home","latitude":43.9,"longitude":-78.8,"radius_m":500}],"coordinate_precision":4,"mask_coordinates_in_zones":true,"shift_timestamps":true}'
```

The API is still unauthenticated, and plain HTTP is not encrypted. This example
is only for a trusted local machine; privacy transformation is not permission to
upload personal telemetry to a remote server.

Save the returned import identifier. Then inspect import status, aggregate
dropped/duplicate counts, field mapping, and warnings:

```bash
curl http://localhost:8000/api/v1/imports/IMPORT_ID
```

Responses expose independent random UUIDv4 import/trip IDs, not content or
request digests. Internal request identity uses a keyed HMAC so identical
requests can replay safely while the server keeps the same
`RANGELAB_IDENTITY_SECRET`. For a persistent database, configure a stable,
high-entropy secret of at least 32 UTF-8 bytes before the first import; do not
put private data in an `Idempotency-Key`.

## Explore trips

```bash
curl http://localhost:8000/api/v1/trips
curl http://localhost:8000/api/v1/trips/TRIP_ID
curl http://localhost:8000/api/v1/trips/TRIP_ID/telemetry
curl http://localhost:8000/api/v1/summary
```

Pagination, accepted query parameters, and response schemas are shown in
Swagger UI. Clients should not infer missing samples or assume every optional
sensor is present.

## Forecast and diagnostics

Open `/docs`, expand `POST /api/v1/forecast`, and use **Try it out** to obtain a
schema-valid request for the current release. Model behavior and appropriate
interpretation are documented in the [Model card](MODEL_CARD.md).

```bash
curl http://localhost:8000/api/v1/model/diagnostics
```

Diagnostics are evidence about the included sample/evaluation set, not proof of
performance for all vehicles, seasons, routes, or drivers.

## Errors

Schema, encoding, and invalid telemetry failures use HTTP `422`; oversized
uploads use `413`; reusing an idempotency key for different content/options uses
`409`; missing resources use `404`; and database health failures use `503`.
Consumers should branch on status and structured fields, not parse
human-readable messages.

## API compatibility

Breaking application changes require a new prefix such as `/api/v2`. Additive
fields may appear within v1, so clients should ignore unknown response fields.
The health endpoint is intentionally outside the versioned business API.
