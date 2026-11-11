# Comparaciones didácticas

La comparación completa de los seis orquestadores vistos en clase (LangChain, LangGraph, LlamaIndex, AutoGen, Semantic Kernel y Langflow) y la justificación de LangChain están en respuestas_rubricas.md §R07. Allí figura también la comparación ejecutada entre LangChain y LangGraph. La tabla siguiente conserva el contraste inicial con AutoGen.

## Agentes y composición

| Aspecto | LangChain clásico / LCEL en este proyecto | AutoGen |
|---|---|---|
| Unidad demostrada | Un agente con herramientas tipadas y una cadena de publicación | Conversaciones coordinadas entre agentes |
| Traza visible | Nombre, argumentos y resultado de herramientas; parser y verificador | Mensajes y acciones entre participantes |
| Uso en Pedro | El integrador necesita un solo agente y una puerta determinista | Se estudia como alternativa; no se ejecutó aquí |
| Límite de evidencia | ReAct clásico se probó con FakeListLLM; agente final remoto pendiente | Sin experimento ejecutado |

La comparación medida entre composición declarativa (LCEL) e imperativa (@chain), con la decisión del proyecto, está en respuestas_rubricas.md §R06. La composición secuencial encadena parser, modelo y validación; RunnableParallel consulta ramas independientes. RouterCompras envía consultas reales a catálogo o comparación. Estos ejemplos están en notebooks 01 y 02. No se solicita ni conserva razonamiento privado; los planes del prompt describen llamadas observables.

## Memoria

| Capa | Pedro | Mem0 / Letta como referencia |
|---|---|---|
| Trabajo | Últimos 12 mensajes de la sesión | Gestión de contexto propia de cada sistema |
| Episódica | SQLite con vectores FastEmbed, modelo y versión; recuperación entre sesiones del mismo usuario | Abstracciones de memoria de terceros |
| Preferencias | Solo cambios explícitos, aislados por user_id | Su política concreta requeriría integración y evaluación |
| Procedimental | Prompt, herramientas y reglas de verificación | Configuración de agente propia |

La comparación es arquitectónica. La única recuperación medida en este workspace es la de Pedro con FastEmbed. Los precios y el stock de episodios se tratan como históricos; la petición actual y el escenario activo gobiernan la decisión.
