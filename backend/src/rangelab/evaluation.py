from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analytics import deduplicate_points, segment_points, summarize_trip
from .forecast import diagnostics
from .ingestion import parse_torque_csv
from .schemas import SegmentationOptions


def evaluate_csv(path: Path, *, gap_minutes: int = 15) -> dict[str, object]:
    parsed = parse_torque_csv(path.read_text(encoding="utf-8-sig"))
    points, duplicate_count = deduplicate_points(parsed.points)
    options = SegmentationOptions(gap_minutes=gap_minutes)
    segments = segment_points(points, options)
    trips = [
        summarize_trip(
            segment,
            import_id="offline-evaluation",
            trip_id=f"evaluation-trip-{index + 1}",
            options=options,
        )
        for index, segment in enumerate(segments)
    ]
    report = diagnostics(trips)
    total_distance = sum(trip.distance_km for trip in trips)
    total_net_energy = sum(trip.net_energy_kwh for trip in trips)
    return {
        "source": path.name,
        "synthetic": "synthetic" in path.name.lower(),
        "point_count": len(points),
        "duplicate_point_count": duplicate_count,
        "trip_count": len(trips),
        "total_distance_km": round(total_distance, 3),
        "total_net_energy_kwh": round(total_net_energy, 3),
        "weighted_efficiency_wh_per_km": round(total_net_energy * 1000 / total_distance, 2)
        if total_distance
        else None,
        "model_diagnostics": report.model_dump(mode="json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reproduce trip metrics and chronological forecast diagnostics for a telemetry CSV."
    )
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--gap-minutes", type=int, default=15)
    args = parser.parse_args()
    print(json.dumps(evaluate_csv(args.csv_path, gap_minutes=args.gap_minutes), indent=2))


if __name__ == "__main__":
    main()
