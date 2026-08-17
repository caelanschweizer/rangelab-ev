from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import fmean

from .schemas import ForecastInterval, ForecastRequest, ForecastResponse, ModelDiagnostics, TripSummary


FEATURE_NAMES = (
    "intercept_kwh",
    "distance_kwh_per_km",
    "cold_distance_kwh_per_km_per_10c",
    "hot_distance_kwh_per_km_per_10c",
    "speed_distance_kwh_per_km",
    "hvac_proxy_multiplier",
)

FALLBACK_COEFFICIENTS = (0.05, 0.155, 0.040, 0.018, 0.028, 0.90)


@dataclass(frozen=True, slots=True)
class FittedModel:
    coefficients: tuple[float, ...]
    kind: str
    sample_count: int
    residual_std: float


def _features(distance: float, temperature: float, speed: float, hvac_kw: float) -> tuple[float, ...]:
    cold = max(0.0, 18 - temperature) / 10
    hot = max(0.0, temperature - 24) / 10
    speed_penalty = ((speed - 55) / 55) ** 2
    duration_hours = distance / max(speed, 5)
    return (1.0, distance, distance * cold, distance * hot, distance * speed_penalty, hvac_kw * duration_hours)


def _value_or_default(value: float | None, default: float) -> float:
    return default if value is None else value


def _trip_features(trip: TripSummary) -> tuple[float, ...]:
    return _features(
        trip.distance_km,
        _value_or_default(trip.average_ambient_temp_c, 20),
        _value_or_default(trip.average_speed_kph, 55),
        _value_or_default(trip.average_hvac_power_kw, 0),
    )


