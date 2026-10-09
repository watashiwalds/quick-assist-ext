"""semantic_search: full-text bỏ dấu tiếng Việt (unaccent) cho note_chunks.tsv — task R01

Người dùng hay gõ không dấu ("cong thuc nau pho") hoặc sai dấu; nhánh từ khoá của
hybrid search trước đây chỉ khớp đúng dấu. Chuẩn hoá cả chỉ mục lẫn truy vấn bằng
unaccent (đ → d, ơ → o …). Cần hàm IMMUTABLE để dùng trong cột sinh (generated column).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-08
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("""
        CREATE OR REPLACE FUNCTION qa_unaccent(text) RETURNS text
        LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
        AS $$ SELECT public.unaccent('public.unaccent'::regdictionary, $1) $$
    """)
    op.drop_index("ix_note_chunks_tsv", table_name="note_chunks")
    op.drop_column("note_chunks", "tsv")
    op.execute("""
        ALTER TABLE note_chunks ADD COLUMN tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', qa_unaccent(text))) STORED NOT NULL
    """)
    op.create_index("ix_note_chunks_tsv", "note_chunks", ["tsv"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_note_chunks_tsv", table_name="note_chunks")
    op.drop_column("note_chunks", "tsv")
    op.execute("""
        ALTER TABLE note_chunks ADD COLUMN tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED NOT NULL
    """)
    op.create_index("ix_note_chunks_tsv", "note_chunks", ["tsv"], postgresql_using="gin")
    op.execute("DROP FUNCTION IF EXISTS qa_unaccent(text)")
