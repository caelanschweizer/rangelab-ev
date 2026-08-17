from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import timedelta
from statistics import fmean

from .privacy import haversine_m
from .schemas import DataQuality, SegmentationOptions, TelemetryPoint, TripSummary


def point_fingerprint(point: TelemetryPoint) -> str:
    payload = point.model_dump(mode="json", exclude={"source_row"})
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def deduplicate_points(points: list[TelemetryPoint]) -> tuple[list[TelemetryPoint], int]:
    seen: set[str] = set()
    unique: list[TelemetryPoint] = []
    for point in sorted(points, key=lambda item: item.observed_at):
        fingerprint = point_fingerprint(point)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(point)
    return unique, len(points) - len(unique)


def segment_points(points: list[TelemetryPoint], options: SegmentationOptions) -> list[list[TelemetryPoint]]:
    if not points:
        return []
    ordered = sorted(points, key=lambda point: point.observed_at)
    gap = timedelta(minutes=options.gap_minutes)
    segments: list[list[TelemetryPoint]] = [[ordered[0]]]
    for point in ordered[1:]:
        if point.observed_at - segments[-1][-1].observed_at >= gap:
            segments.append([point])
        else:
            segments[-1].append(point)
    return [segment for segment in segments if len(segment) >= options.minimum_points]


