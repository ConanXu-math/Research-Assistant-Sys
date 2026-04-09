"""Core orchestration contracts for the assistant middle layer."""

from __future__ import annotations

from dataclasses import dataclass, field

from foundation.models import AssistantResult, ExecutionContext


@dataclass
class TaskRequest:
    intent: str
    payload: dict = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    intent: str
    expert_name: str
    payload: dict = field(default_factory=dict)


@dataclass
class ExecutionEnvelope:
    request: TaskRequest
    context: ExecutionContext
    plan: ExecutionPlan


@dataclass
class RoutedResult:
    result: AssistantResult
    raw_output: dict = field(default_factory=dict)
