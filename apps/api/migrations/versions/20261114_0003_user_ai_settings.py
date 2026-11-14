"""user_ai_settings — cấu hình AI per-user (BYOK) — ADR-0016

Chỉ THÊM bảng, không sửa bảng cũ → deploy an toàn; rollback = drop table.
Không có row → mode='inherit' → hành vi y hệt trước đó.
api_key_enc = nonce(12) || ciphertext || tag(16), AES-GCM, AAD = user_id.bytes.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-14
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE user_ai_settings (
            user_id                UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            mode                   VARCHAR(10) NOT NULL DEFAULT 'inherit',
            provider               VARCHAR(20),
            base_url               TEXT,
            api_key_enc            BYTEA,
            api_key_hint           VARCHAR(8),
            chat_model             VARCHAR(100),
            embedding_model        VARCHAR(100),
            embedding_fingerprint  CHAR(64),
            timeout_seconds        NUMERIC(6,2),
            created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_user_ai_settings_mode CHECK (mode IN ('inherit','byok')),
            CONSTRAINT ck_user_ai_settings_byok CHECK (
                mode = 'inherit' OR (
                    provider IS NOT NULL AND base_url IS NOT NULL AND
                    chat_model IS NOT NULL AND embedding_model IS NOT NULL AND
                    embedding_fingerprint IS NOT NULL
                )
            )
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_ai_settings")