def _eligible(trips: list[TripSummary]) -> list[TripSummary]:
    return sorted(
        [
            trip for trip in trips
            if trip.distance_km >= 1
            and trip.net_energy_kwh > 0
            and trip.average_speed_kph is not None
            and trip.average_ambient_temp_c is not None
            and trip.data_quality.score >= 55
        ],
        key=lambda trip: trip.started_at,
    )


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting for a small dense system."""
    n = len(vector)
    augmented = [row[:] + [vector[index]] for index, row in enumerate(matrix)]
    for column in range(n):
        pivot = max(range(column, n), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("Singular feature matrix")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(n):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor:
                augmented[row] = [
                    value - factor * pivot_value
                    for value, pivot_value in zip(augmented[row], augmented[column])
                ]
    return [augmented[row][-1] for row in range(n)]


def _fit_coefficients(trips: list[TripSummary]) -> tuple[float, ...]:
    rows = [_trip_features(trip) for trip in trips]
    targets = [trip.net_energy_kwh for trip in trips]
    feature_count = len(FEATURE_NAMES)
    xtx = [[0.0] * feature_count for _ in range(feature_count)]
    xty = [0.0] * feature_count
    for row, target in zip(rows, targets):
        for i in range(feature_count):
            xty[i] += row[i] * target
            for j in range(feature_count):
                xtx[i][j] += row[i] * row[j]
    # Ridge keeps correlated environmental features stable; the intercept is nearly unpenalized.
    for index in range(feature_count):
        xtx[index][index] += 1e-6 if index == 0 else 0.35
    solved = _solve(xtx, xty)
    # Negative physical penalties are hard to explain and brittle on small personal datasets.
    solved[1] = min(0.6, max(0.06, solved[1]))
    for index in range(2, feature_count):
        solved[index] = min(3.0, max(0.0, solved[index]))
    solved[0] = min(2.0, max(0.0, solved[0]))
    return tuple(solved)


def _predict(coefficients: tuple[float, ...], features: tuple[float, ...]) -> tuple[float, dict[str, float]]:
    contributions = {
        name: coefficient * value
        for name, coefficient, value in zip(FEATURE_NAMES, coefficients, features)
    }
    return max(0.0, sum(contributions.values())), contributions


def _baseline_rate(trips: list[TripSummary]) -> float:
    distance = sum(trip.distance_km for trip in trips)
    energy = sum(trip.net_energy_kwh for trip in trips)
    return energy / distance if distance > 0 and energy > 0 else 0.18


def fit_model(trips: list[TripSummary]) -> FittedModel:
    eligible = _eligible(trips)
    if len(eligible) < 8:
        coefficients = FALLBACK_COEFFICIENTS
        residuals = [
            trip.net_energy_kwh
            - _predict(
                coefficients,
                _trip_features(trip),
            )[0]
            for trip in eligible
        ]
        residual_std = math.sqrt(fmean([value * value for value in residuals])) if residuals else 0.45
        return FittedModel(coefficients, "engineering_fallback", len(eligible), max(0.2, residual_std))

    coefficients = _fit_coefficients(eligible)
    residuals = [
        trip.net_energy_kwh
        - _predict(
            coefficients,
            _trip_features(trip),
        )[0]
        for trip in eligible
    ]
    residual_std = math.sqrt(sum(value * value for value in residuals) / max(1, len(residuals) - len(coefficients)))
    return FittedModel(coefficients, "trained_ridge", len(eligible), max(0.1, residual_std))


def forecast(request: ForecastRequest, trips: list[TripSummary]) -> ForecastResponse:
    eligible = _eligible(trips)
    model = fit_model(eligible)
    features = _features(request.distance_km, request.ambient_temp_c, request.expected_speed_kph, request.hvac_power_kw)
    predicted, contributions = _predict(model.coefficients, features)
    baseline = request.distance_km * _baseline_rate(eligible)
    # Prediction error grows gently with route length beyond the median personal trip.
    distance_scale = math.sqrt(max(1.0, request.distance_km / 20))
    half_width = 1.282 * model.residual_std * distance_scale
    arrival_soc = None
    if request.starting_soc_pct is not None:
        arrival_soc = max(0.0, min(100.0, request.starting_soc_pct - predicted / request.usable_capacity_kwh * 100))

    coefficient_text = ", ".join(
        f"{name}={coefficient:.4f}" for name, coefficient in zip(FEATURE_NAMES, model.coefficients)
    )
    if model.kind == "engineering_fallback" and model.sample_count == 0:
        interval_confidence = None
        interval_basis = (
            "Illustrative band using 1.282 times a 0.45 kWh engineering heuristic, "
            "scaled by route distance; it is not based on historical residuals or calibrated coverage."
        )
    elif model.kind == "engineering_fallback":
        interval_confidence = None
        interval_basis = (
            f"Illustrative band using fallback residual scale from {model.sample_count} eligible trip(s); "
            "the sample is too small for calibrated coverage."
        )
    else:
        interval_confidence = 80
        interval_basis = (
            "Nominal 80% normal approximation using the fitted model's in-sample residual scale; "
            "empirical interval coverage has not been calibrated."
        )
    return ForecastResponse(
        predicted_energy_kwh=round(predicted, 3),
        baseline_energy_kwh=round(baseline, 3),
        interval=ForecastInterval(
            confidence_pct=interval_confidence,
            calibrated=False,
            basis=interval_basis,
            lower_kwh=round(max(0.0, predicted - half_width), 3),
            upper_kwh=round(predicted + half_width, 3),
        ),
        predicted_arrival_soc_pct=round(arrival_soc, 1) if arrival_soc is not None else None,
        model_kind=model.kind,
        training_trip_count=model.sample_count,
        equation=f"energy_kwh = dot(features, coefficients); {coefficient_text}",
        contributions_kwh={name: round(value, 4) for name, value in contributions.items()},
        assumptions=[
            "Pack power uses positive values for discharge and negative values for regenerative braking.",
            interval_basis,
            "The band does not account explicitly for road, wind, traffic, elevation, or battery uncertainty.",
            "Arrival charge uses the supplied usable capacity and should not be treated as a safety-critical estimate.",
        ],
    )


def diagnostics(trips: list[TripSummary]) -> ModelDiagnostics:
    eligible = _eligible(trips)
    fitted = fit_model(eligible)
    model_errors: list[float] = []
    baseline_errors: list[float] = []
    # Walk-forward evaluation prevents future trips from influencing earlier predictions.
    for index in range(8, len(eligible)):
        training = eligible[:index]
        target = eligible[index]
        model = fit_model(training)
        prediction, _ = _predict(
            model.coefficients,
            _trip_features(target),
        )
        baseline = target.distance_km * _baseline_rate(training)
        model_errors.append(abs(target.net_energy_kwh - prediction))
        baseline_errors.append(abs(target.net_energy_kwh - baseline))

    model_mae = fmean(model_errors) if model_errors else None
    baseline_mae = fmean(baseline_errors) if baseline_errors else None
    improvement = None
    if model_mae is not None and baseline_mae and baseline_mae > 0:
        improvement = (baseline_mae - model_mae) / baseline_mae * 100
    caveats = [
        "Only trips with distance, positive net energy, speed, temperature, and quality score >= 55 are eligible.",
        "Associations in personal driving history do not prove causal effects.",
    ]
    if len(eligible) < 8:
        caveats.append("Fewer than 8 eligible trips are available, so engineering fallback coefficients are active.")
    if not eligible:
        caveats.append(
            "The reported 0.45 kWh fallback scale is an engineering heuristic, not a historical residual estimate."
        )
    if not model_errors:
        caveats.append("At least 9 eligible chronological trips are required for a walk-forward error estimate.")

    return ModelDiagnostics(
        model_kind=fitted.kind,
        eligible_trip_count=len(eligible),
        evaluated_trip_count=len(model_errors),
        model_mae_kwh=round(model_mae, 4) if model_mae is not None else None,
        baseline_mae_kwh=round(baseline_mae, 4) if baseline_mae is not None else None,
        improvement_pct=round(improvement, 2) if improvement is not None else None,
        residual_std_kwh=round(fitted.residual_std, 4),
        coefficients={name: round(value, 6) for name, value in zip(FEATURE_NAMES, fitted.coefficients)},
        backtest_method="Expanding-window chronological validation; distance-only rate is fit on each training window.",
        caveats=caveats,
    )
