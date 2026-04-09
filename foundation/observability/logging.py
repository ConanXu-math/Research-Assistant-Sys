"""Structured logging helpers with run/paper/stage context."""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

_RUN_ID: ContextVar[str] = ContextVar("optibench_run_id", default="")
_PAPER_ID: ContextVar[str] = ContextVar("optibench_paper_id", default="")
_STAGE: ContextVar[str] = ContextVar("optibench_stage", default="")


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = _RUN_ID.get("")
        record.paper_id = _PAPER_ID.get("")
        record.stage = _STAGE.get("")
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "run_id": getattr(record, "run_id", ""),
            "paper_id": getattr(record, "paper_id", ""),
            "stage": getattr(record, "stage", ""),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(*, verbose: bool, json_logs: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler()
    handler.addFilter(ContextFilter())
    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(name)-12s %(levelname)-8s [run=%(run_id)s paper=%(paper_id)s stage=%(stage)s] %(message)s"
            )
        )
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]


def configure_repl_logging(*, log_file: str | Path, json_logs: bool = True) -> None:
    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(path, encoding="utf-8")
    file_handler.addFilter(ContextFilter())
    if json_logs:
        file_handler.setFormatter(JsonFormatter())
    else:
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(name)-12s %(levelname)-8s [run=%(run_id)s paper=%(paper_id)s stage=%(stage)s] %(message)s"
            )
        )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [file_handler]
    noisy_prefixes = ("httpx", "agno", "openai", "httpcore", "urllib3", "arxiv")
    for name in logging.root.manager.loggerDict:
        if not isinstance(name, str):
            continue
        if any(name == p or name.startswith(f"{p}.") for p in noisy_prefixes):
            lg = logging.getLogger(name)
            lg.handlers = []
            lg.propagate = True
    for noisy in noisy_prefixes:
        logging.getLogger(noisy).handlers = []
        logging.getLogger(noisy).propagate = True


def set_run_context(*, run_id: str | None = None, paper_id: str | None = None, stage: str | None = None) -> None:
    if run_id is not None:
        _RUN_ID.set(run_id)
    if paper_id is not None:
        _PAPER_ID.set(paper_id)
    if stage is not None:
        _STAGE.set(stage)


@contextmanager
def stage_context(stage: str) -> Iterator[None]:
    token = _STAGE.set(stage)
    try:
        yield
    finally:
        _STAGE.reset(token)
