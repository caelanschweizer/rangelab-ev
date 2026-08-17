# ADR 0001: Use a modular monolith

- Status: Accepted
- Date: 2026-08-16

## Context

The project needs an interactive web experience, a typed API, analytics, and
durable storage. It is owned by one student and must remain understandable in a
short portfolio review.

## Decision

Use a React/Vinext web application and one FastAPI service with internal domain,
import, forecasting, and persistence modules. Use one relational database.

## Consequences

The separation demonstrates API and deployment boundaries without operational
overhead from multiple backend services. Modules can be tested independently,
but they deploy together. Scaling one backend capability separately would
require later extraction backed by evidence, not speculation.

## Alternatives considered

- A frontend-only notebook/demo would hide API, persistence, and validation
  work.
- Microservices, Kafka, and Kubernetes would create disproportionate deployment
  and debugging cost for the traffic and team size.
