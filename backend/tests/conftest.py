from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from rangelab.schemas import DataQuality, TelemetryPoint, TripSummary


@pytest.fixture
def point_factory():
    def make(
        minute: float,
        *,
        power: float | None = 10,
        speed: float | None = 60,
        odometer: float | None = None,
        latitude: float | None = 43.945,
        longitude: float | None = -78.896,
    ) -> TelemetryPoint:
        return TelemetryPoint(
            observed_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=minute),
            speed_kph=speed,
            soc_pct=80 - minute * 0.1,
            pack_power_kw=power,
            latitude=latitude,
            longitude=longitude,
            ambient_temp_c=5,
            battery_temp_c=12,
            hvac_power_kw=1.5,
            odometer_km=odometer,
            source_row=int(minute) + 2,
        )

    return make

@pytest.fixture
def trip_factory():
    def make(index: int) -> TripSummary:
        started = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=index)
        distance = 8 + index * 1.7
        temperature = -12 + index * 3.5
        speed = 38 + (index % 5) * 9
        hvac = 2.5 if temperature < 5 else (1.2 if temperature > 26 else 0.3)
        cold = max(0, 18 - temperature) / 10
        hot = max(0, temperature - 24) / 10
        speed_penalty = ((speed - 55) / 55) ** 2
        energy = (
            0.05
            + distance * 0.155
            + distance * cold * 0.04
            + distance * hot * 0.018
            + distance * speed_penalty * 0.028
            + hvac * distance / speed * 0.9
        )
        return TripSummary(
            id=f"trip-{index}",
            import_id="import-1",
            started_at=started,
            ended_at=started + timedelta(minutes=distance / speed * 60),
            duration_minutes=distance / speed * 60,
            point_count=100,
            distance_km=distance,
            distance_source="odometer",
            energy_used_kwh=energy + 0.15,
            energy_regenerated_kwh=0.15,
            net_energy_kwh=energy,
            efficiency_wh_per_km=energy * 1000 / distance,
            regen_recovery_pct=5,
            start_soc_pct=80,
            end_soc_pct=80 - energy / 60 * 100,
            soc_used_pct=energy / 60 * 100,
            average_speed_kph=speed,
            average_ambient_temp_c=temperature,
            average_battery_temp_c=temperature + 8,
            average_hvac_power_kw=hvac,
            data_quality=DataQuality(
                score=96,
                grade="A",
                power_coverage_pct=100,
                location_coverage_pct=100,
                interval_coverage_pct=100,
                unexpected_gap_count=0,
                invalid_interval_count=0,
                max_gap_seconds=10,
            ),
        )

    return make
