# Matriz provisional de evidencias

El plan recibido afirma 30 identificadores R1.1–R5.6, mientras sus fases enumeran 29; R4.6 se conserva como fila provisional. El PDF oficial aún no está disponible. Ninguna fila representa un criterio oficial hasta cotejar las páginas 1–8 y remapear los 29 criterios conservando las evidencias.

| ID provisional | Exigencia de trabajo | Ubicación | Evidencia o condición | Estado |
|---|---|---|---|---|
| R1.1 | Catálogo sintético reproducible | scripts/generar_catalogo_piezas.py; catalog.py | prueba local | Local |
| R1.2 | Escenarios UUID y manifiesto | catalog.py | prueba local | Local |
| R1.3 | Contratos Pydantic y null | contracts.py | prueba local | Local |
| R1.4 | Extracción @chain y LCEL | chains.py; NB01 | notebook con doble | Demostrado con doble |
| R1.5 | invoke, batch y stream | NB01 | notebook con doble | Demostrado con doble |
| R1.6 | Evidencia de extracción real | NB01 | requiere OPENAI_API_KEY | Pendiente |
| R2.1 | Comparador exacto | business.py | pytest límites y desempate | Local |
| R2.2 | ReAct y ConversationBufferMemory | legacy.py; NB02 | notebook con doble | Demostrado con doble |
| R2.3 | Secuencia, paralelo y RouterChain | chains.py; legacy.py; NB02 | notebook local | Local |
| R2.4 | ViaCEP síncrono y doble | integrations.py; evidencias.md | llamada real y doble | Real puntual |
| R2.5 | PTCF, parser y reparación | agent.py; chains.py | pytest corrección; extracción real pendiente | Parcial |
| R2.6 | Callback de trayectoria | agent.py | prueba remota pendiente | Implementado |
| R3.1 | Sesiones y mensajes persistentes | memory.py | pytest aislamiento | Local |
| R3.2 | Últimos 12 mensajes | memory.py | pytest ventana | Local |
| R3.3 | Preferencias explícitas | memory.py; agent.py | pytest usuario | Local |
| R3.4 | Episodios multilingües FastEmbed | memory.py; NB03 | ejecución local 384 dimensiones | Real local |
| R3.5 | Corrección y precedencia actual | memory.py; agent.py | prueba actualización; diálogo real pendiente | Parcial |
| R3.6 | CoALA, Mem0 y Letta | NB03; informe.md | comparación documental | Parcial |
| R4.1 | Seis herramientas tipadas | agent.py | pytest cantidad | Local |
| R4.2 | Plan Pydantic a SQL de solo lectura | query.py; NB04 | pytest y traza | Local |
| R4.3 | Procedencia y confianza FAISS | rag.py; test_rag_integrations.py | loader y puerta probados con fixture; índice autorizado ausente | Parcial |
| R4.4 | Fallo y reescritura mismo top-k | NB04 | índice autorizado ausente | Pendiente externo |
| R4.5 | Consulta sin cobertura | NB04 | índice autorizado ausente | Pendiente externo |
| R4.6 | Búsqueda semántica opcional de piezas | catalog.py | aún no implementada | Pendiente |
| R5.1 | Un agente OpenAI tools | agent.py | constructor; ejecución real pendiente | Parcial |
| R5.2 | Verificación de ofertas y evidencia | verification.py | pytest omisiones, dataset y total | Local |
| R5.3 | NLI triclase fijado | nli.py; evidencias.md | modelo real local y dobles | Real local |
| R5.4 | Una corrección y respuesta final | agent.py | pytest corrección e historial | Local con doble |
| R5.5 | Streamlit y LangSmith mismo flujo | app.py; evals/evaluar_flujo.py; casos_derivados.json | app local y 30 referencias; LangSmith remoto pendiente | Parcial |
| R5.6 | Informe, PDF, vídeo y entrega | docs/ | informe local; vídeo/Drive pendientes | Parcial |
