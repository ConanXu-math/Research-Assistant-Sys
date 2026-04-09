"""Batch execution utilities for extraction workflow."""

from __future__ import annotations

import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from interface.ui import StagePrinter
from foundation.observability.logging import set_run_context
from foundation.adapters.paper_tools import download_paper, search_arxiv
from foundation.adapters.pdf_converter import convert_pdf_to_markdown


def run_batch_pipeline(args: Any, wf: Any) -> Path:
    if not args.query and not args.arxiv_id:
        raise ValueError("Provide either a search query or --arxiv-id.")
    if args.top_k < 1:
        raise ValueError("--top-k must be >= 1")

    search_results: list[dict[str, object]] = []
    if args.arxiv_id:
        paper_ids = [args.arxiv_id]
    else:
        papers = search_arxiv(args.query, max_results=args.top_k, domain=args.domain)
        if not papers:
            raise RuntimeError(f"No papers found for query: {args.query}")
        search_results = [
            {"rank": i + 1, "arxiv_id": p.get("arxiv_id", ""), "title": p.get("title", ""), "summary": p.get("summary", "")}
            for i, p in enumerate(papers)
        ]
        paper_ids = [p["arxiv_id"] for p in papers if p.get("arxiv_id")]
        if not paper_ids:
            raise RuntimeError("Search results contained no valid arXiv IDs.")

    summary_items: list[dict[str, object]] = []
    success = 0
    failed = 0
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    logger = logging.getLogger("optibench")
    set_run_context(run_id=run_id, stage="batch")
    ui = StagePrinter(total=len(paper_ids))

    workers = max(1, int(getattr(args, "workers", 1) or 1))
    logger.info("Starting batch run %s with workers=%d", run_id, workers)

    if workers == 1:
        for idx, arxiv_id in enumerate(paper_ids, 1):
            ui.paper_header(idx, arxiv_id)
            result = _process_single_paper(idx, arxiv_id, args, wf, search_stage=("skipped" if args.arxiv_id else "ok"), run_id=run_id)
            summary_items.append(result)
            if result.get("status") == "success":
                success += 1
            else:
                failed += 1
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_process_single_paper, idx, arxiv_id, args, wf, "skipped" if args.arxiv_id else "ok", run_id): (idx, arxiv_id)
                for idx, arxiv_id in enumerate(paper_ids, 1)
            }
            ordered = {}
            for future in as_completed(futures):
                idx, arxiv_id = futures[future]
                try:
                    ordered[idx] = future.result()
                except Exception as exc:
                    logger.exception("Unexpected worker crash for %s: %s", arxiv_id, exc)
                    ordered[idx] = {"arxiv_id": arxiv_id, "paper_name": "", "status": "failed", "error": str(exc), "output_dir": str(Path(args.dataset_root) / arxiv_id.replace("/", "_"))}
            for idx in sorted(ordered):
                result = ordered[idx]
                ui.paper_header(idx, result.get("arxiv_id", ""))
                ui.stage("status", str(result.get("status", "unknown")))
                summary_items.append(result)
                if result.get("status") == "success":
                    success += 1
                else:
                    failed += 1

    dataset_root = Path(args.dataset_root)
    dataset_root.mkdir(parents=True, exist_ok=True)
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": args.query,
        "requested_top_k": args.top_k,
        "total": len(paper_ids),
        "success": success,
        "failed": failed,
        "search_results": search_results,
        "items": summary_items,
        "failure_type_counts": _aggregate_failure_types(summary_items),
        "extraction_strategy_counts": _aggregate_extraction_strategy(summary_items),
    }
    summary_path = dataset_root / "run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    if search_results:
        (dataset_root / "search_results.json").write_text(json.dumps(search_results, indent=2, ensure_ascii=False), encoding="utf-8")
    ui.summary(total=len(paper_ids), success=success, failed=failed, summary_path=str(summary_path))
    return summary_path


def _clone_workflow(wf: Any) -> Any:
    return wf.__class__(model=wf.model, dataset_root=wf.dataset_root, max_retries=wf.max_retries, require_outline=wf.require_outline, enable_benchmark_artifacts=getattr(wf, "enable_benchmark_artifacts", True))


