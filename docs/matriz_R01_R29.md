# Matriz R01–R29 provisional

Los identificadores y textos se derivan de la solicitud del proyecto. **No equivalen aún a la rúbrica del profesor**, que falta. «Verificado local» señala una prueba observada del componente; no acredita la nota académica. La columna de evidencia indica qué se conserva o qué falta.

| ID | Exigencia | Implementación y ubicación | Comprobación y evidencia | Dependencia | Estado |
|---|---|---|---|---|---|
| R01 | Interpretar solicitud natural | Prompt y esquema, `agent.py`, NB01 | Ejecución real de extracción | Modelo | Pendiente |
| R02 | Faltantes e inválidos | `schemas.py` | `test_core.py` | Ninguna | Verificado local |
| R03 | Ambigüedad de producto | `data.py`, `agent.py` | Prueba de diálogo con varios monitores | Modelo | Pendiente |
| R04 | Catálogo ficticio reproducible | `data.py` | `test_core.py`, manifiesto | Ninguna | Verificado local |
| R05 | Modos aleatorio/referencia | Aleatorio en `data.py`; adaptador referencia pendiente | Inventario 8/24 y matriz de modos | Kit | Pendiente |
| R06 | `dataset_id`, `session_id`, `user_id` | `data.py`, `memory.py`, `app.py` | Pruebas de sesión y nuevo escenario | Ninguna | Implementado local |
| R07 | Comparación exacta en centavos | `business.py` | `test_core.py`, fixture Demo B | Ninguna | Verificado local |
| R08 | PROD-003 oficial | Fixture del enunciado en `test_core.py` | Repetir sobre kit original | Kit | Pendiente |
| R09 | Prompts PTCF/few-shot | `prompts.py`, `agent.py`, NB01 | `test_legacy.py`; corrida real pendiente | Modelo | Verificado local |
| R10 | Parser JSON/Pydantic | `chains.py`, `agent.py` | Pruebas de formato y reparación | Modelo | Implementado local |
| R11 | LCEL, @chain, invoke/batch/stream | `chains.py`, NB01 | Tres métodos ejecutados localmente | Ninguna | Verificado local |
| R12 | ReAct clásico | `legacy.py`, NB02 | `test_legacy.py` con LLM guionado | Ninguna | Verificado local |
| R13 | Herramientas y function calling | `agent.py`, `tools.py` | Constructor y trayectoria real | Modelo | Implementado local |
| R14 | RouterChain y composición | `legacy.py`, `chains.py` | `test_legacy.py` | Ninguna | Verificado local |
| R15 | ViaCEP real y simulado | `integrations.py` | `evidencia_viacep.md` | Red | Verificado puntual |
| R16 | Text-to-query seguro | `query.py`, NB04 | `test_query_history.py`, SQL/parámetros/filas | Ninguna | Verificado local |
| R17 | FAISS preconstruido | `rag.py` cargador | Documentos, metadatos e índice real | Índice | Pendiente |
| R18 | Fallo real de recuperación | NB04 preparado | Antes/después sobre mismo índice | Índice | Pendiente |
| R19 | Memoria CoALA persistente | `memory.py`; recuperación vectorial de demostración | `test_episodic.py`; embeddings reales pendientes | Embeddings | Parcial |
| R20 | ConversationBufferMemory | `legacy.py` | `test_legacy.py` | Ninguna | Verificado local |
| R21 | RunnableWithMessageHistory final | `agent.py`, `memory.py` | `test_integrator.py` | Modelo para ejecución real | Verificado local |
| R22 | Procedencia y dataset activo | `verification.py` | `test_integrator.py` | Kit para cobertura final | Implementado local |
| R23 | Total, stock, plazo y descartes | `verification.py` | `test_core.py` y `test_integrator.py` | Ninguna | Verificado local |
| R24 | NLI triclase | `nli.py` | `test_nli.py` guionado; corrida remota pendiente | Modelo | Parcial |
| R25 | Máximo dos propuestas | `agent.py` | `test_integrator.py` | Modelo para corrida real | Verificado local |
| R26 | Streamlit y publicación verificada | `app.py` | AppTest sin excepciones; chat real pendiente | Modelo | Parcial |
| R27 | LangSmith y métricas | Configuración `.env.example`, `evals/` | SDK local 3/3; experimentos y trazas remotos pendientes | Credenciales/kit | Parcial |
| R28 | Comparaciones y didáctica | `comparaciones.md`, notebooks | Revisión documental | Rúbrica | Parcial |
| R29 | Entrega y video | README y docs iniciales | Informe/PDF/video/Drive reales | Rúbrica y usuario | Pendiente |
