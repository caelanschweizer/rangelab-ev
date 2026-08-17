from __future__ import annotations

import pytest

from rangelab.ingestion import CsvIngestionError, detect_fields, parse_torque_csv


def test_parses_torque_headers_and_derives_power() -> None:
    text = """GPS Time,Speed (OBD)(km/h),State of Charge (displayed)(%),Hybrid/EV Battery Pack Voltage(V),Hybrid/EV Battery Pack Current(A),Latitude,Longitude
2026-01-01T10:00:00Z,50,80,360,25,43.9,-78.8
2026-01-01T10:00:10Z,52,79.9,361,-10,43.9001,-78.7999
"""
    result = parse_torque_csv(text)

    assert result.parsed_rows == 2
    assert result.dropped_rows == 0
    assert result.points[0].pack_power_kw == pytest.approx(9)
    assert result.points[1].pack_power_kw == pytest.approx(-3.61)
    assert "derived" in result.warnings[0].lower()


def test_converts_imperial_columns() -> None:
    text = """timestamp,Vehicle Speed(mph),Battery Power(kW),Outside Temp(degF),Battery Temp(degF),Odometer(mi)
2026-01-01T10:00:00Z,62.1371,12,32,68,100
"""
    result = parse_torque_csv(text)
    point = result.points[0]
    assert point.speed_kph == pytest.approx(100, rel=1e-4)
    assert point.ambient_temp_c == pytest.approx(0)
    assert point.battery_temp_c == pytest.approx(20)
    assert point.odometer_km == pytest.approx(160.9344)


def test_drops_bad_timestamps_and_ignores_out_of_range_values() -> None:
    text = """Device Time,Battery Power(kW),Speed (OBD)(km/h)
not-a-date,10,20
2026-01-01 10:00:00,8,999
"""
    result = parse_torque_csv(text)
    assert result.parsed_rows == 2
    assert result.dropped_rows == 1
    assert result.points[0].speed_kph is None
    assert len(result.warnings) == 3


def test_requires_time_and_energy_signal() -> None:
    with pytest.raises(CsvIngestionError, match="timestamp"):
        parse_torque_csv("unrelated\n10\n")
    with pytest.raises(CsvIngestionError, match="pack-energy"):
        parse_torque_csv("timestamp,Speed(km/h)\n2026-01-01T00:00:00Z,10\n")


def test_detect_fields_does_not_treat_hvac_as_pack_power() -> None:
    fields, _ = detect_fields(["timestamp", "HVAC Power(kW)", "Battery Pack Power(kW)"])
    assert fields["hvac_power_kw"] == "HVAC Power(kW)"
    assert fields["pack_power_kw"] == "Battery Pack Power(kW)"


def test_explicit_watts_kph_and_fahrenheit_are_converted() -> None:
    text = """timestamp,Vehicle Speed(kph),Battery Pack Power(W),HVAC Power(W),Ambient Temp(F),Battery Temp(C)
2026-01-01T10:00:00Z,100,12500,750,14,20
"""
    point = parse_torque_csv(text).points[0]
    assert point.speed_kph == 100
    assert point.pack_power_kw == 12.5
    assert point.hvac_power_kw == 0.75
    assert point.ambient_temp_c == pytest.approx(-10)
    assert point.battery_temp_c == 20


@pytest.mark.parametrize(
    "header,error",
    [
        ("Vehicle Speed", "Ambiguous speed unit"),
        ("Battery Pack Power", "Ambiguous power unit"),
        ("Ambient Temp", "Ambiguous temperature unit"),
    ],
)
def test_rejects_ambiguous_sensor_units(header: str, error: str) -> None:
    with pytest.raises(CsvIngestionError, match=error):
        parse_torque_csv(f"timestamp,{header}\n2026-01-01T10:00:00Z,10\n")


def test_counts_invalid_power_voltage_and_current_values() -> None:
    text = """timestamp,Battery Pack Power(kW),Battery Pack Voltage(V),Battery Pack Current(A)
2026-01-01T10:00:00Z,600,1200,not-a-number
2026-01-01T10:00:10Z,10,360,20
"""
    result = parse_torque_csv(text)
    point = result.points[0]
    assert point.pack_power_kw is None
    assert point.pack_voltage_v is None
    assert point.pack_current_a is None
    assert any("3 invalid or out-of-range" in warning for warning in result.warnings)


def test_rejects_file_when_every_energy_value_is_invalid() -> None:
    text = """timestamp,Battery Pack Power(kW),Battery Pack Voltage(V),Battery Pack Current(A)
2026-01-01T10:00:00Z,600,1200,not-a-number
"""
    with pytest.raises(CsvIngestionError, match="All declared or derived pack-energy values are invalid") as error:
        parse_torque_csv(text)
    assert "3 invalid or out-of-range" in str(error.value)


def test_ignores_engine_rpm_but_rejects_bare_odometer() -> None:
    text = """timestamp,Battery Pack Power(kW),Engine Speed(RPM),Odometer(km)
2026-01-01T10:00:00Z,10,4500,100
"""
    result = parse_torque_csv(text)
    assert result.points[0].speed_kph is None
    assert "speed_kph" not in result.field_map

    with pytest.raises(CsvIngestionError, match="Ambiguous odometer unit"):
        parse_torque_csv(
            "timestamp,Battery Pack Power(kW),Odometer\n2026-01-01T10:00:00Z,10,100\n"
        )


def test_rejects_extra_columns_and_unclosed_quotes_as_malformed() -> None:
    with pytest.raises(CsvIngestionError, match="more values"):
        parse_torque_csv(
            "timestamp,Battery Pack Power(kW)\n2026-01-01T10:00:00Z,10,unexpected\n"
        )
    with pytest.raises(CsvIngestionError, match="Malformed CSV"):
        parse_torque_csv(
            'timestamp,Battery Pack Power(kW)\n"2026-01-01T10:00:00Z,10\n'
        )
