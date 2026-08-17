from __future__ import annotations

import csv
import io
import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from rangelab.api import create_app
from rangelab.repository import Repository
from rangelab.settings import Settings
from rangelab.synthetic import HEADERS, generate_rows


def make_client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    repository = Repository("sqlite+pysqlite:///:memory:", engine=engine)
    app = create_app(Settings(database_url="sqlite+pysqlite:///:memory:"), repository)
    return TestClient(app)


def sample_csv() -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=HEADERS)
    writer.writeheader()
    writer.writerows(generate_rows(trips=2, seed=99))
    return buffer.getvalue()


def test_health_import_read_and_forecast_api() -> None:
    with make_client() as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        imported = client.post(
            "/api/v1/imports/csv-text",
            json={"csv_text": sample_csv(), "source_name": "api-demo.csv", "idempotency_key": "api-1"},
        )
        assert imported.status_code == 201, imported.text
        payload = imported.json()
        assert len(payload["trips"]) == 2
        assert "content_sha256" not in payload["import_record"]
        assert "request_sha256" not in payload["import_record"]
        trip_id = payload["trips"][0]["id"]

        assert client.get("/api/v1/trips").status_code == 200
        assert client.get(f"/api/v1/trips/{trip_id}").json()["id"] == trip_id
        assert len(client.get(f"/api/v1/trips/{trip_id}/telemetry").json()) > 50
        assert client.get("/api/v1/summary").json()["trip_count"] == 2

        predicted = client.post(
            "/api/v1/forecast",
            json={"distance_km": 75, "ambient_temp_c": -5, "starting_soc_pct": 80},
        )
        assert predicted.status_code == 200
        assert predicted.json()["predicted_energy_kwh"] > 0
        assert client.get("/api/v1/model/diagnostics").status_code == 200


def test_multipart_and_validation_errors() -> None:
    with make_client() as client:
        privacy = {
            "zones": [
                {"name": "home", "latitude": 43.945, "longitude": -78.896, "radius_m": 20_000}
            ],
            "shift_timestamps": False,
        }
        uploaded = client.post(
            "/api/v1/imports/csv",
            files={"file": ("demo.csv", sample_csv(), "text/csv")},
            data={"privacy_options": json.dumps(privacy)},
            headers={"Idempotency-Key": "multipart-1"},
        )
        assert uploaded.status_code == 201, uploaded.text
        assert uploaded.json()["import_record"]["idempotency_key"] == "multipart-1"
        assert uploaded.json()["import_record"]["privacy_masked_points"] > 0

        invalid = client.post(
            "/api/v1/imports/csv-text",
            json={"csv_text": "timestamp,speed\n2026-01-01T00:00:00Z,5", "source_name": "bad.csv"},
        )
        assert invalid.status_code == 422
        assert "Ambiguous speed unit" in invalid.json()["detail"]
        assert client.get("/api/v1/trips/missing").status_code == 404


def test_api_maps_idempotency_conflict_and_malformed_csv() -> None:
    with make_client() as client:
        text = sample_csv()
        first = client.post(
            "/api/v1/imports/csv-text",
            json={"csv_text": text, "idempotency_key": "one-request"},
        )
        assert first.status_code == 201
        conflict = client.post(
            "/api/v1/imports/csv-text",
            json={
                "csv_text": text,
                "idempotency_key": "one-request",
                "privacy": {"coordinate_precision": 3},
            },
        )
        assert conflict.status_code == 409
        assert "different CSV or import configuration" in conflict.json()["detail"]

        malformed = client.post(
            "/api/v1/imports/csv-text",
            json={
                "csv_text": "timestamp,Battery Pack Power(kW)\n2026-01-01T00:00:00Z,4,extra\n"
            },
        )
        assert malformed.status_code == 422
        assert "Malformed CSV row" in malformed.json()["detail"]

        invalid_energy = client.post(
            "/api/v1/imports/csv-text",
            json={
                "csv_text": "timestamp,Battery Pack Power(kW)\n2026-01-01T00:00:00Z,900\n"
            },
        )
        assert invalid_energy.status_code == 422
        assert "pack-energy values are invalid" in invalid_energy.json()["detail"]


def test_multipart_options_validation_and_database_health() -> None:
    client = make_client()
    with client:
        invalid_options = client.post(
            "/api/v1/imports/csv",
            files={"file": ("demo.csv", sample_csv(), "text/csv")},
            data={"privacy_options": "{not-json"},
        )
        assert invalid_options.status_code == 422
        assert "Invalid JSON import options" in invalid_options.json()["detail"]

        repository = client.app.state.repository
        repository.healthcheck = lambda: False
        unhealthy = client.get("/health")
        assert unhealthy.status_code == 503
        assert "Database health check failed" in unhealthy.json()["detail"]


def test_openapi_keeps_privacy_coordinates_out_of_query_parameters() -> None:
    with make_client() as client:
        operation = client.get("/openapi.json").json()["paths"]["/api/v1/imports/csv"]["post"]
        parameter_names = {parameter["name"] for parameter in operation.get("parameters", [])}
        assert parameter_names == {"Idempotency-Key"}
        body_schema = operation["requestBody"]["content"]["multipart/form-data"]["schema"]
        if "$ref" in body_schema:
            component_name = body_schema["$ref"].rsplit("/", 1)[-1]
            body_schema = client.get("/openapi.json").json()["components"]["schemas"][component_name]
        assert {"file", "privacy_options", "segmentation_options", "invert_power_sign"}.issubset(
            body_schema["properties"]
        )
        import_schema = client.get("/openapi.json").json()["components"]["schemas"]["ImportRecord"]
        assert "content_sha256" not in import_schema["properties"]
        assert "request_sha256" not in import_schema["properties"]
