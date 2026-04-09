## Three-Layer Project Management

### Interface Layer
- Path: `interface/`
- Responsibility: CLI/REPL entrypoints, argument parsing, user-facing output.
- Rule: do not place domain logic here.

### Orchestration Layer
- Path: `orchestrator/`
- Responsibility: intent routing, execution planning, result assembling.
- Rule: depend on expert contracts/registry, not concrete UI.

### Expert Layer
- Path: `experts/`
- Responsibility: implement task experts (search, extraction, QA, comparison, repro, codegen, proof, legacy benchmark).
- Rule: each expert conforms to the same plugin contract and returns structured output.

### Compatibility Policy
- `main.py` remains as a thin compatibility wrapper to `interface.app`.
- legacy `cli/` modules are retained for backwards compatibility; new code should import from `interface/`.
