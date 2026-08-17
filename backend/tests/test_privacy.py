from __future__ import annotations

from datetime import timedelta

import pytest

from rangelab.privacy import apply_privacy, haversine_m
from rangelab.schemas import PrivacyOptions, PrivacyZone


def test_haversine_known_scale() -> None:
    assert haversine_m(0, 0, 0, 1) == pytest.approx(111_195, rel=0.001)


def test_masks_zone_and_rounds_public_coordinates(point_factory) -> None:
    inside = point_factory(0, latitude=43.94501, longitude=-78.89601)
    outside = point_factory(1, latitude=44.123456, longitude=-78.654321)
    options = PrivacyOptions(
        zones=[PrivacyZone(name="home", latitude=43.945, longitude=-78.896, radius_m=250)],
        coordinate_precision=3,
    )
    result = apply_privacy([inside, outside], options)
    assert result.masked_point_count == 1
    assert result.points[0].latitude is None
    assert result.points[0].longitude is None
    assert result.points[1].latitude == 44.123
    assert result.points[1].longitude == -78.654


def test_private_timestamp_shift_preserves_intervals_without_exposing_offset(point_factory) -> None:
    points = [point_factory(0), point_factory(2)]
    options = PrivacyOptions(shift_timestamps=True)
    result = apply_privacy(points, options, timestamp_offset=timedelta(days=73, hours=4))
    assert result.timestamps_shifted is True
    assert not hasattr(result, "shifted_days")
    assert result.points[0].observed_at != points[0].observed_at
    assert result.points[1].observed_at - result.points[0].observed_at == points[1].observed_at - points[0].observed_at
