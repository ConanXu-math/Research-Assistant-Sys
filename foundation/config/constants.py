"""Shared constants used across configuration and CLI defaults."""

from __future__ import annotations

DEFAULT_PROVIDER = "openai"
DEFAULT_MODEL_ID = "gpt-4o"
DEFAULT_DOMAIN = "continuous"

DEFAULT_DATASET_ROOT = "./dataset"
DEFAULT_MAX_RETRIES = 3
DEFAULT_TOP_K = 5
DEFAULT_MAX_WORKERS = 1

DEFAULT_EXTRACT_MAX_CHARS = 24000
DEFAULT_LOCATOR_MIN_CHARS = 12000
DEFAULT_LOCATOR_MIN_MATH_MARKERS = 40

OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434/v1"

SUPPORTED_PROVIDERS = {"openai", "openai-like", "openailike", "ollama", "anthropic", "google"}
SUPPORTED_DOMAINS = {"continuous", "all"}
