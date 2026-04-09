"""Builtin expert plugins (adapters + MVP experts)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from experts.extraction_agent import create_extraction_agent
from foundation.models import ExecutionContext
from foundation.adapters.paper_tools import download_paper, search_arxiv


def _paper_dir(dataset_root: str, arxiv_id: str) -> Path:
    return Path(dataset_root) / arxiv_id.replace("/", "_")


def _load_paper_md(dataset_root: str, arxiv_id: str) -> str:
    path = _paper_dir(dataset_root, arxiv_id) / "paper.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


class ResearchSearchDownloadExpert:
    name = "research.search_download"
    intents = ("research.search_download", "search_parse")
    input_schema = {"required": ["query"]}
    output_schema = {"fields": ["search_results", "best_paper"]}

    def execute(self, payload: dict, context: ExecutionContext) -> dict:
        query = str(payload.get("query") or context.user_query).strip()
        top_k = int(payload.get("top_k") or 5)
        if not query:
            return {"status": "error", "notes": ["query is required"]}
        results = search_arxiv(query, max_results=top_k, domain=context.domain)
        if not results:
            return {"status": "error", "notes": ["no papers found"], "search_results": []}
        best = results[0]
        arxiv_id = str(best.get("arxiv_id") or "").strip()
        paper = {}
        if arxiv_id:
            dl = download_paper(
                arxiv_id=arxiv_id,
                out_dir=context.dataset_root,
                convert_to_md=True,
                save_md_file=True,
            )
            paper = {
                "arxiv_id": arxiv_id,
                "title": dl.get("title") or best.get("title") or "",
                "paper_md_len": len(dl.get("md_content") or ""),
            }
        return {"status": "ok", "search_results": results, "best_paper": paper}


class ExtractionStructureExpert:
    name = "extraction.structure_extract"
    intents = ("extraction.structure_extract", "structure_extract")
    input_schema = {"required": ["arxiv_id"]}
    output_schema = {"fields": ["outline", "score", "is_acceptable"]}

    def __init__(self, model: Any) -> None:
        self.agent = create_extraction_agent(model)

    def execute(self, payload: dict, context: ExecutionContext) -> dict:
        arxiv_id = str(payload.get("arxiv_id") or context.focus_arxiv_id).strip()
        paper_md = str(payload.get("paper_md") or "")
        if not paper_md and arxiv_id:
            paper_md = _load_paper_md(context.dataset_root, arxiv_id)
        if not paper_md:
            return {"status": "error", "notes": ["paper markdown not found"]}
        response = self.agent.run(
            "Extract the optimization structure and self-critique.\n\n" + paper_md[:20000]
        )
        content = response.content
        if hasattr(content, "model_dump"):
            data = content.model_dump(mode="json")
        elif isinstance(content, str):
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                data = {"raw": content}
        elif isinstance(content, dict):
            data = content
        else:
            data = {"raw": str(content)}
        data["status"] = "ok"
        return data


