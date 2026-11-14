"""Test tối thiểu P0 — mã hoá key BYOK (ADR-0016) và config mới."""

import uuid

import pytest

from quickassist.infrastructure import ai_keys
from quickassist.infrastructure.config import get_settings


def test_encrypt_decrypt_roundtrip() -> None:
    uid = uuid.uuid4()
    blob = ai_keys.encrypt(uid, "sk-abc123")
    assert blob != b"sk-abc123"  # không lưu plaintext
    assert b"sk-abc123" not in blob
    assert ai_keys.decrypt(uid, blob) == "sk-abc123"


def test_nonce_unique_same_plaintext() -> None:
    """Cùng plaintext → 2 blob khác nhau (nonce ngẫu nhiên) nhưng đều giải mã đúng."""
    uid = uuid.uuid4()
    b1, b2 = ai_keys.encrypt(uid, "same"), ai_keys.encrypt(uid, "same")
    assert b1 != b2
    assert ai_keys.decrypt(uid, b1) == ai_keys.decrypt(uid, b2) == "same"


def test_aad_binding_other_user_cannot_decrypt() -> None:
    """AAD = user_id → ciphertext của user này không giải mã được bằng user khác."""
    from cryptography.exceptions import InvalidTag

    uid_a, uid_b = uuid.uuid4(), uuid.uuid4()
    blob = ai_keys.encrypt(uid_a, "sk-secret")
    with pytest.raises(InvalidTag):
        ai_keys.decrypt(uid_b, blob)


def test_key_derivation_stable() -> None:
    assert ai_keys._key() == ai_keys._key()
    assert len(ai_keys._key()) == 32


def test_fallback_derives_from_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Không đặt AI_KEY_SECRET → derive từ JWT_SECRET; đổi JWT → khoá khác."""
    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET", "jwt-one")
    monkeypatch.delenv("AI_KEY_SECRET", raising=False)
    get_settings.cache_clear()
    k1 = ai_keys._key()

    monkeypatch.setenv("JWT_SECRET", "jwt-two")
    get_settings.cache_clear()
    k2 = ai_keys._key()
    assert k1 != k2

    monkeypatch.setenv("JWT_SECRET", "jwt-one")
    get_settings.cache_clear()
    assert ai_keys._key() == k1
    get_settings.cache_clear()


def test_new_config_fields_have_safe_defaults() -> None:
    get_settings.cache_clear()
    s = get_settings()
    assert s.auth_mode == "google"
    assert s.ai_key_secret.get_secret_value() == ""
    assert s.ai_base_url_allowlist == []
    assert s.ai_embedding_strict_dim is True
    assert s.ai_request_embedding_dimensions is True
    assert s.rate_limit_ai_settings_test_per_minute == 6
    get_settings.cache_clear()


def test_dev_login_allowed_in_local_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """AUTH_MODE=local cho phép dev-login kể cả khi APP_ENV=prod (ADR-0016 §4.8)."""
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("ENABLE_DEV_LOGIN", "false")
    monkeypatch.setenv("AUTH_MODE", "google")
    get_settings.cache_clear()
    assert get_settings().is_dev_login_allowed is False

    monkeypatch.setenv("AUTH_MODE", "local")
    get_settings.cache_clear()
    assert get_settings().is_dev_login_allowed is True
    get_settings.cache_clear()
