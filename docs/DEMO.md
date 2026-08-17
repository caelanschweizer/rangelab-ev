# Demo and publishing guide

The repository is designed to be reviewable without a Chevrolet Bolt, OBD
adapter, private dataset, or paid service.

Public synthetic dashboard:
[rangelab-ev.caelan.chatgpt.site](https://rangelab-ev.caelan.chatgpt.site)

## Local reviewer path

```bash
docker compose up --build
```

Then open:

- Web demo: `http://localhost:3000`
- API documentation: `http://localhost:8000/docs`
- API health: `http://localhost:8000/health`

Compose binds both published ports to `127.0.0.1`. The API is unauthenticated
and must remain local to one trusted user; changing the bind address is not a
deployment procedure. The web demo is standalone synthetic sample mode and does
not read from the API.

The visible trip is synthetic sample data. Use it to discuss the product and
architecture, not as evidence that a real vehicle produced those exact values.

## Suggested 90-second portfolio walkthrough

1. Start on the trip overview and explain the problem in one sentence: raw EV
   logs are hard to interpret and risky to share.
2. Point out energy used, regeneration, temperature, and arrival-charge
   estimate; state that demo values are synthetic.
3. Open the API docs and show the versioned import, trip, and forecast schemas.
4. Show one importer or domain test for malformed telemetry.
5. Open the architecture, privacy, and model cards to demonstrate that safety,
   limitations, and evidence were designed with the code.
6. End on the
   [successful v1.0.0 GitHub Actions run](https://github.com/caelanschweizer/rangelab-ev/actions/runs/31988801525)
   and [tagged release](https://github.com/caelanschweizer/rangelab-ev/releases/tag/v1.0.0).

## Sites deployment

The checked-in `.openai/hosting.json` marks the web project for Sites. Publishing
should use the tested production build and keep the public experience in sample
mode unless a separately secured API is configured.

The authoritative v1 production URL is
[rangelab-ev.caelan.chatgpt.site](https://rangelab-ev.caelan.chatgpt.site).
Only this standalone synthetic dashboard is hosted. The complete FastAPI and
PostgreSQL stack remains locally reproducible through Docker Compose; it is not
part of the public deployment. If a remote API is later attached, configure a
production CORS allowlist, real secrets, upload limits, retention/deletion,
TLS, monitoring, and authentication before accepting any real person's
telemetry.

## GitHub Pages distinction

GitHub Pages serves static assets and cannot run the FastAPI or PostgreSQL
services. This Vinext project also has a server-capable build, so a Pages
deployment should only be added after verifying a static export path and all
routes/assets under the repository base path.

For v1, GitHub remains the system of record for source, issues, CI, releases,
and documentation, while Sites is the appropriate host for the interactive web
demo. A broken Pages workflow is less credible than a documented, repeatable
local stack.

## Pre-publish checklist

- Production build and all tests pass from a clean checkout.
- Starter copy, placeholder metadata, and unused preview assets are gone.
- Demo data and screenshots are synthetic and labeled.
- No `.env`, database, real log, coordinates, or credentials are staged.
- Mobile and keyboard behavior has been checked.
- README links and API examples match the release.
- The actual published URL is recorded in the README and repository metadata.
