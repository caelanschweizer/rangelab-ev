# ADR 0002: Import exported logs before direct vehicle integration

- Status: Accepted
- Date: 2026-08-16

## Context

Direct OBD/CAN access introduces device compatibility, vehicle-network safety,
driver-distraction, and testability concerns. A portfolio reviewer also needs a
demo without owning the same car and adapter.

## Decision

Version 1 accepts bounded CSV file or text uploads. RangeLab EV never transmits
vehicle commands. Synthetic fixtures exercise the same import boundary.

## Consequences

Development and CI are deterministic, reviewers need no hardware, and vehicle
interaction remains outside the application. Users must configure and operate a
separate logger. Live streaming is deferred, and import adapters must handle
format variation explicitly.

## Alternatives considered

- A Bluetooth logger would be visually impressive but harder to test and easier
  to overclaim as safe.
- An unofficial connected-car API would add credential, availability, and terms-
  of-service risk unrelated to the core analytics problem.
