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

Para administrar la app en segundo plano:

```bash
./project.sh start
./project.sh status
./project.sh restart
./project.sh stop
```

El puerto predeterminado es 8501; use `PEDRO_PORT=8765 ./project.sh start` para iniciarlo en otro puerto, o `PEDRO_PORT=8765 ./project.sh restart` si ya está activo. El PID y el registro se guardan en `storage/run/`.

La app inicia en http://localhost:8501. Copie .env.example a .env para el agente OpenAI y LangSmith. Sin clave funcionan el listado paginado, la ficha, la comparación local y el chat de comparación. Con OpenAI, el chat también puede consultar las políticas ficticias de demostración mediante el agente; la respuesta se etiqueta como ficticia y pasa por verificación de fuente y NLI local. En el chat basta indicar pieza y cantidad; presupuesto y plazo son filtros opcionales. Si falta la cantidad, Pedro la pregunta una vez y conserva la respuesta en la sesión. Puede decir «ahora 3 unidades» para recalcular con los límites indicados antes, o «sin presupuesto y sin plazo» para quitarlos. Las recomendaciones del agente pasan por verificación exacta y NLI local antes de mostrarse.

El primer acceso crea un escenario con dataset_id UUID, una copia de datasets/piezas_electrodomesticos.sqlite3 y un manifiesto con huella SHA-256, fecha, semilla y recuentos. Nuevo chat conserva escenario; nuevo escenario crea un chat. Reabrir una conversación restaura su dataset o avisa si falta. Los archivos de ejecución van en storage/ y no se versionan.

## Componentes

- src/pedro/catalog.py: escenario y consultas SQLite de solo lectura.
- src/pedro/contracts.py y business.py: contratos y comparación de proveedores en centavos. Una oferta se descarta por stock, pedido mínimo del proveedor, plazo o presupuesto; las válidas se ordenan por la preferencia de origen guardada del usuario (nacional o internacional), total, plazo y proveedor. Cada respuesta muestra todas las ofertas con su origen y el motivo de descarte. Las respuestas a las 29 rúbricas están en docs/respuestas_rubricas.md.
- src/pedro/query.py: plan Pydantic a SELECT parametrizado con traza.
- src/pedro/memory.py: mensajes completos, ventana de 12, borradores de compra por sesión, preferencias y episodios FastEmbed por usuario.
- src/pedro/dialogue.py: extracción de restricciones por turno y preguntas solo para datos bloqueantes.
- src/pedro/prompts.py: PTCF y ejemplos con acciones observables.
- src/pedro/agent.py: seis herramientas, un create_openai_tools_agent, una corrección interna y RunnableWithMessageHistory que guarda solo la respuesta pública.
- src/pedro/verification.py y nli.py: comprobación exacta y puerta NLI triclase.
- src/pedro/rag.py: recuperación FAISS con filtro de metadatos e inspección de manifiesto antes de permitir deserialización.
- src/pedro/policy_demo.py y knowledge/politicas_demo/: corpus ficticio extenso e índice FAISS local construido en memoria para T15.
- scripts/diagnosticar_t24.py: comparación reproducible de un fallo de recuperación y su reformulación.
- notebooks/01–05: prácticas ejecutables. Los dobles se identifican explícitamente. Las comparaciones didácticas están en docs/comparaciones.md.

El notebook 04 demuestra T15 sin credenciales: divide tres políticas ficticias en fragmentos, crea embeddings FastEmbed, indexa con FAISS y compara búsquedas con y sin filtro por tema. Las políticas incluyen ejemplos cotejados con la SQLite sintética (SKU, compatibilidad, garantía por pieza y ofertas), fechados según la semilla `20261107`; pedidos y entregas siguen siendo hipotéticos. El chat usa este índice de demostración cuando no dispone de uno autorizado. Para el índice preexistente exigido por R22/T24 se requieren knowledge/politicas/index.faiss, index.pkl y manifest.json con origen, embedding_model, dimension, metrica, documentos y sha256 por archivo. Revise su procedencia antes de establecer PEDRO_TRUST_POLICY_INDEX=true. El docstore pickle exige confianza explícita; el índice ficticio se construye en memoria y no usa ese indicador.

T24 tiene un fallo y una corrección observados en ese corpus ficticio. **Para probar el flujo normal en Chat**, pregunte «¿Se puede mandar en varias cajas?»; también puede repetirla en la misma conversación. La ruta de entrega del flujo llama `consultar_politicas`, reformula esa pregunta como «envío parcial», verifica el fragmento y publica una regla citada solo si NLI la respalda. La respuesta muestra `FIC-ENT-01-S05-C01` y el contraste top-4. La ruta funciona con el índice ficticio cargado en la app y evita depender de que el LLM decida usar una herramienta en cada repetición; la interfaz actual carga ese índice cuando hay `OPENAI_API_KEY`. `/t24` muestra el diagnóstico controlado sin OpenAI. Para repetir la prueba por consola y guardar el JSON: `uv run python scripts/diagnosticar_t24.py --salida storage/evidencias/t24_demo.json`. El [diagnóstico](docs/t24_recuperacion.md) documenta los resultados. Cuando exista un índice preexistente autorizado, use `--indice knowledge/politicas --confiar-indice --original '...' --reescrita '...' --fuente-esperada '...'` después de revisar su procedencia. El cargador y la app aceptan el modelo FastEmbed local conocido o un modelo OpenAI declarado en el manifiesto; para otro modelo, seleccione el embedder compatible en el script. La ejecución con el corpus ficticio no acredita R22/R23 sobre el índice exigido.

## Evaluación y entregables

La matriz de evidencias, cotejada con las 29 rúbricas de la guía integrada en guide/ (etiquetas R01–R29), está en docs/matriz.md y su mapa visual en [Mermaid](docs/rubricas_proyecto.mmd) y [SVG](docs/rubricas_proyecto.svg). El registro de comprobaciones está en docs/evidencias.md y el informe editable y PDF en docs/informe.md y docs/informe.pdf. Hay 30 casos derivados y congelados en evals/casos_derivados.json; no equivalen a los casos oficiales. Para evaluar el mismo flujo final con LangSmith: uv run python evals/evaluar_flujo.py. El script exige OPENAI_API_KEY y LANGSMITH_API_KEY; no publica métricas simuladas.

La guía integrada de fases, temas y rúbricas está en guide/Fases_Temas_Tareas_Rubricas_ComprasLab_Leyendas.pdf; el enunciado original en portugués aún no está en el workspace para el cotejo de cierre. Faltan además el índice FAISS autorizado y una ejecución documentada del chat y LangSmith remotos. La grabación con webcam, subida a Drive institucional y verificación del enlace requieren el acceso del alumno.
