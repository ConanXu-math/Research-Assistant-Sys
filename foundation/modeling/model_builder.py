"""Centralized model construction for runtime."""

from __future__ import annotations

from foundation.config.constants import OLLAMA_DEFAULT_BASE_URL
from foundation.config.settings import Settings


def build_model():
    settings = Settings.from_env()
    provider = settings.provider
    model_id = settings.model_id
    base_url = settings.base_url
    api_key = settings.api_key
    timeout_v = settings.api_timeout_s

    if provider == "ollama":
        from agno.models.openai.like import OpenAILike

        kwargs: dict = {"id": model_id, "base_url": base_url or OLLAMA_DEFAULT_BASE_URL}
        if timeout_v is not None:
            kwargs["timeout"] = timeout_v
        try:
            return OpenAILike(**kwargs)
        except TypeError:
            kwargs.pop("timeout", None)
            return OpenAILike(**kwargs)

    if provider in ("openai-like", "openailike"):
        from agno.models.openai.like import OpenAILike

        kwargs: dict = {"id": model_id}
        if base_url:
            kwargs["base_url"] = base_url
        if api_key:
            kwargs["api_key"] = api_key
        if timeout_v is not None:
            kwargs["timeout"] = timeout_v
        try:
            return OpenAILike(**kwargs)
        except TypeError:
            kwargs.pop("timeout", None)
            return OpenAILike(**kwargs)

    if provider == "openai":
        from agno.models.openai import OpenAIChat

        kwargs: dict = {"id": model_id}
        if timeout_v is not None:
            kwargs["timeout"] = timeout_v
        try:
            return OpenAIChat(**kwargs)
        except TypeError:
            kwargs.pop("timeout", None)
            return OpenAIChat(**kwargs)

    if provider == "anthropic":
        from agno.models.anthropic import Claude

        return Claude(id=model_id)

    if provider == "google":
        from agno.models.google import Gemini

        return Gemini(id=model_id)

    raise ValueError(f"Unknown OPTIBENCH_PROVIDER={provider!r}.")
