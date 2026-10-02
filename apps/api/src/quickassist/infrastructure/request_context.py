"""Infrastructure Layer — request id xuyên suốt request → log → job (không phụ thuộc web framework)."""

from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return _request_id.get()


def set_request_id(value: str | None):  # type: ignore[no-untyped-def]
    """Trả token để reset (dùng trong middleware)."""
    return _request_id.set(value)


def reset_request_id(token) -> None:  # type: ignore[no-untyped-def]
    _request_id.reset(token)
