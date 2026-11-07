# Pedro — Asistente de Compras

Pedro es un asistente académico de compras ficticias. **Estado actual:** núcleo determinista, seis herramientas del agente, text-to-query acotado, persistencia, verificación, cinco notebooks y Streamlit con comparación local y chat online. El chat online necesita credenciales y todavía no tiene evidencia de ejecución con un modelo real. Consulte el [estado verificable](docs/estado.md), la [arquitectura](docs/pedro_asistente_de_compras.mmd) y la [revisión EGM](docs/goldfish_review_report.md).

El repositorio se llama `pedro_asistente_de_compras`. El paquete Python conserva el nombre interno `compraslab` y las variables `COMPRASLAB_*` siguen vigentes para mantener compatibles los imports, notebooks y configuraciones existentes.

## Desarrollo local

El proyecto usa Python 3.13 y un entorno aislado en `.venv/`.

Para administrar la interfaz en Linux:

```bash
./project.sh start
./project.sh status
./project.sh restart
./project.sh stop
```

La app abre en `http://localhost:8501`. El script guarda el PID y el registro en `storage/run/`, y reconoce una instancia del mismo proyecto ya iniciada manualmente en ese puerto. Para usar otro puerto, anteponga `COMPRASLAB_PORT=8765` a cada comando. Debe existir `.venv/`; créelo con el comando `uv sync` indicado abajo.

También puede ejecutar las herramientas directamente:

```bash
uv sync --python 3.13 --all-extras --locked
source .venv/bin/activate
python --version
python -m pytest -q
streamlit run app.py
jupyter lab notebooks
deactivate
```

En Windows PowerShell, active con `.venv\Scripts\Activate.ps1`; al terminar use `deactivate`. Si prefiere no activar el entorno, ejecute `uv run pytest -q`, `uv run streamlit run app.py` o `uv run jupyter lab notebooks`.

Para el chat online, ejecute `cp .env.example .env`, configure `OPENAI_API_KEY` y vuelva a iniciar Streamlit; la aplicación carga `.env` al arrancar. `LANGSMITH_TRACING=true` y `LANGSMITH_API_KEY` habilitan trazas reales cuando se configuren. En modo simulado, solo ViaCEP se sustituye por un adaptador identificado; las respuestas del modelo no se simulan en la interfaz.

Si se recibe el índice FAISS preconstruido, guárdelo en `knowledge/politicas/` junto con `index.faiss`, `index.pkl` y un `manifest.json` con `embedding_model`, `dimension`, `origen` y `documentos`. Revise su procedencia antes de establecer `COMPRASLAB_TRUST_POLICY_INDEX=true`: el docstore usa pickle. El adaptador actual acepta modelos OpenAI `text-embedding-*` que coincidan con el índice.

El kit, la rúbrica del profesor y el índice FAISS de compras no estaban disponibles al iniciar. La prueba de Demo B usa únicamente los valores proporcionados en la solicitud y **no sustituye la referencia original**.
