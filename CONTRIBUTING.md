# Contributing

Thanks for helping people keep accurate records.

- Principle: **the tool never invents a fact.** No auto-filled dates, hours or contacts. Make accuracy easy and fabrication hard.
- Never include real personal data (names, employers, claim numbers, SSNs) in code, tests, issues or examples.
- Keep it local-first: no network calls, accounts or telemetry.
- Rules come from official agency documents. Cite them in the PR.

```bash
pip install -e ".[dev]"
pytest && ruff check . && ruff format --check .
```
