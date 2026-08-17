from __future__ import annotations

import pytest

from rangelab.analytics import deduplicate_points, segment_points, summarize_trip
from rangelab.schemas import SegmentationOptions


def test_segments_on_configured_gap(point_factory) -> None:
    points = [point_factory(0), point_factory(1), point_factory(16), point_factory(17)]
    segments = segment_points(points, SegmentationOptions(gap_minutes=15))
    assert [len(segment) for segment in segments] == [2, 2]


def test_deduplicates_exact_points(point_factory) -> None:
    point = point_factory(0)
    unique, duplicates = deduplicate_points([point, point.model_copy(), point_factory(1)])
    assert len(unique) == 2
    assert duplicates == 1


def test_trapezoidal_energy_splits_regen_zero_crossing(point_factory) -> None:
    points = [
        point_factory(0, power=10, odometer=100),
        point_factory(1, power=10, odometer=100.5),
        point_factory(2, power=-6, odometer=101),
        point_factory(3, power=-6, odometer=101.5),
    ]
    trip = summarize_trip(
        points,
        import_id="import",
        trip_id="trip",
        options=SegmentationOptions(max_integration_gap_seconds=120),
    )
    assert trip.energy_used_kwh == pytest.approx(0.21875)
    assert trip.energy_regenerated_kwh == pytest.approx(0.11875)
    assert trip.net_energy_kwh == pytest.approx(0.1)
    assert trip.distance_km == pytest.approx(1.5)
    assert trip.efficiency_wh_per_km == pytest.approx(66.67)
    assert trip.regen_recovery_pct == pytest.approx(54.29)


def test_excludes_oversized_integration_gap(point_factory) -> None:
    trip = summarize_trip(
        [point_factory(0, power=10), point_factory(5, power=10)],
        import_id="import",
        trip_id="trip",
        options=SegmentationOptions(max_integration_gap_seconds=120),
    )
    assert trip.energy_used_kwh == 0
    assert trip.data_quality.invalid_interval_count == 1
    assert trip.data_quality.score < 80
