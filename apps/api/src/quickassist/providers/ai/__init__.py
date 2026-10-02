"""Factory chọn AI provider theo cấu hình. Module nghiệp vụ dùng `AIProviderDep`."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from quickassist.core.config import get_settings
from quickassist.providers.ai.base import AIProvider


@lru_cache
def get_ai_provider() -> AIProvider:
    s = get_settings()
    if s.ai_provider == "openai":
        from quickassist.providers.ai.openai import OpenAIProvider

        return OpenAIProvider(s)
    from quickassist.providers.ai.mock import MockAIProvider

    return MockAIProvider(s.embedding_dim)


AIProviderDep = Annotated[AIProvider, Depends(get_ai_provider)]
