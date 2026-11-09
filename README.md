# Pedro Infnet reconstruido

Proyecto independiente en Python 3.13 para consultar piezas ficticias, comparar ofertas y ensayar un agente con publicación verificada. El catálogo, los proveedores, las compatibilidades, el stock y los precios son sintéticos. El generador y la base sintética se tomaron del repositorio de referencia; el paquete de aplicación se construyó en este workspace.

## Reproducir

```bash
uv sync --python 3.13 --all-extras --locked
uv run pytest -q
uv run python scripts/generar_catalogo_piezas.py
uv run python scripts/crear_notebooks.py
uv run python scripts/ejecutar_notebooks.py
uv run streamlit run app.py
```

La app inicia en http://localhost:8501. Copie .env.example a .env para el agente OpenAI y LangSmith. Sin clave funcionan el listado paginado, la ficha y la comparación local. El chat sin clave lista piezas y muestra fichas. Las recomendaciones del agente pasan por verificación exacta y NLI local antes de mostrarse.

El primer acceso crea un escenario con dataset_id UUID, una copia de datasets/piezas_electrodomesticos.sqlite3 y un manifiesto con huella SHA-256, fecha, semilla y recuentos. Nuevo chat conserva escenario; nuevo escenario crea un chat. Reabrir una conversación restaura su dataset o avisa si falta. Los archivos de ejecución van en storage/ y no se versionan.

## Componentes

- src/pedro/catalog.py: escenario y consultas SQLite de solo lectura.
- src/pedro/contracts.py y business.py: contratos y decisión en centavos.
- src/pedro/query.py: plan Pydantic a SELECT parametrizado con traza.
- src/pedro/memory.py: mensajes completos, ventana de 12, preferencias y episodios FastEmbed por usuario.
- src/pedro/prompts.py: PTCF y ejemplos con acciones observables.
- src/pedro/agent.py: seis herramientas, un create_openai_tools_agent, una corrección interna y RunnableWithMessageHistory que guarda solo la respuesta pública.
- src/pedro/verification.py y nli.py: comprobación exacta y puerta NLI triclase.
- src/pedro/rag.py: inspección de manifiesto y hashes antes de permitir deserialización FAISS.
- notebooks/01–05: prácticas ejecutables. Los dobles se identifican explícitamente. Las comparaciones didácticas están en docs/comparaciones.md.

Para el índice de políticas se requieren knowledge/politicas/index.faiss, index.pkl y manifest.json con origen, embedding_model, dimension, metrica, documentos y sha256 por archivo. Revise su procedencia antes de establecer PEDRO_TRUST_POLICY_INDEX=true. El docstore pickle exige confianza explícita. Sin el índice, no se acredita recuperación de políticas.

## Evaluación y entregables

La matriz provisional de 30 identificadores está en docs/matriz.md. El registro de comprobaciones está en docs/evidencias.md y el informe editable y PDF en docs/informe.md y docs/informe.pdf. Hay 30 casos derivados y congelados en evals/casos_derivados.json; no equivalen a los casos oficiales. Para evaluar el mismo flujo final con LangSmith: uv run python evals/evaluar_flujo.py. El script exige OPENAI_API_KEY y LANGSMITH_API_KEY; no publica métricas simuladas.

Faltan el PDF oficial de Infnet para cotejar 29 criterios, el índice FAISS autorizado y credenciales para el chat y LangSmith remotos. La grabación con webcam, subida a Drive institucional y verificación del enlace requieren el acceso del alumno.
