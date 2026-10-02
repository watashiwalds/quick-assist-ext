"""Điểm DUY NHẤT nối các module lại với nhau (composition root).

Thêm module mới = thêm 1 dòng router (+ models, + handlers nếu có). Không module
nào tự đăng ký vào app — tránh import vòng và "phép màu" khó lần.
"""

from fastapi import APIRouter


def all_routers() -> list[APIRouter]:
    from quickassist.health import router as health
    from quickassist.modules.accounts.router import router as accounts
    from quickassist.modules.ai.router import router as ai
    from quickassist.modules.auth.router import router as auth
    from quickassist.modules.notes.router import router as notes
    from quickassist.modules.quota.router import router as quota
    from quickassist.modules.search.router import router as search

    return [health, auth, accounts, quota, notes, search, ai]


def load_models() -> None:
    """Import mọi ORM model để Base.metadata đầy đủ (Alembic autogenerate, test)."""
    import quickassist.core.idempotency  # noqa: F401
    import quickassist.core.jobs  # noqa: F401
    import quickassist.modules.accounts.models  # noqa: F401
    import quickassist.modules.auth.models  # noqa: F401
    import quickassist.modules.notes.models  # noqa: F401
    import quickassist.modules.quota.models  # noqa: F401
    import quickassist.modules.search.models  # noqa: F401


def load_job_handlers() -> None:
    """Import module chứa @job_handler để worker biết cách xử lý."""
    import quickassist.modules.search.handlers  # noqa: F401
