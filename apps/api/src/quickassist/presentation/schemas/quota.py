"""Presentation Layer — DTO request/response (quota)."""

from quickassist.presentation.schemas.common import ApiModel


class QuotaOut(ApiModel):
    limit_tokens: int
    used_tokens: int
    reserved_tokens: int
    remaining_tokens: int
