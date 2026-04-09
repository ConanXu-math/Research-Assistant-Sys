"""Factory for building and registering assistant experts."""

from __future__ import annotations

from typing import Any

from experts.builtin import (
    ExtractionStructureExpert,
    ResearchSearchDownloadExpert,
)
from experts.registry import ExpertRegistry


def build_registry(*, model: Any, workflow: Any | None = None) -> ExpertRegistry:
    registry = ExpertRegistry()
    registry.register(ResearchSearchDownloadExpert())
    registry.register(ExtractionStructureExpert(model))
    return registry
