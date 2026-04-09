# Troubleshooting

## Configuration error at startup

Symptoms:

- CLI exits before running pipeline
- Message includes `Configuration error`

Checks:

- `OPTIBENCH_PROVIDER` is valid (`openai`, `openai-like`, `ollama`, `anthropic`, `google`)
- For `openai-like`, `OPTIBENCH_BASE_URL` is set
- Numeric env vars are valid numbers (`OPTIBENCH_API_TIMEOUT`, `OPTIBENCH_WORKERS`)

## Download stage failed

Symptoms:

- `run_summary.json` shows `download failed`

Checks:

- arXiv/network access
- local PDF path exists when using `--pdf-path`
- proxy settings (`HTTP_PROXY`, `HTTPS_PROXY`)

## Repeated upstream/API failures

Symptoms:

- Stage failure type is `upstream_api` or `timeout`

Actions:

- reduce `--workers` to lower request pressure
- increase API timeout
- switch provider/model endpoint temporarily

## Poor extraction quality

Symptoms:

- empty/weak objective or variables in `outline.json`

Actions:

- increase `OPTIBENCH_EXTRACT_MAX_CHARS`
- set `OPTIBENCH_EXTRACTION_STRATEGY=locator_first` for long papers
- verify PDF-to-Markdown backend quality
