# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Pedro is a purchase-assistant agent for a fictitious appliance-parts catalog, built as an Infnet course project. All data (catalog, suppliers, stock, prices, policies) is synthetic. Code, comments, docs, and UI text are in Spanish — keep new code and user-facing strings in Spanish to match.

## Commands

```bash
uv sync --python 3.13 --all-extras --locked   # install locked deps (Python 3.13 required)
uv run pytest -q                              # run all tests
uv run pytest tests/test_core.py -q           # run one test file
uv run pytest tests/test_core.py::test_name   # run one test
uv run streamlit run app.py                   # run the UI (http://localhost:8501)
./project.sh start|status|restart|stop        # manage the app in background (PID/log in storage/run/; PEDRO_PORT=8765 for another port)
uv run python scripts/generar_catalogo_piezas.py  # regenerate synthetic SQLite catalog
uv run python scripts/crear_notebooks.py          # regenerate the 5 teaching notebooks
uv run python scripts/ejecutar_notebooks.py       # execute notebooks and save outputs
uv run python scripts/diagnosticar_t24.py --salida storage/evidencias/t24_demo.json  # T24 retrieval diagnostic (no OpenAI needed)
uv run python scripts/construir_indice_politicas.py  # rebuild the persisted policy index in knowledge/politicas/ (run after editing the corpus)
uv run python evals/evaluar_flujo.py          # LangSmith eval (requires OPENAI_API_KEY + LANGSMITH_API_KEY; never simulate metrics)
```

Type-check edited code with `ty` when available. Run the full test suite before submitting changes.

## Architecture

`app.py` is the only Streamlit entry point; all reusable logic lives in `src/pedro/`. The app works degraded without credentials (paginated listing, part detail, local comparison, comparison chat); `OPENAI_API_KEY` enables the agent and policy RAG.

**Data flow:** On first access the app creates a *scenario* — a UUID `dataset_id`, a copy of `datasets/piezas_electrodomesticos.sqlite3`, and a SHA-256 manifest — under ignored `storage/`. "New chat" keeps the scenario; "new scenario" creates a chat. Reopening a conversation restores its dataset or warns if missing. Preserve `dataset_id` isolation in any change.

**Core pipeline** (reads span several files):
- `catalog.py` — scenario creation and read-only SQLite queries.
- `contracts.py` + `business.py` — Pydantic contracts and purchase decision logic. **All money is integer centavos, never floats.**
- `query.py` — Pydantic plan → parameterized SELECT with trace (text-to-query).
- `dialogue.py` — per-turn constraint extraction; asks only for blocking data (quantity); budget/deadline are optional filters kept in session.
- `agent.py` — six tools wired into `create_openai_tools_agent`, one internal correction pass, `RunnableWithMessageHistory` that persists only the public reply. Also hosts the T24 partial-delivery route (`resolver_entrega_parcial`) and the `/t24` diagnostic rendering.
- `verification.py` + `nli.py` — every agent recommendation passes exact-source verification plus a local tri-class NLI gate before being shown; cited policy rules are published only if NLI supports them. Policy quotes are re-anchored to the literal text of the retrieved fragment (`anclar_citas`) before verification; if only the summary fails NLI, the flow publishes the literal quotes instead. CEP answers are filled from the ViaCEP tool observation of the same turn (`anclar_cep`). Principle: the model decides what to answer, the system supplies the data it already holds. Every verification attempt and its errors are recorded in `Traza`.
- `memory.py` — full messages, 12-message window, per-session purchase drafts, per-user preferences and FastEmbed episodes (SQLite-backed).
- `rag.py` — FAISS retrieval with metadata filtering; inspects a `manifest.json` (origin, embedding model, dimension, metric, per-file sha256) before allowing docstore deserialization.
- `policy_demo.py` + `knowledge/politicas_demo/` — extensive fictitious policy corpus indexed in-memory with FastEmbed/FAISS; the chat uses this demo index when no authorized index exists.
- `chains.py` + `laboratorio.py` — teaching chains (LCEL, `@chain`, and `crear_lcel_robusta` with a one-shot repair fallback and a strict complete-JSON check) and the broken-output lab that exercises them; not used by the chat flow.
- `prompts.py` — the two named reusable templates (`PLANTILLA_EXTRACCION`, `PLANTILLA_AGENTE`, PTCF) and the observable-action few-shot examples.

**Security gate:** the persisted index at `knowledge/politicas/` (our own, built from the fictitious corpus; committed with its manifest) requires `index.faiss`, `index.pkl`, and a complete `manifest.json`; its docstore is pickle, so `PEDRO_TRUST_POLICY_INDEX=true` must only be set after verifying provenance, hashes, model, dimension, metric, and metadata. The in-memory demo index never uses that flag.

**Env vars:** `OPENAI_API_KEY`, `PEDRO_MODEL`, `PEDRO_TRUST_POLICY_INDEX`, `PEDRO_PORT`, `LANGSMITH_API_KEY` (evals). Copy `.env.example` to `.env`; never commit `.env` or `storage/`.

## Style and tests

Python 3.13, four-space indentation, `snake_case`, type hints on public functions. Keep UI in `app.py` and reusable rules in `src/pedro/`. Tests go in `tests/test_*.py`; use `tmp_path` for file-backed tests and deterministic fixtures for comparison rules.

## Evidence and reporting constraints

- External calls and test doubles must be labeled separately in `docs/evidencias.md`; notebooks identify their test doubles explicitly.
- The matrix in `docs/matriz.md` maps evidence to the 29 rubrics (R01–R29) of the integrated guide in `guide/`; those codes are the guide's labels, and the final check against the original Portuguese enunciado is still pending.
- Derived eval cases in `evals/casos_derivados.json` are frozen and are not the official cases.
