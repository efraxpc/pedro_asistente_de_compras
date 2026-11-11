# Matriz de evidencias — rúbricas oficiales R01–R29

Cotejada el 2026-11-10 contra la guía integrada [guide/Fases_Temas_Tareas_Rubricas_ComprasLab_Leyendas.pdf](../guide/Fases_Temas_Tareas_Rubricas_ComprasLab_Leyendas.pdf), que reproduce en español las 29 preguntas de la rúbrica del enunciado «Agentes Cognitivos com LangChain [26E4_2]» (páginas 6–8) y los temas T1–T26 de las clases 2 a 6. Los códigos R01–R29 y T1–T26 son etiquetas de esa guía, no numeración del profesor; el enunciado original en portugués sigue sin estar en este workspace, por lo que el cotejo final contra su redacción exacta queda como verificación de cierre.

La columna «ID previo» conserva el identificador provisional de la matriz anterior para rastrear la evidencia. La fila provisional R4.6 (búsqueda semántica opcional de piezas) no corresponde a ninguna rúbrica oficial y se retira de la matriz; R1.1, R1.2, R2.1, R3.1 y R3.3 pasan a la sección de infraestructura de soporte.

El diagrama [rubricas_proyecto.mmd](rubricas_proyecto.mmd) y su [vista SVG](rubricas_proyecto.svg) aún usan los IDs provisionales; actualizarlos es un pendiente de documentación.

## Fase 1 — Chain ejecutable y arquitectura (R01–R06)

| Rúbrica | Pregunta resumida | ID previo | Ubicación | Evidencia o condición | Estado |
|---|---|---|---|---|---|
| R01 | Anatomía y arquitectura cognitiva; tipo y madurez agéntica | — | docs/respuestas_rubricas.md §R01; src/pedro/anatomia.py; NB01; docs/arquitectura.mmd | Anatomía leída del agente real y ejecutada en NB01; agente híbrido demostrado con doble (0 llamadas al modelo en rutas por regla, herramienta elegida en la ruta con modelo); arquitectura CoALA; madurez actual/objetivo con criterios medibles; **escala de madurez genérica (supuesto declarado) hasta disponer de la clase 1** | Local con doble |
| R02 | Arquitectura de planificación y memoria aumentada | R3.2, R3.4 | docs/respuestas_rubricas.md §R02; src/pedro/planner.py; NB01; scripts/demostrar_r02.py; tests/test_planner.py; docs/trazas/r02_planificacion_llm.json | Cinco pasos observables y mapa de memoria ejecutados sin modelo; planificador de turno explícito: una solicitud mixta produce un plan de tres peticiones, validado, y cada una se verifica y publica con gpt-4.1-mini real; antes del planificador no se publicaba (traza conservada) | Real local y remoto puntual |
| R03 | PromptTemplate/ChatPromptTemplate reutilizables | R1.4 | docs/respuestas_rubricas.md §R03; src/pedro/prompts.py; src/pedro/chains.py; NB01; tests/test_prompts.py; docs/trazas/fase1_chain_llm.json | Dos ChatPromptTemplate con nombre propio y variables del dominio; la de extracción se reutiliza en LCEL y @chain, se rellena con tres solicitudes en NB01 y se ejecutó con gpt-4.1-mini real | Real local y remoto puntual |
| R04 | Output parser con salida JSON estructurada | R1.3, R2.5 | docs/respuestas_rubricas.md §R04; src/pedro/chains.py; src/pedro/laboratorio.py; NB01; tests/test_salida_estructurada.py; docs/trazas/fase1_chain_llm.json | Objeto Pydantic validado con gpt-4.1-mini real; laboratorio de ocho salidas rotas resueltas por parser, reparación (modelo real) o regla de dominio; hallazgo y corrección de pérdida silenciosa con JSON truncado; comparación ejecutada con with_structured_output | Real local y remoto puntual |
| R05 | invoke, batch, stream y composición con @chain | R1.5, R1.6 | docs/respuestas_rubricas.md §R05; src/pedro/chains.py; NB01; tests/test_salida_estructurada.py; docs/trazas/fase1_chain_llm.json | Tres métodos con gpt-4.1-mini real y medidos (batch de 3 en 1,43 s frente a 4,55 s en serie; stream con 19 estados parciales, primero a 0,45 s); dos cadenas @chain, una con reparación por try/except equivalente a la declarativa en el laboratorio | Real local y remoto puntual |
| R06 | Composición LCEL y justificación imperativa vs. declarativa | R1.4 | docs/respuestas_rubricas.md §R06; src/pedro/chains.py; src/pedro/laboratorio.py; NB01; tests/test_salida_estructurada.py | Cuatro cadenas LCEL (secuencia, fallback, stream parcial, paralelo); la misma cadena en los dos estilos con igual resultado y medición de lo que ve la traza (16 pasos y error visible en LCEL frente a 9 sin error en @chain); decisión: LCEL para tuberías, imperativo para orquestar el turno | Real local y remoto puntual |

