from __future__ import annotations

import math
import secrets
from dataclasses import dataclass
from datetime import timedelta

from .schemas import PrivacyOptions, TelemetryPoint


EARTH_RADIUS_M = 6_371_008.8


@dataclass(frozen=True, slots=True)
class PrivacyResult:
    points: list[TelemetryPoint]
    masked_point_count: int
    timestamps_shifted: bool


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in metres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _private_timestamp_offset() -> timedelta:
    """Return a non-exposed, per-import offset that obscures dates and clock time."""
    minimum_seconds = 30 * 24 * 60 * 60
    maximum_seconds = 5 * 365 * 24 * 60 * 60
    magnitude = minimum_seconds + secrets.randbelow(maximum_seconds - minimum_seconds + 1)
    direction = -1 if secrets.randbelow(2) == 0 else 1
    return timedelta(seconds=direction * magnitude)


def apply_privacy(
    points: list[TelemetryPoint],
    options: PrivacyOptions,
    *,
    timestamp_offset: timedelta | None = None,
) -> PrivacyResult:
    if not options.enabled:
        return PrivacyResult(
            points=[point.model_copy(deep=True) for point in points],
            masked_point_count=0,
            timestamps_shifted=False,
        )

    shift = (timestamp_offset or _private_timestamp_offset()) if options.shift_timestamps else timedelta(0)

    sanitized: list[TelemetryPoint] = []
    masked = 0
    for original in points:
        point = original.model_copy(deep=True)
        if shift:
            point.observed_at = point.observed_at + shift

        has_location = point.latitude is not None and point.longitude is not None
        in_private_zone = False
        if has_location:
            in_private_zone = any(
                haversine_m(point.latitude, point.longitude, zone.latitude, zone.longitude) <= zone.radius_m
                for zone in options.zones
            )

        if has_location and in_private_zone and options.mask_coordinates_in_zones:
            point.latitude = None
            point.longitude = None
            masked += 1
        elif has_location and options.coordinate_precision is not None:
            point.latitude = round(point.latitude, options.coordinate_precision)
            point.longitude = round(point.longitude, options.coordinate_precision)

        sanitized.append(point)

    return PrivacyResult(
        points=sanitized,
        masked_point_count=masked,
        timestamps_shifted=bool(shift),
    )
