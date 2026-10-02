import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.modules.search.models import NoteChunk


@dataclass(frozen=True)
class ChunkHit:
    chunk_id: uuid.UUID
    note_id: uuid.UUID
    text: str
    score: float


# Hybrid retrieval: vector (cosine, HNSW) + từ khoá (tsvector) → hợp nhất bằng
# Reciprocal Rank Fusion (k=60). RRF không cần chuẩn hoá thang điểm giữa 2 nguồn.
# Điều kiện user_id nằm TRONG từng nhánh → không bao giờ rò dữ liệu chéo user.
_HYBRID_SQL = text("""
WITH vec AS (
    SELECT id, row_number() OVER (ORDER BY embedding <=> CAST(:qvec AS vector)) AS r
    FROM note_chunks
    WHERE user_id = :uid AND (CAST(:fid AS uuid) IS NULL OR folder_id = CAST(:fid AS uuid))
    ORDER BY embedding <=> CAST(:qvec AS vector)
    LIMIT :cand
),
kw AS (
    SELECT id, row_number() OVER (ORDER BY ts_rank_cd(tsv, q) DESC) AS r
    FROM note_chunks, plainto_tsquery('simple', :qtext) AS q
    WHERE user_id = :uid AND (CAST(:fid AS uuid) IS NULL OR folder_id = CAST(:fid AS uuid))
      AND tsv @@ q
    ORDER BY ts_rank_cd(tsv, q) DESC
    LIMIT :cand
),
fused AS (
    SELECT id, SUM(1.0 / (60 + r)) AS score
    FROM (SELECT * FROM vec UNION ALL SELECT * FROM kw) u
    GROUP BY id
)
SELECT c.id, c.note_id, c.text, f.score
FROM fused f JOIN note_chunks c ON c.id = f.id
ORDER BY f.score DESC
LIMIT :k
""")


class ChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def content_hash_of(self, note_id: uuid.UUID) -> str | None:
        stmt = select(NoteChunk.content_hash).where(NoteChunk.note_id == note_id).limit(1)
        return (await self.s.execute(stmt)).scalar_one_or_none()

    async def delete_for_note(self, note_id: uuid.UUID) -> None:
        await self.s.execute(delete(NoteChunk).where(NoteChunk.note_id == note_id))

    async def set_folder(self, note_id: uuid.UUID, folder_id: uuid.UUID) -> None:
        await self.s.execute(
            update(NoteChunk).where(NoteChunk.note_id == note_id).values(folder_id=folder_id)
        )

    async def replace_for_note(self, rows: list[NoteChunk], note_id: uuid.UUID) -> None:
        """Xoá chunk cũ + thêm chunk mới trong CÙNG transaction → không có khoảng trống index."""
        await self.delete_for_note(note_id)
        self.s.add_all(rows)
        await self.s.flush()

    async def hybrid_search(
        self, user_id: uuid.UUID, query_text: str, query_vec: list[float], *,
        folder_id: uuid.UUID | None, k: int, candidate_k: int,
    ) -> list[ChunkHit]:
        res = await self.s.execute(_HYBRID_SQL, {
            "uid": user_id, "fid": folder_id, "qtext": query_text, "k": k, "cand": candidate_k,
            "qvec": "[" + ",".join(f"{x:.7f}" for x in query_vec) + "]",
        })
        return [ChunkHit(r.id, r.note_id, r.text, float(r.score)) for r in res]
