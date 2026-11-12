"""Presentation Layer — DTO cho POST /ai/page-match (AutoChunk: ghi chú theo truy vấn)."""

from typing import Literal

from pydantic import Field

from quickassist.presentation.schemas.common import ApiModel


class PageMatchIn(ApiModel):
    query: str = Field(min_length=1, max_length=500, description="Ý định người dùng, ngôn ngữ tự nhiên")
    html: str = Field(min_length=1, description="HTML trang đã bỏ script/style/noscript/template/svg; "
                                                "≤ PAGE_MATCH_MAX_HTML_BYTES (mặc định 2MB)")
    url: str | None = Field(default=None, max_length=2048, description="Chỉ để log/metadata")
    title: str | None = Field(default=None, max_length=500, description="Chỉ để log/metadata")


class PageMatchItemOut(ApiModel):
    id: str = Field(description="Id khối trong lần quét này (b00, b01…)")
    occ: int = Field(description="Lần xuất hiện thứ n (từ 0) của đúng text này trên trang — để highlight")
    text: str
    score: float = Field(description="Cosine giữa truy vấn và đoạn")
    verified: bool = Field(description="True = LLM đã xác nhận; False = chỉ theo điểm (VERIFY_UNAVAILABLE)")


class PageMatchOut(ApiModel):
    mode: Literal["segments", "full_page"]
    match_ratio: float = Field(description="∑ ký tự đoạn khớp / ∑ ký tự nội dung trích được")
    warning: Literal["VERIFY_UNAVAILABLE"] | None = None
    items: list[PageMatchItemOut] = Field(description="Đoạn khớp, sắp theo thứ tự trên trang")
    total_chars: int = Field(description="Tổng ký tự nội dung chính trích được")
    truncated: bool = Field(description="True = trang dài hơn giới hạn, phần cuối không được quét")
    full_text: str | None = Field(default=None, description="Nội dung cả trang — chỉ có khi mode=full_page")
