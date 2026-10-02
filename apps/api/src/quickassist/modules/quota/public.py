"""Public API module quota — dùng bởi search, ai.

LƯU Ý: QuotaService tự commit. Luôn tạo nó trên một session RIÊNG:
    async with get_sessionmaker()() as qs:
        quota = QuotaService(qs)
"""

from quickassist.modules.quota.service import QuotaLease, QuotaService, QuotaStatus

__all__ = ["QuotaLease", "QuotaService", "QuotaStatus"]
