"""notes.document_id — tài liệu dài gồm nhiều part (D2, docs/ideas/tai-lieu-dai-nhieu-phan.md)

Một tài liệu logic = nhiều note vật lý ≤ MAX_NOTE_CHARS, cùng `document_id`; `part_index`
đánh từ 0. Note cũ không có `document_id` giữ nguyên hành vi (group theo domain).

Chỉ THÊM cột + ràng buộc, không sửa cột cũ → deploy an toàn; rollback = drop cột.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-19
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("notes", sa.Column("document_id", sa.UUID(), nullable=True))
    op.add_column(
        "notes",
        sa.Column("part_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "notes",
        sa.Column("part_count", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column("notes", sa.Column("original_chars", sa.Integer(), nullable=True))
    op.add_column(
        "notes",
        sa.Column(
            "source_type", sa.String(length=20), nullable=False, server_default=sa.text("'selection'")
        ),
    )
    op.create_check_constraint(
        "ck_notes_source_type", "notes", "source_type IN ('selection','document')"
    )
    op.create_check_constraint(
        "ck_notes_part_range",
        "notes",
        "part_index >= 0 AND part_count >= 1 AND part_index < part_count",
    )
    op.create_unique_constraint(
        "uq_notes_user_document_part", "notes", ["user_id", "document_id", "part_index"]
    )
    op.create_index("ix_notes_user_document", "notes", ["user_id", "document_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notes_user_document", table_name="notes")
    op.drop_constraint("uq_notes_user_document_part", "notes", type_="unique")
    op.drop_constraint("ck_notes_part_range", "notes", type_="check")
    op.drop_constraint("ck_notes_source_type", "notes", type_="check")
    op.drop_column("notes", "source_type")
    op.drop_column("notes", "original_chars")
    op.drop_column("notes", "part_count")
    op.drop_column("notes", "part_index")
    op.drop_column("notes", "document_id")
