# Runbook

## 1) Pre-flight checklist

- `.env` configured (`OPTIBENCH_PROVIDER`, model, API key/base URL)
- Optional: `OPTIBENCH_WORKERS` tuned for machine/network capacity
- Dependencies installed (`uv pip install -e .`)

## 2) Common run patterns

Single arXiv paper:

```bash
python main.py --arxiv-id 1406.0899 --skip-lean
```

Batch by query with concurrency:

```bash
python main.py "convex optimization" --top-k 5 --workers 2
```

## 3) Operational outputs

- Per paper: `dataset/<arxiv_id>/result.json`
- Per paper metrics: `dataset/<arxiv_id>/pipeline_metrics.json`
- Batch summary: `dataset/run_summary.json`

## 4) Failure triage order

1. Check log context (`run_id`, `paper_id`, `stage`)
2. Inspect `pipeline_metrics.json` for stage-level `failure_type`
3. Confirm provider/network config for upstream failures
4. Re-run with lower `--workers` if rate-limited
