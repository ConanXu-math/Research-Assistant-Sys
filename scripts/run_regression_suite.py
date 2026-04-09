"""Run mini regression suite and aggregate run summaries.

Usage:
  uv run python scripts/run_regression_suite.py
  uv run python scripts/run_regression_suite.py --skip-lean --limit 4
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Research Assistant Sys mini regression suite")
    p.add_argument(
        "--set",
        default="dataset/regression_set_v1.json",
        help="Path to regression set json",
    )
    p.add_argument(
        "--dataset-root",
        default="./dataset/regression",
        help="Dataset output root",
    )
    p.add_argument("--skip-lean", action="store_true", help="Skip Lean stage")
    p.add_argument("--limit", type=int, default=0, help="Run only first N papers")
    p.add_argument(
        "--strategy",
        default="unified",
        choices=["unified", "locator_first", "auto"],
        help="Extraction strategy for this run",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    set_path = Path(args.set)
    if not set_path.exists():
        raise FileNotFoundError(f"Regression set not found: {set_path}")

    raw = json.loads(set_path.read_text(encoding="utf-8"))
    papers = raw.get("papers", [])
    if not isinstance(papers, list) or not papers:
        raise ValueError("Regression set has no papers")
    if args.limit > 0:
        papers = papers[: args.limit]

    ds_root = Path(args.dataset_root)
    ds_root.mkdir(parents=True, exist_ok=True)
    suite_result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "strategy": args.strategy,
        "skip_lean": bool(args.skip_lean),
        "total": len(papers),
        "results": [],
    }

    env = dict(**__import__("os").environ)
    env["OPTIBENCH_EXTRACTION_STRATEGY"] = args.strategy

    for i, item in enumerate(papers, 1):
        arxiv_id = item.get("arxiv_id", "")
        if not arxiv_id:
            continue
        print(f"\n[{i}/{len(papers)}] arXiv {arxiv_id}")
        cmd = [
            sys.executable,
            "main.py",
            "--arxiv-id",
            arxiv_id,
            "--dataset-root",
            str(ds_root),
        ]
        if args.skip_lean:
            cmd.append("--skip-lean")

        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
        paper_dir = ds_root / arxiv_id.replace("/", "_")
        suite_result["results"].append(
            {
                "arxiv_id": arxiv_id,
                "returncode": proc.returncode,
                "paper_dir": str(paper_dir),
                "has_metrics": (paper_dir / "pipeline_metrics.json").exists(),
                "has_outline": (paper_dir / "outline.json").exists(),
                "stderr_tail": proc.stderr[-800:],
            }
        )

    out = ds_root / "regression_suite_result.json"
    out.write_text(json.dumps(suite_result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSuite result saved to: {out}")


if __name__ == "__main__":
    main()

