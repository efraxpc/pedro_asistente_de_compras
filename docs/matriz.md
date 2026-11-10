# Matriz de evidencias — rúbricas oficiales R01–R29

Cotejada el 2026-11-10 contra la guía integrada [guide/Fases_Temas_Tareas_Rubricas_ComprasLab_Leyendas.pdf](../guide/Fases_Temas_Tareas_Rubricas_ComprasLab_Leyendas.pdf), que reproduce en español las 29 preguntas de la rúbrica del enunciado «Agentes Cognitivos com LangChain [26E4_2]» (páginas 6–8) y los temas T1–T26 de las clases 2 a 6. Los códigos R01–R29 y T1–T26 son etiquetas de esa guía, no numeración del profesor; el enunciado original en portugués sigue sin estar en este workspace, por lo que el cotejo final contra su redacción exacta queda como verificación de cierre.

La columna «ID previo» conserva el identificador provisional de la matriz anterior para rastrear la evidencia. La fila provisional R4.6 (búsqueda semántica opcional de piezas) no corresponde a ninguna rúbrica oficial y se retira de la matriz; R1.1, R1.2, R2.1, R3.1 y R3.3 pasan a la sección de infraestructura de soporte.

El diagrama [rubricas_proyecto.mmd](rubricas_proyecto.mmd) y su [vista SVG](rubricas_proyecto.svg) aún usan los IDs provisionales; actualizarlos es un pendiente de documentación.

## Fase 1 — Chain ejecutable y arquitectura (R01–R06)

| Rúbrica | Pregunta resumida | ID previo | Ubicación | Evidencia o condición | Estado |
|---|---|---|---|---|---|
| R01 | Anatomía y arquitectura cognitiva; tipo y madurez agéntica | — | docs/respuestas_rubricas.md §R01; src/pedro/anatomia.py; NB01; docs/arquitectura.mmd | Anatomía leída del agente real y ejecutada en NB01; agente híbrido demostrado con doble (0 llamadas al modelo en rutas por regla, herramienta elegida en la ruta con modelo); arquitectura CoALA; madurez actual/objetivo con criterios medibles; **escala de madurez genérica (supuesto declarado) hasta disponer de la clase 1** | Local con doble |
| R02 | Arquitectura de planificación y memoria aumentada | R3.2, R3.4 | docs/respuestas_rubricas.md §R02; NB01; scripts/demostrar_r02.py; docs/trazas/r02_planificacion_llm.json | Cinco pasos observables y mapa de memoria ejecutados sin modelo; plan decidido por gpt-4.1-mini real en compra, CEP y cambio de cantidad; pregunta de política corregida con citas ancladas; **solicitud mixta en un turno no se publica** (limitación declarada) | Real local y remoto puntual |
| R03 | PromptTemplate/ChatPromptTemplate reutilizables | R1.4 | docs/respuestas_rubricas.md §R03; src/pedro/prompts.py; src/pedro/chains.py; NB01; tests/test_prompts.py; docs/trazas/fase1_chain_llm.json | Dos ChatPromptTemplate con nombre propio y variables del dominio; la de extracción se reutiliza en LCEL y @chain, se rellena con tres solicitudes en NB01 y se ejecutó con gpt-4.1-mini real | Real local y remoto puntual |
| R04 | Output parser con salida JSON estructurada | R1.3, R2.5 | docs/respuestas_rubricas.md §R04; src/pedro/chains.py; src/pedro/laboratorio.py; NB01; tests/test_salida_estructurada.py; docs/trazas/fase1_chain_llm.json | Objeto Pydantic validado con gpt-4.1-mini real; laboratorio de ocho salidas rotas resueltas por parser, reparación (modelo real) o regla de dominio; hallazgo y corrección de pérdida silenciosa con JSON truncado; comparación ejecutada con with_structured_output | Real local y remoto puntual |
| R05 | invoke, batch, stream y composición con @chain | R1.5, R1.6 | docs/respuestas_rubricas.md §R05; src/pedro/chains.py; NB01; tests/test_salida_estructurada.py; docs/trazas/fase1_chain_llm.json | Tres métodos con gpt-4.1-mini real y medidos (batch de 3 en 1,43 s frente a 4,55 s en serie; stream con 19 estados parciales, primero a 0,45 s); dos cadenas @chain, una con reparación por try/except equivalente a la declarativa en el laboratorio | Real local y remoto puntual |
| R06 | Composición LCEL y justificación imperativa vs. declarativa | R1.4 | docs/respuestas_rubricas.md §R06; src/pedro/chains.py; src/pedro/laboratorio.py; NB01; tests/test_salida_estructurada.py | Cuatro cadenas LCEL (secuencia, fallback, stream parcial, paralelo); la misma cadena en los dos estilos con igual resultado y medición de lo que ve la traza (16 pasos y error visible en LCEL frente a 9 sin error en @chain); decisión: LCEL para tuberías, imperativo para orquestar el turno | Real local y remoto puntual |

