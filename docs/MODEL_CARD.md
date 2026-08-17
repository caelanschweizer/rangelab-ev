# Model card

## Model name

RangeLab EV trip-energy and optional arrival state-of-charge forecast.

## Intended question

Given route distance, expected ambient temperature, speed, and HVAC load, what
trip energy is a reasonable software estimate? If starting state of charge and
usable capacity are supplied, what arrival state of charge follows from that
energy estimate, and how does it compare with a distance-only baseline?

This is a range-planning demonstration, not a promise that a vehicle will reach
a destination.

## Version 1 implementation

The estimator uses six explainable features: an intercept, distance, cold ×
distance, heat × distance, a squared speed-deviation × distance term, and an
HVAC energy proxy. With fewer than eight eligible stored trips it uses disclosed
engineering fallback coefficients. At eight or more, it fits ridge-regularized
linear coefficients and constrains physically confusing negative penalties.

Eligibility requires at least 1 km, positive net energy, speed and ambient
temperature, and a data-quality score of at least 55. Every response identifies
whether `engineering_fallback` or `trained_ridge` was used and includes feature
contributions, the equation coefficients, assumptions, and an energy
uncertainty band. The fallback band is an illustrative engineering heuristic;
it does not have a probability or coverage interpretation.

## Inputs and output

The versioned request/response schema is published in OpenAPI under
`POST /api/v1/forecast`. Distance is required. Inputs also accept ambient
temperature (20°C default), expected speed (60 km/h default), HVAC power
(0 kW default), optional starting state of charge, and usable capacity (60 kWh
default). There is no caller-supplied recent-efficiency input in v1; stored
eligible trips influence the fitted estimator and distance-only baseline.

The response includes predicted/baseline energy, an uncertainty-band object in
the `interval` field, optional arrival state of charge, `model_kind`,
training-trip count, equation, contributions, and assumptions. For the
engineering fallback, `confidence_pct` is null and `calibrated` is false. The
band is a sensitivity aid, not a confidence interval. Defaults are
request-schema behavior, not observed sensor values.

## Baseline

The baseline estimates energy from distance multiplied by the historical mean
net kWh/km of eligible trips. When no eligible history exists, it uses
0.18 kWh/km. The optional arrival state of charge divides predicted energy by
the caller-supplied usable capacity (60 kWh default). It is intentionally easy
to explain and difficult for a more elaborate method to beat by accident.

Any enhanced estimator must demonstrate lower held-out error than that baseline
before the README or resume calls it an improvement.

## Evaluation

Primary metrics are:

- model mean absolute energy error in kWh;
- distance-only baseline mean absolute energy error in kWh; and
- relative error improvement on the same walk-forward predictions.

The API uses expanding-window chronological validation beginning with eight
training trips; at least nine eligible trips are needed for one evaluated
prediction. This prevents a future trip from being used to fit its own
prediction. The synthetic generator validates software behavior and the
evaluation pipeline, not real-world accuracy. Until a sufficiently sized,
sanitized, versioned real-trip evaluation exists, diagnostics are illustrative
and no production accuracy claim is warranted. Use
`GET /api/v1/model/diagnostics` for current values.

For the checked-in 1,908-point/16-trip synthetic fixture, the reproducible
report evaluates eight walk-forward predictions: model MAE is 0.3414 kWh,
distance-only baseline MAE is 0.3480 kWh, and reported improvement is 1.9%.
Those figures are a software benchmark on generated data, not real-world Bolt
performance.

## Known limitations

- The engineering fallback uses a heuristic uncertainty band with no claimed
  probability or calibrated coverage. A trained model labels its
  residual-based normal approximation as nominal 80%, but still returns
  `calibrated: false`; this small-sample diagnostic is not a real-world coverage
  guarantee.
- Results may not transfer across vehicles, battery replacements, degradation,
  tires, payload, driving style, elevation, traffic, or seasons.
- Usable capacity is not constant and is not a certified health measurement.
- Temperature and HVAC relationships can be nonlinear and confounded.
- Mobile logger sampling gaps can bias integrated energy and distance.
- Route elevation and forecast weather are not guaranteed inputs in v1.
- Small samples can make an improvement disappear on the next trip.
- Very short, very long, towing, track, diagnostic, or fault-condition trips are
  outside intended use.

## Ethical and safety considerations

Do not use the estimate to continue driving against vehicle warnings, choose a
route with no safe charging margin, diagnose a fault, or make a financial or
warranty representation. The vehicle display and official manufacturer/service
guidance take precedence.

## Versioning and evidence

Model-affecting changes require tests, an updated card, and release notes. The
v1 response does not contain a dedicated model-version field; it exposes the
API version through OpenAPI plus `model_kind`, equation coefficients, and
training-trip count. A future incompatible contract requires a new API version.
Resume claims must name the evaluation size and metric; placeholders remain
placeholders until generated by reproducible evidence.
