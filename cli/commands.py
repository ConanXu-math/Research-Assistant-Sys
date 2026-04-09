"""CLI subcommands that do not run the full workflow."""

from __future__ import annotations

import json
from pathlib import Path

from foundation.adapters.paper_tools import get_arxiv_info, search_arxiv, download_paper
from foundation.adapters.pdf_converter import convert_pdf_to_markdown


def cmd_search(query: str, max_results: int = 10, domain: str = "continuous") -> None:
    papers = search_arxiv(query, max_results=max_results, domain=domain)
    if not papers:
        print("No results found.")
        return
    print(f"Found {len(papers)} papers for '{query}':\n")
    for i, p in enumerate(papers, 1):
        print(f"  {i}. [{p['arxiv_id']}] {p['title'][:70]}...")
        print(f"     {p['summary'][:120]}...")
        print()


def cmd_download(arxiv_id: str, out_dir: str, no_convert: bool) -> None:
    result = download_paper(
        arxiv_id,
        Path(out_dir),
        convert_to_md=not no_convert,
        save_md_file=True,
    )
    print(f"Downloaded: {result['pdf_path']}")
    if result.get("md_path"):
        print(f"Markdown:   {result['md_path']}")
    print(f"Title:      {result['title']}")


def cmd_convert_pdf(pdf_path: str, output_path: str | None) -> None:
    md = convert_pdf_to_markdown(pdf_path)
    if output_path:
        Path(output_path).write_text(md, encoding="utf-8")
        print(f"Written: {output_path}")
    else:
        print(md[:2000] + ("..." if len(md) > 2000 else ""))


def cmd_list(dataset_root: str) -> None:
    root = Path(dataset_root)
    if not root.is_dir():
        print(f"Dataset root not found: {root}")
        return
    entries: list[tuple[str, str, str]] = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        result_file = d / "result.json"
        if result_file.exists():
            try:
                data = json.loads(result_file.read_text(encoding="utf-8"))
                meta = data.get("meta", {}) if isinstance(data, dict) else {}
                arxiv_id = meta.get("arxiv_id", d.name)
                paper_name = meta.get("paper_name", d.name)
            except Exception:
                arxiv_id = d.name
                paper_name = d.name
        else:
            arxiv_id = d.name
            paper_name = d.name
        entries.append((arxiv_id, paper_name, d.name))
    if not entries:
        print(f"No papers in {root}. Run the pipeline or use 'download' first.")
        return
    print(f"Papers in {root} ({len(entries)}):\n")
    for arxiv_id, paper_name, dir_name in entries:
        title_short = (paper_name[:60] + "…") if len(paper_name) > 60 else paper_name
        print(f"  [{arxiv_id}] {title_short}")
        print(f"      → {root / dir_name}")


def cmd_info(arxiv_id: str) -> None:
    info = get_arxiv_info(arxiv_id)
    if info is None:
        print(f"No paper found for arXiv ID: {arxiv_id}")
        return
    print(f"Title:   {info['title']}")
    print(f"arXiv:   {info['arxiv_id']}")
    print(
        f"Authors: {', '.join(info['authors'][:5])}"
        f"{' …' if len(info['authors']) > 5 else ''}"
    )
    print(f"PDF:     {info['pdf_url']}")
    print(f"\nAbstract:\n{info['summary']}")

