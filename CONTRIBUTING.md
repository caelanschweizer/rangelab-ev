# Contributing to RangeLab EV

Thanks for helping improve the project. Small, reviewable changes with tests
are preferred over broad rewrites.

## Local setup

The fastest complete setup is:

```bash
docker compose up --build
```

That starts the demo at `http://localhost:3000`, the API at
`http://localhost:8000`, and interactive API documentation at
`http://localhost:8000/docs`. The frontend can also run by itself with its
built-in sample trip. Published ports bind to `127.0.0.1`; the API has no
authentication and must not be exposed to a network.

For native development:

```bash
corepack enable
pnpm install --frozen-lockfile
pnpm dev
```

In another terminal:

```bash
cd backend
python -m venv .venv
# Activate .venv using the command for your shell.
python -m pip install -e ".[dev]"
uvicorn rangelab.api:app --reload --port 8000
```

Copy `.env.example` to `.env` only when overriding the documented defaults.
Never commit `.env`, local databases, raw trip exports, or credentials.

## Before opening a pull request

Run the core checks used by CI:

```bash
pnpm lint
pnpm typecheck
pnpm test
cd backend
pytest --cov=rangelab --cov-branch --cov-report=term-missing --cov-fail-under=85
```

CI additionally starts PostgreSQL and exercises API health, synthetic import,
and summary endpoints against it. It also validates and builds both containers.

For container changes, also run:

```bash
docker compose config --quiet
docker compose build
```

## Pull request expectations

- Explain the user-visible outcome and the tradeoff being made.
- Add or update tests for behavior changes.
- Use synthetic fixtures; never add a real person's raw telemetry.
- Update the data card, model card, API guide, or ADR when the contract changes.
- Keep vehicle interaction read-only and import-first. A change that transmits
  OBD/CAN commands is out of scope.
- Do not copy a third-party PID table into this MIT-licensed repository without
  reviewing its terms and preserving attribution.

Conventional Commit-style subjects such as `feat:`, `fix:`, `docs:`, and
`test:` are encouraged but not required.

## Definition of done

A change is complete when it is understandable without private context,
covered in proportion to its risk, passes CI, preserves privacy/safety
invariants, and does not make unsupported performance or model claims.
