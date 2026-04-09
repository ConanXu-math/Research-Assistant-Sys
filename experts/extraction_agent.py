"""Pipeline extraction agent factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agno.agent import Agent

from foundation.models import PipelineExtractionResult

if TYPE_CHECKING:
    from agno.models.base import Model


def create_extraction_agent(model: "Model") -> Agent:
    return Agent(
        name="Pipeline Extraction Agent",
        model=model,
        output_schema=PipelineExtractionResult,
        instructions=[
            "Extract primary optimization formulation from paper markdown.",
            "Return strict JSON only: outline, score, is_acceptable, issues, fix_prompt.",
            "Objective/constraints/variables must match source equations.",
        ],
    )
