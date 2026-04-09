"""Unified orchestration service used by CLI and REPL."""

from __future__ import annotations

from orchestrator.assembler import ResultAssembler
from orchestrator.contracts import ExecutionEnvelope, TaskRequest
from orchestrator.executor import PlanExecutor
from orchestrator.router import TaskRouter
from experts.registry import ExpertRegistry
from foundation.models import ExecutionContext


class AssistantOrchestrator:
    def __init__(self, registry: ExpertRegistry) -> None:
        self.registry = registry
        self.router = TaskRouter(registry)
        self.executor = PlanExecutor(registry)
        self.assembler = ResultAssembler()

    def handle(self, *, intent: str, payload: dict, context: ExecutionContext) -> dict:
        request = TaskRequest(intent=intent, payload=payload)
        plan = self.router.build_plan(request)
        envelope = ExecutionEnvelope(request=request, context=context, plan=plan)
        output = self.executor.run(envelope)
        routed = self.assembler.assemble(envelope, output)
        return routed.result.model_dump(mode="json")
