from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Callable

from .schemas import TelemetryPoint


class CsvIngestionError(ValueError):
    """Raised when a CSV cannot be interpreted as telemetry."""


@dataclass(slots=True)
class CsvParseResult:
    points: list[TelemetryPoint]
    parsed_rows: int
    dropped_rows: int
    warnings: list[str] = field(default_factory=list)
    field_map: dict[str, str] = field(default_factory=dict)


def _canonical_header(value: str) -> str:
    value = value.lstrip("\ufeff").strip().lower()
    value = value.replace("°", "deg").replace("%", "pct")
    return re.sub(r"[^a-z0-9]+", "", value)


def _is_missing(value: str | None) -> bool:
    return value is None or value.strip().lower() in {"", "-", "--", "null", "none", "nan", "n/a"}


def _number(value: str | None) -> float | None:
    if _is_missing(value):
        return None
    cleaned = value.strip().replace(",", "")
    try:
        number = float(cleaned)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _timestamp(value: str | None) -> datetime | None:
    if _is_missing(value):
        return None
    raw = value.strip()
    numeric = _number(raw)
    if numeric is not None and re.fullmatch(r"[-+]?\d+(?:\.\d+)?", raw):
        seconds = numeric / 1000 if abs(numeric) > 10_000_000_000 else numeric
        try:
            return datetime.fromtimestamp(seconds, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None

    iso_candidate = raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw
    try:
        parsed = datetime.fromisoformat(iso_candidate)
    except ValueError:
        parsed = None
    if parsed is None:
        formats = (
            "%d-%b-%Y %H:%M:%S.%f",
            "%d-%b-%Y %H:%M:%S",
            "%m/%d/%Y %H:%M:%S.%f",
            "%m/%d/%Y %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
        )
        for fmt in formats:
            try:
                parsed = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _find_header(headers: list[str], predicate: Callable[[str], bool]) -> str | None:
    return next((header for header in headers if predicate(_canonical_header(header))), None)


def _speed_unit(header: str) -> str | None:
    if any(token in header for token in ("kmh", "kph", "kilometerperhour", "kilometreperhour")):
        return "kph"
    if "mph" in header or "mileperhour" in header:
        return "mph"
    return None


def _is_supported_vehicle_speed(header: str) -> bool:
    if "speed" not in header:
        return False
    if any(token in header for token in ("engine", "motor", "wheel", "shaft", "fan", "rpm")):
        return False
    return (
        header == "speed"
        or header.startswith("speed")
        or "vehiclespeed" in header
        or "obdspeed" in header
        or "gpsspeed" in header
    )


def _power_unit(header: str) -> str | None:
    if header.endswith("kw") or "kilowatt" in header:
        return "kw"
    if header.endswith("w") or "watt" in header:
        return "w"
    return None


def _odometer_unit(header: str) -> str | None:
    if any(token in header for token in ("kilometer", "kilometre")) or header.endswith("km"):
        return "km"
    if "mile" in header or header.endswith("mi"):
        return "mi"
    return None


def _temperature_unit(header: str) -> str | None:
    if "degf" in header or "fahrenheit" in header or header.endswith("tempf") or header.endswith("temperaturef"):
        return "f"
    if "degc" in header or "celsius" in header or header.endswith("tempc") or header.endswith("temperaturec"):
        return "c"
    return None


def detect_fields(headers: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    """Map common Torque/OBD Fusion headers to RangeLab's canonical fields."""
    for raw_header in headers:
        header = _canonical_header(raw_header)
        if _is_supported_vehicle_speed(header) and _speed_unit(header) is None:
            raise CsvIngestionError(
                f"Ambiguous speed unit in column '{raw_header}'. Label it explicitly as km/h, kph, or mph."
            )
        is_pack_power = ("pack" in header or "battery" in header) and "power" in header and "hvac" not in header
        is_hvac_power = ("hvac" in header or "climate" in header) and "power" in header
        if (is_pack_power or is_hvac_power) and _power_unit(header) is None:
            raise CsvIngestionError(
                f"Ambiguous power unit in column '{raw_header}'. Label it explicitly as W or kW."
            )
        is_ambient_temp = ("ambient" in header or "outside" in header) and "temp" in header
        is_battery_temp = "battery" in header and "temp" in header
        if (is_ambient_temp or is_battery_temp) and _temperature_unit(header) is None:
            raise CsvIngestionError(
                f"Ambiguous temperature unit in column '{raw_header}'. Label it explicitly as C or F."
            )
        if "odometer" in header and _odometer_unit(header) is None:
            raise CsvIngestionError(
                f"Ambiguous odometer unit in column '{raw_header}'. Label it explicitly as km or mi."
            )

    finders: dict[str, Callable[[str], bool]] = {
        "observed_at": lambda h: h in {
            "gpstime", "devicetime", "utctime", "timestamp", "datetime", "time", "dateandtime"
        } or h.endswith("timestamp"),
        "speed_kph": lambda h: _is_supported_vehicle_speed(h) and _speed_unit(h) == "kph",
        "speed_mph": lambda h: _is_supported_vehicle_speed(h) and _speed_unit(h) == "mph",
        "soc_pct": lambda h: "stateofcharge" in h or h in {"soc", "socpct", "batterylevel"},
        "pack_voltage_v": lambda h: ("pack" in h or "battery" in h) and "voltage" in h,
        "pack_current_a": lambda h: ("pack" in h or "battery" in h) and "current" in h,
        "pack_power_kw": lambda h: (("pack" in h or "battery" in h) and "power" in h and "hvac" not in h and _power_unit(h) == "kw"),
        "pack_power_w": lambda h: (("pack" in h or "battery" in h) and "power" in h and "hvac" not in h and _power_unit(h) == "w"),
        "latitude": lambda h: h in {"latitude", "gpslatitude", "lat"},
        "longitude": lambda h: h in {"longitude", "gpslongitude", "lon", "lng", "long"},
        "ambient_temp_c": lambda h: ("ambient" in h or "outside" in h) and "temp" in h and _temperature_unit(h) == "c",
        "ambient_temp_f": lambda h: ("ambient" in h or "outside" in h) and "temp" in h and _temperature_unit(h) == "f",
        "battery_temp_c": lambda h: "battery" in h and "temp" in h and _temperature_unit(h) == "c",
        "battery_temp_f": lambda h: "battery" in h and "temp" in h and _temperature_unit(h) == "f",
        "hvac_power_kw": lambda h: ("hvac" in h or "climate" in h) and "power" in h and _power_unit(h) == "kw",
        "hvac_power_w": lambda h: ("hvac" in h or "climate" in h) and "power" in h and _power_unit(h) == "w",
        "odometer_km": lambda h: ("odometer" in h or h.startswith("distance")) and _odometer_unit(h) == "km",
        "odometer_mi": lambda h: ("odometer" in h or h.startswith("distance")) and _odometer_unit(h) == "mi",
    }

    field_map: dict[str, str] = {}
    units: dict[str, str] = {}
    # Prefer explicit kilometre/Celsius columns when both unit variants exist.
    order = (
        "observed_at", "speed_kph", "speed_mph", "soc_pct", "pack_voltage_v",
        "pack_current_a", "pack_power_kw", "pack_power_w", "latitude", "longitude", "ambient_temp_c",
        "ambient_temp_f", "battery_temp_c", "battery_temp_f", "hvac_power_kw", "hvac_power_w",
        "odometer_km", "odometer_mi",
    )
    for candidate in order:
        header = _find_header(headers, finders[candidate])
        if header is None:
            continue
        if candidate == "speed_mph":
            canonical = "speed_kph"
        elif candidate == "pack_power_w":
            canonical = "pack_power_kw"
        elif candidate == "hvac_power_w":
            canonical = "hvac_power_kw"
        elif candidate == "odometer_mi":
            canonical = "odometer_km"
        elif candidate.endswith("_f"):
            canonical = candidate.removesuffix("_f") + "_c"
        else:
            canonical = candidate
        if canonical in field_map:
            continue
        field_map[canonical] = header
        if candidate.endswith("_mph"):
            units[canonical] = "mph"
        elif candidate.endswith("_power_w"):
            units[canonical] = "w"
        elif candidate.endswith("_mi"):
            units[canonical] = "mi"
        elif candidate.endswith("_f"):
            units[canonical] = "f"
    return field_map, units


def _bounded(value: float | None, lower: float, upper: float) -> float | None:
    return value if value is not None and lower <= value <= upper else None


def parse_torque_csv(text: str, *, invert_power_sign: bool = False) -> CsvParseResult:
    if not text.strip():
        raise CsvIngestionError("The uploaded CSV is empty.")
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect, strict=True)
    if not reader.fieldnames:
        raise CsvIngestionError("The CSV does not contain a header row.")

    headers = [header for header in reader.fieldnames if header is not None]
    field_map, units = detect_fields(headers)
    if "observed_at" not in field_map:
        raise CsvIngestionError(
            "No timestamp column was found. Expected a heading such as GPS Time, Device Time, or timestamp."
        )
    has_power = "pack_power_kw" in field_map
    has_voltage_and_current = {"pack_voltage_v", "pack_current_a"}.issubset(field_map)
    if not (has_power or has_voltage_and_current):
        raise CsvIngestionError(
            "No pack-energy signal was found. Include pack power, or both pack voltage and current."
        )

    points: list[TelemetryPoint] = []
    parsed_rows = 0
    dropped_rows = 0
    invalid_timestamp_rows = 0
    invalid_value_count = 0
    try:
        for source_row, row in enumerate(reader, start=2):
            extra_values = row.get(None)
            if extra_values and any(not _is_missing(str(value)) for value in extra_values):
                raise CsvIngestionError(
                    f"Malformed CSV row {source_row}: it contains more values than the header row."
                )
            if not any(not _is_missing(row.get(header)) for header in headers):
                continue
            parsed_rows += 1
            observed_at = _timestamp(row.get(field_map["observed_at"]))
            if observed_at is None:
                dropped_rows += 1
                invalid_timestamp_rows += 1
                continue

            values: dict[str, float | None] = {}
            for name, header in field_map.items():
                if name == "observed_at":
                    continue
                cell = row.get(header)
                value = _number(cell)
                if not _is_missing(cell) and value is None:
                    invalid_value_count += 1
                values[name] = value

            if values.get("speed_kph") is not None and units.get("speed_kph") == "mph":
                values["speed_kph"] *= 1.609344
            if values.get("odometer_km") is not None and units.get("odometer_km") == "mi":
                values["odometer_km"] *= 1.609344
            for name in ("ambient_temp_c", "battery_temp_c"):
                if values.get(name) is not None and units.get(name) == "f":
                    values[name] = (values[name] - 32) * 5 / 9
            for name in ("pack_power_kw", "hvac_power_kw"):
                if values.get(name) is not None and units.get(name) == "w":
                    values[name] /= 1000

            ranges = {
                "speed_kph": (0, 300),
                "soc_pct": (0, 100),
                "pack_voltage_v": (0, 1000),
                "pack_current_a": (-1000, 1000),
                "pack_power_kw": (-500, 500),
                "latitude": (-90, 90),
                "longitude": (-180, 180),
                "ambient_temp_c": (-80, 80),
                "battery_temp_c": (-80, 100),
                "hvac_power_kw": (0, 20),
                "odometer_km": (0, 5_000_000),
            }
            for name, (lower, upper) in ranges.items():
                value = values.get(name)
                if value is not None and not (lower <= value <= upper):
                    invalid_value_count += 1
                    values[name] = None

            voltage = values.get("pack_voltage_v")
            current = values.get("pack_current_a")
            power = values.get("pack_power_kw")
            if power is None and voltage is not None and current is not None:
                derived_power = voltage * current / 1000
                if -500 <= derived_power <= 500:
                    power = derived_power
                else:
                    invalid_value_count += 1
            if power is not None and invert_power_sign:
                power = -power

            point = TelemetryPoint(
                observed_at=observed_at,
                speed_kph=values.get("speed_kph"),
                soc_pct=values.get("soc_pct"),
                pack_voltage_v=voltage,
                pack_current_a=current,
                pack_power_kw=power,
                latitude=values.get("latitude"),
                longitude=values.get("longitude"),
                ambient_temp_c=values.get("ambient_temp_c"),
                battery_temp_c=values.get("battery_temp_c"),
                hvac_power_kw=values.get("hvac_power_kw"),
                odometer_km=values.get("odometer_km"),
                source_row=source_row,
            )
            points.append(point)
    except csv.Error as exc:
        raise CsvIngestionError(f"Malformed CSV data: {exc}") from exc

    if not points:
        raise CsvIngestionError("No valid telemetry rows remained after parsing timestamps and values.")
    if all(point.pack_power_kw is None for point in points):
        invalid_context = (
            f" ({invalid_value_count} invalid or out-of-range sensor value(s) were ignored)"
            if invalid_value_count
            else ""
        )
        raise CsvIngestionError(
            "All declared or derived pack-energy values are invalid; no trip energy can be computed"
            f"{invalid_context}."
        )

    warnings: list[str] = []
    if invalid_timestamp_rows:
        warnings.append(f"Dropped {invalid_timestamp_rows} row(s) with missing or invalid timestamps.")
    if invalid_value_count:
        warnings.append(f"Ignored {invalid_value_count} invalid or out-of-range sensor value(s).")
    if "pack_power_kw" not in field_map:
        warnings.append("Pack power was derived as voltage x current; verify the adapter's current sign convention.")
    if all(point.latitude is None for point in points):
        warnings.append("No usable GPS coordinates were present; distance will fall back to odometer or speed.")

    points.sort(key=lambda point: point.observed_at)
    return CsvParseResult(
        points=points,
        parsed_rows=parsed_rows,
        dropped_rows=dropped_rows,
        warnings=warnings,
        field_map=field_map,
    )