## Fase 2 — Agente con herramientas y ReAct (R07–R12)

| Rúbrica | Pregunta resumida | ID previo | Ubicación | Evidencia o condición | Estado |
|---|---|---|---|---|---|
| R07 | Comparación de orquestadores y justificación de LangChain | — | docs/respuestas_rubricas.md §R07; src/pedro/orquestadores.py; scripts/demostrar_r07.py; src/pedro/anatomia.py; NB02; docs/trazas/r07_orquestadores_llm.json | Seis orquestadores comparados por autonomía, abstracción y modularidad; el mismo agente ejecutado en LangChain y en LangGraph con gpt-4.1-mini real (mismas respuestas; LangGraph reutiliza el resultado de la herramienta guardado en su estado); decisión argumentada con el inventario de 13 piezas y sus límites; los otros cuatro, comparación conceptual | Real remoto puntual y local |
| R08 | ReAct con initialize_agent, herramientas y memoria | R2.2 | docs/respuestas_rubricas.md §R08; src/pedro/legacy.py; scripts/demostrar_r08.py; NB02; tests/test_legacy.py; docs/trazas/r08_react_llm.json | ZERO_SHOT_REACT_DESCRIPTION con dos herramientas y ConversationBufferMemory ejecutado con gpt-4.1-mini real: pensamiento, acción, observación y respuesta correcta; contraste con y sin historial en el prompt | Real remoto puntual y doble |
| R09 | Chains secuenciales/paralelas y RouterChain | R2.3 | docs/respuestas_rubricas.md §R09; src/pedro/legacy.py; src/pedro/chains.py; scripts/demostrar_r09.py; NB02; tests/test_legacy.py; docs/trazas/r09_router_llm.json | Cadenas secuenciales y RunnableParallel; dos routers sobre RouterChain (reglas y LLMRouterChain) comparados con gpt-4.1-mini real en siete preguntas: reglas 2/7, LLM 6/7 | Real remoto puntual y local |
| R10 | API externa como herramienta vía function calling | R2.4 | docs/respuestas_rubricas.md §R10; src/pedro/integrations.py; src/pedro/agent.py; src/pedro/verification.py; scripts/demostrar_r10.py; docs/trazas/r10_viacep_llm.json | ViaCEP real llamado por gpt-4.1-mini por function calling: esquema, argumentos, respuesta de la API y respuesta publicada en tres casos (válido, inexistente, inválido); fallo real de publicación diagnosticado con la traza y corregido con anclar_cep, con antes/después | Real remoto puntual |
| R11 | Prompt PTCF con few-shot y chain-of-thought | R2.5 | docs/respuestas_rubricas.md §R11; src/pedro/prompts.py; src/pedro/chains.py; scripts/demostrar_r11.py; tests/test_prompts.py; docs/trazas/r11_prompts_llm.json | PTCF en el prompt del agente con cuatro ejemplos; FewShotChatMessagePromptTemplate y variante CoT con razonamiento antes de los datos; medición con gpt-4.1-mini real en diez solicitudes difíciles: zero-shot 6/10, few-shot 10/10, few-shot + CoT 10/10 | Real remoto puntual |
| R12 | Confiabilidad: parsers con errores, memoria, FAISS y callbacks | R2.5, R2.6 | docs/respuestas_rubricas.md §R12; src/pedro/agent.py (Traza); src/pedro/chains.py; src/pedro/verification.py; NB02; docs/citas_ancladas.md | Los cuatro componentes con caso normal y de error: reparación de salidas, memoria que guarda solo lo publicado, FAISS sobre el índice guardado y callback que registra herramientas y verificaciones; bitácora de un turno con error y recuperación; dos fallos reales hallados con la traza y corregidos | Real remoto puntual y doble |

