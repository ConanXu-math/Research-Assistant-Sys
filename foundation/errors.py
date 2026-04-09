"""Typed exception hierarchy used across the project."""

from __future__ import annotations


class OptiBenchError(Exception):
    """Base class for all domain exceptions."""


class ConfigError(OptiBenchError):
    """Invalid or missing configuration."""


class UpstreamAPIError(OptiBenchError):
    """External model/API/network call failed."""


class ParseError(OptiBenchError):
    """Structured parsing failed."""


class ValidationError(OptiBenchError):
    """Generated artifacts did not pass validation."""


class PersistenceError(OptiBenchError):
    """Writing artifacts to local storage failed."""
