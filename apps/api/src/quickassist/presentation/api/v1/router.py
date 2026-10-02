"""Presentation Layer — gom mọi controller của API v1 (prefix /api/v1)."""

from fastapi import APIRouter

from quickassist.presentation.api.v1.controllers import (
    account_controller,
    auth_controller,
    folders_controller,
    health_controller,
    notes_controller,
    quota_controller,
    rag_controller,
    search_controller,
    summary_controller,
)

api_v1 = APIRouter()
for c in (health_controller, auth_controller, account_controller, quota_controller, folders_controller,
          notes_controller, search_controller, summary_controller, rag_controller):
    api_v1.include_router(c.router)
