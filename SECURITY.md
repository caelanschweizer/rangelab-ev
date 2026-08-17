# Security policy

RangeLab EV processes files that can reveal driving habits, locations, and
vehicle details. Security and privacy defects are therefore treated as product
bugs, not documentation-only concerns.

## Supported version

Security fixes are applied to the latest commit on the default branch. This is
a student portfolio project and does not currently maintain older release
branches.

## Reporting a vulnerability

Please use **Security → Report a vulnerability** in the GitHub repository so
the report is handled through a private security advisory. Do not include a
real trip log, VIN, home/work coordinates, access token, or other personal data
in a public issue.

Include:

- the affected commit or release;
- a minimal reproduction using synthetic data;
- the expected and observed behavior; and
- the likely impact, if known.

If private advisories are unavailable, open a public issue containing no
exploit details or private data and ask the maintainer for a private contact
channel. Receipt should be acknowledged within seven days. No guaranteed
response or remediation SLA is offered.

## Security boundaries

The project:

- imports exported CSV text; it does not send commands to a vehicle;
- treats uploads as untrusted input and applies size, encoding, and schema checks;
- does not require a VIN, precise address, account credential, or API key for
  the public demo;
- ships synthetic demo records, not a maintainer's raw trips; and
- keeps local environment files and databases out of version control.

The API keys internal import identities with `RANGELAB_IDENTITY_SECRET` and
does not return those HMAC values. For any persistent database, use a
high-entropy value containing at least 32 UTF-8 bytes and keep it stable and out
of version control. The Compose fallback is public, local-development
material—not a production secret or a privacy guarantee for real telemetry.

The v1 API has no authentication, authorization, or tenant isolation. Docker
Compose binds published ports to `127.0.0.1` by default; this is a local
exposure boundary, not an authentication mechanism. CORS is not access control.
Do not expose the API to a LAN or the internet.

The project is not an automotive diagnostic device, a safety system, a secure
telemetry recorder, or a substitute for manufacturer service information.
See [Vehicle safety](docs/VEHICLE_SAFETY.md) and
[Privacy](docs/PRIVACY.md).

## Maintainer release checklist

Before publishing a release:

1. Run the frontend, backend, and container CI jobs.
2. Search the staged diff for secrets, VIN-like values, email addresses, and
   precise coordinates.
3. Confirm demo files are synthetic and labeled as such.
4. Review dependency alerts and the upload/import threat model.
5. Keep the API local, or verify an authenticated TLS gateway, retention and
   deletion controls, production secrets, and restricted CORS origins exist
   before any network exposure.
