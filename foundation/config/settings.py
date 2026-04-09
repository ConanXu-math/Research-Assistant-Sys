"""Centralized runtime settings."""

from __future__ import annotations

import os
from dataclasses import dataclass

from foundation.config.constants import (
    DEFAULT_DOMAIN,
    DEFAULT_EXTRACT_MAX_CHARS,
    DEFAULT_LOCATOR_MIN_CHARS,
    DEFAULT_LOCATOR_MIN_MATH_MARKERS,
    DEFAULT_MAX_WORKERS,
    DEFAULT_MODEL_ID,
    DEFAULT_PROVIDER,
    SUPPORTED_DOMAINS,
    SUPPORTED_PROVIDERS,
)
from foundation.errors import ConfigError


def _read_float_env(name: str, default: float | None = None) -> float | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got: {raw!r}") from exc


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got: {raw!r}") from exc


@dataclass(frozen=True)
class Settings:
    provider: str
    model_id: str
    base_url: str
    api_key: str
    api_timeout_s: float | None
    domain: str
    extraction_strategy: str
    extract_max_chars: int
    locator_min_chars: int
    locator_min_math_markers: int
    log_json: bool
    max_workers: int

    @classmethod
    def from_env(cls) -> "Settings":
        provider = os.getenv("OPTIBENCH_PROVIDER", DEFAULT_PROVIDER).strip().lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise ConfigError(f"Unknown OPTIBENCH_PROVIDER={provider!r}.")
        domain = os.getenv("OPTIBENCH_DOMAIN", DEFAULT_DOMAIN).strip().lower()
        if domain not in SUPPORTED_DOMAINS:
            raise ConfigError("OPTIBENCH_DOMAIN must be one of: continuous, all")
        extraction_strategy = (
            os.getenv("OPTIBENCH_EXTRACTION_STRATEGY", "unified").strip().lower() or "unified"
        )
        if extraction_strategy not in {"unified", "locator_first", "auto"}:
            raise ConfigError("OPTIBENCH_EXTRACTION_STRATEGY must be unified|locator_first|auto")
        model_id = os.getenv("OPTIBENCH_MODEL", DEFAULT_MODEL_ID).strip()
        if not model_id:
            raise ConfigError("OPTIBENCH_MODEL cannot be empty")
        max_workers = _read_int_env("OPTIBENCH_WORKERS", DEFAULT_MAX_WORKERS)
        if max_workers < 1:
            raise ConfigError("OPTIBENCH_WORKERS must be >= 1")
        return cls(
            provider=provider,
            model_id=model_id,
            base_url=os.getenv("OPTIBENCH_BASE_URL", "").strip(),
            api_key=os.getenv("OPTIBENCH_API_KEY", "").strip(),
            api_timeout_s=_read_float_env("OPTIBENCH_API_TIMEOUT", None),
            domain=domain,
            extraction_strategy=extraction_strategy,
            extract_max_chars=_read_int_env("OPTIBENCH_EXTRACT_MAX_CHARS", DEFAULT_EXTRACT_MAX_CHARS),
            locator_min_chars=_read_int_env("OPTIBENCH_LOCATOR_MIN_CHARS", DEFAULT_LOCATOR_MIN_CHARS),
            locator_min_math_markers=_read_int_env(
                "OPTIBENCH_LOCATOR_MIN_MATH_MARKERS", DEFAULT_LOCATOR_MIN_MATH_MARKERS
            ),
            log_json=os.getenv("OPTIBENCH_LOG_JSON", "").strip().lower() in {"1", "true", "yes"},
            max_workers=max_workers,
        )

    def validate_runtime_requirements(self) -> None:
        if self.provider in {"openai-like", "openailike"} and not self.base_url:
            raise ConfigError("OPTIBENCH_BASE_URL is required for openai-like provider")
