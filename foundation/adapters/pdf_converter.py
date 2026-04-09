"""PDF-to-Markdown conversion with fallback chain."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

logger = logging.getLogger("optibench.pdf")


def _find_bin(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    venv_bin = Path(sys.prefix) / "bin" / name
    if venv_bin.is_file() and os.access(venv_bin, os.X_OK):
        return str(venv_bin)
    return None


def convert_pdf_to_markdown(pdf_path: str) -> str:
    pdf = Path(pdf_path)
    if not pdf.exists():
        return f"ERROR: file not found - {pdf_path}"
    backend = os.getenv("OPTIBENCH_PDF_BACKEND", "pypdf").strip().lower()
    if backend == "pypdf":
        return _convert_with_pypdf(pdf)
    if backend == "marker":
        return _convert_with_marker(pdf)
    if backend == "nougat":
        return _convert_with_nougat(pdf)
    if backend in ("mineru", "http-ocr", "http_ocr", "remote-ocr", "remote_ocr"):
        return _convert_with_mineru(pdf)
    if _find_bin("marker_single") or _find_bin("marker"):
        result = _convert_with_marker(pdf)
        if not result.startswith("ERROR"):
            return result
    if _find_bin("nougat"):
        result = _convert_with_nougat(pdf)
        if not result.startswith("ERROR"):
            return result
    return _convert_with_pypdf(pdf)


def _convert_with_pypdf(pdf: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return "ERROR: pypdf not installed."
    try:
        reader = PdfReader(str(pdf))
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"<!-- page {i + 1} -->\n{text}")
        if not pages:
            return "ERROR: pypdf extracted no text from the PDF."
        return "\n\n".join(pages)
    except Exception as exc:
        return f"ERROR: pypdf failed - {exc}"


def _convert_with_mineru(pdf: Path) -> str:
    try:
        import io
        import zipfile
        import requests
    except Exception as exc:
        return f"ERROR: mineru requirements missing - {exc}"
    token = (os.getenv("OPTIBENCH_MINERU_TOKEN") or os.getenv("MINERU_API_TOKEN") or "").strip()
    if not token:
        return "ERROR: mineru backend requires OPTIBENCH_MINERU_TOKEN."
    model_version = (os.getenv("OPTIBENCH_MINERU_MODEL_VERSION") or "vlm").strip() or "vlm"
    timeout_s = float((os.getenv("OPTIBENCH_MINERU_TIMEOUT") or "120").strip())
    poll_interval_s = float((os.getenv("OPTIBENCH_MINERU_POLL_INTERVAL") or "3").strip())
    poll_timeout_s = float((os.getenv("OPTIBENCH_MINERU_POLL_TIMEOUT") or "300").strip())
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    apply_resp = requests.post(
        "https://mineru.net/api/v4/file-urls/batch",
        headers=headers,
        json={"files": [{"name": pdf.name, "data_id": pdf.stem}], "model_version": model_version},
        timeout=timeout_s,
    )
    if apply_resp.status_code != 200:
        return f"ERROR: mineru apply HTTP {apply_resp.status_code}"
    apply_data = apply_resp.json()
    if apply_data.get("code") != 0:
        return f"ERROR: mineru apply failed: {apply_data.get('msg')}"
    batch_id = (apply_data.get("data") or {}).get("batch_id")
    file_urls = (apply_data.get("data") or {}).get("file_urls") or []
    if not batch_id or not file_urls:
        return "ERROR: mineru apply response missing batch_id or file_urls."
    with pdf.open("rb") as f:
        upload_resp = requests.put(file_urls[0], data=f, timeout=timeout_s)
    if upload_resp.status_code not in (200, 201):
        return f"ERROR: mineru upload HTTP {upload_resp.status_code}"
    poll_url = f"https://mineru.net/api/v4/extract-results/batch/{batch_id}"
    start_ts = time.time()
    full_zip_url = ""
    while True:
        if time.time() - start_ts > poll_timeout_s:
            return f"ERROR: mineru poll timeout after {int(poll_timeout_s)}s."
        poll_resp = requests.get(poll_url, headers=headers, timeout=timeout_s)
        if poll_resp.status_code != 200:
            return f"ERROR: mineru poll HTTP {poll_resp.status_code}"
        poll_data = poll_resp.json()
        if poll_data.get("code") != 0:
            return f"ERROR: mineru poll failed: {poll_data.get('msg')}"
        items = ((poll_data.get("data") or {}).get("extract_result") or [])
        if not items:
            return "ERROR: mineru poll response missing extract_result."
        item = items[0]
        if item.get("state") == "done":
            full_zip_url = item.get("full_zip_url") or ""
            break
        if item.get("state") == "failed":
            return f"ERROR: mineru parse failed: {item.get('err_msg')}"
        time.sleep(poll_interval_s)
    if not full_zip_url:
        return "ERROR: mineru done but full_zip_url is empty."
    zip_resp = requests.get(full_zip_url, timeout=timeout_s)
    if zip_resp.status_code != 200:
        return f"ERROR: mineru download zip HTTP {zip_resp.status_code}"
    with zipfile.ZipFile(io.BytesIO(zip_resp.content), "r") as zf:
        if "full.md" not in zf.namelist():
            return "ERROR: mineru zip missing full.md."
        content = zf.read("full.md").decode("utf-8", errors="replace")
    return content if content.strip() else "ERROR: mineru full.md is empty."


def _convert_with_marker(pdf: Path) -> str:
    outdir = tempfile.mkdtemp(prefix="optibench_marker_")
    ms = _find_bin("marker_single")
    cmd = [ms, str(pdf), "--output_dir", outdir, "--output_format", "markdown"] if ms else [_find_bin("marker") or "marker", "convert", str(pdf), "--output_dir", outdir, "--output_format", "markdown"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=int(os.getenv("OPTIBENCH_MARKER_TIMEOUT", "300")))
        md_files = list(Path(outdir).rglob("*.md"))
        if not md_files:
            return f"ERROR: marker produced no output. {result.stderr.strip()[:300]}"
        return md_files[0].read_text(encoding="utf-8")
    except FileNotFoundError:
        return "ERROR: marker command not found."
    except subprocess.TimeoutExpired:
        return "ERROR: marker timed out."
    finally:
        shutil.rmtree(outdir, ignore_errors=True)


def _convert_with_nougat(pdf: Path) -> str:
    outdir = tempfile.mkdtemp(prefix="optibench_nougat_")
    try:
        subprocess.run(["nougat", str(pdf), "-o", outdir], capture_output=True, text=True, timeout=int(os.getenv("OPTIBENCH_NOUGAT_TIMEOUT", "300")))
        candidates = list(Path(outdir).rglob("*.mmd")) or list(Path(outdir).rglob("*.md"))
        if not candidates:
            return "ERROR: nougat produced no output."
        return candidates[0].read_text(encoding="utf-8")
    except FileNotFoundError:
        return "ERROR: nougat command not found."
    except subprocess.TimeoutExpired:
        return "ERROR: nougat timed out."
    finally:
        shutil.rmtree(outdir, ignore_errors=True)
