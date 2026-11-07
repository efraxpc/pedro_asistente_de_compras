# Repository Guidelines

## Project Structure & Module Organization

`app.py` is the Streamlit entry point. Reusable shopping logic lives in `src/compraslab/`: `data.py` and `business.py` handle the fictional catalog and comparisons; `agent.py`, `tools.py`, `rag.py`, and `nli.py` support the agent; `memory.py` and `verification.py` handle persistence and answer checks. Add focused unit tests under `tests/test_*.py`. `datasets/` holds the appliance parts SQLite sample; `scripts/` holds its generator. `notebooks/` contains demos, `evals/` optional evaluation, `docs/` design and evidence, and `knowledge/` the optional policy index. Runtime files belong in ignored `storage/`.

## Build, Test, and Development Commands

- `uv sync --python 3.13 --all-extras --locked`: create `.venv` from `uv.lock` with UI, agent, notebook, and development dependencies.
- `uv run pytest -q`: run the test suite.
- `uv run streamlit run app.py`: run the app locally at `http://localhost:8501`.
- `./project.sh start` (also `status`, `restart`, `stop`): manage the local Streamlit process; set `COMPRASLAB_PORT=8765` to use another port.
- `uv run jupyter lab notebooks`: open the demos. `uv run python evals/evaluar_componentes.py` runs the optional LangSmith component evaluation when configured.

## Coding Style & Naming Conventions

Use Python 3.13, four-space indentation, `snake_case` for modules/functions/variables, and `PascalCase` for classes. Follow the existing Portuguese domain names and keep UI code in `app.py` while placing reusable rules in `src/compraslab/`. Add type hints to new public functions. No formatter or linter is configured; match nearby code and keep imports grouped by standard library, third party, and local package.

## Testing Guidelines

Tests use `pytest` and names such as `test_core.py` and `test_dataset_semilla_e_identidades`. Add a focused regression test when changing catalog rules, memory, verification, or agent behavior. Use `tmp_path` for file-backed tests and deterministic fixtures for business rules. Run `uv run pytest -q` before submitting; no coverage threshold is configured.

## Commits, Pull Requests & Configuration

Recent commits use short English summaries such as `Rename project...` and `Refactor code structure...`; keep messages concise and action oriented. Pull requests should explain the behavior changed, list test commands and results, link a relevant issue when available, and include screenshots for visible UI changes. Copy `.env.example` to `.env` for local credentials; never commit `.env`, `storage/`, or API keys. Only enable `COMPRASLAB_TRUST_POLICY_INDEX` after checking the source of a FAISS index, because its docstore uses pickle.
