"""LLM-driven conversational REPL for Research Assistant Sys."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr
from datetime import datetime, timezone
from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any

from orchestrator.bootstrap import build_assistant_orchestrator, build_execution_context
from foundation.adapters.paper_tools import download_paper, get_arxiv_info, search_arxiv


@dataclass
class ReplSession:
    dataset_root: Path
    top_k: int
    domain: str
    skip_lean: bool
    max_retries: int
    workers: int
    focus_arxiv_id: str = ""
    last_summary_path: str = ""
    last_search_results: list[dict[str, Any]] = field(default_factory=list)
    conversation_summary: str = ""
    recent_turns: list[dict[str, str]] = field(default_factory=list)


MAX_RECENT_TURNS = 8


def _session_state_path(dataset_root: Path) -> Path:
    return dataset_root / "session.json"


def _trace_path(dataset_root: Path) -> Path:
    log_dir = dataset_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "repl_trace.jsonl"


def _load_session_state(session: ReplSession) -> None:
    state_file = _session_state_path(session.dataset_root)
    if not state_file.exists():
        return
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return
    session.focus_arxiv_id = str(data.get("focus_arxiv_id") or "")
    session.last_summary_path = str(data.get("last_summary_path") or "")
    search_results = data.get("last_search_results")
    if isinstance(search_results, list):
        session.last_search_results = [r for r in search_results if isinstance(r, dict)][:20]
    session.conversation_summary = str(data.get("conversation_summary") or "")
    turns = data.get("recent_turns")
    if isinstance(turns, list):
        clean: list[dict[str, str]] = []
        for t in turns:
            if not isinstance(t, dict):
                continue
            role = str(t.get("role") or "").strip()
            content = str(t.get("content") or "").strip()
            if role and content:
                clean.append({"role": role, "content": content})
        session.recent_turns = clean[-MAX_RECENT_TURNS:]


def _save_session_state(session: ReplSession) -> None:
    state_file = _session_state_path(session.dataset_root)
    payload = {
        "focus_arxiv_id": session.focus_arxiv_id,
        "last_summary_path": session.last_summary_path,
        "last_search_results": session.last_search_results[:20],
        "conversation_summary": session.conversation_summary,
        "recent_turns": session.recent_turns[-MAX_RECENT_TURNS:],
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    state_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_trace(dataset_root: Path, record: dict[str, Any]) -> None:
    trace_file = _trace_path(dataset_root)
    line = json.dumps(record, ensure_ascii=False)
    with trace_file.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _rollup_summary(summary: str, turns: list[dict[str, str]]) -> str:
    snippets: list[str] = []
    for t in turns[-4:]:
        role = t.get("role", "")
        content = (t.get("content", "") or "").replace("\n", " ").strip()
        if not content:
            continue
        snippets.append(f"{role}: {content[:120]}")
    merged = (" | ".join(snippets)).strip()
    if not merged:
        return summary
    if not summary:
        return merged[:1200]
    new_summary = (summary + " || " + merged).strip()
    return new_summary[-1200:]


def _build_context_prompt(session: ReplSession, user_input: str) -> str:
    state = {
        "focus_arxiv_id": session.focus_arxiv_id,
        "last_search_count": len(session.last_search_results),
        "dataset_root": str(session.dataset_root),
        "conversation_summary": session.conversation_summary,
    }
    recent = session.recent_turns[-MAX_RECENT_TURNS:]
    recent_text = "\n".join(
        f"{t.get('role','')}: {t.get('content','')}" for t in recent if t.get("content")
    )
    return (
        "以下是当前会话状态与最近对话，请先利用这些上下文再回答。\n\n"
        f"[session_state]\n{json.dumps(state, ensure_ascii=False, indent=2)}\n\n"
        f"[recent_turns]\n{recent_text if recent_text else '(empty)'}\n\n"
        f"[user]\n{user_input}"
    )


def _stream_agent_reply(chat_agent: Any, prompt: str) -> tuple[str, bool]:
    """Run agent in streaming mode and print chunks progressively."""
    collected: list[str] = []
    stream_iter = chat_agent.run(prompt, stream=True)
    printed_any = False
    for event in stream_iter:
        # Try common text-bearing fields used by streaming events.
        chunk = ""
        if isinstance(event, str):
            chunk = event
        else:
            for attr in ("delta", "content", "text", "token", "chunk"):
                value = getattr(event, attr, None)
                if isinstance(value, str) and value:
                    chunk = value
                    break
            if not chunk:
                try:
                    content = event.get_content_as_string()
                    if isinstance(content, str):
                        chunk = content
                except Exception:
                    pass
        if chunk:
            print(chunk, end="", flush=True)
            collected.append(chunk)
            printed_any = True
    if printed_any:
        print()
    return "".join(collected).strip(), printed_any


def start_repl(*, model: Any, wf: Any, args: Any) -> None:
    from agno.agent import Agent

    session = ReplSession(
        dataset_root=Path(args.dataset_root),
        top_k=args.top_k,
        domain=args.domain,
        skip_lean=args.skip_lean,
        max_retries=args.max_retries,
        workers=args.workers,
    )
    session.dataset_root.mkdir(parents=True, exist_ok=True)
    _load_session_state(session)
    orchestrator = build_assistant_orchestrator(model=model, workflow=wf)

    def tool_search(query: str, top_k: int | None = None) -> str:
        k = int(top_k or session.top_k or 5)
        try:
            papers = search_arxiv(query, max_results=k, domain=session.domain)
        except Exception as exc:
            logging.getLogger("optibench.repl").warning("tool_search failed: %s", exc)
            return (
                "检索 arXiv 失败（网络/SSL 问题）。\n"
                "建议：\n"
                "1) 稍后重试；\n"
                "2) 配置代理 HTTP_PROXY/HTTPS_PROXY；\n"
                "3) 使用本地已下载论文继续：先 `list local` 再 `show result`。"
            )
        session.last_search_results = papers
        _save_session_state(session)
        if not papers:
            return "没有找到结果。"
        lines = []
        for idx, p in enumerate(papers, 1):
            lines.append(f"{idx}. [{p.get('arxiv_id','')}] {p.get('title','')}")
        return "\n".join(lines)

    def tool_set_focus(arxiv_id: str) -> str:
        session.focus_arxiv_id = arxiv_id.strip()
        _save_session_state(session)
        return f"已设置焦点论文: {session.focus_arxiv_id}"

    def tool_info(arxiv_id: str | None = None) -> str:
        target = (arxiv_id or session.focus_arxiv_id).strip()
        if not target:
            return "请先提供 arXiv ID，或先设置焦点论文。"
        try:
            info = get_arxiv_info(target)
        except Exception as exc:
            logging.getLogger("optibench.repl").warning("tool_info failed: %s", exc)
            return f"查询论文元数据失败：{exc}"
        if info is None:
            return f"未找到论文: {target}"
        return json.dumps(info, ensure_ascii=False, indent=2, default=str)

    def tool_list_local() -> str:
        root = session.dataset_root
        if not root.exists():
            return f"目录不存在: {root}"
        rows: list[str] = []
        for d in sorted(root.iterdir()):
            if not d.is_dir():
                continue
            result_file = d / "result.json"
            if result_file.exists():
                try:
                    data = json.loads(result_file.read_text(encoding="utf-8"))
                    meta = data.get("meta", {}) if isinstance(data, dict) else {}
                    rows.append(f"[{meta.get('arxiv_id', d.name)}] {meta.get('paper_name', d.name)}")
                except Exception:
                    rows.append(f"[{d.name}] {d.name}")
        return "\n".join(rows) if rows else "本地还没有已处理论文。"

    def tool_show_result(arxiv_id: str | None = None) -> str:
        target = (arxiv_id or session.focus_arxiv_id).strip()
        if not target:
            return "请先提供 arXiv ID，或先设置焦点论文。"
        folder = session.dataset_root / target.replace("/", "_")
        result_file = folder / "result.json"
        if not result_file.exists():
            return f"未找到结果文件: {result_file}"
        data = json.loads(result_file.read_text(encoding="utf-8"))
        return json.dumps(data, ensure_ascii=False, indent=2)

    def tool_run_pipeline(arxiv_id: str | None = None, pdf_path: str | None = None) -> str:
        target = (arxiv_id or session.focus_arxiv_id).strip()
        if not target:
            return "请先提供 arXiv ID，或先设置焦点论文。"
        try:
            if pdf_path:
                pdf = Path(pdf_path)
                if not pdf.exists():
                    return f"本地 PDF 不存在: {pdf}"
                from foundation.adapters.pdf_converter import convert_pdf_to_markdown

                md_body = convert_pdf_to_markdown(str(pdf))
                paper_name = pdf.stem or "Untitled"
                paper_md = (
                    f"# {paper_name}\n\n"
                    f"**arXiv ID:** {target}\n\n"
                    f"**Authors:** N/A\n\n"
                    f"**Abstract:** N/A (local pdf mode)\n\n---\n\n"
                    f"{md_body}"
                )
            else:
                dl = download_paper(
                    arxiv_id=target,
                    out_dir=session.dataset_root,
                    convert_to_md=True,
                    save_md_file=True,
                )
                paper_md = dl.get("md_content") or ""
                paper_name = dl.get("title") or "Untitled"
            item = wf.run_from_paper(
                paper_md=paper_md,
                arxiv_id=target,
                paper_name=paper_name,
            )
            out_dir = session.dataset_root / (item.arxiv_id or target).replace("/", "_")
            session.focus_arxiv_id = item.arxiv_id or target
            session.last_summary_path = str((session.dataset_root / "run_summary.json"))
            _save_session_state(session)
            return (
                "处理完成。\n"
                f"- paper: {item.paper_name}\n"
                f"- arxiv_id: {item.arxiv_id or target}\n"
                f"- output: {out_dir}"
            )
        except Exception as exc:
            return f"流水线执行失败: {exc}"

    def tool_status() -> str:
        return json.dumps(
            {
                "focus_arxiv_id": session.focus_arxiv_id,
                "dataset_root": str(session.dataset_root),
                "top_k": session.top_k,
                "domain": session.domain,
                "skip_lean": session.skip_lean,
                "max_retries": session.max_retries,
                "workers": session.workers,
                "last_summary_path": session.last_summary_path,
                "last_search_count": len(session.last_search_results),
                "conversation_summary_len": len(session.conversation_summary),
                "recent_turn_count": len(session.recent_turns),
            },
            ensure_ascii=False,
            indent=2,
        )

    def tool_assistant_task(intent: str, payload_json: str = "{}") -> str:
        try:
            payload_obj = json.loads(payload_json) if payload_json.strip() else {}
        except json.JSONDecodeError as exc:
            return f"payload_json 不是合法 JSON: {exc}"
        context = build_execution_context(
            dataset_root=str(session.dataset_root),
            user_query=session.recent_turns[-1]["content"] if session.recent_turns else "",
            focus_arxiv_id=session.focus_arxiv_id,
            domain=session.domain,
            skip_lean=session.skip_lean,
            max_retries=session.max_retries,
        )
        try:
            result = orchestrator.handle(intent=intent, payload=payload_obj, context=context)
        except Exception as exc:
            return f"assistant task 执行失败: {exc}"
        return json.dumps(result, ensure_ascii=False, indent=2)

    chat_agent = Agent(
        name="Research Assistant Sys Leader",
        model=model,
        tools=[
            tool_assistant_task,
            tool_search,
            tool_set_focus,
            tool_info,
            tool_list_local,
            tool_show_result,
            tool_run_pipeline,
            tool_status,
        ],
        instructions=[
            "你是科研助手的对话式 CLI 主管代理。",
            "优先调用 tool_assistant_task 进行统一意图路由；必要时再调用底层工具补充信息。",
            "支持意图：search_parse, structure_extract。",
            "当用户提到“这篇论文/当前论文”时，使用 focus_arxiv_id。",
            "回答使用简体中文，结构清晰简短。",
            "如需要 arXiv ID 但缺失，先明确提示用户提供。",
        ],
        markdown=True,
    )

    print("\n=== Research Assistant Sys 对话式模式（LLM 驱动）===")
    print("输入你的问题或命令，输入 exit/quit 退出。\n")
    while True:
        try:
            user_input = input("ResearchSys> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n已退出。")
            break
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "bye"}:
            _save_session_state(session)
            print("已退出。")
            break
        prompt = _build_context_prompt(session, user_input)
        try:
            sink_err = io.StringIO()
            # Silence internal SDK/framework logs printed directly to stdout/stderr.
            prev_disable = logging.root.manager.disable
            logging.disable(logging.CRITICAL)
            with redirect_stderr(sink_err):
                reply_streamed, printed_any = _stream_agent_reply(chat_agent, prompt)
            logging.disable(prev_disable)
            reply = reply_streamed or "(无响应)"
        except Exception as exc:
            logging.disable(logging.NOTSET)
            printed_any = False
            reply = (
                "当前与模型服务连接失败，请稍后重试。\n"
                f"错误: {type(exc).__name__}: {exc}"
            )
        if not printed_any:
            print(reply)

        session.recent_turns.append({"role": "user", "content": user_input})
        session.recent_turns.append({"role": "assistant", "content": str(reply)})
        if len(session.recent_turns) > MAX_RECENT_TURNS * 2:
            dropped = session.recent_turns[: len(session.recent_turns) - MAX_RECENT_TURNS * 2]
            session.recent_turns = session.recent_turns[-MAX_RECENT_TURNS * 2 :]
            session.conversation_summary = _rollup_summary(session.conversation_summary, dropped)
        _save_session_state(session)
        _append_trace(
            session.dataset_root,
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "user_input": user_input,
                "assistant_output": str(reply),
                "focus_arxiv_id": session.focus_arxiv_id,
            },
        )