def _mean(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return fmean(present) if present else None


def _grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def _distance_for_interval(first: TelemetryPoint, second: TelemetryPoint, dt_seconds: float) -> tuple[float, str]:
    if first.odometer_km is not None and second.odometer_km is not None:
        delta = second.odometer_km - first.odometer_km
        plausible_max = max(0.15, dt_seconds / 3600 * 220)
        if 0 <= delta <= plausible_max:
            return delta, "odometer"
    if None not in (first.latitude, first.longitude, second.latitude, second.longitude):
        distance = haversine_m(first.latitude, first.longitude, second.latitude, second.longitude) / 1000
        plausible_max = max(0.15, dt_seconds / 3600 * 220)
        if distance <= plausible_max:
            return distance, "gps"
    if first.speed_kph is not None and second.speed_kph is not None:
        return (first.speed_kph + second.speed_kph) / 2 * dt_seconds / 3600, "speed"
    return 0, "unavailable"


def _integrate_power_interval(first_kw: float, second_kw: float, dt_seconds: float) -> tuple[float, float]:
    """Trapezoidally integrate discharge and regen, splitting a linear zero crossing."""
    if first_kw >= 0 and second_kw >= 0:
        return (first_kw + second_kw) / 2 * dt_seconds / 3600, 0.0
    if first_kw <= 0 and second_kw <= 0:
        return 0.0, -(first_kw + second_kw) / 2 * dt_seconds / 3600
    crossing_fraction = abs(first_kw) / (abs(first_kw) + abs(second_kw))
    first_duration = dt_seconds * crossing_fraction
    second_duration = dt_seconds - first_duration
    first_energy = abs(first_kw) * first_duration / 2 / 3600
    second_energy = abs(second_kw) * second_duration / 2 / 3600
    if first_kw > 0:
        return first_energy, second_energy
    return second_energy, first_energy


def summarize_trip(
    points: list[TelemetryPoint], *, import_id: str, trip_id: str, options: SegmentationOptions
) -> TripSummary:
    if not points:
        raise ValueError("A trip requires at least one telemetry point.")
    ordered = sorted(points, key=lambda point: point.observed_at)
    duration_seconds = max(0.0, (ordered[-1].observed_at - ordered[0].observed_at).total_seconds())
    used = 0.0
    regenerated = 0.0
    distance = 0.0
    sources: Counter[str] = Counter()
    valid_interval_seconds = 0.0
    invalid_intervals = 0
    unexpected_gaps = 0
    gaps: list[float] = []

    for first, second in zip(ordered, ordered[1:]):
        dt_seconds = (second.observed_at - first.observed_at).total_seconds()
        gaps.append(max(0.0, dt_seconds))
        if dt_seconds <= 0:
            invalid_intervals += 1
            continue
        if dt_seconds > 30:
            unexpected_gaps += 1
        if dt_seconds > options.max_integration_gap_seconds:
            invalid_intervals += 1
            continue
        valid_interval_seconds += dt_seconds
        interval_distance, source = _distance_for_interval(first, second, dt_seconds)
        distance += interval_distance
        if source != "unavailable":
            sources[source] += 1
        if first.pack_power_kw is not None and second.pack_power_kw is not None:
            interval_used, interval_regenerated = _integrate_power_interval(
                first.pack_power_kw, second.pack_power_kw, dt_seconds
            )
            used += interval_used
            regenerated += interval_regenerated

    net_energy = used - regenerated
    efficiency = net_energy * 1000 / distance if distance >= 0.1 else None
    regen_recovery = regenerated / used * 100 if used > 0.01 else None
    first_soc = next((point.soc_pct for point in ordered if point.soc_pct is not None), None)
    last_soc = next((point.soc_pct for point in reversed(ordered) if point.soc_pct is not None), None)
    soc_used = first_soc - last_soc if first_soc is not None and last_soc is not None else None

    point_count = len(ordered)
    power_coverage = sum(point.pack_power_kw is not None for point in ordered) / point_count * 100
    location_coverage = sum(point.latitude is not None and point.longitude is not None for point in ordered) / point_count * 100
    interval_coverage = (valid_interval_seconds / duration_seconds * 100) if duration_seconds else 100.0
    interval_coverage = min(100.0, interval_coverage)
    score = 100.0
    score -= (100 - power_coverage) * 0.45
    score -= (100 - interval_coverage) * 0.3
    if not sources:
        score -= 15
    score -= min(10, unexpected_gaps * 2)
    score -= min(10, invalid_intervals * 2)
    score = max(0.0, min(100.0, score))

    notes: list[str] = []
    if power_coverage < 95:
        notes.append("Some points lack pack power, so energy totals are incomplete.")
    if not sources:
        notes.append("Distance could not be estimated from odometer, GPS, or speed.")
    if unexpected_gaps:
        notes.append(f"Detected {unexpected_gaps} sampling gap(s) longer than 30 seconds.")
    if invalid_intervals:
        notes.append(f"Excluded {invalid_intervals} invalid or oversized interval(s) from integration.")

    source_names = set(sources)
    if not source_names:
        distance_source = "unavailable"
    elif len(source_names) == 1:
        distance_source = next(iter(source_names))
    else:
        distance_source = "mixed"

    return TripSummary(
        id=trip_id,
        import_id=import_id,
        started_at=ordered[0].observed_at,
        ended_at=ordered[-1].observed_at,
        duration_minutes=round(duration_seconds / 60, 3),
        point_count=point_count,
        distance_km=round(distance, 4),
        distance_source=distance_source,
        energy_used_kwh=round(used, 5),
        energy_regenerated_kwh=round(regenerated, 5),
        net_energy_kwh=round(net_energy, 5),
        efficiency_wh_per_km=round(efficiency, 2) if efficiency is not None else None,
        regen_recovery_pct=round(regen_recovery, 2) if regen_recovery is not None else None,
        start_soc_pct=round(first_soc, 3) if first_soc is not None else None,
        end_soc_pct=round(last_soc, 3) if last_soc is not None else None,
        soc_used_pct=round(soc_used, 3) if soc_used is not None else None,
        average_speed_kph=round(value, 3) if (value := _mean([p.speed_kph for p in ordered])) is not None else None,
        average_ambient_temp_c=round(value, 3) if (value := _mean([p.ambient_temp_c for p in ordered])) is not None else None,
        average_battery_temp_c=round(value, 3) if (value := _mean([p.battery_temp_c for p in ordered])) is not None else None,
        average_hvac_power_kw=round(value, 3) if (value := _mean([p.hvac_power_kw for p in ordered])) is not None else None,
        data_quality=DataQuality(
            score=round(score, 2),
            grade=_grade(score),
            power_coverage_pct=round(power_coverage, 2),
            location_coverage_pct=round(location_coverage, 2),
            interval_coverage_pct=round(interval_coverage, 2),
            unexpected_gap_count=unexpected_gaps,
            invalid_interval_count=invalid_intervals,
            max_gap_seconds=max(gaps, default=0),
            notes=notes,
        ),
    )
