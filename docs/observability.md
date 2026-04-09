# Observability

OptiBench now supports structured execution context in logs:

- `run_id`: one batch execution ID
- `paper_id`: current arXiv ID
- `stage`: current stage (`batch`, `download`, `pipeline`, etc.)

## Enable JSON logs

Set in `.env`:

```env
OPTIBENCH_LOG_JSON=1
```

Then run the CLI normally. Each log line is a JSON object for easier ingestion by log systems.

## Plain logs with context

Default plain logs also include context fields:

`[run=<run_id> paper=<paper_id> stage=<stage>]`

Use these fields to correlate failures in `run_summary.json` and `pipeline_metrics.json`.
