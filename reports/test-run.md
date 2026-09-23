# Test run (versioned evidence)

- Date: 2026-09-23
- Python: 3.11.9
- Command: `pytest --cov=src tests/`
- Result: **57 passed**, 0 failed
- Coverage: **89%** (`--cov=src`)
- Environment: local Windows venv from `requirements.lock.txt`

This report documents a clean execution of the suite after the P0 corrections. It does not claim observed-data accuracy or energy savings.

Generated model binaries and MLflow runs remain gitignored. Reproduce artifacts with `python scripts/run_pipeline.py` and inspect `results/manifest.json`.
