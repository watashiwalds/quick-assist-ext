"""Business Layer — Page Match Service (AutoChunk: ghi chú theo truy vấn, ADR-0013). Không sở hữu bảng.

Duy nhất package này được import trafilatura (kiểm bằng tests/architecture/test_layers.py).
"""

from quickassist.business.page_match.extractor import shutdown_extractor
from quickassist.business.page_match.page_match_service import (
    VERIFY_UNAVAILABLE,
    MatchItem,
    PageMatchResult,
    PageMatchService,
)

__all__ = ["VERIFY_UNAVAILABLE", "MatchItem", "PageMatchResult", "PageMatchService", "shutdown_extractor"]