## Fase 2 — Agente con herramientas y ReAct (R07–R12)

| Rúbrica | Pregunta resumida | ID previo | Ubicación | Evidencia o condición | Estado |
|---|---|---|---|---|---|
| R07 | Comparación de orquestadores y justificación de LangChain | — | docs/respuestas_rubricas.md §R07; docs/comparaciones.md; src/pedro/anatomia.py; NB02 | Seis orquestadores comparados por autonomía, abstracción y modularidad; decisión argumentada con el inventario de 13 piezas de LangChain usadas (obtenido de los imports) y con sus límites (APIs obsoletas, migración a LangGraph); comparación conceptual, solo LangChain ejecutado | Local |
| R08 | ReAct con initialize_agent, herramientas y memoria | R2.2 | docs/respuestas_rubricas.md §R08; src/pedro/legacy.py; scripts/demostrar_r08.py; NB02; tests/test_legacy.py; docs/trazas/r08_react_llm.json | ZERO_SHOT_REACT_DESCRIPTION con dos herramientas y ConversationBufferMemory ejecutado con gpt-4.1-mini real: pensamiento, acción, observación y respuesta correcta; contraste con y sin historial en el prompt | Real remoto puntual y doble |
| R09 | Chains secuenciales/paralelas y RouterChain | R2.3 | docs/respuestas_rubricas.md §R09; src/pedro/legacy.py; src/pedro/chains.py; scripts/demostrar_r09.py; NB02; tests/test_legacy.py; docs/trazas/r09_router_llm.json | Cadenas secuenciales y RunnableParallel; dos routers sobre RouterChain (reglas y LLMRouterChain) comparados con gpt-4.1-mini real en siete preguntas: reglas 2/7, LLM 6/7 | Real remoto puntual y local |
| R10 | API externa como herramienta vía function calling | R2.4 | docs/respuestas_rubricas.md §R10; src/pedro/integrations.py; src/pedro/agent.py; src/pedro/verification.py; scripts/demostrar_r10.py; docs/trazas/r10_viacep_llm.json | ViaCEP real llamado por gpt-4.1-mini por function calling: esquema, argumentos, respuesta de la API y respuesta publicada en tres casos (válido, inexistente, inválido); fallo real de publicación diagnosticado con la traza y corregido con anclar_cep, con antes/después | Real remoto puntual |
| R11 | Prompt PTCF con few-shot y chain-of-thought | R2.5 | docs/respuestas_rubricas.md §R11; src/pedro/prompts.py; src/pedro/chains.py; scripts/demostrar_r11.py; tests/test_prompts.py; docs/trazas/r11_prompts_llm.json | PTCF en el prompt del agente con cuatro ejemplos; FewShotChatMessagePromptTemplate y variante CoT con razonamiento antes de los datos; medición con gpt-4.1-mini real en diez solicitudes difíciles: zero-shot 6/10, few-shot 10/10, few-shot + CoT 10/10 | Real remoto puntual |
| R12 | Confiabilidad: parsers con errores, memoria, FAISS y callbacks | R2.5, R2.6 | docs/respuestas_rubricas.md §R12; src/pedro/agent.py (Traza); src/pedro/chains.py; src/pedro/verification.py; NB02; docs/citas_ancladas.md | Los cuatro componentes con caso normal y de error: reparación de salidas, memoria que guarda solo lo publicado, FAISS sobre el índice guardado y callback que registra herramientas y verificaciones; bitácora de un turno con error y recuperación; dos fallos reales hallados con la traza y corregidos | Real remoto puntual y doble |

