# Repository Guidelines

## Structure

`app.py` is the Streamlit entry point. Reusable logic lives in `src/pedro/`: `catalog.py` and `business.py` handle scenarios and exact comparisons; `agent.py`, `query.py`, `rag.py`, and `nli.py` handle the agent and verification; `memory.py` persists sessions and preferences. Add focused tests in `tests/test_*.py`. `datasets/` contains the synthetic SQLite catalog, `scripts/` its generator and artifact scripts, `notebooks/` the five teaching demos, `evals/` the derived cases and LangSmith runner, and `docs/` the report and evidence. Runtime files belong in ignored `storage/`.

## Commands

- `uv sync --python 3.13 --all-extras --locked`: install locked dependencies.
- `uv run pytest -q`: run tests.
- `uv run python scripts/generar_catalogo_piezas.py`: regenerate the synthetic catalog.
- `uv run python scripts/ejecutar_notebooks.py`: execute and save the notebook outputs.
- `uv run streamlit run app.py`: run the UI at `http://localhost:8501`.
- `./project.sh start` (also `restart`, `stop`, `status`): manage the local app; set `PEDRO_PORT=8765` for another port.
- `uv run python evals/evaluar_flujo.py`: evaluate the final flow when OpenAI and LangSmith credentials are configured.

## Style and Tests

Use Python 3.13, four-space indentation, `snake_case` names, and type hints on public functions. Keep UI in `app.py` and reusable rules in `src/pedro/`. Use `tmp_path` for file-backed tests and deterministic fixtures for comparison rules. Run the full test suite before submitting changes. Type-check edited code with `ty` when available.

## Data, Secrets, and Evidence

Never commit `.env`, `storage/`, or API keys. The SQLite catalog and offers are fictitious. Preserve `dataset_id` isolation and compare integer centavos, not floats. Keep external calls and test doubles labeled separately in `docs/evidencias.md`. Only enable `PEDRO_TRUST_POLICY_INDEX` after verifying the FAISS index source, manifest, hashes, model, dimension, metric, and document metadata; its docstore uses pickle. The provisional matrix must not be called official until the Infnet PDF is supplied and checked.
