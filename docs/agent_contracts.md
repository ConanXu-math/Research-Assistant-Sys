# Agent Contracts

This document defines stable input/output contracts and failure semantics for the
core multi-agent execution stages.

## Stage 2: Pipeline Extraction Agent

- **Input context**
  - Paper markdown (possibly pre-processed via `locator_first` strategy).
  - Retry fix hints from previous attempts (`fix_prompt`).
- **Output schema**
  - `PipelineExtractionResult`:
    - `outline: MathOutline`
    - `score: int`
    - `is_acceptable: bool`
    - `issues: list[str]`
    - `fix_prompt: str`
- **Recoverable failures**
  - `schema_parse`, `upstream_api`, `timeout` -> retry.
- **Non-recoverable failures**
  - Persistent invalid outputs after max retries -> stage outcome `failed`.

## Stage 3: Coding Agent

- **Input context**
  - `MathOutline` JSON.
  - Previous validator error and previous code on retry.
- **Output schema**
  - `CodingOutput`:
    - `pseudocode: str`
    - `pycode: str`
- **Recoverable failures**
  - `schema_parse`, `upstream_api`, `validation_fail`, `timeout` -> retry.
- **Non-recoverable failures**
  - Empty/invalid structured output after max retries -> stage `failed`.

## Stage 4: Formalization Agent

- **Input context**
  - `MathOutline` JSON.
  - Previous Lean validator diagnostics on retry.
- **Output schema**
  - `FormalizationOutput`:
    - `prove_cot: str`
    - `lean4_formal: str`
- **Recoverable failures**
  - `schema_parse`, `upstream_api`, `validation_fail`, `timeout` -> retry.
- **Non-recoverable failures**
  - Empty/invalid structured output after max retries -> stage `failed`.

## Failure Taxonomy

All stages should map errors into:

- `upstream_api`
- `schema_parse`
- `validation_fail`
- `timeout`
- `tool_error`
- `config_error`
- `skipped`
- `unknown`

These are persisted in `pipeline_metrics.json` as `failure_type`.
