from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PrivacyZone(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_m: float = Field(default=500, gt=0, le=20_000)


class PrivacyOptions(StrictModel):
    enabled: bool = True
    zones: list[PrivacyZone] = Field(default_factory=list, max_length=20)
    coordinate_precision: int | None = Field(default=4, ge=0, le=6)
    mask_coordinates_in_zones: bool = True
    shift_timestamps: bool = False


class SegmentationOptions(StrictModel):
    gap_minutes: int = Field(default=15, ge=2, le=180)
    max_integration_gap_seconds: int = Field(default=120, ge=10, le=900)
    minimum_points: int = Field(default=2, ge=1, le=100)


class TelemetryPoint(StrictModel):
    observed_at: datetime
    speed_kph: float | None = Field(default=None, ge=0, le=300)
    soc_pct: float | None = Field(default=None, ge=0, le=100)
    pack_voltage_v: float | None = Field(default=None, ge=0, le=1000)
    pack_current_a: float | None = Field(default=None, ge=-1000, le=1000)
    pack_power_kw: float | None = Field(default=None, ge=-500, le=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    ambient_temp_c: float | None = Field(default=None, ge=-80, le=80)
    battery_temp_c: float | None = Field(default=None, ge=-80, le=100)
    hvac_power_kw: float | None = Field(default=None, ge=0, le=20)
    odometer_km: float | None = Field(default=None, ge=0, le=5_000_000)
    source_row: int | None = Field(default=None, ge=2)

    @model_validator(mode="after")
    def coordinates_are_a_pair(self) -> "TelemetryPoint":
        if (self.latitude is None) != (self.longitude is None):
            self.latitude = None
            self.longitude = None
        return self


class DataQuality(StrictModel):
    score: float = Field(ge=0, le=100)
    grade: Literal["A", "B", "C", "D", "F"]
    power_coverage_pct: float = Field(ge=0, le=100)
    location_coverage_pct: float = Field(ge=0, le=100)
    interval_coverage_pct: float = Field(ge=0, le=100)
    unexpected_gap_count: int = Field(ge=0)
    invalid_interval_count: int = Field(ge=0)
    max_gap_seconds: float = Field(ge=0)
    notes: list[str] = Field(default_factory=list)


class TripSummary(StrictModel):
    id: str
    import_id: str
    started_at: datetime
    ended_at: datetime
    duration_minutes: float = Field(ge=0)
    point_count: int = Field(ge=1)
    distance_km: float = Field(ge=0)
    distance_source: Literal["odometer", "gps", "speed", "mixed", "unavailable"]
    energy_used_kwh: float = Field(ge=0)
    energy_regenerated_kwh: float = Field(ge=0)
    net_energy_kwh: float
    efficiency_wh_per_km: float | None
    regen_recovery_pct: float | None
    start_soc_pct: float | None
    end_soc_pct: float | None
    soc_used_pct: float | None
    average_speed_kph: float | None
    average_ambient_temp_c: float | None
    average_battery_temp_c: float | None
    average_hvac_power_kw: float | None
    data_quality: DataQuality


class ImportRecord(StrictModel):
    id: str
    source_name: str
    idempotency_key: str | None = None
    status: Literal["completed"] = "completed"
    created_at: datetime
    parsed_rows: int = Field(ge=0)
    accepted_rows: int = Field(ge=0)
    dropped_rows: int = Field(ge=0)
    duplicate_rows: int = Field(ge=0)
    privacy_masked_points: int = Field(ge=0)
    trip_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    field_map: dict[str, str] = Field(default_factory=dict)
    idempotent_replay: bool = False


class CsvTextImportRequest(StrictModel):
    csv_text: str = Field(min_length=1)
    source_name: str = Field(default="telemetry.csv", min_length=1, max_length=255)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)
    privacy: PrivacyOptions = Field(default_factory=PrivacyOptions)
    segmentation: SegmentationOptions | None = None
    invert_power_sign: bool = False


class ForecastRequest(StrictModel):
    distance_km: float = Field(gt=0, le=2_000)
    ambient_temp_c: float = Field(default=20, ge=-60, le=60)
    expected_speed_kph: float = Field(default=60, gt=0, le=180)
    hvac_power_kw: float = Field(default=0, ge=0, le=15)
    starting_soc_pct: float | None = Field(default=None, ge=0, le=100)
    usable_capacity_kwh: float = Field(default=60, gt=1, le=250)


class ForecastInterval(StrictModel):
    confidence_pct: int | None
    calibrated: bool
    basis: str
    lower_kwh: float = Field(ge=0)
    upper_kwh: float = Field(ge=0)


class ForecastResponse(StrictModel):
    predicted_energy_kwh: float = Field(ge=0)
    baseline_energy_kwh: float = Field(ge=0)
    interval: ForecastInterval
    predicted_arrival_soc_pct: float | None
    model_kind: Literal["trained_ridge", "engineering_fallback"]
    training_trip_count: int = Field(ge=0)
    equation: str
    contributions_kwh: dict[str, float]
    assumptions: list[str]


class ModelDiagnostics(StrictModel):
    model_kind: Literal["trained_ridge", "engineering_fallback"]
    eligible_trip_count: int = Field(ge=0)
    evaluated_trip_count: int = Field(ge=0)
    model_mae_kwh: float | None
    baseline_mae_kwh: float | None
    improvement_pct: float | None
    residual_std_kwh: float = Field(ge=0)
    coefficients: dict[str, float]
    backtest_method: str
    caveats: list[str]


class FleetSummary(StrictModel):
    trip_count: int = Field(ge=0)
    total_distance_km: float = Field(ge=0)
    total_energy_used_kwh: float = Field(ge=0)
    total_energy_regenerated_kwh: float = Field(ge=0)
    overall_efficiency_wh_per_km: float | None
    average_quality_score: float | None
    newest_trip_at: datetime | None


class ImportWithTrips(StrictModel):
    import_record: ImportRecord
    trips: list[TripSummary]


class ApiError(StrictModel):
    detail: str
    context: dict[str, Any] | None = None
