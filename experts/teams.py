"""Expert-layer component assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from experts.extraction_agent import create_extraction_agent
from experts.research_agent import create_research_agent

if TYPE_CHECKING:
    from agno.agent import Agent
    from agno.models.base import Model


@dataclass
class ExpertComponents:
    research_agent: Agent
    extraction_agent: Agent


def build_expert_components(model: "Model") -> ExpertComponents:
    return ExpertComponents(
        research_agent=create_research_agent(model),
        extraction_agent=create_extraction_agent(model),
    )
