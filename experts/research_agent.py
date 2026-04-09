"""Research agent factory."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import arxiv

from foundation.adapters.paper_tools import _arxiv_client, _arxiv_download_domain
from foundation.adapters.pdf_converter import convert_pdf_to_markdown

if TYPE_CHECKING:
    from agno.models.base import Model


def download_and_convert_paper(arxiv_id: str) -> str:
    try:
        client = _arxiv_client()
        search = arxiv.Search(id_list=[arxiv_id])
        paper = next(client.results(search))
    except Exception as exc:
        return f"ERROR: could not fetch paper {arxiv_id} - {exc}"

    with tempfile.TemporaryDirectory(prefix="optibench_dl_") as tmpdir:
        pdf_path = paper.download_pdf(dirpath=tmpdir, download_domain=_arxiv_download_domain())
        markdown = convert_pdf_to_markdown(str(pdf_path))

    header = (
        f"# {paper.title}\n\n"
        f"**arXiv ID:** {arxiv_id}\n\n"
        f"**Authors:** {', '.join(a.name for a in paper.authors)}\n\n"
        f"**Abstract:** {paper.summary}\n\n---\n\n"
    )
    return header + markdown


def create_research_agent(model: Model, *, download_dir: Path | None = None) -> "Agent":  # noqa: F821
    from agno.agent import Agent
    from agno.tools.arxiv import ArxivTools

    toolkit_kwargs = {}
    if download_dir is not None:
        toolkit_kwargs["download_dir"] = download_dir

    return Agent(
        name="Research Agent",
        model=model,
        tools=[ArxivTools(**toolkit_kwargs), download_and_convert_paper],
        instructions=[
            "Search arXiv and return markdown of the single best-matching optimization paper.",
            "Return only markdown content without extra commentary.",
        ],
        markdown=True,
    )