## Fase 3 — Chatbot con memoria (R13–R18)

| Rúbrica | Pregunta resumida | ID previo | Ubicación | Evidencia o condición | Estado |
|---|---|---|---|---|---|
| R13 | Memoria corto/largo plazo con taxonomía CoALA | R3.6 | NB03; docs/comparaciones.md §Memoria | Mapa de capas (trabajo, episódica, preferencias, procedimental) con ejemplos del dominio | Local |
| R14 | Ventana de contexto + búsqueda vectorial | R3.2, R3.4 | src/pedro/memory.py; NB03 | Ventana de 12 probada con pytest; episodios FastEmbed 384d guardados, actualizados y recuperados entre sesiones (0.674 vs. 0.113) | Real local |
| R15 | Comparación de herramientas especializadas de memoria | R3.6 | docs/comparaciones.md; NB03 | Mem0 y Letta/MemGPT comparados por arquitectura y caso de uso frente a la implementación propia; sin ejecutarlas (declarado) | Local |
| R16 | Chatbot con ConversationBufferMemory | R2.2 | src/pedro/legacy.py; NB02; NB03 | Conversación de varios turnos con ConversationBufferMemory y doble | Demostrado con doble |
| R17 | Intención y extracción de entidades | R3.5 | src/pedro/dialogue.py; tests/test_dialogue.py | Extracción de pieza, cantidad, presupuesto y plazo por turno; pregunta solo datos bloqueantes | Local |
| R18 | Contexto y descomposición validados en conversación real | R3.1, R3.5, R5.5 | app.py; src/pedro/memory.py; evidencias.md | Agent API: «Compara PEC-01-0001» → «2» → «ahora 3 unidades» recalculó conservando límites, con borrador aislado por sesión; **conversación equivalente con LLM remoto pendiente** | Parcial |

## Fase 4 — SQL, APIs y RAG existente (R19–R23)

| Rúbrica | Pregunta resumida | ID previo | Ubicación | Evidencia o condición | Estado |
|---|---|---|---|---|---|
| R19 | Herramientas hardcoded vs. semánticas | R4.1 | src/pedro/agent.py; docs/informe.md | Seis herramientas tipadas con docstring; deterministas (comparar, CEP), text-to-query y semántica (políticas) diferenciadas | Local |
| R20 | APIs internas/externas según tipo de uso | R2.4 | src/pedro/integrations.py; src/pedro/agent.py | ViaCEP real y simulado integrado como herramienta con propósito documentado (confirmar ciudad/UF, no flete) | Real puntual |
| R21 | Patrón text-to-query | R4.2 | src/pedro/query.py; NB04; tests/test_tools_flow.py | Pregunta natural → PlanConsulta Pydantic → SELECT parametrizado de solo lectura, validación, ejecución y filas con traza | Local |
| R22 | Agente de recuperación sobre índice FAISS existente | R4.3 | docs/respuestas_rubricas.md §R22; knowledge/politicas/; scripts/construir_indice_politicas.py; scripts/demostrar_r22.py; NB04; tests/test_indice_existente.py; docs/trazas/r22_indice_existente.json | Índice guardado (75 fragmentos, 384d, L2) con manifiesto y huellas; el agente lo carga sin reconstruirlo y respondió dos preguntas con gpt-4.1-mini real; puerta de seguridad probada; **índice propio: la actividad no entregó uno** | Real local y remoto puntual |
| R23 | Fallo real de recuperación diagnosticado y corregido | R4.4, R4.5 | docs/respuestas_rubricas.md §R23; docs/t24_recuperacion.md; scripts/diagnosticar_t24.py; NB04; docs/trazas/r23_t24_indice_existente.json | Antes/después sobre el índice guardado en disco: `FIC-ENT-01-S05-C01` fuera del top-4 y luego primero tras reformular la consulta, con fuente, ID y distancia L2; diagnóstico de desajuste de vocabulario y técnica justificada; corpus ficticio propio | Real local |

