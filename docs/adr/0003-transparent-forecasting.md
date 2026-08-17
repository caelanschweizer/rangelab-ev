# ADR 0003: Prefer transparent forecasting before complex ML

- Status: Accepted
- Date: 2026-08-16

## Context

A small, single-vehicle dataset cannot justify a sophisticated model or broad
accuracy claim. Still, arrival-charge estimation is useful for demonstrating
feature engineering and evaluation discipline.

## Decision

Ship an explainable estimator with visible inputs and compare it to a fixed-
efficiency, distance-only baseline. Use chronological holdouts for later real-
trip evaluation. Expose diagnostics and limitations through the API and model
card.

## Consequences

The result is easy to audit and harder to embellish. A complex method is added
only if it wins on a versioned holdout and remains explainable enough for the
product. The initial synthetic diagnostics validate code behavior, not external
accuracy.

## Alternatives considered

- A neural network or opaque ensemble would add little credibility with a small
  dataset and make failures harder to explain.
- No forecast would miss an opportunity to demonstrate honest baseline design
  and evaluation.
