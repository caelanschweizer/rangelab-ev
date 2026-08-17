from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    delete,
    insert,
    select,
    text,
)
from sqlalchemy.engine import Engine

from .schemas import FleetSummary, ImportRecord, TelemetryPoint, TripSummary


metadata = MetaData()


@dataclass(frozen=True, slots=True)
class StoredImport:
    record: ImportRecord
    request_digest: str

imports_table = Table(
    "imports",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("source_name", String(255), nullable=False),
    Column("content_sha256", String(64), nullable=False, index=True),
    Column("request_sha256", String(64), nullable=False, unique=True, index=True),
    Column("idempotency_key", String(200), nullable=True, unique=True, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("payload", JSON, nullable=False),
)

idempotency_keys_table = Table(
    "idempotency_keys",
    metadata,
    Column("key", String(200), primary_key=True),
    Column("import_id", String(36), ForeignKey("imports.id", ondelete="CASCADE"), nullable=False),
    Column("request_sha256", String(64), nullable=False),
)

trips_table = Table(
    "trips",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("import_id", String(36), ForeignKey("imports.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("started_at", DateTime(timezone=True), nullable=False, index=True),
    Column("payload", JSON, nullable=False),
)

telemetry_table = Table(
    "telemetry_points",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("trip_id", String(36), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("fingerprint", String(64), nullable=False, index=True),
    Column("observed_at", DateTime(timezone=True), nullable=False, index=True),
    Column("payload", JSON, nullable=False),
    UniqueConstraint("trip_id", "fingerprint", name="uq_telemetry_trip_fingerprint"),
)


class Repository:
    """Persistence boundary shared by SQLite and PostgreSQL deployments."""

    def __init__(self, database_url: str, *, engine: Engine | None = None) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine = engine or create_engine(database_url, future=True, connect_args=connect_args)

    def create_schema(self) -> None:
        metadata.create_all(self.engine)
        # Backfill the dedicated key table for databases created by pre-release builds.
        missing_bindings = (
            select(
                imports_table.c.id.label("import_id"),
                imports_table.c.idempotency_key.label("key"),
                imports_table.c.request_sha256.label("request_digest"),
            )
            .select_from(
                imports_table.outerjoin(
                    idempotency_keys_table,
                    imports_table.c.idempotency_key == idempotency_keys_table.c.key,
                )
            )
            .where(imports_table.c.idempotency_key.is_not(None))
            .where(idempotency_keys_table.c.key.is_(None))
        )
        with self.engine.begin() as connection:
            rows = connection.execute(missing_bindings).mappings().all()
            if rows:
                connection.execute(
                    insert(idempotency_keys_table),
                    [
                        {
                            "key": row["key"],
                            "import_id": row["import_id"],
                            "request_sha256": row["request_digest"],
                        }
                        for row in rows
                    ],
                )

    def close(self) -> None:
        self.engine.dispose()

    def healthcheck(self) -> bool:
        with self.engine.connect() as connection:
            return connection.execute(text("SELECT 1")).scalar_one() == 1

    @staticmethod
    def _import_from_payload(payload: dict[str, Any], *, replay: bool = False) -> ImportRecord:
        data = dict(payload)
        # Pre-release databases may contain these legacy public hash fields.
        data.pop("content_sha256", None)
        data.pop("request_sha256", None)
        data["idempotent_replay"] = replay
        return ImportRecord.model_validate(data)

    def find_import_by_request(self, request_digest: str) -> StoredImport | None:
        statement = (
            select(
                imports_table.c.payload,
                imports_table.c.request_sha256.label("request_digest"),
            )
            .where(imports_table.c.request_sha256 == request_digest)
            .limit(1)
        )
        with self.engine.connect() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        return (
            StoredImport(
                record=self._import_from_payload(row["payload"], replay=True),
                request_digest=row["request_digest"],
            )
            if row
            else None
        )

    def find_import_by_idempotency_key(self, idempotency_key: str) -> StoredImport | None:
        statement = (
            select(
                imports_table.c.payload,
                idempotency_keys_table.c.request_sha256.label("request_digest"),
            )
            .select_from(
                idempotency_keys_table.join(
                    imports_table, idempotency_keys_table.c.import_id == imports_table.c.id
                )
            )
            .where(idempotency_keys_table.c.key == idempotency_key)
            .limit(1)
        )
        with self.engine.connect() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        return (
            StoredImport(
                record=self._import_from_payload(row["payload"], replay=True),
                request_digest=row["request_digest"],
            )
            if row
            else None
        )

    def bind_idempotency_key(
        self, idempotency_key: str, record: ImportRecord, request_digest: str
    ) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                insert(idempotency_keys_table).values(
                    key=idempotency_key,
                    import_id=record.id,
                    request_sha256=request_digest,
                )
            )

    def get_import(self, import_id: str) -> ImportRecord | None:
        with self.engine.connect() as connection:
            payload = connection.execute(
                select(imports_table.c.payload).where(imports_table.c.id == import_id)
            ).scalar_one_or_none()
        return self._import_from_payload(payload) if payload else None

    def save_import(
        self,
        record: ImportRecord,
        trips: list[TripSummary],
        points_by_trip: dict[str, list[tuple[str, TelemetryPoint]]],
        *,
        content_digest: str,
        request_digest: str,
    ) -> None:
        import_payload = record.model_dump(mode="json")
        with self.engine.begin() as connection:
            connection.execute(
                insert(imports_table).values(
                    id=record.id,
                    source_name=record.source_name,
                    content_sha256=content_digest,
                    request_sha256=request_digest,
                    idempotency_key=record.idempotency_key,
                    created_at=record.created_at,
                    payload=import_payload,
                )
            )
            if record.idempotency_key:
                connection.execute(
                    insert(idempotency_keys_table).values(
                        key=record.idempotency_key,
                        import_id=record.id,
                        request_sha256=request_digest,
                    )
                )
            if trips:
                connection.execute(
                    insert(trips_table),
                    [
                        {
                            "id": trip.id,
                            "import_id": trip.import_id,
                            "started_at": trip.started_at,
                            "payload": trip.model_dump(mode="json"),
                        }
                        for trip in trips
                    ],
                )
            telemetry_rows = [
                {
                    "trip_id": trip_id,
                    "fingerprint": fingerprint,
                    "observed_at": point.observed_at,
                    "payload": point.model_dump(mode="json"),
                }
                for trip_id, fingerprinted_points in points_by_trip.items()
                for fingerprint, point in fingerprinted_points
            ]
            if telemetry_rows:
                connection.execute(insert(telemetry_table), telemetry_rows)

    def list_trips(self, *, limit: int = 100, offset: int = 0) -> list[TripSummary]:
        statement = (
            select(trips_table.c.payload)
            .order_by(trips_table.c.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        with self.engine.connect() as connection:
            return [TripSummary.model_validate(payload) for payload in connection.execute(statement).scalars()]

    def get_trip(self, trip_id: str) -> TripSummary | None:
        with self.engine.connect() as connection:
            payload = connection.execute(
                select(trips_table.c.payload).where(trips_table.c.id == trip_id)
            ).scalar_one_or_none()
        return TripSummary.model_validate(payload) if payload else None

    def list_import_trips(self, import_id: str) -> list[TripSummary]:
        statement = (
            select(trips_table.c.payload)
            .where(trips_table.c.import_id == import_id)
            .order_by(trips_table.c.started_at)
        )
        with self.engine.connect() as connection:
            return [TripSummary.model_validate(payload) for payload in connection.execute(statement).scalars()]

    def get_trip_points(self, trip_id: str, *, limit: int = 20_000) -> list[TelemetryPoint]:
        statement = (
            select(telemetry_table.c.payload)
            .where(telemetry_table.c.trip_id == trip_id)
            .order_by(telemetry_table.c.observed_at)
            .limit(limit)
        )
        with self.engine.connect() as connection:
            return [TelemetryPoint.model_validate(payload) for payload in connection.execute(statement).scalars()]

    def fleet_summary(self) -> FleetSummary:
        trips = self.list_trips(limit=100_000)
        if not trips:
            return FleetSummary(
                trip_count=0,
                total_distance_km=0,
                total_energy_used_kwh=0,
                total_energy_regenerated_kwh=0,
                overall_efficiency_wh_per_km=None,
                average_quality_score=None,
                newest_trip_at=None,
            )
        distance = sum(trip.distance_km for trip in trips)
        net_energy = sum(trip.net_energy_kwh for trip in trips)
        return FleetSummary(
            trip_count=len(trips),
            total_distance_km=round(distance, 3),
            total_energy_used_kwh=round(sum(trip.energy_used_kwh for trip in trips), 3),
            total_energy_regenerated_kwh=round(sum(trip.energy_regenerated_kwh for trip in trips), 3),
            overall_efficiency_wh_per_km=round(net_energy * 1000 / distance, 2) if distance else None,
            average_quality_score=round(sum(trip.data_quality.score for trip in trips) / len(trips), 2),
            newest_trip_at=max(trip.ended_at for trip in trips),
        )

    def clear_all(self) -> None:
        """Test helper; callers must explicitly choose to destroy local records."""
        with self.engine.begin() as connection:
            connection.execute(delete(telemetry_table))
            connection.execute(delete(trips_table))
            connection.execute(delete(idempotency_keys_table))
            connection.execute(delete(imports_table))
