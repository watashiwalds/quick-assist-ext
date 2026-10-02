"""Presentation Layer — DTO dùng chung (phân trang, lỗi). Giữ contract đồng nhất giữa các controller."""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ApiModel(BaseModel):
    """Base cho mọi schema request/response: đọc được từ ORM, cấm field lạ."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class Page(ApiModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None


class ErrorBody(ApiModel):
    code: str
    message: str
    details: dict = {}
    request_id: str | None = None


class ErrorResponse(ApiModel):
    error: ErrorBody
