"""Presentation Layer — DTO request/response (quota)."""

from typing import Literal

from quickassist.presentation.schemas.common import ApiModel


class QuotaOut(ApiModel):
    limit_tokens: int
    used_tokens: int
    reserved_tokens: int
    remaining_tokens: int
    # server = dùng hạn mức của server; byok = user tự trả qua key riêng (ADR-0016 D6)
    billing_mode: Literal["server", "byok"]
    # False = DEV_UNLIMITED: vẫn đếm token nhưng không chặn AI (UI không hiện banner hết hạn mức).
    limit_enforced: bool = True
