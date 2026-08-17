# Privacy design

EV telemetry is sensitive even when it contains no name. Repeated coordinates,
timestamps, and trip endpoints can reveal a person's home, workplace, schedule,
and habits. A VIN is a persistent vehicle identifier. RangeLab EV therefore
uses data minimization and a synthetic-first public demo.

## Public repository rule

Do not commit raw exports from a real vehicle. Public fixtures, screenshots,
tests, and demos must be synthetic or reviewed derivatives that cannot be
linked back to a person or vehicle.

Before publishing any derivative, check for:

- VINs, device IDs, adapter IDs, usernames, email addresses, and filenames;
- latitude/longitude, addresses, route polylines, and named endpoints;
- exact timestamps and stable trip identifiers;
- free-text notes or CSV headers copied from a personal device profile; and
- metadata embedded in images or exported files.

Deleting a visible column is not enough if the same information survives in a
filename, screenshot, database, git history, or derived identifier.

## Version 1 behavior

The v1 analytics contract does not require a VIN, driver identity, or online
vehicle account. The importer allowlists recognized telemetry fields and does
not retain the original CSV body. It stores normalized points, import metadata,
the source filename, and server-internal request identities used for safe
replay and idempotency. Those internal values are not returned by the API.

Import identity uses domain-separated HMAC-SHA-256 values keyed by
`RANGELAB_IDENTITY_SECRET`: one covers canonical CSV content and another covers
that content identity plus privacy, segmentation, and power-sign options. A
plain content hash would let someone test guesses against a leaked database;
the HMAC makes that comparison depend on the secret. This does **not** anonymize
the stored telemetry or source filename if the database itself is exposed.

Public import and trip IDs are independent random UUIDv4 values rather than
content-derived hashes. Replaying the same request resolves to the same stored
import only while its internal identity can be matched; public IDs themselves
are not privacy controls. The optional `Idempotency-Key` is stored for replay
handling, so it must not contain a VIN, address, account value, or other secret.

When `RANGELAB_IDENTITY_SECRET` is unset, the API creates a cryptographically
random process-local value. That is convenient for a disposable native session
but does not survive a restart. Set a stable, high-entropy value containing at
least 32 UTF-8 bytes before using a persistent database; changing it prevents
old request identities from matching and makes reuse of an existing idempotency
key conflict. The loopback Compose setup supplies an explicitly non-production
development fallback so its local database remains consistent across container
restarts.

Location is optional but, if supplied, is persisted after the requested privacy
transform. Privacy processing is enabled by default and rounds coordinates to
four decimal places. **Rounding alone is not anonymization.** For a real log,
the caller should also provide sensitive zones so matching coordinates are
removed, and may request a private timestamp shift. Both the multipart and JSON
endpoints support multiple named zones through `PrivacyOptions`; the multipart
form carries those options as a JSON `privacy_options` field so coordinates do
not appear in its URL.

Zone coordinates are request-body values used during processing and are not
stored as configuration records, though a server can still observe requests and
normalized results. Plain HTTP is not encrypted. The v1 API has no authentication
or tenant separation, so real telemetry must remain on a trusted local machine.
The Compose ports bind to loopback by default. CORS does not protect an API that
has been exposed to a network. Disabling privacy is supported for controlled
local analysis and should never be used for public output.

The public web demo uses fabricated values and labels them as sample data. A
real local import stays on the operator's machine unless they deliberately
configure a remote API.

## Recommended sanitization pipeline

For any location-bearing import or derivative, sanitize before sharing—not
after upload:

1. Remove VIN and account/device identifiers.
2. Remove coordinates within a configurable radius of every sensitive place.
3. Coarsen remaining coordinates and timestamps to the minimum resolution
   needed for the stated analysis.
4. Replace source and trip IDs with random, release-specific identifiers.
5. Recompute derived data from the sanitized set.
6. Inspect the final artifact and its metadata manually.

Hashing a VIN, address, or predictable trip ID is not anonymization: an attacker
can guess candidates and compare hashes.

When `shift_timestamps` is enabled, the current implementation applies one
cryptographically random positive or negative offset between roughly 30 days
and five years to every point in that import. The offset includes clock time,
is not returned or logged, and preserves sampling intervals. Date, season, and
time-of-day are therefore no longer valid analytical features after shifting.

## Retention and deletion

The project does not promise cloud retention or deletion workflows. In the
local setup, the operator controls the database and Docker volume. Stop the
stack before removing data, and verify backups separately. A hosted version
must publish a retention policy and implement deletion before accepting real
user logs.

## Threat model

| Risk | Current control | Residual risk |
| --- | --- | --- |
| Real route appears in Git history | Synthetic-only contribution policy and review checklist | A contributor can still make a mistake |
| CSV executes content | Cells are parsed as data; no spreadsheet evaluation | Opening an export in external spreadsheet software has separate risks |
| Identifier is hidden in unused columns | Allowlist parsed fields; raw CSV body is not persisted | Source filename, request logs, or screenshots need manual review |
| Predictable CSV is correlated from an internal digest | Keyed, domain-separated HMAC; digests omitted from API responses | A known/deployed weak secret or database compromise still exposes risk |
| Rounded coordinates reveal endpoints | Optional zone masking and timestamp shifting | Defaults alone do not anonymize a real route |
| Public demo is mistaken for measured evidence | Synthetic labels and data/model cards | Reviewers may skip disclosures |
| API is exposed beyond the owner machine | Compose publishes to loopback by default | There is no authentication; overriding the bind can expose all stored trips |

## Incident response

If private data is committed, stop sharing the repository, rotate any exposed
credentials, and follow GitHub's sensitive-data removal process. A later commit
that deletes the file does not erase earlier Git objects. Report security or
privacy defects through [SECURITY.md](../SECURITY.md).
