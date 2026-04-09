"""Bootstrap helpers for assistant orchestration service."""

from __future__ import annotations

from typing import Any

from experts.factory import build_registry
from foundation.models import ExecutionContext
from orchestrator.service import AssistantOrchestrator


def build_assistant_orchestrator(*, model: Any, workflow: Any | None = None) -> AssistantOrchestrator:
    registry = build_registry(model=model, workflow=workflow)
    return AssistantOrchestrator(registry)


def build_execution_context(
    *,
    dataset_root: str,
    user_query: str = "",
    focus_arxiv_id: str = "",
    domain: str = "continuous",
    skip_lean: bool = False,
    max_retries: int = 3,
) -> ExecutionContext:
    return ExecutionContext(
        dataset_root=dataset_root,
        user_query=user_query,
        focus_arxiv_id=focus_arxiv_id,
        domain=domain,
        skip_lean=skip_lean,
        max_retries=max_retries,
    )
