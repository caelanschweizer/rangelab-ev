from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError

from .forecast import diagnostics, forecast
from .ingestion import CsvIngestionError
from .repository import Repository
from .schemas import (
    CsvTextImportRequest,
    FleetSummary,
    ForecastRequest,
    ForecastResponse,
    ImportWithTrips,
    ModelDiagnostics,
    PrivacyOptions,
    SegmentationOptions,
    TelemetryPoint,
    TripSummary,
)
from .service import IdempotencyConflict, ImportService
from .settings import Settings


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    database: str


def create_app(settings: Settings | None = None, repository: Repository | None = None) -> FastAPI:
    configured = settings or Settings.from_env()
    repo = repository or Repository(configured.database_url)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        repo.create_schema()
        application.state.repository = repo
        yield
        if repository is None:
            repo.close()

    application = FastAPI(
        title="RangeLab EV API",
        version="1.0.0",
        description=(
            "Read-only EV telemetry ingestion, privacy protection, trip analytics, "
            "and transparent energy forecasting."
        ),
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(configured.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Idempotency-Key"],
    )

    def service() -> ImportService:
        return ImportService(
            repo,
            default_gap_minutes=configured.trip_gap_minutes,
            identity_secret=configured.identity_secret,
        )

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        database_kind = "sqlite" if configured.database_url.startswith("sqlite") else "postgresql"
        try:
            database_healthy = repo.healthcheck()
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Database health check failed.") from exc
        if not database_healthy:
            raise HTTPException(status_code=503, detail="Database health check failed.")
        return HealthResponse(status="ok", service="rangelab-ev-api", version="1.0.0", database=database_kind)

    @application.post(
        "/api/v1/imports/csv-text",
        response_model=ImportWithTrips,
        status_code=status.HTTP_201_CREATED,
        tags=["imports"],
    )
    def import_csv_text(payload: CsvTextImportRequest) -> ImportWithTrips:
        if len(payload.csv_text.encode("utf-8")) > configured.max_upload_bytes:
            raise HTTPException(status_code=413, detail="CSV exceeds the configured upload limit.")
        try:
            record, trips = service().import_csv(
                payload.csv_text,
                source_name=payload.source_name,
                idempotency_key=payload.idempotency_key,
                privacy=payload.privacy,
                segmentation=payload.segmentation,
                invert_power_sign=payload.invert_power_sign,
            )
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except CsvIngestionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return ImportWithTrips(import_record=record, trips=trips)

    @application.post(
        "/api/v1/imports/csv",
        response_model=ImportWithTrips,
        status_code=status.HTTP_201_CREATED,
        tags=["imports"],
    )
    async def import_csv_file(
        file: Annotated[UploadFile, File(description="Torque/OBD Fusion-style CSV")],
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=200)] = None,
        privacy_options: Annotated[
            str | None,
            Form(description="JSON PrivacyOptions; sensitive coordinates remain in the request body."),
        ] = None,
        segmentation_options: Annotated[
            str | None,
            Form(description="Optional JSON SegmentationOptions."),
        ] = None,
        invert_power_sign: Annotated[bool, Form()] = False,
    ) -> ImportWithTrips:
        raw = await file.read(configured.max_upload_bytes + 1)
        if len(raw) > configured.max_upload_bytes:
            raise HTTPException(status_code=413, detail="CSV exceeds the configured upload limit.")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=422, detail="CSV must be UTF-8 encoded.") from exc
        try:
            privacy = PrivacyOptions.model_validate_json(privacy_options) if privacy_options else PrivacyOptions()
            segmentation = (
                SegmentationOptions.model_validate_json(segmentation_options)
                if segmentation_options
                else None
            )
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=f"Invalid JSON import options: {exc}") from exc
        try:
            record, trips = service().import_csv(
                text,
                source_name=file.filename or "telemetry.csv",
                idempotency_key=idempotency_key,
                privacy=privacy,
                segmentation=segmentation,
                invert_power_sign=invert_power_sign,
            )
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except CsvIngestionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return ImportWithTrips(import_record=record, trips=trips)

    @application.get("/api/v1/imports/{import_id}", response_model=ImportWithTrips, tags=["imports"])
    def get_import(import_id: str) -> ImportWithTrips:
        record = repo.get_import(import_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Import not found.")
        return ImportWithTrips(import_record=record, trips=repo.list_import_trips(import_id))

    @application.get("/api/v1/trips", response_model=list[TripSummary], tags=["trips"])
    def list_trips(
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> list[TripSummary]:
        return repo.list_trips(limit=limit, offset=offset)

    @application.get("/api/v1/trips/{trip_id}", response_model=TripSummary, tags=["trips"])
    def get_trip(trip_id: str) -> TripSummary:
        trip = repo.get_trip(trip_id)
        if trip is None:
            raise HTTPException(status_code=404, detail="Trip not found.")
        return trip

    @application.get(
        "/api/v1/trips/{trip_id}/telemetry", response_model=list[TelemetryPoint], tags=["trips"]
    )
    def get_trip_telemetry(
        trip_id: str, limit: Annotated[int, Query(ge=1, le=20_000)] = 20_000
    ) -> list[TelemetryPoint]:
        if repo.get_trip(trip_id) is None:
            raise HTTPException(status_code=404, detail="Trip not found.")
        return repo.get_trip_points(trip_id, limit=limit)

    @application.post("/api/v1/forecast", response_model=ForecastResponse, tags=["forecast"])
    def create_forecast(payload: ForecastRequest) -> ForecastResponse:
        return forecast(payload, repo.list_trips(limit=100_000))

    @application.get("/api/v1/model/diagnostics", response_model=ModelDiagnostics, tags=["forecast"])
    def model_diagnostics() -> ModelDiagnostics:
        return diagnostics(repo.list_trips(limit=100_000))

    @application.get("/api/v1/summary", response_model=FleetSummary, tags=["trips"])
    def summary() -> FleetSummary:
        return repo.fleet_summary()

    return application


app = create_app()
