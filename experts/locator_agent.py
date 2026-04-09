"""Locator agent factory for long-paper clipping."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agno.agent import Agent

from foundation.models import SectionSelection

if TYPE_CHECKING:
    from agno.models.base import Model


def create_locator_agent(model: "Model") -> Agent:
    return Agent(
        name="Locator Agent",
        model=model,
        output_schema=SectionSelection,
        instructions=[
            "Select high-value sections for optimization extraction.",
            "Prefer abstract/problem/formulation/equation-heavy method snippets.",
            "Return concise markdown excerpt in selected_markdown.",
        ],
    )
