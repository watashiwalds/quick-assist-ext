"""Lỗi kỹ thuật của Infrastructure Layer.

Tầng hạ tầng KHÔNG biết mã lỗi nghiệp vụ hay HTTP. Nó ném các lỗi dưới đây;
Business Layer bắt và dịch sang lỗi nghiệp vụ (business/common/exceptions.py).
"""


class InfrastructureError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code


class TokenError(InfrastructureError):
    """JWT app session không hợp lệ / hết hạn. code: TOKEN_EXPIRED | TOKEN_INVALID."""


class OAuthError(InfrastructureError):
    """Google OAuth thất bại. code: OAUTH_* ; upstream=True nếu do không kết nối được Google."""

    def __init__(self, code: str, message: str = "", *, upstream: bool = False) -> None:
        super().__init__(code, message)
        self.upstream = upstream
