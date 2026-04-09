"""Extraction-focused pipeline models."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class NotationItem(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=120)
    dimension: str = Field(..., min_length=1, max_length=120)
    description: str = Field(..., min_length=1, max_length=500)


class MathOutline(BaseModel):
    objective: str = Field(..., max_length=4000)
    constraints: list[str] = Field(default_factory=list)
    variables: list[str] = Field(default_factory=list)
    notation_table: list[NotationItem] = Field(default_factory=list)

    @field_validator("constraints", "variables")
    @classmethod
    def _dedupe_text_list(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for v in value:
            t = str(v).strip()
            if t and t not in cleaned:
                cleaned.append(t)
        return cleaned


class CodingOutput(BaseModel):
    pseudocode: str = Field(default="")
    pycode: str = Field(default="")


class FormalizationOutput(BaseModel):
    prove_cot: str = Field(default="")
    lean4_formal: str = Field(default="")


class ExtractionItem(BaseModel):
    paper_name: str = Field(..., min_length=1, max_length=500)
    arxiv_id: str = Field(default="", max_length=64)
    outline: MathOutline


class SectionSelection(BaseModel):
    selected_markdown: str
    rationale: str = Field(default="")

    @field_validator("selected_markdown")
    @classmethod
    def _selected_not_empty(cls, value: str) -> str:
        v = value.strip()
        if not v:
            raise ValueError("selected_markdown cannot be empty")
        return v


class PipelineExtractionResult(BaseModel):
    outline: MathOutline
    score: int = Field(..., ge=0, le=100)
    is_acceptable: bool
    issues: list[str] = Field(default_factory=list)
    fix_prompt: str = Field(default="")

    @field_validator("issues")
    @classmethod
    def _trim_issues(cls, value: list[str]) -> list[str]:
        return [v.strip() for v in value if isinstance(v, str) and v.strip()]


class ExtractionCritique(BaseModel):
    score: int = Field(..., ge=0, le=100)
    is_acceptable: bool
    issues: list[str] = Field(default_factory=list)
    fix_prompt: str = Field(default="")
