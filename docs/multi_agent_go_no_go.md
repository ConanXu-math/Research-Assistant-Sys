# Multi-Agent Go/No-Go Checklist

Use this checklist after running regression suite(s) to decide whether the
project is ready to enter external adapter work (`opencode` / `ClaudeCode`).

## Inputs

- `dataset/regression/regression_suite_result.json`
- `dataset/regression/run_summary.json` (per run)
- `dataset/<arxiv_id>/pipeline_metrics.json`

## Decision Matrix

### 1) Stability Gate

- [ ] Overall success rate does not regress against previous baseline.
- [ ] `extract` stage failure_type distribution is stable (no spike in `schema_parse` / `timeout`).
- [ ] `code` and `formalize` repeated `validation_fail` count trends downward.

### 2) Observability Gate

- [ ] >= 90% failed runs include structured `failure_type` in stage metrics.
- [ ] Failed runs have enough context in `detail` for root-cause analysis.
- [ ] `pipeline_metrics_partial` is present for failed runs in batch summary.

### 3) Branch Strategy Gate

- [ ] `unified` and `locator_first` both have measurable outcomes.
- [ ] `auto` strategy picks `locator_first` only for long/math-dense papers.
- [ ] Branch switching rules are deterministic and documented.

### 4) Contract Gate

- [ ] Extraction contract (`PipelineExtractionResult`) is consistently parseable.
- [ ] Coding contract (`CodingOutput`) parse and validation paths are consistent.
- [ ] Formalization contract (`FormalizationOutput`) parse and validation paths are consistent.

## Go Criteria

Mark **GO** when all gates above pass for at least one full regression run
(recommended 10+ papers), and no critical blocker remains open.

## No-Go Criteria

Mark **NO-GO** when one of these occurs:

- Success rate regression > acceptable threshold.
- Missing structured failure types in frequent failure paths.
- Branch strategy behavior cannot be explained/reproduced.

## Current Decision

- Date:
- Strategy:
- Result: GO / NO-GO
- Notes:

