from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from .analytics import deduplicate_points, point_fingerprint, segment_points, summarize_trip
from .ingestion import CsvParseResult, parse_torque_csv
from .privacy import apply_privacy
from .repository import Repository
from .schemas import ImportRecord, PrivacyOptions, SegmentationOptions, TripSummary
from .settings import PROCESS_LOCAL_IDENTITY_SECRET


class IdempotencyConflict(ValueError):
    """Raised when a key is reused for a different canonical import request."""


def _canonical_csv(csv_text: str) -> str:
    return csv_text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")


def _request_digest(
    canonical_csv: str,
    *,
    privacy: PrivacyOptions,
    segmentation: SegmentationOptions,
    invert_power_sign: bool,
    identity_secret: str | bytes,
) -> tuple[str, str]:
    secret = identity_secret.encode("utf-8") if isinstance(identity_secret, str) else identity_secret
    if len(secret) < 32:
        raise ValueError("RANGELAB_IDENTITY_SECRET must contain at least 32 bytes.")
    content_digest = hmac.new(
        secret,
        b"rangelab-content-v1\0" + canonical_csv.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    privacy_payload = privacy.model_dump(mode="json")
    privacy_payload["zones"] = sorted(
        privacy_payload["zones"],
        key=lambda zone: json.dumps(zone, sort_keys=True, separators=(",", ":")),
    )
    identity = {
        "content_digest": content_digest,
        "privacy": privacy_payload,
        "segmentation": segmentation.model_dump(mode="json"),
        "invert_power_sign": invert_power_sign,
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    request_digest = hmac.new(
        secret, b"rangelab-request-v1\0" + encoded, hashlib.sha256
    ).hexdigest()
    return content_digest, request_digest


class ImportService:
    def __init__(
        self,
        repository: Repository,
        *,
        default_gap_minutes: int = 15,
        identity_secret: str | bytes = PROCESS_LOCAL_IDENTITY_SECRET,
    ) -> None:
        self.repository = repository
        self.default_gap_minutes = default_gap_minutes
        self.identity_secret = identity_secret

    def import_csv(
        self,
        csv_text: str,
        *,
        source_name: str,
        idempotency_key: str | None = None,
        privacy: PrivacyOptions | None = None,
        segmentation: SegmentationOptions | None = None,
        invert_power_sign: bool = False,
    ) -> tuple[ImportRecord, list[TripSummary]]:
        canonical_csv = _canonical_csv(csv_text)
        privacy_options = privacy or PrivacyOptions()
        options = segmentation or SegmentationOptions(gap_minutes=self.default_gap_minutes)
        content_digest, request_digest = _request_digest(
            canonical_csv,
            privacy=privacy_options,
            segmentation=options,
            invert_power_sign=invert_power_sign,
            identity_secret=self.identity_secret,
        )

        if idempotency_key:
            keyed_import = self.repository.find_import_by_idempotency_key(idempotency_key)
            if keyed_import and keyed_import.request_digest != request_digest:
                raise IdempotencyConflict(
                    "The Idempotency-Key was already used for a different CSV or import configuration."
                )
            if keyed_import:
                return keyed_import.record, self.repository.list_import_trips(keyed_import.record.id)

        existing = self.repository.find_import_by_request(request_digest)
        if existing:
            if idempotency_key:
                self.repository.bind_idempotency_key(
                    idempotency_key, existing.record, existing.request_digest
                )
            return existing.record, self.repository.list_import_trips(existing.record.id)

        parsed: CsvParseResult = parse_torque_csv(canonical_csv, invert_power_sign=invert_power_sign)
        private = apply_privacy(parsed.points, privacy_options)
        accepted, duplicate_rows = deduplicate_points(private.points)

        segments = segment_points(accepted, options)
        persisted_point_count = sum(len(segment) for segment in segments)
        short_segment_points = len(accepted) - persisted_point_count

        import_id = str(uuid.uuid4())
        trips: list[TripSummary] = []
        points_by_trip: dict[str, list[tuple[str, Any]]] = {}
        for points in segments:
            trip_id = str(uuid.uuid4())
            trips.append(summarize_trip(points, import_id=import_id, trip_id=trip_id, options=options))
            points_by_trip[trip_id] = [(point_fingerprint(point), point) for point in points]

        warnings = list(parsed.warnings)
        if duplicate_rows:
            warnings.append(f"Skipped {duplicate_rows} duplicate telemetry row(s).")
        if private.masked_point_count:
            warnings.append(
                f"Masked coordinates for {private.masked_point_count} point(s) inside configured privacy zones."
            )
        if private.timestamps_shifted:
            warnings.append(
                "Shifted every timestamp by a private per-import offset while preserving sampling intervals."
            )
        if short_segment_points:
            warnings.append(
                f"Excluded {short_segment_points} point(s) in segments shorter than the configured minimum."
            )

        record = ImportRecord(
            id=import_id,
            source_name=source_name,
            idempotency_key=idempotency_key,
            created_at=datetime.now(tz=UTC),
            parsed_rows=parsed.parsed_rows,
            accepted_rows=persisted_point_count,
            dropped_rows=parsed.dropped_rows + short_segment_points,
            duplicate_rows=duplicate_rows,
            privacy_masked_points=private.masked_point_count,
            trip_ids=[trip.id for trip in trips],
            warnings=warnings,
            field_map=parsed.field_map,
        )
        self.repository.save_import(
            record,
            trips,
            points_by_trip,
            content_digest=content_digest,
            request_digest=request_digest,
        )
        return record, trips
