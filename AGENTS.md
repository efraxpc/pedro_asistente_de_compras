# Repository Guidelines

## Structure

`app.py` is the Streamlit entry point. Reusable logic lives in `src/pedro/`: `catalog.py` and `business.py` handle scenarios and exact comparisons; `guardrails.py` screens each message before the agent; `agent.py`, `query.py`, `rag.py`, and `nli.py` handle the agent and verification; `modelos.py` picks the chat model (OpenAI or an OpenAI-compatible server); `memory.py` persists sessions and preferences. Add focused tests in `tests/test_*.py`. `datasets/` contains the synthetic SQLite catalog, `scripts/` its generator and artifact scripts, `notebooks/` the five teaching demos, `evals/` the derived cases and LangSmith runner, and `docs/` the report and evidence. Runtime files belong in ignored `storage/`. Code, docs, and UI text are in Brazilian Portuguese; follow the naming glossary in `docs/glossario_migracao.md`.

## Commands

- `uv sync --python 3.13 --all-extras --locked`: install locked dependencies.
- `uv run pytest -q`: run tests.
- `uv run python scripts/gerar_catalogo_pecas.py`: regenerate the synthetic catalog.
- `uv run python scripts/executar_notebooks.py`: execute and save the notebook outputs.
- `uv run streamlit run app.py`: run the UI at `http://localhost:8501`.
- `./project.sh start` (also `restart`, `stop`, `status`): manage the local app; set `PEDRO_PORT=8765` for another port.
- `uv run python evals/avaliar_fluxo.py`: evaluate the final flow when OpenAI and LangSmith credentials are configured.

## Style and Tests

Use Python 3.13, four-space indentation, `snake_case` names, and type hints on public functions. Keep UI in `app.py` and reusable rules in `src/pedro/`. Use `tmp_path` for file-backed tests and deterministic fixtures for comparison rules. Run the full test suite before submitting changes. Type-check edited code with `ty` when available.

## Data, Secrets, and Evidence

Never commit `.env`, `storage/`, or API keys. The SQLite catalog and offers are fictitious. Preserve `dataset_id` isolation and compare integer centavos, not floats. Keep external calls and test doubles labeled separately in `docs/evidencias.md`. Only enable `PEDRO_TRUST_POLICY_INDEX` after verifying the FAISS index source, manifest, hashes, model, dimension, metric, and document metadata; its docstore uses pickle. The matrix in `docs/matriz.md` uses the R01–R29 labels of the integrated guide in `guide/`; do not call it official until it is checked against the original Infnet enunciado. In `docs/rastros/`, the `*_antes.json`, `*_sin_plan.json`, and `r29_langsmith_*` files not ending in `_portugues.json` are historical runs of the earlier Spanish version: do not regenerate or edit them.
