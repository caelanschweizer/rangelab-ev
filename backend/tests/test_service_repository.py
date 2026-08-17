from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, insert
from sqlalchemy.pool import StaticPool

from rangelab.repository import Repository, imports_table
from rangelab.schemas import ImportRecord, PrivacyOptions, PrivacyZone, SegmentationOptions
from rangelab.service import IdempotencyConflict, ImportService, _canonical_csv, _request_digest
from rangelab.synthetic import HEADERS, generate_rows


def csv_from_rows(rows: list[dict[str, str]]) -> str:
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=HEADERS)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def memory_repository() -> Repository:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    repository = Repository("sqlite+pysqlite:///:memory:", engine=engine)
    repository.create_schema()
    return repository


def test_end_to_end_import_is_idempotent_and_queryable() -> None:
    repository = memory_repository()
    service = ImportService(repository)
    text = csv_from_rows(generate_rows(trips=3, seed=7))

    record, trips = service.import_csv(text, source_name="demo.csv", idempotency_key="demo-1")
    replay, replay_trips = ImportService(repository).import_csv(
        text, source_name="renamed.csv", idempotency_key="demo-1"
    )

    assert len(trips) == 3
    assert record.accepted_rows > 200
    assert replay.id == record.id
    assert uuid.UUID(record.id).version == 4
    assert all(uuid.UUID(trip.id).version == 4 for trip in trips)
    assert "content_sha256" not in record.model_dump()
    assert "request_sha256" not in record.model_dump()
    assert replay.idempotent_replay is True
    assert [trip.id for trip in replay_trips] == [trip.id for trip in trips]
    assert repository.get_trip(trips[0].id) == trips[0]
    assert len(repository.get_trip_points(trips[0].id)) == trips[0].point_count
    assert repository.fleet_summary().trip_count == 3


def test_import_identity_includes_all_processing_options_and_scopes_points() -> None:
    repository = memory_repository()
    service = ImportService(repository)
    text = csv_from_rows(generate_rows(trips=1, seed=17))
    first_latitude = float(generate_rows(trips=1, seed=17)[0][HEADERS[6]])
    first_longitude = float(generate_rows(trips=1, seed=17)[0][HEADERS[7]])

    public_record, public_trips = service.import_csv(text, source_name="same.csv")
    private_record, private_trips = service.import_csv(
        text,
        source_name="same.csv",
        privacy=PrivacyOptions(
            zones=[
                PrivacyZone(
                    name="home",
                    latitude=first_latitude,
                    longitude=first_longitude,
                    radius_m=20_000,
                )
            ]
        ),
    )
    inverted_record, inverted_trips = service.import_csv(
        text,
        source_name="same.csv",
        invert_power_sign=True,
    )
    segmented_record, segmented_trips = service.import_csv(
        text,
        source_name="same.csv",
        segmentation=SegmentationOptions(gap_minutes=30),
    )

    records = (public_record, private_record, inverted_record, segmented_record)
    assert len({record.id for record in records}) == 4
    assert all(uuid.UUID(record.id).version == 4 for record in records)
    assert private_record.privacy_masked_points > 0
    assert repository.get_trip_points(public_trips[0].id)[0].latitude is not None
    assert repository.get_trip_points(private_trips[0].id)[0].latitude is None
    assert len(repository.get_trip_points(inverted_trips[0].id)) == inverted_trips[0].point_count
    assert len(repository.get_trip_points(segmented_trips[0].id)) == segmented_trips[0].point_count
    assert repository.fleet_summary().trip_count == 4


def test_internal_identity_is_secret_keyed_and_not_a_public_hash() -> None:
    text = _canonical_csv(csv_from_rows(generate_rows(trips=1, seed=19)))
    privacy = PrivacyOptions(
        zones=[PrivacyZone(name="home", latitude=43.9, longitude=-78.8, radius_m=500)]
    )
    segmentation = SegmentationOptions()
    first = _request_digest(
        text,
        privacy=privacy,
        segmentation=segmentation,
        invert_power_sign=False,
        identity_secret="a" * 48,
    )
    second = _request_digest(
        text,
        privacy=privacy,
        segmentation=segmentation,
        invert_power_sign=False,
        identity_secret="b" * 48,
    )
    assert first != second
    assert first[0] != hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_idempotency_key_conflicts_for_different_canonical_request() -> None:
    repository = memory_repository()
    service = ImportService(repository)
    text = csv_from_rows(generate_rows(trips=1, seed=23))
    service.import_csv(text, source_name="first.csv", idempotency_key="stable-key")
    with pytest.raises(IdempotencyConflict, match="different CSV or import configuration"):
        service.import_csv(
            text,
            source_name="second.csv",
            idempotency_key="stable-key",
            segmentation=SegmentationOptions(gap_minutes=30),
        )


