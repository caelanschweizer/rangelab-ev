# Vehicle safety and read-only boundary

RangeLab EV is an analytics project, not a vehicle controller. Version 1 reads
CSV files that were exported by separate logging software; it does not connect
to the Chevrolet Bolt, transmit CAN/OBD commands, clear diagnostic codes,
change charge limits, or interact with safety-critical systems.

## Non-negotiable boundary

Code that requests or transmits write/service/reprogramming commands is out of
scope. A future direct adapter integration would require a separate design and
security review and must remain demonstrably read-only.

## If you collect your own log

1. Read the owner's manual and the adapter/app instructions first.
2. Use reputable, compatible hardware and current software.
3. Configure logging while parked. Do not handle a phone, laptop, or dashboard
   while driving.
4. Do not use the project to diagnose a warning light or decide whether a
   vehicle is safe to drive.
5. Disconnect the adapter if the vehicle behaves unexpectedly, service or
   diagnostic features stop working, or the 12-volt battery may be affected.
6. Remove aftermarket equipment before service and tell the technician what was
   connected.

Chevrolet's official manuals and guides are the primary vehicle reference:
[Chevrolet manuals and guides](https://www.chevrolet.com/support/vehicle/manuals-guides).
General Motors has also documented that unauthorized devices on a diagnostic
link can cause difficult-to-diagnose communication conditions. Treat an OBD
adapter as equipment connected to a vehicle network, not as a harmless USB
drive.

## Interpretation safety

- Community-discovered PIDs may be incomplete, mislabeled, vehicle-specific, or
  based on an unvalidated formula.
- A calculated usable-capacity trend is not a certified battery state-of-health
  measurement.
- Arrival state of charge is an estimate affected by weather, speed, elevation,
  HVAC, traffic, tires, payload, battery temperature, and missing data.
- The dashboard must not be used as a replacement for the vehicle display,
  service tools, recalls, or professional advice.

If a RangeLab result conflicts with the vehicle or official service guidance,
trust the vehicle/manufacturer guidance and treat the project result as a bug
or unsupported case.

## Project disclaimers

Chevrolet, Bolt, OnStar, Torque Pro, EngineLink, and OBD Fusion are trademarks
of their respective owners. This independent project is not affiliated with or
endorsed by General Motors or those products. The MIT license provides the
software without warranty; it does not waive vehicle, traffic, privacy, or
device-safety obligations.
