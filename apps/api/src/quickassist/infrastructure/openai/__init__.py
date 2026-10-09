"""Infrastructure Layer — "OpenAI API" (SDS Hình 1) sau một port chung (ADR-0004).

Business Layer chỉ dùng `AIProvider` (base.py) và `get_ai_provider()`; không import SDK.
AI_PROVIDER=mock → MockAIClient (test/CI/demo offline); =openai → OpenAIClient;
=gemini → GeminiClient (Gemma 4 + gemini-embedding-001).
"""

from functools import lru_cache

from quickassist.infrastructure.config import get_settings
from quickassist.infrastructure.openai.base import AIProvider


@lru_cache
def get_ai_provider() -> AIProvider:
    s = get_settings()
    if s.ai_provider == "openai":
        from quickassist.infrastructure.openai.openai_client import OpenAIClient

        return OpenAIClient(s)
    if s.ai_provider == "gemini":
        from quickassist.infrastructure.openai.gemini_client import GeminiClient

        return GeminiClient(s)
    from quickassist.infrastructure.openai.mock_client import MockAIClient

    return MockAIClient(s.embedding_dim)