def _process_single_paper(index: int, arxiv_id: str, args: Any, wf: Any, search_stage: str, run_id: str) -> dict[str, object]:
    logger = logging.getLogger("optibench")
    paper_dir = Path(args.dataset_root) / arxiv_id.replace("/", "_")
    set_run_context(run_id=run_id, paper_id=arxiv_id)
    worker_wf = _clone_workflow(wf)
    try:
        set_run_context(stage="download")
        pdf_path_arg = getattr(args, "pdf_path", None)
        if pdf_path_arg:
            local_pdf = Path(pdf_path_arg)
            if not local_pdf.exists() or not local_pdf.is_file():
                raise FileNotFoundError(f"--pdf-path not found: {local_pdf}")
            md_body = convert_pdf_to_markdown(str(local_pdf))
            paper_name = local_pdf.stem or "Untitled"
            paper_md = f"# {paper_name}\n\n**arXiv ID:** {arxiv_id}\n\n**Authors:** N/A\n\n**Abstract:** N/A (local pdf mode)\n\n---\n\n{md_body}"
            paper_dir.mkdir(parents=True, exist_ok=True)
            (paper_dir / "paper.md").write_text(paper_md, encoding="utf-8")
        else:
            dl = download_paper(arxiv_id=arxiv_id, out_dir=args.dataset_root, convert_to_md=True, save_md_file=True)
            paper_md = dl.get("md_content") or ""
            paper_name = dl.get("title") or "Untitled"
    except Exception as exc:
        logger.exception("Download stage failed for arXiv %s: %s", arxiv_id, exc)
        return {"arxiv_id": arxiv_id, "paper_name": "", "status": "failed", "error": f"download failed: {exc}", "output_dir": str(paper_dir), "stages": {"search": search_stage, "download": "failed", "extract": "not_run", "organize": "partial"}}

    try:
        set_run_context(stage="pipeline")
        item = worker_wf.run_from_paper(paper_md=paper_md, arxiv_id=arxiv_id, paper_name=paper_name)
        stage_extract = _outline_stage_status(item.outline)
        pm_file = paper_dir / "pipeline_metrics.json"
        pipeline_metrics: dict[str, object] | None = None
        if pm_file.exists():
            try:
                pipeline_metrics = json.loads(pm_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pipeline_metrics = None
        logger.info("Finished paper %s at index %d", arxiv_id, index)
        return {"arxiv_id": item.arxiv_id or arxiv_id, "paper_name": item.paper_name, "status": "success", "output_dir": f"{args.dataset_root}/{(item.arxiv_id or arxiv_id).replace('/', '_')}", "pipeline_metrics": pipeline_metrics, "stages": {"search": search_stage, "download": "ok" if (paper_dir / "paper.pdf").exists() or (paper_dir / "paper.md").exists() else "failed", "extract": stage_extract, "organize": "ok" if (paper_dir / "outline.json").exists() else "failed"}}
    except Exception as exc:
        logger.exception("Pipeline failed for arXiv %s: %s", arxiv_id, exc)
        stage_extract = _outline_stage_status_from_file(paper_dir / "outline.json")
        partial_metrics: dict[str, object] | None = None
        try:
            pm = worker_wf.get_pipeline_metrics()
            if pm is not None:
                partial_metrics = pm.model_dump(mode="json")
        except Exception:
            partial_metrics = None
        return {"arxiv_id": arxiv_id, "paper_name": "", "status": "failed", "error": str(exc), "output_dir": str(paper_dir), "pipeline_metrics_partial": partial_metrics, "stages": {"search": search_stage, "download": "ok" if (paper_dir / "paper.pdf").exists() or (paper_dir / "paper.md").exists() else "failed", "extract": stage_extract, "organize": "ok" if (paper_dir / "outline.json").exists() else "partial"}}


def _outline_stage_status(outline: object) -> str:
    objective = getattr(outline, "objective", "") or ""
    constraints = getattr(outline, "constraints", []) or []
    variables = getattr(outline, "variables", []) or []
    return "ok" if (objective.strip() or constraints or variables) else "failed"


def _outline_stage_status_from_file(path: Path) -> str:
    if not path.exists():
        return "not_run"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return "failed"
    objective = (data.get("objective") or "").strip()
    constraints = data.get("constraints") or []
    variables = data.get("variables") or []
    return "ok" if (objective or constraints or variables) else "failed"


def _aggregate_failure_types(items: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        pm = item.get("pipeline_metrics")
        if not isinstance(pm, dict):
            pm = item.get("pipeline_metrics_partial")
        if not isinstance(pm, dict):
            continue
        stages = pm.get("stages")
        if not isinstance(stages, list):
            continue
        for st in stages:
            if not isinstance(st, dict):
                continue
            ft = (st.get("failure_type") or "").strip()
            if ft:
                counts[ft] = counts.get(ft, 0) + 1
    return counts


def _aggregate_extraction_strategy(items: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        pm = item.get("pipeline_metrics")
        if not isinstance(pm, dict):
            pm = item.get("pipeline_metrics_partial")
        if not isinstance(pm, dict):
            continue
        strategy = (pm.get("extraction_strategy") or "").strip()
        if strategy:
            counts[strategy] = counts.get(strategy, 0) + 1
    return counts