## Fase 3 — Chatbot con memoria (R13–R18)

| Rúbrica | Pregunta resumida | ID previo | Ubicación | Evidencia o condición | Estado |
|---|---|---|---|---|---|
| R13 | Memoria corto/largo plazo con taxonomía CoALA | R3.6 | docs/respuestas_rubricas.md §R13; src/pedro/memory.py (mapa_memorias); NB03; docs/trazas/fase3_memoria_llm.json | Mapa de las cuatro memorias CoALA con alcance y reglas; contenido observado tras una conversación real de siete turnos (borrador, 4 episodios, preferencia guardada) | Real remoto puntual y local |
| R14 | Ventana de contexto + búsqueda vectorial | R3.2, R3.4 | docs/respuestas_rubricas.md §R14; src/pedro/memory.py; NB03; docs/trazas/fase3_memoria_llm.json | Ventana deslizante de 12 (14 guardados) combinada con recuperación vectorial: tres episodios recuperados en una sesión nueva (similitud 0,31–0,36) y ninguno para otro usuario; reglas de reemplazo, actualización e ignorado de recuerdos | Real remoto puntual y local |
| R15 | Comparación de herramientas especializadas de memoria | R3.6 | docs/respuestas_rubricas.md §R15; src/pedro/orquestadores.py; scripts/demostrar_r15.py; docs/comparaciones.md; docs/trazas/r15_memoria_llm.json | Mem0, Letta/MemGPT y LangMem comparados con la implementación propia por arquitectura y caso de uso; LangMem ejecutado con gpt-4.1-mini real en la misma conversación que la memoria propia: ambas guardan la preferencia y aíslan por usuario; LangMem deja decidir al modelo y responde sin verificación; Mem0 y Letta, comparación conceptual | Real remoto puntual |
| R16 | Chatbot con ConversationBufferMemory | R2.2 | docs/respuestas_rubricas.md §R16; src/pedro/legacy.py (crear_chatbot_buffer); NB03; tests/test_legacy.py; docs/trazas/fase3_memoria_llm.json | ConversationChain con ConversationBufferMemory en una conversación real de cuatro turnos: recuerda nombre, cantidad, presupuesto y plazo; la memoria crece de 260 a 935 caracteres | Real remoto puntual y doble |
| R17 | Intención y extracción de entidades | R3.5 | docs/respuestas_rubricas.md §R17; src/pedro/dialogue.py (interpretar_turno); scripts/demostrar_r17.py; tests/test_dialogue.py; docs/trazas/r17_interprete_llm.json | Seis intenciones y cinco entidades; el chat combina reglas (pieza) y modelo few-shot (si es compra y qué cambia); medido con gpt-4.1-mini en catorce mensajes difíciles: solo reglas 8/14, reglas y modelo 14/14; aclaraciones reales por pieza ambigua y cantidad ausente | Real remoto puntual y local |
| R18 | Contexto y descomposición validados en conversación real | R3.1, R3.5, R5.5 | docs/respuestas_rubricas.md §R18; scripts/demostrar_fase3.py; docs/trazas/fase3_memoria_llm.json; docs/trazas/fase3_memoria_llm_antes.json | Conversación real de siete turnos con el agente final: cambia cantidad conservando plazo, cambia límites, guarda preferencia, responde CEP y política sin perder el borrador y vuelve a comparar; persistencia tras reinicio y aislamiento; tres fallos de la primera ejecución diagnosticados y corregidos | Real remoto puntual |

## Fase 4 — SQL, APIs y RAG existente (R19–R23)

