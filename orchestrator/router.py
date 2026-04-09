"""Task routing from intent to expert execution plan."""

from __future__ import annotations

from orchestrator.contracts import ExecutionPlan, TaskRequest
from experts.registry import ExpertRegistry


class TaskRouter:
    def __init__(self, registry: ExpertRegistry) -> None:
        self.registry = registry

    def build_plan(self, request: TaskRequest) -> ExecutionPlan:
        expert = self.registry.resolve_intent(request.intent)
        return ExecutionPlan(
            intent=request.intent,
            expert_name=expert.name,
            payload=request.payload,
        )
