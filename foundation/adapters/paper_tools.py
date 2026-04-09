"""Paper utilities: arXiv search/download and markdown conversion."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import arxiv
import requests

from foundation.adapters.pdf_converter import convert_pdf_to_markdown

_DEFAULT_ARXIV_API_BASE = "https://export.arxiv.org"


def _arxiv_client() -> arxiv.Client:
    base = (os.getenv("OPTIBENCH_ARXIV_BASE_URL") or "").strip().rstrip("/")
    arxiv.Client.query_url_format = f"{(base or _DEFAULT_ARXIV_API_BASE)}/api/query?{{}}"
    timeout_s = (os.getenv("OPTIBENCH_ARXIV_TIMEOUT") or "120").strip()
    try:
        timeout_f = float(timeout_s)
    except ValueError:
        timeout_f = 120.0
    client = arxiv.Client()
    orig_get = client._session.get

    def _get_with_timeout(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("timeout", timeout_f)
        return orig_get(*args, **kwargs)

    client._session.get = _get_with_timeout
    return client


def _arxiv_download_domain() -> str:
    base = (os.getenv("OPTIBENCH_ARXIV_BASE_URL") or _DEFAULT_ARXIV_API_BASE).strip()
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    parsed = urlparse(base)
    return parsed.netloc or "export.arxiv.org"


def _direct_pdf_url(arxiv_id: str) -> str:
    aid = arxiv_id.strip()
    return f"https://arxiv.org/pdf/{aid or 'unknown'}.pdf"


def _find_cached_pdf(paper_dir: Path) -> Path | None:
    preferred = paper_dir / "paper.pdf"
    if preferred.exists() and preferred.is_file():
        return preferred
    for p in sorted(paper_dir.glob("*.pdf")):
        if p.is_file():
            return p
    return None


def _download_pdf_direct(arxiv_id: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "paper.pdf"
    timeout_s = (os.getenv("OPTIBENCH_ARXIV_TIMEOUT") or "120").strip()
    try:
        timeout_f = float(timeout_s)
    except ValueError:
        timeout_f = 120.0
    with requests.get(_direct_pdf_url(arxiv_id), stream=True, timeout=timeout_f) as resp:
        resp.raise_for_status()
        with pdf_path.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    return pdf_path


def get_arxiv_info(arxiv_id: str) -> dict[str, Any] | None:
    client = _arxiv_client()
    search = arxiv.Search(id_list=[arxiv_id])
    try:
        paper = next(client.results(search))
    except StopIteration:
        return None
    raw_id = getattr(paper, "entry_id", None) or ""
    aid = raw_id.split("/abs/")[-1].strip() if isinstance(raw_id, str) else arxiv_id
    return {
        "title": paper.title,
        "arxiv_id": aid,
        "summary": paper.summary or "",
        "pdf_url": getattr(paper, "pdf_url", None) or f"https://arxiv.org/pdf/{aid}.pdf",
        "authors": [a.name for a in paper.authors],
        "published": getattr(paper, "published", None),
    }


def search_arxiv(query: str, max_results: int = 10, *, domain: str | None = None) -> list[dict[str, Any]]:
    if domain is None:
        domain = os.getenv("OPTIBENCH_DOMAIN", "continuous")
    domain = (domain or "all").strip().lower()
    candidate_pool = max(max_results * 5, max_results)
    client = _arxiv_client()
    search = arxiv.Search(query=query, max_results=candidate_pool)
    out: list[dict[str, Any]] = []
    for p in client.results(search):
        categories = list(getattr(p, "categories", []) or [])
        if domain in {"continuous", "continuous-optimization"} and not _is_continuous_optimization_paper(
            title=p.title, summary=p.summary or "", categories=categories
        ):
            continue
        raw_id = getattr(p, "entry_id", None) or getattr(p, "arxiv_id", str(p))
        arxiv_id = raw_id.split("/abs/")[-1].strip() if isinstance(raw_id, str) else str(raw_id)
        out.append(
            {
                "title": p.title,
                "arxiv_id": arxiv_id,
                "summary": (p.summary or "")[:500],
                "pdf_url": p.pdf_url,
                "authors": [a.name for a in p.authors],
                "categories": categories,
            }
        )
        if len(out) >= max_results:
            break
    return out


def _is_continuous_optimization_paper(*, title: str, summary: str, categories: list[str]) -> bool:
    text = f"{title}\n{summary}".lower()
    cats = {c.lower() for c in categories}
    category_match = bool(cats.intersection({"math.oc", "math.na", "math.ap"}))
    include_terms = [
        "convex optimization",
        "non-convex optimization",
        "lagrangian",
        "kkt",
        "duality",
        "interior-point",
        "trust-region",
        "line search",
        "gradient method",
        "variational inequality",
        "semidefinite",
        "quadratic programming",
        "linear programming",
    ]
    include_match = any(t in text for t in include_terms)
    exclude_terms = [
        "reinforcement learning",
        "deep learning",
        "neural network",
        "transformer",
        "diffusion model",
        "language model",
        "llm",
        "bert",
        "gpt",
    ]
    exclude_match = any(t in text for t in exclude_terms)
    return (category_match or include_match) and not exclude_match


def download_arxiv_pdf(arxiv_id: str, out_dir: str | Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    client = _arxiv_client()
    search = arxiv.Search(id_list=[arxiv_id])
    try:
        paper = next(client.results(search))
        return Path(paper.download_pdf(dirpath=str(out_dir), download_domain=_arxiv_download_domain()))
    except StopIteration:
        raise ValueError(f"No paper found for arXiv ID: {arxiv_id}") from None
    except Exception:
        return _download_pdf_direct(arxiv_id, out_dir)


def download_paper(
    arxiv_id: str,
    out_dir: str | Path,
    *,
    convert_to_md: bool = True,
    save_md_file: bool = True,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    paper_dir = out_dir / arxiv_id.replace("/", "_")
    paper_dir.mkdir(parents=True, exist_ok=True)
    cached_pdf = _find_cached_pdf(paper_dir)
    use_cached = (os.getenv("OPTIBENCH_USE_CACHED_PDF") or "1").strip().lower() in {"1", "true", "yes"}
    title = f"arXiv {arxiv_id}"
    authors: list[str] = []
    summary = ""
    paper = None
    client = _arxiv_client()
    search = arxiv.Search(id_list=[arxiv_id])
    try:
        paper = next(client.results(search))
        title = paper.title
        authors = [a.name for a in paper.authors]
        summary = paper.summary or ""
    except StopIteration:
        raise ValueError(f"No paper found for arXiv ID: {arxiv_id}") from None
    except Exception:
        paper = None
    try:
        if use_cached and cached_pdf is not None:
            pdf_path = cached_pdf
        elif paper is not None:
            pdf_path = Path(paper.download_pdf(dirpath=str(paper_dir), download_domain=_arxiv_download_domain()))
        else:
            pdf_path = _download_pdf_direct(arxiv_id, paper_dir)
    except Exception:
        cached_after_error = _find_cached_pdf(paper_dir)
        if cached_after_error is not None:
            pdf_path = cached_after_error
        else:
            raise
    result: dict[str, Any] = {"pdf_path": pdf_path, "md_path": None, "md_content": None, "title": title, "authors": authors, "summary": summary}
    if convert_to_md:
        md_content = convert_pdf_to_markdown(str(pdf_path))
        header = (
            f"# {title}\n\n"
            f"**arXiv ID:** {arxiv_id}\n\n"
            f"**Authors:** {', '.join(authors) if authors else 'N/A'}\n\n"
            f"**Abstract:** {summary if summary else 'N/A (metadata fallback mode)'}\n\n---\n\n"
        )
        result["md_content"] = header + md_content
        if save_md_file:
            md_path = paper_dir / "paper.md"
            md_path.write_text(result["md_content"], encoding="utf-8")
            result["md_path"] = md_path
    return result
