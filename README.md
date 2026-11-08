# Pedro — Asistente de Compras

Pedro es un asistente académico de compras ficticias. **Estado actual:** núcleo determinista, seis herramientas del agente, text-to-query acotado, persistencia, verificación, cinco notebooks y Streamlit con comparación local y chat online. La interfaz crea escenarios únicamente desde la base SQLite local de piezas de electrodomésticos. Los productos y ofertas del escenario se guardan en una instantánea verificable. El chat online necesita credenciales y todavía no tiene evidencia de ejecución con un modelo real. Consulte el [estado verificable](docs/estado.md), la [arquitectura](docs/pedro_asistente_de_compras.mmd) y la [revisión EGM](docs/goldfish_review_report.md).

El repositorio también incluye un [catálogo ficticio de piezas de electrodomésticos](datasets/README.md) con 2.640 piezas y ofertas de proveedores nacionales e internacionales, generado de forma reproducible en SQLite.

El repositorio se llama `pedro_asistente_de_compras`. El paquete Python conserva el nombre interno `compraslab` y las variables `COMPRASLAB_*` siguen vigentes para mantener compatibles los imports, notebooks y configuraciones existentes.

## Desarrollo local

El proyecto usa Python 3.13 y un entorno aislado en `.venv/`.

Para administrar la interfaz en Linux:

```bash
./project.sh start
./project.sh logs
./project.sh status
./project.sh restart
./project.sh stop
```

La app abre en `http://localhost:8501`. `./project.sh` equivale a `./project.sh start`: inicia la app y muestra su registro continuamente en la consola. `Ctrl+C` deja de seguir los logs; la app continúa activa hasta `./project.sh stop`. `./project.sh logs` vuelve a mostrar el registro. El script guarda el PID y el registro en `storage/run/`; para usar otro puerto, anteponga `COMPRASLAB_PORT=8765` a cada comando. Debe existir `.venv/`; créelo con el comando `uv sync` indicado abajo.

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

La única fuente de productos es `datasets/piezas_electrodomesticos.sqlite3`, sin necesidad de red. Cada escenario guarda una copia de sus productos y ofertas y la fecha de captura en `storage/catalogos/<dataset_id>/manifest.json`. Los chats antiguos de otras fuentes conservan su historial, pero sus catálogos no se reactivan; pulse «Nuevo escenario» para usar SQLite. La vista «Catálogo de piezas» muestra las 2.640 piezas, con filtros, ficha técnica, compatibilidades, ofertas e historial de precios. En el chat, «Muéstrame todas las piezas», «Lista piezas página 2» y «Detalle de PROD-0001» funcionan sin clave de OpenAI; las listas se presentan en páginas de 20.

Para activar la búsqueda semántica de la tool `buscar_productos`, configure `OPENAI_API_KEY` y ejecute `uv run python scripts/indexar_piezas.py`. El comando envía los textos ficticios de las piezas a OpenAI una vez y guarda un índice local en `storage/indices/piezas/`; las consultas semánticas posteriores también usan la API de embeddings. Si falta la clave, el índice o este no coincide con la base SQLite, la tool conserva la búsqueda SQL exacta. El índice ofrece candidatos: la compatibilidad y las ofertas se verifican por separado.

Si se recibe el índice FAISS preconstruido, guárdelo en `knowledge/politicas/` junto con `index.faiss`, `index.pkl` y un `manifest.json` con `embedding_model`, `dimension`, `origen` y `documentos`. Revise su procedencia antes de establecer `COMPRASLAB_TRUST_POLICY_INDEX=true`: el docstore usa pickle. El adaptador actual acepta modelos OpenAI `text-embedding-*` que coincidan con el índice.

El kit, la rúbrica del profesor y el índice FAISS de compras no estaban disponibles al iniciar. La prueba de Demo B usa únicamente los valores proporcionados en la solicitud y **no sustituye la referencia original**.
