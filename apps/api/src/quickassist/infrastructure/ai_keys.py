"""Mã hoá khoá API của user (BYOK) — AES-GCM với AAD = user_id (ADR-0016).

Format blob: ``nonce(12) || ciphertext || tag(16)``. AAD gắn chặt ciphertext với row
của user → không thể hoán đổi ciphertext giữa 2 row. Khoá gốc derive bằng HKDF-SHA256
từ ``AI_KEY_SECRET`` (nếu đặt) hoặc fallback ``JWT_SECRET`` — KHÔNG log plaintext/ciphertext.
"""

import os
import uuid

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from quickassist.infrastructure.config import get_settings

_NONCE_BYTES = 12


def _key() -> bytes:
    base = (
        get_settings().ai_key_secret.get_secret_value()
        or get_settings().jwt_secret.get_secret_value()
    )
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=b"quickassist", info=b"ai-keys-v1"
    ).derive(base.encode())


def encrypt(user_id: uuid.UUID, plaintext: str) -> bytes:
    nonce = os.urandom(_NONCE_BYTES)
    return nonce + AESGCM(_key()).encrypt(nonce, plaintext.encode(), user_id.bytes)


def decrypt(user_id: uuid.UUID, blob: bytes) -> str:
    aes = AESGCM(_key())
    return aes.decrypt(bytes(blob[:_NONCE_BYTES]), bytes(blob[_NONCE_BYTES:]), user_id.bytes).decode()
