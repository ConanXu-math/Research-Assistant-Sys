"""Interactive wizard for pipeline arguments."""

from __future__ import annotations

import argparse
import os
from getpass import getpass


def prompt_str(prompt: str, default: str = "") -> str:
    value = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return value or default


def prompt_int(prompt: str, default: int) -> int:
    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            print("请输入整数。")


def prompt_bool(prompt: str, default: bool = False) -> bool:
    default_str = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{prompt} ({default_str}): ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes", "1"}:
            return True
        if raw in {"n", "no", "0"}:
            return False
        print("请输入 y 或 n。")


def prompt_choice(prompt: str, choices: list[str], default: str) -> str:
    options = "/".join(choices)
    while True:
        raw = input(f"{prompt} [{options}] (default: {default}): ").strip().lower()
        if not raw:
            return default
        if raw in choices:
            return raw
        print(f"请输入以下之一: {options}")


def interactive_pipeline_args() -> argparse.Namespace:
    """Collect all pipeline arguments from interactive prompts."""
    print("\n=== Research Assistant Sys 交互式配置 ===")

    provider = prompt_choice(
        "LLM Provider",
        ["openai", "openai-like", "ollama", "anthropic", "google"],
        os.getenv("OPTIBENCH_PROVIDER", "openai-like"),
    )
    os.environ["OPTIBENCH_PROVIDER"] = provider

    model_default = "qwen2.5:7b" if provider == "ollama" else os.getenv("OPTIBENCH_MODEL", "gpt-4o")
    model_id = prompt_str("Model ID", model_default)
    if model_id:
        os.environ["OPTIBENCH_MODEL"] = model_id

    timeout_default = os.getenv("OPTIBENCH_API_TIMEOUT", "90")
    api_timeout = prompt_str("API timeout seconds", timeout_default)
    if api_timeout:
        os.environ["OPTIBENCH_API_TIMEOUT"] = api_timeout

    if provider == "ollama":
        base_default = os.getenv("OPTIBENCH_BASE_URL", "http://localhost:11434/v1")
        base_url = prompt_str("Ollama API Base URL", base_default)
        if base_url:
            os.environ["OPTIBENCH_BASE_URL"] = base_url
    elif provider in {"openai-like", "openailike"}:
        base_default = os.getenv("OPTIBENCH_BASE_URL", "")
        base_url = prompt_str("OpenAI-like Base URL", base_default)
        if base_url:
            os.environ["OPTIBENCH_BASE_URL"] = base_url
        api_default_set = bool(os.getenv("OPTIBENCH_API_KEY"))
        if prompt_bool(
            f"是否输入/更新 OPTIBENCH_API_KEY（当前{'已设置' if api_default_set else '未设置'}）",
            default=not api_default_set,
        ):
            api_key = getpass("OPTIBENCH_API_KEY: ").strip()
            if api_key:
                os.environ["OPTIBENCH_API_KEY"] = api_key

    run_mode = prompt_choice("运行模式", ["query", "arxiv-id"], "query")
    query = None
    arxiv_id = None
    if run_mode == "query":
        query = prompt_str("搜索关键词（如 convex optimisation）")
    else:
        arxiv_id = prompt_str("arXiv ID（如 1406.0899v4）")

    dataset_root = prompt_str("输出目录 dataset_root", "./dataset")
    top_k = prompt_int("top-k 论文数", 5)
    workers = prompt_int("批处理并发 workers", int(os.getenv("OPTIBENCH_WORKERS", "1")))
    max_retries = prompt_int("代码/形式化最大重试次数", 3)
    domain = prompt_choice("论文领域过滤", ["continuous", "all"], "continuous")
    skip_lean = prompt_bool("跳过 Lean 4 形式化", True)
    allow_empty_outline = prompt_bool("允许空 outline 继续", False)
    verbose = prompt_bool("启用 verbose 日志", False)

    print("=== 配置完成，开始执行 ===\n")
    return argparse.Namespace(
        query=query,
        arxiv_id=arxiv_id,
        dataset_root=dataset_root,
        max_retries=max_retries,
        domain=domain,
        top_k=top_k,
        workers=workers,
        skip_lean=skip_lean,
        allow_empty_outline=allow_empty_outline,
        verbose=verbose,
    )

