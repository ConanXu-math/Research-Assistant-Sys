#!/usr/bin/env python3
"""诊断 arXiv 连接问题，帮助定位「请求超时」的根本原因。

根本原因说明：
  - 本程序访问的是 export.arxiv.org（arXiv 官方 API），服务器在国外。
  - 在国内网络环境下，该域名常被限速或无法直连，TCP 建连/首包很慢或失败，
    表现为：一直卡在 "Requesting page (first: True, try: 0/1/2/3)" 然后超时。
  - arxiv 官方自 2024 年 9 月起已关闭镜像网络，无官方镜像可用。
  - 国内常见的网页/PDF 镜像（如 xxx.itp.ac.cn）一般不提供 export 的 API 接口，
    无法替代 export.arxiv.org 做搜索/列表。

治本方案（任选其一）：
  1. 配置 HTTP 代理或 VPN，使本机可访问 export.arxiv.org，然后设置：
       set HTTP_PROXY=http://你的代理:端口
       set HTTPS_PROXY=http://你的代理:端口
     （Linux/macOS 用 export 代替 set）
  2. 在可直连 arXiv 的网络下运行（例如海外服务器、校园网出口等）。

用法:
  python scripts/diagnose_arxiv_connection.py
  # 或从项目根目录:
  python -m scripts.diagnose_arxiv_connection
"""

from __future__ import annotations

import os
import sys

# 加载 .env（与 main.py 一致）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 项目根目录
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

ARXIV_API_BASE = (os.getenv("OPTIBENCH_ARXIV_BASE_URL") or "").strip().rstrip("/")
if not ARXIV_API_BASE:
    ARXIV_API_BASE = "https://export.arxiv.org"
if not ARXIV_API_BASE.startswith(("http://", "https://")):
    ARXIV_API_BASE = "https://" + ARXIV_API_BASE
TEST_URL = f"{ARXIV_API_BASE}/api/query?search_query=all:electron&max_results=1&start=0"


def main() -> None:
    print("=== arXiv 连接诊断 ===\n")
    print(f"  测试 URL: {TEST_URL}")
    print(f"  环境: HTTP_PROXY={os.getenv('HTTP_PROXY', '(未设置)')!r}")
    print(f"        HTTPS_PROXY={os.getenv('HTTPS_PROXY', '(未设置)')!r}\n")

    # 短超时，快速判断「能连 / 不能连」；用 requests 以与主程序一致（会走 HTTP_PROXY/HTTPS_PROXY）
    timeout_sec = 15
    print(f"  使用 {timeout_sec} 秒超时进行连接测试…\n")

    try:
        import requests
        resp = requests.get(
            TEST_URL,
            timeout=timeout_sec,
            headers={"User-Agent": "Research-Assistant-Sys-diagnose/1.0"},
        )
        status = resp.status_code
        body = resp.content
    except Exception as e:
        print("  结果: 连接失败\n")
        print("  可能原因:")
        print("    1. 当前网络无法访问 export.arxiv.org（国内常见：被限速或无法直连）")
        print("    2. 防火墙/代理拦截")
        print("    3. 本机未配置可用的 HTTP/HTTPS 代理\n")
        print("  建议:")
        print("    - 设置 HTTP_PROXY / HTTPS_PROXY 后重试，或使用 VPN")
        print("    - 在可直连 arXiv 的网络（如海外/校园网出口）下运行\n")
        print(f"  错误详情: {type(e).__name__}: {e}")
        sys.exit(1)

    if status != 200:
        print(f"  结果: HTTP {status}\n")
        sys.exit(1)

    print("  结果: 连接成功，API 可访问。")
    print(f"  响应长度: {len(body)} 字节\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
