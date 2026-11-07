# Pedro — Asistente de Compras — plan de implementación

## Estado y prioridades

El directorio inicial está vacío. Faltan el enunciado, el diseño PDF, el plan detallado, el kit de datos y el índice FAISS de políticas de compras. La rúbrica del profesor tendrá prioridad sobre esta especificación; los identificadores R01–R29 son provisionales hasta cotejarla. No se atribuirán resultados de integraciones reales a simulaciones ni se inventarán evidencias.

## Objetivo

Crear una aplicación Python local de compras ficticias, cinco notebooks progresivos, Streamlit y un agente final. Interpretará solicitudes, aclarará faltantes y ambigüedad, consultará un catálogo, comparará ofertas con reglas exactas, recuperará políticas desde un índice FAISS preconstruido, verificará la respuesta y registrará evaluaciones en LangSmith. No hará compras, pagos ni mensajes a terceros.

## Arquitectura

La interfaz mantiene `user_id`, `session_id` y `dataset_id`. El agente usa herramientas tipadas para catálogo SQLite, comparación determinista, políticas FAISS, ViaCEP y preferencias persistentes. El flujo final es `AgentExecutor -> RespuestaCompra -> verificación exacta/procedencia/NLI -> respuesta publicada`. `RunnableWithMessageHistory` envuelve el resultado verificado y es el único escritor del historial final. Las propuestas rechazadas se conservan solo en trazas. `chat_history` y `agent_scratchpad` son entradas separadas.

El catálogo aleatorio se genera una vez por escenario: 1.000 productos por defecto, tamaño configurable, tres proveedores y tres ofertas por producto. Guarda semilla, versión y ruta en manifiesto inmutable. Un nuevo chat conserva el dataset; un nuevo escenario crea dataset y chat; un nuevo arranque crea otro dataset salvo reutilización explícita. El modo referencia importa ocho productos y 24 ofertas del kit cuando llegue. `preparar_sesion().sesion_id` se adapta a `dataset_id`. Preferencias, sesiones y episodios viven fuera de carpetas de catálogos. Las ofertas históricas conservan su dataset, pero las recomendaciones usan el activo. Los datos comerciales son ficticios incluso con integraciones reales.

Las reglas usan centavos BRL, cantidad positiva, presupuesto y plazo no negativos, días corridos, impuestos incluidos y un solo flete. Una oferta cumple si stock >= cantidad, plazo <= máximo y cantidad * precio + flete <= presupuesto. Se ordena por total, plazo e ID de proveedor. No se divide compra, reserva ni descuenta stock. En la referencia, 20 monitores `PROD-003`, R$ 12.000 y siete días eligen Demo B por R$ 10.550; si “monitor” es ambiguo se pide aclaración.

Pydantic definirá `SolicitudCompra`, `Producto`, `Oferta`, `Evidencia`, `ResultadoHerramienta`, `RespuestaCompra` y `ResultadoVerificacion`. Los campos desconocidos no se convierten en cero. Las herramientas son `buscar_productos`, `consultar_catalogo`, `comparar_ofertas`, `consultar_politicas`, `consultar_cep`, `guardar_preferencia` y opcionalmente `preparar_borrador`. Text-to-query registrará pregunta, SQL, parámetros, validación y filas; solo lectura, esquema permitido y límite de filas, con ruta SQLite tomada del contexto. ViaCEP validará ocho dígitos y solo confirmará ciudad/estado.

Se usan `langchain-core` y `langchain-classic` para APIs exigidas: PromptTemplate, ChatPromptTemplate, parsers JSON/Pydantic, LCEL, `@chain`, invoke/batch/stream, initialize_agent, ZERO_SHOT_REACT_DESCRIPTION, RouterChain, ConversationBufferMemory, create_openai_tools_agent, AgentExecutor y RunnableWithMessageHistory. Las APIs clásicas deprecadas quedan en demos didácticas; el integrador usa herramientas de modelo y verificación. Se probará compatibilidad antes de fijar el lock.

El prompt seguirá PTCF y few-shot ajenos a los casos de evaluación. La memoria tendrá trabajo reciente, preferencias semánticas, episodios y reglas procedimentales, con SQLite e índice vectorial de recuerdos separado del índice de políticas. Se compararán LangMem/Mem0 y LangChain/Semantic Kernel. No se pedirá razonamiento privado.

El índice FAISS de políticas deberá inventariarse: documentos, IDs, metadatos, embeddings y procedencia. Una demo de fallo de recuperación exige que el documento pertinente exista, una consulta inicial que lo omita y una mejora medida sobre el mismo índice. No se presentará un índice de prueba como cumplimiento.

El verificador comprobará procedencia, dataset, evidencia, totales, stock, presupuesto, plazo y motivos de descarte. NLI triclase se evaluará con modelo/revisión/etiquetas fijados y pares en los idiomas usados. Se permiten propuesta inicial y una corrección; después se publica respuesta limitada. La interfaz solo transmite progreso antes de la verificación.

## Hitos y aceptación

1. **H0: insumos y compatibilidad.** Inventariar archivos, cotejar rúbrica y contradicciones, probar APIs/modelo y bloquear dependencias. Aceptación: inventario, pruebas mínimas y lock; bloqueos reales identificados.
2. **H1: datos y cadenas.** SQLite, generador, adaptador kit, contratos y `01_chain_mvp.ipynb`. Aceptación: semilla reproducible, ciclo de chat/escenario, reglas exactas, aclaraciones y demostración de invoke/batch/stream.
3. **H2: agentes y herramientas.** ReAct clásico, RouterChain, function calling, ViaCEP, callbacks y `02_react_herramientas.ipynb`. Aceptación: trazas de acciones, argumentos, rutas y API real separada de simulación.
4. **H3: memoria.** SQLite persistente, recuerdos vectoriales, CoALA y `03_memoria_chatbot.ipynb`. Aceptación: aislamiento, reinicio, precedencia del mensaje actual y catálogo activo.
5. **H4: RAG y SQL.** Cargador FAISS preconstruido, recuperación antes/después, text-to-query y `04_rag_text_to_query.ipynb`. Aceptación: SQL auditado y evidencia real de recuperación si llega el índice.
6. **H5: integrador.** Agente final, verificación, Streamlit, LangSmith, 30 escenarios y `05_integrador_evaluacion.ipynb`. Aceptación: no publicar propuesta no verificada, métricas reales por grupo y documentación reproducible.

## Pruebas y entregables

Guardar los 20 casos originales del kit intactos y crear 20 derivados, tres de memoria, tres de API, uno de recuperación y tres de NLI en archivos separados. Evaluar componentes y agente completo, con expectativas invisibles al agente. Las métricas abarcan extracción, aclaraciones, selección, importes, restricciones, fuentes, memoria, insuficiencia y trayectoria; órdenes distintos de consultas independientes son válidos.

Entregables: `pyproject.toml`, lock, `.env.example`, README con comandos, `src/compraslab/` para configuración/datos/esquemas/prompts/cadenas/herramientas/memoria/RAG/verificación/agente, cinco notebooks, `app.py`, `tests/`, `evals/`, `knowledge/`, `storage/` y `docs/`. Documentar diagramas, matriz R01–R29 con exigencia/implementación/ubicación/prueba/evidencia/dependencia/estado, comparaciones, informe editable y PDF, registro LangSmith, fuentes/IA y guion de video. La entrega del video real por Google Drive institucional seguirá el permiso exacto de la consigna cuando esté disponible.
