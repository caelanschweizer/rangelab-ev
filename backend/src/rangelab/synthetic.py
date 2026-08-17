from __future__ import annotations

import argparse
import csv
import math
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path


HEADERS = (
    "GPS Time",
    "Speed (OBD)(km/h)",
    "State of Charge (displayed)(%)",
    "Hybrid/EV Battery Pack Voltage(V)",
    "Hybrid/EV Battery Pack Current(A)",
    "Hybrid/EV Battery Pack Power(kW)",
    "Latitude",
    "Longitude",
    "Ambient air temp(degC)",
    "Battery Temp(degC)",
    "HVAC Power(kW)",
    "Odometer(km)",
)


def generate_rows(*, trips: int = 16, seed: int = 2018, interval_seconds: int = 10) -> list[dict[str, str]]:
    """Create deterministic, plausible Bolt-like trips for demos and tests."""
    if trips < 1:
        raise ValueError("trips must be at least 1")
    rng = random.Random(seed)
    rows: list[dict[str, str]] = []
    current_time = datetime(2025, 1, 6, 7, 30, tzinfo=UTC)
    latitude, longitude = 43.9450, -78.8960
    odometer = 84_120.0
    soc = 88.0
    usable_capacity = 59.5

    for trip_index in range(trips):
        ambient = (-12, -5, 2, 8, 16, 23, 29, 34)[trip_index % 8] + rng.uniform(-1.5, 1.5)
        battery_temp = ambient * 0.55 + 10 + rng.uniform(-1, 1)
        hvac = (2.8 + max(0, 5 - ambient) * 0.08) if ambient < 10 else (1.4 if ambient > 27 else 0.25)
        point_count = rng.randint(75, 165)
        heading = rng.uniform(0, math.tau)
        current_time += timedelta(hours=3 + rng.uniform(0, 8))

        for point_index in range(point_count):
            phase = point_index / max(1, point_count - 1)
            cruise = 38 + 32 * abs(math.sin(phase * math.pi))
            traffic = 12 * math.sin(point_index * 0.23 + trip_index)
            speed = max(0.0, cruise + traffic + rng.uniform(-3, 3))
            if point_index < 3 or point_index >= point_count - 3:
                speed *= max(0, min(point_index, point_count - 1 - point_index)) / 3

            acceleration_wave = math.sin(point_index * 0.31 + trip_index * 0.4)
            road_load = 4.2 + 0.00215 * speed**2
            thermal_penalty = max(0, 15 - ambient) * 0.085 + max(0, ambient - 26) * 0.04
            power = road_load + hvac + thermal_penalty + 10 * acceleration_wave
            if acceleration_wave < -0.55 and speed > 15:
                power = -min(35, 7 + speed * 0.22)
            power += rng.uniform(-0.8, 0.8)
            voltage = 345 + soc * 0.55 + rng.uniform(-1, 1)
            current = power * 1000 / voltage
            energy_delta = power * interval_seconds / 3600
            soc = max(8, soc - energy_delta / usable_capacity * 100)

            distance_delta = speed * interval_seconds / 3600
            odometer += distance_delta
            heading += rng.uniform(-0.025, 0.025)
            latitude += math.cos(heading) * distance_delta / 111.32
            longitude += math.sin(heading) * distance_delta / (111.32 * math.cos(math.radians(latitude)))
            battery_temp += (ambient + abs(power) * 0.07 - battery_temp) * 0.004

            rows.append(
                {
                    HEADERS[0]: current_time.isoformat().replace("+00:00", "Z"),
                    HEADERS[1]: f"{speed:.3f}",
                    HEADERS[2]: f"{soc:.4f}",
                    HEADERS[3]: f"{voltage:.3f}",
                    HEADERS[4]: f"{current:.4f}",
                    HEADERS[5]: f"{power:.4f}",
                    HEADERS[6]: f"{latitude:.6f}",
                    HEADERS[7]: f"{longitude:.6f}",
                    HEADERS[8]: f"{ambient:.2f}",
                    HEADERS[9]: f"{battery_temp:.2f}",
                    HEADERS[10]: f"{hvac:.2f}",
                    HEADERS[11]: f"{odometer:.5f}",
                }
            )
            current_time += timedelta(seconds=interval_seconds)

        if soc < 25:
            soc = rng.uniform(72, 92)
            current_time += timedelta(hours=6)

    return rows


def write_csv(path: Path, *, trips: int = 16, seed: int = 2018, interval_seconds: int = 10) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(generate_rows(trips=trips, seed=seed, interval_seconds=interval_seconds))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic synthetic Chevrolet Bolt-like telemetry.")
    parser.add_argument("--output", type=Path, default=Path("../data/synthetic_bolt_trips.csv"))
    parser.add_argument("--trips", type=int, default=16)
    parser.add_argument("--seed", type=int, default=2018)
    parser.add_argument("--interval-seconds", type=int, default=10)
    args = parser.parse_args()
    write_csv(args.output, trips=args.trips, seed=args.seed, interval_seconds=args.interval_seconds)
    print(f"Wrote {args.trips} synthetic trips to {args.output}")


if __name__ == "__main__":
    main()
