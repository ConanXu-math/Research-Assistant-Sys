"""Extraction-only workflow: arXiv paper -> structured math outline."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from experts.locator_agent import create_locator_agent
from experts.teams import build_expert_components
from foundation.config.settings import Settings
from foundation.errors import ParseError, PersistenceError, UpstreamAPIError
from foundation.models import ExtractionItem, MathOutline, SectionSelection
from foundation.parsing.parsers import (
    classify_failure,
    extraction_budgets,
    extract_arxiv_id,
    fallback_outline_from_markdown,
    is_agent_error_text,
    is_outline_meaningful,
    is_timeout_like_error,
    parse_pipeline_extraction_output,
    prepare_extraction_input,
    resolve_extraction_strategy,
)
from foundation.observability.logging import stage_context
from foundation.execution.stage_metrics import PipelineMetrics, StageMetric

if TYPE_CHECKING:
    from agno.agent import Agent
    from agno.models.base import Model

logger = logging.getLogger("optibench")


class OptiBenchWorkflow:
    """End-to-end extraction pipeline from paper markdown to MathOutline."""

    def __init__(
        self,
        model: Model,
        *,
        dataset_root: str | Path = "./dataset",
        max_retries: int = 3,
        require_outline: bool = True,
        enable_benchmark_artifacts: bool = False,
        skip_lean: bool = True,
    ) -> None:
        self.model = model
        self.dataset_root = Path(dataset_root)
        self.max_retries = max_retries
        self.require_outline = require_outline
        self.enable_benchmark_artifacts = enable_benchmark_artifacts
        self.skip_lean = skip_lean
        c = build_expert_components(model)
        self.research_agent: Agent = c.research_agent
        self.extraction_agent: Agent = c.extraction_agent
        self._pipeline_metrics: PipelineMetrics | None = None
        self._settings = Settings.from_env()
        self._extraction_strategy = self._settings.extraction_strategy
        self.locator_agent: Agent | None = None
        if self._extraction_strategy == "locator_first":
            self.locator_agent = create_locator_agent(model)

    def _reset_pipeline_metrics(self) -> None:
        self._pipeline_metrics = PipelineMetrics(extraction_strategy=self._extraction_strategy)

    def get_pipeline_metrics(self) -> PipelineMetrics | None:
        return self._pipeline_metrics

    def _push_stage(
        self,
        *,
        stage: str,
        attempts: int,
        success: bool,
        outcome: str = "",
        failure_type: str = "",
        last_error: str = "",
        detail: dict | None = None,
    ) -> None:
        if self._pipeline_metrics is None:
            return
        self._pipeline_metrics.stages.append(
            StageMetric(
                stage=stage,
                attempts=attempts,
                success=success,
                outcome=outcome,
                failure_type=failure_type,
                last_error=(last_error or "")[:800],
                detail=detail or {},
            )
        )

    def run(self, query: str) -> ExtractionItem:
        self._reset_pipeline_metrics()
        logger.info("=== Step 1: Search & Parse ===")
        paper_md, arxiv_id, paper_name = self._step_search(query)
        return self._run_from_paper_sync(paper_md=paper_md, arxiv_id=arxiv_id, paper_name=paper_name)

    def run_from_paper(self, *, paper_md: str, arxiv_id: str, paper_name: str) -> ExtractionItem:
        self._reset_pipeline_metrics()
        self._push_stage(stage="search", attempts=0, success=True, outcome="skipped", failure_type="skipped")
        return self._run_from_paper_sync(paper_md=paper_md, arxiv_id=arxiv_id, paper_name=paper_name)

    def _run_from_paper_sync(self, *, paper_md: str, arxiv_id: str, paper_name: str) -> ExtractionItem:
        logger.info("=== Step 2: Extract MathOutline ===")
        outline = self._step_extract(paper_md)
        if not is_outline_meaningful(outline) and self.require_outline:
            raise ParseError("Extraction produced empty outline.")
        item = ExtractionItem(paper_name=paper_name, arxiv_id=arxiv_id, outline=outline)
        self._save(item, paper_md=paper_md, arxiv_id=arxiv_id)
        return item

    def _step_search(self, query: str) -> tuple[str, str, str]:
        with stage_context("search"):
            response = self.research_agent.run(
                f"Search arXiv for optimization topic and return the full markdown paper:\n\n{query}"
            )
        paper_md: str = response.content or ""
        if is_agent_error_text(paper_md) or len(paper_md.strip()) < 200:
            fallback = self._step_search_fallback(query)
            if fallback is not None:
                paper_md, arxiv_id, paper_name = fallback
                self._push_stage(stage="search", attempts=1, success=True, outcome="ok", detail={"fallback": True})
                return paper_md, arxiv_id, paper_name
        arxiv_id = extract_arxiv_id(paper_md)
        paper_name = _extract_title(paper_md)
        self._push_stage(stage="search", attempts=1, success=True, outcome="ok", detail={"fallback": False})
        return paper_md, arxiv_id, paper_name

    def _step_search_fallback(self, query: str) -> tuple[str, str, str] | None:
        try:
            from foundation.adapters.paper_tools import download_paper, search_arxiv

            results = search_arxiv(query, max_results=5)
            if not results:
                return None
            best = results[0]
            arxiv_id = best.get("arxiv_id", "")
            if not arxiv_id:
                return None
            dl = download_paper(arxiv_id=arxiv_id, out_dir=self.dataset_root, convert_to_md=True, save_md_file=True)
            paper_md = dl.get("md_content") or ""
            paper_name = dl.get("title") or best.get("title") or "Untitled"
            if not paper_md.strip():
                return None
            return paper_md, arxiv_id, paper_name
        except Exception as exc:
            raise UpstreamAPIError(f"Fallback search pipeline failed: {exc}") from exc

    def _step_locate_sections(self, paper_md: str) -> str:
        if self.locator_agent is None or len(paper_md) < 5000:
            return paper_md
        prompt = "Select high-value sections for optimization formulation extraction.\n\n" + paper_md
        try:
            response = self.locator_agent.run(prompt)
            raw = response.content
        except Exception:
            return prepare_extraction_input(paper_md, char_budget=12000)
        if isinstance(raw, SectionSelection) and raw.selected_markdown.strip():
            return raw.selected_markdown
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = SectionSelection.model_validate_json(raw)
                if parsed.selected_markdown.strip():
                    return parsed.selected_markdown
            except Exception:
                pass
        return prepare_extraction_input(paper_md, char_budget=12000)

    def _step_extract(self, paper_md: str) -> MathOutline:
        max_attempts = max(3, self.max_retries)
        strategy = resolve_extraction_strategy(self._extraction_strategy, paper_md)
        paper_work = self._step_locate_sections(paper_md) if strategy == "locator_first" else paper_md
        prompt_prefix = (
            "Extract the primary optimisation formulation from paper markdown. "
            "Return PipelineExtractionResult JSON.\n\n"
        )
        last_error = ""
        parse_failure = ""
        last_outline = MathOutline(objective="", constraints=[], variables=[], notation_table=[])
        budgets = extraction_budgets(max_attempts)
        for attempt in range(1, max_attempts + 1):
            budget = budgets[min(attempt - 1, len(budgets) - 1)]
            extraction_md = prepare_extraction_input(paper_work, char_budget=budget)
            with stage_context("extract"):
                response = self.extraction_agent.run(f"{prompt_prefix}{extraction_md}")
            parsed, error, parse_failure = parse_pipeline_extraction_output(response.content)
            if parsed is None:
                last_error = error or "unknown extraction error"
                continue
            outline = parsed.outline
            last_outline = outline
            if is_outline_meaningful(outline) and parsed.is_acceptable:
                self._push_stage(
                    stage="extract",
                    attempts=attempt,
                    success=True,
                    outcome="ok",
                    detail={"strategy": strategy, "score": parsed.score},
                )
                return outline
        if is_outline_meaningful(last_outline):
            self._push_stage(stage="extract", attempts=max_attempts, success=True, outcome="partial")
            return last_outline
        if is_timeout_like_error(last_error):
            self._push_stage(stage="extract", attempts=max_attempts, success=True, outcome="partial", failure_type="timeout")
            return fallback_outline_from_markdown(paper_md)
        self._push_stage(
            stage="extract",
            attempts=max_attempts,
            success=False,
            outcome="failed",
            failure_type=parse_failure or classify_failure(last_error, stage="extract"),
            last_error=last_error,
        )
        raise ParseError(f"Extraction failed after retries. Last error: {last_error or 'empty outline'}")

    def _save(self, item: ExtractionItem, *, paper_md: str | None = None, arxiv_id: str = "") -> Path:
        folder_name = item.arxiv_id.replace("/", "_") if item.arxiv_id else "unknown"
        out_dir = self.dataset_root / folder_name
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            raise PersistenceError(f"Failed creating output directory {out_dir}: {exc}") from exc
        if paper_md and paper_md.strip():
            (out_dir / "paper.md").write_text(paper_md, encoding="utf-8")
        if arxiv_id and not (out_dir / "paper.pdf").exists():
            try:
                from foundation.adapters.paper_tools import download_arxiv_pdf

                download_arxiv_pdf(arxiv_id, out_dir)
            except Exception:
                pass
        try:
            (out_dir / "outline.json").write_text(item.outline.model_dump_json(indent=2), encoding="utf-8")
            (out_dir / "result.json").write_text(
                json.dumps(
                    {
                        "meta": {"schema_version": "v3", "paper_name": item.paper_name, "arxiv_id": item.arxiv_id},
                        "outline": item.outline.model_dump(mode="json"),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as exc:
            raise PersistenceError(f"Failed writing extraction artifacts: {exc}") from exc
        if self._pipeline_metrics is not None:
            from datetime import datetime, timezone

            self._pipeline_metrics.finished_at = datetime.now(timezone.utc).isoformat()
            (out_dir / "pipeline_metrics.json").write_text(
                self._pipeline_metrics.model_dump_json(indent=2),
                encoding="utf-8",
            )
        return out_dir


def _extract_title(md: str) -> str:
    for line in md.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return "Untitled"
