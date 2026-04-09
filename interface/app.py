"""Research Assistant Sys interaction entrypoint."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from foundation.config.constants import DEFAULT_DATASET_ROOT, DEFAULT_DOMAIN, DEFAULT_MAX_RETRIES, DEFAULT_TOP_K
from foundation.config.settings import Settings
from foundation.execution.pipeline_batch import run_batch_pipeline
from orchestrator.bootstrap import build_assistant_orchestrator, build_execution_context
from foundation.modeling.model_builder import build_model
from foundation.errors import ConfigError
from interface.commands import cmd_convert_pdf, cmd_download, cmd_info, cmd_list, cmd_search
from interface.interactive import interactive_pipeline_args
from interface.repl import start_repl
from foundation.observability.logging import configure_logging, configure_repl_logging

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _dispatch_tool_subcommand() -> bool:
    if len(sys.argv) < 2:
        return False
    sub = sys.argv[1]
    if sub not in ("download", "search", "convert-pdf", "list", "info", "repl", "assistant"):
        return False

    subparser = argparse.ArgumentParser(prog=f"main.py {sub}")
    if sub == "search":
        subparser.add_argument("query", help="Search keywords")
        subparser.add_argument("--max", type=int, default=10, help="Max results (default 10)")
        subparser.add_argument(
            "--domain",
            default=os.getenv("OPTIBENCH_DOMAIN", DEFAULT_DOMAIN),
            choices=["continuous", "all"],
            help="Search domain filter (default: continuous).",
        )
        args = subparser.parse_args(sys.argv[2:])
        cmd_search(args.query, args.max, args.domain)
    elif sub == "download":
        subparser.add_argument("arxiv_id", help="arXiv ID (e.g. 1406.0899 or 1406.0899v4)")
        subparser.add_argument(
            "--output",
            "-o",
            default=DEFAULT_DATASET_ROOT,
            help=f"Output directory (default {DEFAULT_DATASET_ROOT})",
        )
        subparser.add_argument("--no-convert", action="store_true", help="Only download PDF, do not convert to Markdown")
        args = subparser.parse_args(sys.argv[2:])
        cmd_download(args.arxiv_id, args.output, args.no_convert)
    elif sub == "list":
        subparser.add_argument(
            "--dataset-root",
            "-d",
            default=DEFAULT_DATASET_ROOT,
            help=f"Dataset directory (default {DEFAULT_DATASET_ROOT})",
        )
        args = subparser.parse_args(sys.argv[2:])
        cmd_list(args.dataset_root)
    elif sub == "info":
        subparser.add_argument("arxiv_id", help="arXiv ID (e.g. 1406.0899)")
        args = subparser.parse_args(sys.argv[2:])
        cmd_info(args.arxiv_id)
    elif sub == "repl":
        subparser.add_argument("--dataset-root", default=DEFAULT_DATASET_ROOT)
        subparser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
        subparser.add_argument(
            "--domain",
            default=os.getenv("OPTIBENCH_DOMAIN", DEFAULT_DOMAIN),
            choices=["continuous", "all"],
        )
        subparser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
        subparser.add_argument("--workers", type=int, default=None)
        subparser.add_argument("--verbose", "-v", action="store_true")
        args = subparser.parse_args(sys.argv[2:])

        settings = Settings.from_env()
        if args.workers is None:
            args.workers = settings.max_workers
        repl_log_file = Path(args.dataset_root) / "logs" / "repl.log"
        configure_repl_logging(log_file=repl_log_file, json_logs=True)
        os.environ["OPTIBENCH_DOMAIN"] = args.domain
        from orchestrator.workflow import OptiBenchWorkflow

        model = build_model()
        wf = OptiBenchWorkflow(
            model=model,
            dataset_root=args.dataset_root,
            max_retries=args.max_retries,
            require_outline=True,
        )
        print(f"REPL 日志已写入: {repl_log_file}")
        start_repl(model=model, wf=wf, args=args)
    elif sub == "assistant":
        subparser.add_argument("--intent", required=True)
        subparser.add_argument("--query", default="")
        subparser.add_argument("--arxiv-id", default="")
        subparser.add_argument("--dataset-root", default=DEFAULT_DATASET_ROOT)
        subparser.add_argument(
            "--domain",
            default=os.getenv("OPTIBENCH_DOMAIN", DEFAULT_DOMAIN),
            choices=["continuous", "all"],
        )
        subparser.add_argument("--payload-json", default="")
        subparser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
        args = subparser.parse_args(sys.argv[2:])
        payload: dict = {}
        if args.payload_json.strip():
            import json

            payload = json.loads(args.payload_json)
        if args.query and "query" not in payload:
            payload["query"] = args.query
        if args.arxiv_id and "arxiv_id" not in payload:
            payload["arxiv_id"] = args.arxiv_id
        orchestrator = build_assistant_orchestrator(model=build_model(), workflow=None)
        context = build_execution_context(
            dataset_root=args.dataset_root,
            user_query=args.query,
            focus_arxiv_id=args.arxiv_id,
            domain=args.domain,
            max_retries=args.max_retries,
        )
        result = orchestrator.handle(intent=args.intent, payload=payload, context=context)
        import json

        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        subparser.add_argument("pdf_path", help="Path to PDF file")
        subparser.add_argument("-o", "--output", default=None, help="Output .md file (default: print to stdout)")
        args = subparser.parse_args(sys.argv[2:])
        cmd_convert_pdf(args.pdf_path, args.output)
    return True


def _parse_pipeline_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Research Assistant Sys: paper-structure expert pipeline",
    )
    parser.add_argument("query", nargs="?", default=None)
    parser.add_argument("--arxiv-id", default=None)
    parser.add_argument(
        "--pdf-path",
        default=None,
        help="Use a local PDF file and skip arXiv download/network stage.",
    )
    parser.add_argument("--dataset-root", default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument(
        "--domain",
        default=os.getenv("OPTIBENCH_DOMAIN", DEFAULT_DOMAIN),
        choices=["continuous", "all"],
    )
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Batch parallel workers (default from OPTIBENCH_WORKERS or 1).",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser.parse_args()


def main() -> None:
    if _dispatch_tool_subcommand():
        return

    args = interactive_pipeline_args() if len(sys.argv) == 1 else _parse_pipeline_args()
    try:
        settings = Settings.from_env()
        settings.validate_runtime_requirements()
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        raise SystemExit(2) from exc

    if args.workers is None:
        args.workers = settings.max_workers

    configure_logging(verbose=args.verbose, json_logs=settings.log_json)

    os.environ["OPTIBENCH_DOMAIN"] = args.domain
    from orchestrator.workflow import OptiBenchWorkflow

    wf = OptiBenchWorkflow(
        model=build_model(),
        dataset_root=args.dataset_root,
        max_retries=args.max_retries,
        require_outline=True,
    )
    run_batch_pipeline(args, wf)


if __name__ == "__main__":
    main()
