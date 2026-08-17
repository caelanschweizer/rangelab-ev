from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field


PROCESS_LOCAL_IDENTITY_SECRET = secrets.token_urlsafe(48)


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str = "sqlite:///./rangelab.db"
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)
    max_upload_bytes: int = 10_000_000
    trip_gap_minutes: int = 15
    identity_secret: str = field(default=PROCESS_LOCAL_IDENTITY_SECRET, repr=False)

    def __post_init__(self) -> None:
        if len(self.identity_secret.encode("utf-8")) < 32:
            raise ValueError("RANGELAB_IDENTITY_SECRET must contain at least 32 bytes.")

    @classmethod
    def from_env(cls) -> "Settings":
        origins = tuple(
            value.strip()
            for value in os.getenv("RANGELAB_CORS_ORIGINS", "http://localhost:3000").split(",")
            if value.strip()
        )
        return cls(
            database_url=os.getenv("RANGELAB_DATABASE_URL", "sqlite:///./rangelab.db"),
            cors_origins=origins,
            max_upload_bytes=int(os.getenv("RANGELAB_MAX_UPLOAD_BYTES", "10000000")),
            trip_gap_minutes=int(os.getenv("RANGELAB_TRIP_GAP_MINUTES", "15")),
            identity_secret=os.getenv(
                "RANGELAB_IDENTITY_SECRET", PROCESS_LOCAL_IDENTITY_SECRET
            ),
        )