def test_key_is_bound_when_added_to_an_existing_unkeyed_request() -> None:
    repository = memory_repository()
    service = ImportService(repository)
    text = csv_from_rows(generate_rows(trips=1, seed=29))
    original, _ = service.import_csv(text, source_name="unkeyed.csv")
    replay, _ = service.import_csv(text, source_name="keyed.csv", idempotency_key="bound-later")
    assert replay.id == original.id
    with pytest.raises(IdempotencyConflict):
        service.import_csv(
            text,
            source_name="changed.csv",
            idempotency_key="bound-later",
            invert_power_sign=True,
        )


def test_changed_secret_cannot_replay_an_existing_explicit_key() -> None:
    repository = memory_repository()
    text = csv_from_rows(generate_rows(trips=1, seed=37))
    ImportService(repository, identity_secret="a" * 48).import_csv(
        text, source_name="first.csv", idempotency_key="secret-bound-key"
    )
    with pytest.raises(IdempotencyConflict):
        ImportService(repository, identity_secret="b" * 48).import_csv(
            text, source_name="second.csv", idempotency_key="secret-bound-key"
        )


def test_schema_upgrade_backfills_pre_release_idempotency_binding() -> None:
    repository = memory_repository()
    record = ImportRecord(
        id=str(uuid.uuid4()),
        source_name="legacy.csv",
        idempotency_key="legacy-key",
        created_at=datetime.now(tz=UTC),
        parsed_rows=0,
        accepted_rows=0,
        dropped_rows=0,
        duplicate_rows=0,
        privacy_masked_points=0,
    )
    with repository.engine.begin() as connection:
        connection.execute(
            insert(imports_table).values(
                id=record.id,
                source_name=record.source_name,
                content_sha256="c" * 64,
                request_sha256="r" * 64,
                idempotency_key=record.idempotency_key,
                created_at=record.created_at,
                payload=record.model_dump(mode="json"),
            )
        )
    repository.create_schema()
    stored = repository.find_import_by_idempotency_key("legacy-key")
    assert stored is not None
    assert stored.record.id == record.id
    assert stored.request_digest == "r" * 64


def test_csv_line_endings_and_zone_order_have_canonical_identity() -> None:
    repository = memory_repository()
    service = ImportService(repository)
    text = csv_from_rows(generate_rows(trips=1, seed=31))
    zones = [
        PrivacyZone(name="work", latitude=43.8, longitude=-78.7, radius_m=300),
        PrivacyZone(name="home", latitude=43.9, longitude=-78.8, radius_m=500),
    ]
    lf_text = text.replace("\r\n", "\n")
    first, _ = service.import_csv(lf_text, source_name="one.csv", privacy=PrivacyOptions(zones=zones))
    replay, _ = service.import_csv(
        lf_text.replace("\n", "\r\n"),
        source_name="two.csv",
        privacy=PrivacyOptions(zones=list(reversed(zones))),
    )
    assert replay.id == first.id
    assert replay.idempotent_replay is True


def test_masks_home_zone_before_persistence() -> None:
    repository = memory_repository()
    service = ImportService(repository)
    rows = generate_rows(trips=1, seed=7)[:10]
    first_lat = float(rows[0][HEADERS[6]])
    first_lon = float(rows[0][HEADERS[7]])
    record, trips = service.import_csv(
        csv_from_rows(rows),
        source_name="private.csv",
        privacy=PrivacyOptions(
            zones=[PrivacyZone(name="home", latitude=first_lat, longitude=first_lon, radius_m=10_000)]
        ),
        segmentation=SegmentationOptions(minimum_points=2),
    )
    stored = repository.get_trip_points(trips[0].id)
    assert record.privacy_masked_points == 10
    assert all(point.latitude is None and point.longitude is None for point in stored)