| Rúbrica | Pregunta resumida | ID previo | Ubicación | Evidencia o condición | Estado |
|---|---|---|---|---|---|
| R19 | Herramientas hardcoded vs. semánticas | R4.1 | docs/respuestas_rubricas.md §R19; src/pedro/agent.py; src/pedro/anatomia.py; docs/trazas/fase4_sql_llm.json | Catálogo de seis herramientas generado del código con tipo, lógica, entradas, salidas y errores: cinco hardcoded y una semántica (FAISS); criterio de reparto justificado; las seis usadas por el modelo real | Real local y remoto puntual |
| R20 | APIs internas/externas según tipo de uso | R2.4 | docs/respuestas_rubricas.md §R20; src/pedro/integrations.py; src/pedro/catalog.py; src/pedro/rag.py; src/pedro/memory.py | Tres APIs externas (ViaCEP, OpenAI, LangSmith) y cuatro internas (catálogo, políticas, memoria, verificación), cada una con su tipo de uso, su integración y su comportamiento ante fallos; todas ejercitadas con el modelo real | Real remoto puntual |
| R21 | Patrón text-to-query | R4.2 | docs/respuestas_rubricas.md §R21; src/pedro/query.py; src/pedro/agent.py; scripts/demostrar_fase4.py; NB04; tests/test_text_to_sql.py; docs/trazas/fase4_sql_llm.json | consultar_catalogo con dos modos: plan con plantillas si hay ID y text-to-SQL completo en preguntas abiertas (SELECT de gpt-4.1-mini, autorizador de SQLite por tabla y columna, solo lectura y límites); 5/5 preguntas correctas (3/5 antes de mejorar el prompt), 7/7 consultas hostiles rechazadas; conectado al chat, que publica la tabla de la consulta ejecutada | Real remoto puntual y local |
| R22 | Agente de recuperación sobre índice FAISS existente | R4.3 | docs/respuestas_rubricas.md §R22; knowledge/politicas/; scripts/construir_indice_politicas.py; scripts/demostrar_r22.py; NB04; tests/test_indice_existente.py; docs/trazas/r22_indice_existente.json | Índice guardado (75 fragmentos, 384d, L2) con manifiesto y huellas; el agente lo carga sin reconstruirlo y respondió dos preguntas con gpt-4.1-mini real; puerta de seguridad probada; **índice propio: la actividad no entregó uno** | Real local y remoto puntual |
| R23 | Fallo real de recuperación diagnosticado y corregido | R4.4, R4.5 | docs/respuestas_rubricas.md §R23; docs/t24_recuperacion.md; scripts/diagnosticar_t24.py; NB04; docs/trazas/r23_t24_indice_existente.json | Antes/después sobre el índice guardado en disco: `FIC-ENT-01-S05-C01` fuera del top-4 y luego primero tras reformular la consulta, con fuente, ID y distancia L2; diagnóstico de desajuste de vocabulario y técnica justificada; corpus ficticio propio | Real local |

## Fase 5 — Agente final verificado y evaluado (R24–R29)

