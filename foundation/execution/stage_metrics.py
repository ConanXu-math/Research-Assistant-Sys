"""Pipeline stage metrics models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class StageMetric(BaseModel):
    stage: str = Field(..., description="search | extract")
    attempts: int = 0
    success: bool = False
    outcome: str = Field(default="", description="ok | partial | failed | skipped")
    failure_type: str = Field(default="")
    last_error: str = Field(default="")
    detail: dict[str, Any] = Field(default_factory=dict)


class PipelineMetrics(BaseModel):
    schema_version: str = "1"
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str = ""
    extraction_strategy: str = Field(default="unified")
    stages: list[StageMetric] = Field(default_factory=list)
