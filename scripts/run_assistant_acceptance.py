"""Minimal E2E acceptance checks for research assistant MVP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from orchestrator.bootstrap import build_assistant_orchestrator, build_execution_context
from foundation.modeling.model_builder import build_model


def run_checks(dataset_root: str) -> dict:
    orchestrator = build_assistant_orchestrator(model=build_model(), workflow=None)
    context = build_execution_context(dataset_root=dataset_root, domain="continuous")

    checks: dict[str, dict] = {}

    checks["search_parse"] = orchestrator.handle(
        intent="search_parse",
        payload={"query": "alternating direction method of multipliers", "top_k": 1},
        context=context,
    )

    checks["structure_extract"] = orchestrator.handle(
        intent="structure_extract",
        payload={"arxiv_id": "1406.0899"},
        context=context,
    )

    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description="Run assistant MVP acceptance checks")
    parser.add_argument("--dataset-root", default="./dataset")
    parser.add_argument("--output", default="./dataset/assistant_acceptance.json")
    args = parser.parse_args()

    report = run_checks(args.dataset_root)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Acceptance report written to: {out}")


if __name__ == "__main__":
    main()
