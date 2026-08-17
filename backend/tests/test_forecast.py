from __future__ import annotations

from rangelab.forecast import _trip_features, diagnostics, forecast
from rangelab.schemas import ForecastRequest


def test_fallback_forecast_is_transparent_and_bounded() -> None:
    response = forecast(
        ForecastRequest(distance_km=100, ambient_temp_c=-10, expected_speed_kph=90, hvac_power_kw=3, starting_soc_pct=90),
        [],
    )
    assert response.model_kind == "engineering_fallback"
    assert response.training_trip_count == 0
    assert response.predicted_energy_kwh > response.baseline_energy_kwh
    assert 0 <= response.predicted_arrival_soc_pct < 90
    assert response.interval.lower_kwh < response.predicted_energy_kwh < response.interval.upper_kwh
    assert response.interval.confidence_pct is None
    assert response.interval.calibrated is False
    assert "0.45 kWh engineering heuristic" in response.interval.basis
    assert "not based on historical residuals" in response.interval.basis
    assert set(response.contributions_kwh) == {
        "intercept_kwh", "distance_kwh_per_km", "cold_distance_kwh_per_km_per_10c",
        "hot_distance_kwh_per_km_per_10c", "speed_distance_kwh_per_km", "hvac_proxy_multiplier",
    }


def test_trains_and_walk_forward_evaluates(trip_factory) -> None:
    trips = [trip_factory(index) for index in range(14)]
    result = forecast(ForecastRequest(distance_km=42, ambient_temp_c=0), trips)
    report = diagnostics(trips)
    assert result.model_kind == "trained_ridge"
    assert result.training_trip_count == 14
    assert result.interval.confidence_pct == 80
    assert result.interval.calibrated is False
    assert "not been calibrated" in result.interval.basis
    assert report.eligible_trip_count == 14
    assert report.evaluated_trip_count == 6
    assert report.model_mae_kwh is not None
    assert report.baseline_mae_kwh is not None
    assert "chronological" in report.backtest_method.lower()


def test_diagnostics_refuses_to_claim_unmeasured_improvement(trip_factory) -> None:
    report = diagnostics([trip_factory(index) for index in range(5)])
    assert report.model_kind == "engineering_fallback"
    assert report.evaluated_trip_count == 0
    assert report.improvement_pct is None


def test_zero_celsius_is_not_replaced_by_default_temperature(trip_factory) -> None:
    trip = trip_factory(1).model_copy(update={"average_ambient_temp_c": 0.0})
    features = _trip_features(trip)
    assert features[2] == trip.distance_km * 1.8
