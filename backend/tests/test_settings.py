from __future__ import annotations

import pytest

from rangelab.settings import PROCESS_LOCAL_IDENTITY_SECRET, Settings


def test_identity_secret_has_safe_process_local_default_and_is_hidden_from_repr() -> None:
    first = Settings()
    second = Settings()
    assert first.identity_secret == second.identity_secret == PROCESS_LOCAL_IDENTITY_SECRET
    assert len(first.identity_secret.encode("utf-8")) >= 32
    assert first.identity_secret not in repr(first)


def test_identity_secret_rejects_short_configuration() -> None:
    with pytest.raises(ValueError, match="at least 32 bytes"):
        Settings(identity_secret="too-short")


def test_identity_secret_can_be_persisted_through_environment(monkeypatch) -> None:
    stable_secret = "stable-local-secret-value-that-is-long-enough"
    monkeypatch.setenv("RANGELAB_IDENTITY_SECRET", stable_secret)
    assert Settings.from_env().identity_secret == stable_secret
