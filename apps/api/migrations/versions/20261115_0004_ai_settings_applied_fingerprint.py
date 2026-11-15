"""user_ai_settings.applied_fingerprint — "cấu hình đã được bàn giao cho rebuild" (P5 §7)

Save hiện hành: commit #1 (config mới) rồi commit #2 (mark PROCESSING + enqueue). Crash giữa
2 commit → config mới, chunk cũ, và re-save cùng config không bao giờ sửa (fingerprint bằng
nhau). `applied_fingerprint` = fingerprint đã được enqueue để rebuild; lệch
`embedding_fingerprint` → worker repair enqueue lại (business/semantic_search/rebuild.py).

Kèm theo: 0003 tạo `embedding_fingerprint` CHAR(64) nhưng model dùng String(64) —
`alembic check` ở head đỏ. 0004 đổi cột cũ sang VARCHAR(64) để khớp model.

Backfill chỉ cho mode='byok' (giả định chunk hiện tại đúng cấu hình đang lưu); inherit để
NULL — không thể biết fingerprint server trong SQL, tránh rebuild toàn bộ user cũ khi deploy.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-15
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE user_ai_settings
        ALTER COLUMN embedding_fingerprint TYPE VARCHAR(64),
        ADD COLUMN applied_fingerprint VARCHAR(64)
    """)
    op.execute("""
        UPDATE user_ai_settings
        SET applied_fingerprint = embedding_fingerprint
        WHERE mode = 'byok' AND embedding_fingerprint IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE user_ai_settings
        DROP COLUMN IF EXISTS applied_fingerprint,
        ALTER COLUMN embedding_fingerprint TYPE CHAR(64)
    """)
