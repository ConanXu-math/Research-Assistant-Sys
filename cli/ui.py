"""Simple CLI UI helpers for progress display."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StagePrinter:
    total: int

    def paper_header(self, index: int, arxiv_id: str) -> None:
        print("\n" + "=" * 60)
        print(f"[{index}/{self.total}] Processing arXiv {arxiv_id}")
        print("=" * 60)

    def stage(self, name: str, status: str) -> None:
        print(f"  - {name:<10}: {status}")

    def summary(self, *, total: int, success: int, failed: int, summary_path: str) -> None:
        print("\n" + "=" * 60)
        print("Batch finished!")
        print(f"  Total   : {total}")
        print(f"  Success : {success}")
        print(f"  Failed  : {failed}")
        print(f"  Summary : {summary_path}")
        print("=" * 60)
