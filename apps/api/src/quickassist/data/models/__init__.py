"""Data Layer — toàn bộ entity. Import package này = đăng ký đủ bảng vào Base.metadata
(Alembic autogenerate, test). Mỗi entity ghi rõ service nào ở Business Layer SỞ HỮU nó."""

from quickassist.data.models.auth_session import AuthSession
from quickassist.data.models.idempotency_key import IdempotencyKey
from quickassist.data.models.job import Job
from quickassist.data.models.note import INBOX_NAME, INDEX_STATUSES, Folder, Note
from quickassist.data.models.note_chunk import EMBEDDING_DIM, NoteChunk
from quickassist.data.models.quota import QuotaAccount, QuotaLedger
from quickassist.data.models.user import User

__all__ = [
    "EMBEDDING_DIM", "INBOX_NAME", "INDEX_STATUSES",
    "AuthSession", "Folder", "IdempotencyKey", "Job", "Note", "NoteChunk",
    "QuotaAccount", "QuotaLedger", "User",
]