## Fase 5 — Agente final verificado y evaluado (R24–R29)

| Rúbrica | Pregunta resumida | ID previo | Ubicación | Evidencia o condición | Estado |
|---|---|---|---|---|---|
| R24 | Verificación de consistencia factual y coherencia | R5.2, R5.3 | src/pedro/verification.py; src/pedro/nli.py; docs/citas_ancladas.md; tests/test_citas_ancladas.py | Verificación exacta (total, stock, presupuesto, plazo, IDs, dataset) + NLI triclase real local integradas antes de publicar; anclaje de citas con cuatro estados en la traza: el modelo elige la fuente y el sistema pone el texto | Real local |
| R25 | Agente único con ≥2 categorías de herramientas | R4.1, R5.1 | src/pedro/agent.py | SQL + RAG + API + deterministas bajo el mismo executor; ejecuciones remotas puntuales registradas en T24 | Local |
| R26 | Executor con create_openai_tools_agent y AgentExecutor | R5.1 | src/pedro/agent.py | Constructor con las APIs exigidas; ejecuciones remotas puntuales con gpt-4.1-mini (T24); **sesión remota completa documentada pendiente** | Parcial |
| R27 | Historial con RunnableWithMessageHistory | R5.4 | src/pedro/agent.py; tests/test_tools_flow.py | Historial multi-turno operativo que guarda solo petición y respuesta pública | Local |
| R28 | Agente completo integrado a Streamlit | R5.5 | app.py | Agent API ready en Chat, Catálogo y Comparación con el mismo agente, memoria y verificador | Real local |
| R29 | Evaluación LangSmith de calidad y trayectoria | R5.5 | evals/evaluar_flujo.py; evals/casos_derivados.json | 30 casos derivados congelados con respuestas y trayectorias de referencia; **evaluación remota sin ejecutar** (requiere OPENAI_API_KEY y LANGSMITH_API_KEY); no se publican métricas simuladas | Pendiente |

## Infraestructura de soporte (sin rúbrica oficial directa)

| ID previo | Aporte | Ubicación | Estado |
|---|---|---|---|
| R1.1 | Catálogo sintético reproducible (semilla 20261107) | scripts/generar_catalogo_piezas.py; catalog.py | Local |
| R1.2 | Escenarios UUID con manifiesto SHA-256 | catalog.py | Local |
| R2.1 | Comparador exacto en centavos con desempate | business.py | Local |
| R3.1 | Sesiones y mensajes persistentes aislados | memory.py | Local |
| R3.3 | Preferencias explícitas por usuario | memory.py; agent.py | Local |
| R4.6 | Búsqueda semántica de piezas | — | Retirada: no la exige ninguna rúbrica; la búsqueda de piezas es SQL |

## Entregables finales (guía, p. 16)

| Entregable | Estado |
|---|---|
| Código y notebooks reproducibles con dobles identificados | Local: 66/66 pruebas, 5/5 notebooks reejecutados |
| Informe técnico en PDF | Local: docs/informe.md y docs/informe.pdf; actualizar tras cerrar pendientes |
| Registro de evaluación en LangSmith | Pendiente (ver R29) |
| Video de demostración + enlace Drive institucional | Pendiente: requiere grabación y acceso del alumno |

## Pendientes que bloquean el cierre

1. **R01**: sustituir la escala genérica de madurez por la de la clase 1 cuando esté disponible.
2. **R05, R18, R26**: documentar ejecuciones reales con OPENAI_API_KEY (extracción, conversación multi-turno y sesión del agente final).
4. **R22–R23**: confirmar con el profesor si la actividad entrega un índice FAISS; hoy se usa uno propio guardado en knowledge/politicas/.
5. **R29**: ejecutar evals/evaluar_flujo.py con credenciales y registrar métricas reales.
6. Cotejo final contra el enunciado original en portugués cuando esté disponible, y actualización del diagrama rubricas_proyecto.mmd/svg a los IDs oficiales.
