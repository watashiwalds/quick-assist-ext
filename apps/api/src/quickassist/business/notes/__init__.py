"""Business Layer — Notes Service (SDS Hình 1 "NotesService", §5.2 "Notes Service").

Public API: chỉ import từ package này. Sở hữu bảng: folders, notes, idempotency_keys(notes.create).
"""

from quickassist.business.notes.contracts import (
    NoteBrief,
    NoteForIndexing,
    get_briefs,
    get_note_content,
    get_note_for_indexing,
    set_index_status,
)
from quickassist.business.notes.folder_service import FolderService
from quickassist.business.notes.notes_service import CreateNoteCommand, NotesService, UpdateNoteCommand

__all__ = [
    "CreateNoteCommand", "FolderService", "NoteBrief", "NoteForIndexing", "NotesService",
    "UpdateNoteCommand", "get_briefs", "get_note_content", "get_note_for_indexing", "set_index_status",
]
