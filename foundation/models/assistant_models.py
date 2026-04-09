"""Domain models for assistant orchestration."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExecutionContext(BaseModel):
    dataset_root: str = Field(default="./dataset")
    user_query: str = Field(default="")
    focus_arxiv_id: str = Field(default="")
    domain: str = Field(default="continuous")
    skip_lean: bool = Field(default=False)
    max_retries: int = Field(default=3, ge=1)


class Citation(BaseModel):
    source: str = Field(default="")
    snippet: str = Field(default="")
    location: str = Field(default="")


class PaperProfile(BaseModel):
    arxiv_id: str = Field(default="")
    title: str = Field(default="")
    abstract: str = Field(default="")
    markdown_path: str = Field(default="")


class StructuredExtraction(BaseModel):
    objective: str = Field(default="")
    variables: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    key_contributions: list[str] = Field(default_factory=list)


class AnswerWithCitations(BaseModel):
    answer: str = Field(default="")
    citations: list[Citation] = Field(default_factory=list)


class ComparisonReport(BaseModel):
    summary: str = Field(default="")
    dimensions: dict[str, str] = Field(default_factory=dict)
    paper_ids: list[str] = Field(default_factory=list)


class ReproPlan(BaseModel):
    summary: str = Field(default="")
    prerequisites: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class AssistantResult(BaseModel):
    intent: str
    status: str = "ok"
    output: dict = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