| Rúbrica | Pregunta resumida | ID previo | Ubicación | Evidencia o condición | Estado |
|---|---|---|---|---|---|
| R24 | Verificación de consistencia factual y coherencia | R5.2, R5.3 | docs/respuestas_rubricas.md §R24; src/pedro/verification.py; src/pedro/nli.py; docs/citas_ancladas.md; docs/trazas/r29_langsmith_*.json | Verificación exacta y NLI triclase dentro del flujo, con anclaje de citas, CEP y preferencias; 0 recomendaciones erróneas publicadas en seis experimentos; ganadores equivocados de gpt-4o-mini bloqueados; rechazos y correcciones registrados en la traza | Real remoto y local |
| R25 | Agente único con ≥2 categorías de herramientas | R4.1, R5.1 | docs/respuestas_rubricas.md §R25; src/pedro/agent.py; docs/trazas/fase3_memoria_llm.json | SQL, RAG y API bajo el mismo AgentExecutor; las tres categorías usadas en una conversación real de siete turnos y desde Streamlit; un mensaje que mezcla categorías lo divide el planificador de turno y el mismo ejecutor resuelve cada parte | Real remoto puntual |
| R26 | Executor con create_openai_tools_agent y AgentExecutor | R5.1 | docs/respuestas_rubricas.md §R26; src/pedro/agent.py; docs/trazas/fase3_memoria_llm.json; docs/trazas/r29_langsmith_*.json | Agente final construido con las dos APIs exigidas, 6 herramientas y 6 iteraciones; ejecutado con gpt-4.1-mini en una conversación de siete turnos, en seis experimentos de 30 casos y desde la interfaz | Real remoto |
| R27 | Historial con RunnableWithMessageHistory | R5.4 | docs/respuestas_rubricas.md §R27; src/pedro/agent.py; src/pedro/memory.py; docs/trazas/fase3_memoria_llm.json | Agente envuelto en RunnableWithMessageHistory con historial SQLite por usuario y sesión; siete turnos reales con contexto, 14 mensajes guardados (solo lo publicado), ventana de 12 y recuperación tras recrear el flujo | Real remoto puntual |
| R28 | Agente completo integrado a Streamlit | R5.5 | docs/respuestas_rubricas.md §R28; app.py; scripts/demostrar_r28.py; docs/trazas/r28_streamlit.json | app.py ejecutada con AppTest y el modelo real: cuatro turnos de chat (compra, cambio de cantidad, CEP, política), nuevo chat, conversación reabierta y las tres vistas sin excepciones; chat y formulario coinciden en R$ 4.401,99; falta el vídeo | Real remoto puntual |
| R29 | Evaluación LangSmith de calidad y trayectoria | R5.5 | docs/respuestas_rubricas.md §R29; evals/evaluar_flujo.py; evals/casos_derivados.json; docs/trazas/r29_langsmith_*.json | Seis experimentos reales sobre 30 casos derivados con seis métricas; versión final con gpt-4.1-mini: ganador e importe 14/14, contenido 16/16, primera propuesta 24/24 sin errores de verificación, herramienta decisiva 23/23 y trayectoria completa 13/30 (camino más corto que el de la referencia); gpt-4o-mini 13/14; 0 recomendaciones erróneas publicadas; la evaluación halló el defecto del CEP y el efecto de la memoria compartida; casos derivados, no oficiales | Real remoto |

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
| Código y notebooks reproducibles con dobles identificados | Local: 116/116 pruebas, 5/5 notebooks reejecutados |
| Informe técnico en PDF | Local: docs/informe.md y docs/informe.pdf; actualizar tras cerrar pendientes |
| Registro de evaluación en LangSmith | Real: seis experimentos sobre el conjunto pedro-infnet-casos-derivados-7610315f (ver R29) |
| Video de demostración + enlace Drive institucional | Pendiente: requiere grabación y acceso del alumno |

## Pendientes que bloquean el cierre

Las 29 rúbricas tienen respuesta redactada y ejecución guardada. Lo que queda no es código:

1. **Vídeo de demostración** y enlace Drive institucional: requieren grabación y acceso del alumno.
2. **Cotejo contra el enunciado original en portugués**, que no está en este workspace. Los códigos R01–R29 son etiquetas de la guía.
3. **R01**: sustituir la escala genérica de madurez por la de la clase 1 cuando esté disponible.
4. **R22–R23**: confirmar con el profesor si la actividad entrega un índice FAISS; hoy se usa uno propio guardado en knowledge/politicas/.
5. **R29**: los 30 casos son derivados, no los oficiales; si el curso entrega casos, hay que repetir la evaluación.
6. Actualizar el diagrama rubricas_proyecto.mmd/svg a los IDs oficiales.

## Limitaciones conocidas del agente

- El planificador de turno admite como mucho una petición de cada tipo y solo actúa con el modelo disponible (R02).
- El agente no conversa fuera de sus tipos de respuesta: no contesta «¿qué recuerdas de mí?» y repite la comparación ante un comentario sin petición (R15).
- Sin credenciales el chat interpreta solo con reglas, que son frágiles ante formas de hablar no previstas (R17).
- La verificación comprueba que la respuesta sea cierta, no que sea pertinente (R24).
- El text-to-SQL del chat comprueba que la consulta sea segura, no que responda exactamente a la pregunta; por eso muestra la consulta (R21).
