#!/usr/bin/env python3
"""测试 MinerU 提取任务接口（单个 URL / 本地文件单个或批量）。

用法:
  # URL 模式（单个）
  python scripts/test_mineru_extract.py --token <你的token> --mode single-url --poll --download-zip --unzip

  # 本地文件模式（可单个可批量）
  python scripts/test_mineru_extract.py --token <你的token> --mode batch-file --files demo.pdf a.pdf --poll --download-zip --unzip

  # 只查询已有任务（不重复提交）
  python scripts/test_mineru_extract.py --token <你的token> --task-id <task_id> --poll
  python scripts/test_mineru_extract.py --token <你的token> --batch-id <batch_id> --poll

也可以通过环境变量传 token:
  set MINERU_API_TOKEN=你的token
  python scripts/test_mineru_extract.py
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

import requests


API_URL = "https://mineru.net/api/v4/extract/task"
FILE_URLS_BATCH_API_URL = "https://mineru.net/api/v4/file-urls/batch"
BATCH_RESULT_API_URL = "https://mineru.net/api/v4/extract-results/batch"
DEFAULT_PDF_URL = "https://cdn-mineru.openxlab.org.cn/demo/example.pdf"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="测试 MinerU extract/task 接口")
    parser.add_argument(
        "--token",
        default=(os.getenv("OPTIBENCH_MINERU_TOKEN") or "").strip(),
        help="MinerU API token（默认读取环境变量 OPTIBENCH_MINERU_TOKEN）",
    )
    parser.add_argument(
        "--task-id",
        default="",
        help="已有 task_id。提供后将跳过提交，直接查询/轮询。",
    )
    parser.add_argument(
        "--batch-id",
        default="",
        help="已有 batch_id。提供后将跳过提交，直接查询/轮询。",
    )
    parser.add_argument(
        "--mode",
        choices=["single-url", "batch-file"],
        default="single-url",
        help="提交模式：single-url（URL 单任务）或 batch-file（本地文件单个/批量）",
    )
    parser.add_argument(
        "--pdf-url",
        default=DEFAULT_PDF_URL,
        help=f"待提取的 PDF URL（默认: {DEFAULT_PDF_URL}）",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        default=[],
        help="本地文件路径列表（batch-file 模式使用，可传 1 个或多个）",
    )
    parser.add_argument(
        "--model-version",
        default="vlm",
        help="模型版本（默认: vlm）",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="请求超时时间（秒，默认: 30）",
    )
    parser.add_argument(
        "--poll",
        action="store_true",
        help="提交任务后轮询任务状态直到 done/failed",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=3.0,
        help="轮询间隔秒数（默认: 3）",
    )
    parser.add_argument(
        "--poll-timeout",
        type=float,
        default=300.0,
        help="轮询总超时秒数（默认: 300）",
    )
    parser.add_argument(
        "--download-zip",
        action="store_true",
        help="任务完成后下载 full_zip_url 到本地",
    )
    parser.add_argument(
        "--unzip",
        action="store_true",
        help="下载后自动解压 zip（建议与 --download-zip 一起使用）",
    )
    parser.add_argument(
        "--output-dir",
        default="tmp/mineru",
        help="下载目录（默认: tmp/mineru）",
    )
    return parser.parse_args()


def query_task(task_id: str, headers: dict[str, str], timeout: float) -> dict:
    query_url = f"{API_URL}/{task_id}"
    response = requests.get(query_url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def query_batch(batch_id: str, headers: dict[str, str], timeout: float) -> dict:
    query_url = f"{BATCH_RESULT_API_URL}/{batch_id}"
    response = requests.get(query_url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def download_file(url: str, output_path: Path, timeout: float) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        with output_path.open("wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def extract_zip(zip_path: Path, extract_dir: Path) -> None:
    import zipfile

    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)


def print_key_outputs(extract_dir: Path) -> None:
    full_md = extract_dir / "full.md"
    layout_json = extract_dir / "layout.json"
    content_json = extract_dir / "content_list_v2.json"
    print("解压目录:", extract_dir)
    print("关键文件:")
    print(" - full.md:", full_md if full_md.exists() else "(不存在)")
    print(" - layout.json:", layout_json if layout_json.exists() else "(不存在)")
    print(" - content_list_v2.json:", content_json if content_json.exists() else "(不存在)")


def submit_single_url(args: argparse.Namespace, headers: dict[str, str]) -> str:
    payload = {
        "url": args.pdf_url,
        "model_version": args.model_version,
    }
    print("请求地址:", API_URL)
    print("请求参数:", json.dumps(payload, ensure_ascii=False))
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=args.timeout)
    except requests.RequestException as exc:
        print(f"请求失败: {type(exc).__name__}: {exc}")
        sys.exit(2)

    print("status_code:", response.status_code)
    try:
        data = response.json()
    except ValueError:
        print("响应不是 JSON，原始文本如下:")
        print(response.text)
        sys.exit(3)
    print("response.json():")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    if response.status_code != 200 or data.get("code") != 0:
        print("创建任务失败，结束。")
        sys.exit(4)
    task_id = (data.get("data") or {}).get("task_id", "")
    if not task_id:
        print("未拿到 task_id，结束。")
        sys.exit(5)
    return task_id


def submit_batch_files(args: argparse.Namespace, headers: dict[str, str]) -> str:
    if not args.files:
        print("错误: batch-file 模式必须提供 --files。")
        sys.exit(10)

    file_paths = [Path(p) for p in args.files]
    for p in file_paths:
        if not p.exists() or not p.is_file():
            print(f"错误: 文件不存在或不是文件: {p}")
            sys.exit(11)

    payload = {
        "files": [{"name": p.name, "data_id": p.stem} for p in file_paths],
        "model_version": args.model_version,
    }
    print("请求地址:", FILE_URLS_BATCH_API_URL)
    print("请求参数:", json.dumps(payload, ensure_ascii=False))

    try:
        response = requests.post(FILE_URLS_BATCH_API_URL, headers=headers, json=payload, timeout=args.timeout)
    except requests.RequestException as exc:
        print(f"申请上传链接失败: {type(exc).__name__}: {exc}")
        sys.exit(12)

    print("status_code:", response.status_code)
    try:
        data = response.json()
    except ValueError:
        print("响应不是 JSON，原始文本如下:")
        print(response.text)
        sys.exit(13)
    print("response.json():")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    if response.status_code != 200 or data.get("code") != 0:
        print("申请上传链接失败，结束。")
        sys.exit(14)

    batch_id = (data.get("data") or {}).get("batch_id", "")
    urls = (data.get("data") or {}).get("file_urls") or []
    if not batch_id or not urls:
        print("未拿到 batch_id 或 file_urls，结束。")
        sys.exit(15)
    if len(urls) != len(file_paths):
        print("返回 file_urls 数量与本地文件数量不一致，结束。")
        sys.exit(16)

    for path, upload_url in zip(file_paths, urls):
        print(f"上传文件: {path}")
        try:
            with path.open("rb") as f:
                res_upload = requests.put(upload_url, data=f, timeout=args.timeout)
        except requests.RequestException as exc:
            print(f"上传失败: {path} -> {type(exc).__name__}: {exc}")
            sys.exit(17)
        if res_upload.status_code not in (200, 201):
            print(f"上传失败: {path}, status={res_upload.status_code}")
            sys.exit(18)
        print(f"上传成功: {path.name}")
    return batch_id


def main() -> None:
    args = parse_args()
    token = args.token
    if not token:
        print("错误: 未提供 token。请用 --token 或设置环境变量 MINERU_API_TOKEN。")
        sys.exit(1)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    print("token 前缀:", token[:8] + ("..." if len(token) > 8 else ""))

    task_id = args.task_id.strip()
    batch_id = args.batch_id.strip()
    if task_id and batch_id:
        print("错误: --task-id 与 --batch-id 只能提供一个。")
        sys.exit(19)

    if not task_id and not batch_id:
        if args.mode == "single-url":
            task_id = submit_single_url(args, headers)
        else:
            batch_id = submit_batch_files(args, headers)
            print(f"batch_id: {batch_id}")
            print(f"可用以下接口查询结果: {BATCH_RESULT_API_URL}/{batch_id}")
    elif task_id:
        print(f"使用已有 task_id: {task_id}")
    else:
        print(f"使用已有 batch_id: {batch_id}")

    if not args.poll:
        if task_id:
            print(f"可用以下接口查询结果: {API_URL}/{task_id}")
        else:
            print(f"可用以下接口查询结果: {BATCH_RESULT_API_URL}/{batch_id}")
        return

    poll_label = f"task_id={task_id}" if task_id else f"batch_id={batch_id}"
    print(f"开始轮询 {poll_label}")
    start_at = time.time()
    final_result: dict | None = None

    while True:
        elapsed = time.time() - start_at
        if elapsed > args.poll_timeout:
            if task_id:
                print(f"轮询超时（{args.poll_timeout:.0f}s），请稍后手动查询: {API_URL}/{task_id}")
            else:
                print(f"轮询超时（{args.poll_timeout:.0f}s），请稍后手动查询: {BATCH_RESULT_API_URL}/{batch_id}")
            sys.exit(6)
        try:
            if task_id:
                result = query_task(task_id=task_id, headers=headers, timeout=args.timeout)
            else:
                result = query_batch(batch_id=batch_id, headers=headers, timeout=args.timeout)
        except requests.RequestException as exc:
            print(f"查询失败: {type(exc).__name__}: {exc}")
            time.sleep(args.poll_interval)
            continue

        data_obj = result.get("data") or {}
        if task_id:
            state = data_obj.get("state")
            print(f"[{int(elapsed)}s] state: {state}")
            if state in {"done", "failed"}:
                final_result = result
                break
        else:
            extract_results = data_obj.get("extract_result") or []
            states = [item.get("state") for item in extract_results]
            print(f"[{int(elapsed)}s] states: {states}")
            done = all(s in {"done", "failed"} for s in states) and len(states) > 0
            if done:
                final_result = result
                break
        time.sleep(args.poll_interval)

    print("最终查询结果:")
    print(json.dumps(final_result, ensure_ascii=False, indent=2))

    if not args.download_zip:
        return

    final_data = (final_result or {}).get("data") or {}
    download_jobs: list[tuple[str, str]] = []
    if task_id:
        if final_data.get("state") == "failed":
            print("任务失败原因:", final_data.get("err_msg"))
            sys.exit(7)
        full_zip_url = final_data.get("full_zip_url")
        if full_zip_url:
            download_jobs.append((task_id, full_zip_url))
    else:
        for item in final_data.get("extract_result") or []:
            if item.get("state") == "done" and item.get("full_zip_url"):
                job_id = str(item.get("data_id") or item.get("file_name") or "item")
                download_jobs.append((job_id, item["full_zip_url"]))
            elif item.get("state") == "failed":
                print(f"子任务失败: {item.get('file_name')} -> {item.get('err_msg')}")

    if not download_jobs:
        print("没有可下载的 full_zip_url。")
        return

    for job_id, zip_url in download_jobs:
        safe_id = job_id.replace("/", "_").replace("\\", "_")
        output_base = Path(args.output_dir) / safe_id
        zip_path = output_base / "result.zip"
        print(f"下载: {zip_url}")
        try:
            download_file(zip_url, output_path=zip_path, timeout=args.timeout)
        except requests.RequestException as exc:
            print(f"下载失败: {type(exc).__name__}: {exc}")
            continue
        print(f"已下载到: {zip_path}")

        if args.unzip:
            extract_dir = output_base / "unzipped"
            try:
                extract_zip(zip_path, extract_dir)
            except Exception as exc:  # noqa: BLE001
                print(f"解压失败: {type(exc).__name__}: {exc}")
                continue
            print_key_outputs(extract_dir)


if __name__ == "__main__":
    main()
