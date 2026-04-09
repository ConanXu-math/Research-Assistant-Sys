"""Expert plugin base contracts."""

from __future__ import annotations

from typing import Protocol

from foundation.models import ExecutionContext


class ExpertPlugin(Protocol):
    name: str
    intents: tuple[str, ...]
    input_schema: dict
    output_schema: dict

    def execute(self, payload: dict, context: ExecutionContext) -> dict:
        """Run expert task and return structured dictionary."""
