"""Execution engine for expert plans."""

from __future__ import annotations

from orchestrator.contracts import ExecutionEnvelope
from experts.registry import ExpertRegistry


class PlanExecutor:
    def __init__(self, registry: ExpertRegistry) -> None:
        self.registry = registry

    def run(self, envelope: ExecutionEnvelope) -> dict:
        expert = self.registry.get_by_name(envelope.plan.expert_name)
        return expert.execute(envelope.plan.payload, envelope.context)
