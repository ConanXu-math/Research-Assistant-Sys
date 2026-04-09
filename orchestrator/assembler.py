"""Result assembly for orchestration outputs."""

from __future__ import annotations

from orchestrator.contracts import ExecutionEnvelope, RoutedResult
from foundation.models import AssistantResult


class ResultAssembler:
    def assemble(self, envelope: ExecutionEnvelope, output: dict) -> RoutedResult:
        status = str(output.get("status", "ok"))
        notes = output.get("notes", [])
        if not isinstance(notes, list):
            notes = [str(notes)]
        result = AssistantResult(
            intent=envelope.request.intent,
            status=status,
            output=output,
            notes=[str(n) for n in notes],
        )
        return RoutedResult(result=result, raw_output=output)
