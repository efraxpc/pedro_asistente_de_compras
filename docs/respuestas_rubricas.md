# Respuestas a las rúbricas R01–R29

Este documento responde, una por una, a las 29 preguntas de la rúbrica según la guía integrada [guide/Fases_Temas_Tareas_Rubricas_ComprasLab_Leyendas.pdf](../guide/Fases_Temas_Tareas_Rubricas_ComprasLab_Leyendas.pdf). Cada respuesta indica qué se hizo, dónde está la evidencia, qué decisión técnica se tomó y qué queda pendiente. El estado resumido de todas las rúbricas vive en [matriz.md](matriz.md) y el registro de ejecuciones en [evidencias.md](evidencias.md).

Todos los datos del proyecto (catálogo, proveedores, stock, precios y políticas) son sintéticos.

**Avance de redacción:** redactadas y con ejecución guardada R01–R08, R22 y R23. Pendientes de redactar: R09–R21 y R24–R29.

---

# Fase 1 — Chain ejecutable y arquitectura

## R01 — Anatomía, arquitectura cognitiva, tipo de agente y madurez agéntica

> ¿El alumno estructuró la anatomía y la arquitectura cognitiva del agente, clasificando su tipo y nivel de madurez agéntica?

**Respuesta corta.** Pedro es un agente **híbrido**: una capa reactiva de reglas deterministas resuelve lo que no debe quedar a criterio del modelo, y una capa deliberativa, guiada por el LLM, elige herramientas, mantiene estado entre turnos y revisa su propia propuesta antes de publicarla. Su madurez actual es la de un **agente único con herramientas, memoria y autoverificación** (nivel 4 de 5 en la escala usada abajo), y esa es también su madurez objetivo, consolidada con evaluación medida.

### 1. Anatomía del agente

En clase, la anatomía general de un agente se describió con cuatro elementos — ambiente, sensores, herramientas y motor cognitivo (el LLM) — más un orquestrador que comunica herramientas, prompts y memorias (clase del 14-10-2026, repaso de la primera clase). La tabla aplica esa anatomía a Pedro y añade los componentes que pide la guía: system message, memoria, base de conocimiento y flujo general.

| Componente | En Pedro | Ubicación |
|---|---|---|
| **Ambiente** | Un escenario aislado: copia SQLite del catálogo con `dataset_id` UUID y manifiesto SHA-256, el corpus de políticas y el servicio externo ViaCEP. El agente solo lee; no compra ni paga. | [catalog.py](../src/pedro/catalog.py) |
| **Motor cognitivo (LLM)** | `ChatOpenAI`, modelo `gpt-4.1-mini` por defecto, configurable con `PEDRO_MODEL`. Sin `OPENAI_API_KEY` la aplicación funciona degradada con la capa determinista. | [app.py](../app.py) |
| **System message** | Prompt con estructura PTCF (Persona, Tarea, Contexto, Formato), el `dataset_id` activo, cuatro ejemplos few-shot de acciones observables y las instrucciones de formato de `RespuestaCompra`. | `crear_agente` en [agent.py](../src/pedro/agent.py); [prompts.py](../src/pedro/prompts.py) |
| **Sensores** (herramientas que perciben el ambiente) | `buscar_productos` (candidatos por ID, SKU o nombre), `consultar_catalogo` (text-to-query sobre SQLite), `consultar_politicas` (recuperación FAISS con fuentes) y `consultar_cep` (API externa ViaCEP). | `herramientas` en [agent.py](../src/pedro/agent.py); [query.py](../src/pedro/query.py); [rag.py](../src/pedro/rag.py); [integrations.py](../src/pedro/integrations.py) |
| **Herramientas** (que calculan o actúan) | `comparar_ofertas` (cálculo exacto en centavos con descartes) y `guardar_preferencia` (única escritura: una preferencia citada explícitamente por el usuario). | `herramientas` en [agent.py](../src/pedro/agent.py); [business.py](../src/pedro/business.py) |
| **Memoria** | Corto plazo: ventana de los últimos 12 mensajes y borrador de compra por sesión. Largo plazo: preferencias explícitas por usuario y episodios vectoriales FastEmbed (384 dimensiones) recuperables entre sesiones. Todo en SQLite, aislado por `user_id`. | [memory.py](../src/pedro/memory.py); [dialogue.py](../src/pedro/dialogue.py) |
| **Base de conocimiento** | Datos estructurados: catálogo SQLite (2640 piezas, 7920 ofertas). Datos documentales: políticas indexadas en FAISS con metadatos y filtro por tema. | [catalog.py](../src/pedro/catalog.py); [policy_demo.py](../src/pedro/policy_demo.py); [knowledge/politicas_demo/](../knowledge/politicas_demo/) |
| **Orquestrador** | LangChain: `create_openai_tools_agent` + `AgentExecutor` (máximo 6 iteraciones) envueltos en `RunnableWithMessageHistory`. | `crear_agente` y `crear_flujo` en [agent.py](../src/pedro/agent.py) |
| **Puerta de publicación** | Verificación exacta (total, stock, presupuesto, plazo, IDs, procedencia) y NLI local triclase. Solo se muestra lo que pasa ambas. | [verification.py](../src/pedro/verification.py); [nli.py](../src/pedro/nli.py) |
| **Interfaz** | Streamlit con vistas de Chat, Catálogo y Comparación sobre el mismo agente, memoria y verificador. | [app.py](../app.py) |

### 2. Arquitectura cognitiva y flujo general

```mermaid
flowchart TD
    U[Usuario en Streamlit] --> D[Extracción de restricciones del turno<br/>y borrador de compra]
    D -->|falta pieza o cantidad| Q[Pregunta de aclaración]
    D -->|regla determinista aplicable| R[Ruta directa:<br/>listado, comparación local, entrega parcial]
    D -->|requiere decidir| M[Memoria: 12 mensajes,<br/>preferencias y episodios]
    M --> A[LLM + AgentExecutor<br/>elige herramientas]
    A <--> T[6 herramientas:<br/>SQL, FAISS, ViaCEP, cálculo, preferencias]
    A --> J[Propuesta RespuestaCompra]
    R --> J
    J --> V[Verificación exacta]
    V --> N[NLI local]
    N -->|respaldada| P[Respuesta pública]
    N -->|rechazada, una vez| A
    P --> H[(Historial: solo petición<br/>y respuesta pública)]
```

La arquitectura cognitiva se describe con CoALA, el marco que el curso usa por defecto para agentes cognitivos (clase del 21-10-2026):

| Elemento CoALA | En Pedro |
|---|---|
| Memoria de trabajo | Mensaje actual, borrador de compra de la sesión y ventana de 12 mensajes |
| Memoria episódica | Episodios vectoriales de recomendaciones pasadas, por usuario |
| Memoria semántica | Catálogo SQLite, políticas en FAISS y preferencias explícitas del usuario |
| Memoria procedimental | System message PTCF, ejemplos few-shot, reglas deterministas y código de verificación |
| Acciones internas | Recuperar recuerdos y políticas (retrieval), razonar con el LLM, guardar un episodio o una preferencia (aprendizaje) |
| Acciones externas | Leer SQLite, consultar ViaCEP y responder al usuario |
| Ciclo de decisión | Proponer (regla o LLM con herramientas) → evaluar (verificación exacta y NLI) → ejecutar (publicar o corregir una vez) |

El ciclo de un turno es: **percibir** (extraer intención y restricciones del mensaje, cargar memoria), **decidir** (regla directa o agente con herramientas), **actuar** (consultar SQL, políticas o API y calcular), **verificar** (comprobaciones exactas y NLI) y **responder**. Si la propuesta no pasa la verificación, el agente dispone de una única pasada de corrección; si vuelve a fallar, no se publica la recomendación. El mismo flujo está en [arquitectura.mmd](arquitectura.mmd).

### 3. Clasificación: agente híbrido

| Capa | Comportamiento en Pedro | Por qué pertenece a esa capa |
|---|---|---|
| **Reactiva** | Pedir la cantidad cuando falta; enrutar «¿se puede mandar en varias cajas?» directamente a `consultar_politicas`; comparar ofertas en centavos enteros con desempate fijo; listar el catálogo; operar sin clave de OpenAI. | Estímulo → respuesta por regla fija, sin modelo del mundo ni planificación. Es predecible y verificable. |
| **Deliberativa** | El LLM decide qué herramientas llamar y en qué orden (hasta 6 iteraciones); mantiene un estado interno entre turnos (borrador, ventana de mensajes, recuerdos); contrasta su propuesta con la evidencia y la corrige una vez antes de publicar. | Hay representación de estado, elección entre alternativas y revisión de la propia salida frente a un objetivo. |

Pedro no es **reactivo puro** porque conserva estado entre turnos y elige herramientas según la solicitud. Tampoco es **deliberativo puro** porque no construye un plan explícito de varios pasos ni replanifica más allá de la única corrección, y porque una parte de las decisiones la toman reglas deterministas.

**Decisión técnica.** Se eligió el diseño híbrido de forma deliberada. En clase se definió la autonomía como un agente «pronto para tomar decisões e não só para obedecer direcionamentos», y se advirtió que usar un LLM solo para seguir órdenes es desperdiciar el recurso. Pedro aplica ese criterio donde aporta valor — interpretar la solicitud, elegir herramientas, redactar la respuesta — y lo retira donde un error tendría coste: los importes, el stock, los plazos y la procedencia de las fuentes se calculan y verifican con código determinista, nunca con el modelo.

### 4. Madurez agéntica: actual y objetivo

> **Supuesto declarado.** La escala de madurez se presentó en la primera clase, cuya transcripción no está en este workspace. Se usa aquí una escala genérica de cinco niveles; debe sustituirse por la escala exacta del curso cuando esté disponible, ajustando solo la etiqueta del nivel.

| Nivel | Descripción | ¿Pedro lo alcanza? |
|---|---|---|
| 1 | Chain fija: una llamada al LLM con entrada y salida estructuradas | Sí — [chains.py](../src/pedro/chains.py), notebook 01 |
| 2 | Enrutamiento: el flujo elige entre caminos predefinidos | Sí — `RouterCompras` en [legacy.py](../src/pedro/legacy.py) y rutas directas en [agent.py](../src/pedro/agent.py) |
| 3 | Agente con herramientas: el LLM decide qué herramienta usar | Sí — seis herramientas bajo `AgentExecutor` |
| 4 | Agente con memoria y autoverificación: estado entre turnos y sesiones, y revisión de la propia salida antes de publicar | **Sí — nivel actual** |
| 5 | Sistema multiagente o autónomo: planificación de largo horizonte, varios agentes, acciones con efecto real | No, y no es el objetivo |

**Madurez actual: nivel 4 en diseño, demostrado solo en local.** El agente decide herramientas, recuerda y se autoverifica, con autonomía acotada a propósito: solo lee del escenario, su única escritura es una preferencia explícita del usuario, tiene un máximo de 6 iteraciones y una sola corrección. Lo que falta para darlo por demostrado es evidencia con el modelo real: no hay todavía una sesión remota completa documentada ni métricas.

**Madurez objetivo: nivel 4 demostrado con mediciones.** Se considera alcanzado cuando se cumplan estos criterios:

| Criterio | Cómo se mide | Rúbrica |
|---|---|---|
| El LLM real elige las herramientas correctas | Trayectoria esperada frente a observada en los 30 casos de LangSmith | R29 |
| Las respuestas son correctas | Métricas de contenido, ganador e importe en LangSmith | R29 |
| Nada se publica sin respaldo | Cero recomendaciones publicadas que no pasen verificación exacta y NLI | R24 |
| Hay continuidad entre turnos con el modelo real | Sesión remota multi-turno documentada | R18, R26, R27 |

No se persigue el nivel 5 porque el problema — recomendar una oferta verificada para una pieza — no requiere varios agentes ni ejecutar compras, y más autonomía reduciría la trazabilidad que la puerta de verificación garantiza.

### Evidencia

| Evidencia | Ubicación | Tipo |
|---|---|---|
| Anatomía leída de los objetos reales del agente: modelo, executor, system message PTCF, seis herramientas con su papel y lógica, memoria, base de conocimiento y puerta de publicación | [notebooks/01_chain_mvp.ipynb](../notebooks/01_chain_mvp.ipynb) §«R01 · anatomía del agente»; [anatomia.py](../src/pedro/anatomia.py) | Ejecución real local (sin modelo) |
| Agente híbrido en acción: «lista piezas» y «Compara PEC-01-0001» se resuelven por regla con 0 llamadas al modelo; la pregunta de CEP pasa por el modelo, que recibe seis herramientas y ejecuta `consultar_cep` | [notebooks/01_chain_mvp.ipynb](../notebooks/01_chain_mvp.ipynb) §«R01 · agente híbrido» | Ejecución con **doble de prueba**: modelo guionado y ViaCEP simulado; el flujo, el executor, la herramienta y la verificación son los reales |
| La anatomía descrita coincide con el agente construido | [tests/test_anatomia.py](../tests/test_anatomia.py) | Prueba automática (32/32 pruebas) |
| Explicación de componentes, clasificación y madurez | Esta sección; [arquitectura.mmd](arquitectura.mmd) | Documentación |

### Pendientes y limitaciones

- La escala de madurez es genérica (supuesto declarado); sustituirla por la del curso cuando esté disponible la clase 1.
- En la demostración de la capa deliberativa la herramienta la pide un modelo guionado, no un LLM. La elección hecha por el modelo real se documenta en R26.
- El chat usa el índice de políticas demo en memoria; el índice preexistente que exige R22 aún no existe.

---

## R02 — Arquitectura de planificación y memoria aumentada

> ¿El alumno proyectó una arquitectura de planificación y memoria aumentada para el agente?

**Respuesta corta.** Una solicitud compleja se divide en cinco subtareas con salida observable (extraer, consultar, comparar, verificar, publicar). La memoria se reparte en dos niveles: la **sesión** guarda lo que solo sirve para la compra en curso y el **usuario** guarda lo que debe sobrevivir a la sesión. Ningún precio ni stock se toma de la memoria: siempre se releen del escenario activo.

### 1. Planificación: cómo se divide una solicitud

| Paso | Subtarea | Quién la hace | Salida observable |
|---|---|---|---|
| 1 | Extraer pieza, cantidad, presupuesto y plazo del mensaje; detectar qué falta | Regla determinista | Borrador `EstadoCompra` o pregunta de aclaración |
| 2 | Consultar los datos necesarios | Herramientas de lectura (SQL, FAISS, ViaCEP) | Ofertas, fragmentos de política o ciudad/UF |
| 3 | Comparar ofertas con las restricciones | Cálculo determinista en centavos | Alternativas con «cumple» o motivo de descarte |
| 4 | Verificar la propuesta | Verificación exacta y NLI | Lista de errores (vacía si pasa) |
| 5 | Publicar o corregir | Flujo | Respuesta pública, o una única corrección |

Hay dos planificadores, según el tipo de solicitud:

- **Plan fijo (capa reactiva).** Una compra con ID y cantidad sigue siempre los pasos 1 a 5 en ese orden, sin modelo.
- **Plan decidido por el LLM (capa deliberativa).** Cuando interviene el modelo — por ejemplo para confirmar un CEP o recalcular tras «ahora 3 unidades» —, el agente elige qué herramientas llamar y en qué orden dentro del `AgentExecutor`, con un máximo de 6 iteraciones. El prompt le da un «plan visible»: `buscar_productos` para resolver el ID, `consultar_catalogo` para las ofertas y `comparar_ofertas` para todos los importes.

Reglas de planificación:

- Solo se pregunta por lo que bloquea el plan: la pieza y la cantidad. Presupuesto y plazo son filtros opcionales.
- La petición actual prevalece sobre el historial: un cambio de cantidad conserva los demás límites.
- El plan nunca termina en una acción con efecto real: no hay compra ni pago.

**Decisión técnica.** No se añadió un planificador explícito (un paso que escriba el plan antes de actuar). Para un dominio con cinco subtareas conocidas, el plan fijo es más predecible y verificable, y el bucle de herramientas cubre los casos mixtos. Se descartó además guardar el razonamiento privado del modelo: lo que se conserva son las llamadas a herramientas, que son observables.

### 2. Memoria aumentada: qué va a cada nivel

| Información | Nivel | Dónde vive | Cuándo se actualiza o descarta |
|---|---|---|---|
| Mensaje actual | Corto plazo | Entrada del turno | Se sustituye en cada turno |
| Borrador de compra (pieza, cantidad, presupuesto, plazo) | Corto plazo | SQLite, por sesión | Cada turno; un ID distinto lo reinicia; «sin presupuesto/plazo» borra ese límite |
| Ventana de conversación | Corto plazo | Últimos 12 mensajes de la sesión | Ventana deslizante; el historial completo se conserva pero no se envía |
| Preferencias del usuario | Largo plazo (semántica) | SQLite, por usuario | Solo si el usuario la cita explícitamente; el valor nuevo reemplaza al anterior |
| Episodios de recomendaciones | Largo plazo (episódica) | SQLite con vector FastEmbed, por usuario | Se guarda cuando el agente publica una respuesta de compra verificada; se recupera por similitud (top 3) |
| Reglas, prompt y verificación | Largo plazo (procedimental) | Código y `prompts.py` | Cambia solo con una nueva versión del proyecto |
| Precios, stock y plazos | **No es memoria** | Escenario SQLite activo | Siempre se releen; los valores de un episodio se tratan como históricos |

**Decisión técnica.** La separación por sesión y por usuario evita dos errores del dominio: arrastrar la cantidad de una compra a otra, y recomendar con un precio viejo. Por eso el borrador muere con la sesión y los episodios se inyectan con la etiqueta «histórico» y la instrucción de no usar sus precios ni su stock. Cada recuerdo lleva su `dataset_id`, así que un episodio de otro catálogo queda identificado.

### Evidencia

| Evidencia | Ubicación | Tipo |
|---|---|---|
| Solicitud «Necesito 2 unidades de PEC-01-0001 hasta R$ 5.000 en 7 días» dividida en los cinco pasos, con la salida de cada uno | [notebooks/01_chain_mvp.ipynb](../notebooks/01_chain_mvp.ipynb) §«R02 · planificación» | Ejecución real local (sin modelo) |
| Corto plazo: al pedir «ahora 3 unidades» el borrador conserva el plazo de 7 días; 18 mensajes guardados, 12 visibles | [notebooks/01_chain_mvp.ipynb](../notebooks/01_chain_mvp.ipynb) §«R02 · memoria aumentada» | Ejecución real local (sin modelo) |
| Largo plazo: la preferencia aparece en una sesión nueva del mismo usuario y no en otro usuario; la sesión nueva empieza sin borrador | Mismo notebook | Ejecución real local |
| Plan decidido por el LLM real, por turnos: compra → `consultar_catalogo` y `comparar_ofertas`; CEP → `consultar_cep` (São Paulo/SP); «ahora 3 unidades» → `comparar_ofertas` con cantidad 3 y el plazo de 7 días conservado (R$ 4.401,99) | [trazas/r02_planificacion_llm.json](trazas/r02_planificacion_llm.json); [scripts/demostrar_r02.py](../scripts/demostrar_r02.py) | **Ejecución real remota** (OpenAI `gpt-4.1-mini`, ViaCEP real, NLI real local) |
| Pregunta de política por turnos: antes no se publicaba; tras anclar las citas se publica con dos fuentes | [trazas/r02_planificacion_llm_antes.json](trazas/r02_planificacion_llm_antes.json) y [trazas/r02_planificacion_llm.json](trazas/r02_planificacion_llm.json); [citas_ancladas.md](citas_ancladas.md) | Ejecución real remota, antes y después |
| Solicitud mixta en un solo turno: el LLM la dividió en las cinco herramientas necesarias (catálogo, comparación, políticas, CEP, búsqueda), pero la respuesta **no se publicó** | Mismo archivo | Ejecución real remota; resultado negativo conservado |
| Episodios vectoriales guardados, actualizados y recuperados | [notebooks/03_memoria_chatbot.ipynb](../notebooks/03_memoria_chatbot.ipynb) | Ejecución real local (FastEmbed) |
| Reglas del borrador y aislamiento | [tests/test_dialogue.py](../tests/test_dialogue.py); [tests/test_memory_nli.py](../tests/test_memory_nli.py) | Pruebas automáticas |

### Pendientes y limitaciones

- **Una solicitud mixta en un solo turno no se publica.** El LLM planifica bien las herramientas, pero `RespuestaCompra` admite un solo estado (recomendación, política o CEP) y la verificación rechaza la mezcla. El diseño vigente es una intención por turno; la solicitud compleja se resuelve repartida en turnos, como muestra la evidencia.
- **La pregunta general de política falló con el modelo real y se corrigió.** El modelo citaba el fragmento casi literal y la verificación exigía texto idéntico. Ahora el sistema ancla la cita al texto de la fuente; diagnóstico y antes/después en [citas_ancladas.md](citas_ancladas.md).
- No hay planificador explícito: el plan mixto lo decide el LLM en el bucle de herramientas y no queda escrito antes de ejecutarse.
- No hay resumen del historial: lo que sale de la ventana de 12 mensajes solo vuelve si quedó como episodio o preferencia.
- La trayectoria del LLM puede variar entre ejecuciones; la traza guardada es una observación, no una métrica.

## R03 — Plantillas de prompt reutilizables

> ¿El alumno construyó plantillas de prompt reutilizables con PromptTemplate o ChatPromptTemplate?

**Respuesta corta.** Sí. Hay dos `ChatPromptTemplate` con nombre propio en [prompts.py](../src/pedro/prompts.py): una para interpretar solicitudes de compra y otra para el agente final. La primera se reutiliza en dos cadenas distintas y se ejecutó con el modelo real sobre tres solicitudes del dominio.

### 1. Las plantillas

| Plantilla | Para qué sirve | Variables | Dónde se reutiliza |
|---|---|---|---|
| `PLANTILLA_EXTRACCION` (alias `PROMPT` en [chains.py](../src/pedro/chains.py)) | Interpretar una solicitud y devolver intención, datos y faltantes | `texto` (la solicitud) y `formato` (instrucciones del parser) | Cadena LCEL (`crear_lcel`) y cadena `@chain` (`crear_chain`) |
| `PLANTILLA_AGENTE`, usada por `crear_agente` en [agent.py](../src/pedro/agent.py) | System message PTCF del agente final | `dataset_id`, `ejemplos`, `formato`, `input`, `chat_history`, `agent_scratchpad` | Cada turno y cada corrección del agente, con cualquier escenario |

Las dos tienen la misma forma: un mensaje de sistema fijo con huecos y un mensaje humano con la solicitud. Los ejemplos few-shot están en el mismo archivo y entran a la plantilla del agente como una variable más.

### 2. Qué las hace reutilizables

- **Variables en lugar de texto fijo.** La solicitud, el escenario y los ejemplos se inyectan; el texto de la plantilla no cambia.
- **`partial` para lo que no cambia por turno.** Las instrucciones de formato salen del parser Pydantic y se fijan una vez; queda libre solo `texto`.
- **Un solo archivo.** Las dos plantillas y los ejemplos viven en `prompts.py`; el resto del código las importa.
- **Un objeto, varias cadenas.** La misma `PROMPT` alimenta la versión declarativa y la imperativa, así que un cambio de redacción se hace en un solo sitio.

**Decisión técnica.** Se eligió `ChatPromptTemplate` y no `PromptTemplate` porque el modelo es de chat y la plantilla necesita separar papeles: las reglas van en el mensaje de sistema y la solicitud del usuario en el mensaje humano. Esa separación evita que el texto del usuario se mezcle con las instrucciones. Coincide con la indicación de clase de centrarse en `ChatPromptTemplate` como patrón actual. No se añadió un `PromptTemplate` de texto plano solo para exhibirlo: la rúbrica pide una u otra y ningún punto del flujo usa un modelo de texto.

### Evidencia

| Evidencia | Ubicación | Tipo |
|---|---|---|
| La plantilla rellenada con tres solicitudes del dominio: clase, variables, `partial`, mensajes resultantes y comprobación de que la cadena LCEL usa la misma plantilla | [notebooks/01_chain_mvp.ipynb](../notebooks/01_chain_mvp.ipynb) §«R03 · plantilla reutilizable» | Ejecución real local (sin modelo) |
| La plantilla ejecutada con el modelo: «Compara 2 unidades de PEC-01-0001 hasta R$ 5.000 en 7 días» → comparar, 2 unidades, 500000 centavos, 7 días; «Necesito un termostato para nevera, sin prisa» → falta cantidad; «¿A qué ciudad corresponde el CEP 01001000?» → intención cep | [trazas/fase1_chain_llm.json](trazas/fase1_chain_llm.json); [scripts/demostrar_fase1.py](../scripts/demostrar_fase1.py) | **Ejecución real remota** (OpenAI `gpt-4.1-mini`, temperatura 0) |
| Cada plantilla declara sus variables, separa sistema y humano, sirve para cualquier escenario y falla si falta una variable | [tests/test_prompts.py](../tests/test_prompts.py) | Pruebas automáticas |
| La misma plantilla en las cadenas LCEL y `@chain` con modelo doble | [notebooks/01_chain_mvp.ipynb](../notebooks/01_chain_mvp.ipynb), primera celda | Ejecución con doble de prueba |

### Pendientes y limitaciones

- La ejecución real es una sola corrida de tres solicitudes; no mide la tasa de acierto de la extracción.

## R04 — Output parser con salida estructurada en JSON

> ¿El alumno implementó un output parser para generar salida estructurada en JSON a partir de la chain?

**Respuesta corta.** Sí. La cadena convierte una solicitud en un objeto `Extraccion` validado con Pydantic. Además se construyó un **laboratorio de salidas rotas**: ocho defectos típicos de un modelo, cada uno resuelto por una capa distinta, con el modelo real haciendo las reparaciones.

### 1. De la solicitud al objeto validado

«Compara 2 unidades de PEC-01-0001 hasta R$ 5.000 en 7 días» produce, con el modelo real:

```json
{"intencion": "comparar",
 "solicitud": {"producto_id": "PEC-01-0001", "cantidad": 2,
               "presupuesto_centavos": 500000, "plazo_max_dias": 7},
 "faltantes": []}
```

El esquema está en [contracts.py](../src/pedro/contracts.py) y la cadena en [chains.py](../src/pedro/chains.py): plantilla → modelo → `PydanticOutputParser` → regla de dominio.

### 2. Tres capas de defensa

Un modelo puede fallar de tres maneras distintas, y cada una necesita una defensa diferente:

| Capa | Qué defiende | Cómo |
|---|---|---|
| **Sintaxis** | Que la salida sea JSON | El parser tolera cercas de markdown y texto alrededor |
| **Esquema** | Que los datos tengan el tipo correcto | Pydantic rechaza «dos» como cantidad, una cantidad negativa o una intención fuera de la lista |
| **Dominio** | Que el dato signifique lo correcto | Los faltantes los recalcula el código: no se confía en lo que el modelo declare. Un dato ausente es `null`, nunca cero |

Cuando la sintaxis o el esquema fallan, una **segunda cadena repara** la salida (`crear_lcel_robusta`). Recibe la solicitud original, la salida inválida y el mensaje de error, y su respuesta vuelve a pasar por el mismo parser. Está montada con `with_fallbacks`, así que la reparación solo se ejecuta si hay error. Hay una sola reparación: si también falla, el error se propaga y no se publica nada.

### 3. El laboratorio de salidas rotas

Ocho salidas para la misma solicitud. El generador es un doble que emite el defecto; el reparador es `gpt-4.1-mini` real.

| Defecto | Capa que lo resolvió | Reparaciones | Datos finales correctos |
|---|---|---|---|
| JSON válido | Ninguna | 0 | Sí |
| Cercas markdown y charla alrededor | Parser | 0 | Sí |
| JSON truncado | Reparación | 1 | Sí |
| Cantidad en letras («dos») | Reparación | 1 | Sí |
| Cantidad negativa | Reparación | 1 | Sí |
| Intención fuera de la lista | Reparación | 1 | Sí |
| Texto libre sin JSON | Reparación | 1 | Sí |
| Faltantes mal declarados | Regla de dominio | 0 | Sí (marca «cantidad» como faltante) |

### 4. Hallazgo: un parser tolerante puede perder datos en silencio

Al montar el laboratorio apareció algo que no estaba previsto. El parser de LangChain acepta JSON cortado. Con la cadena simple, una salida truncada se convirtió en un objeto válido **sin el plazo de 7 días y sin ningún error**. En este dominio eso es grave: la comparación se haría sin un límite que el usuario sí pidió.

La corrección fue añadir a la cadena robusta una comprobación estricta de que el JSON esté entero. Si no lo está, la salida va a reparación. La cadena simple conserva el comportamiento original, y una prueba deja documentados los dos resultados.

### 5. Parser frente a `with_structured_output`

En clase se vieron dos formas de obtener salida estructurada. Se ejecutaron las dos con el modelo real sobre las tres solicitudes y dieron **el mismo resultado**.

| | `PydanticOutputParser` | `with_structured_output` |
|---|---|---|
| Cómo fuerza el formato | Instrucciones dentro del prompt | Esquema enviado por la API del modelo |
| Funciona con cualquier modelo | Sí, también con dobles de prueba | Solo si el modelo lo soporta |
| Se puede probar sin credenciales | Sí | No |
| Permite ver y reparar la salida cruda | Sí | No, la salida ya llega convertida |

**Decisión técnica.** Se mantiene `PydanticOutputParser` como patrón principal por dos razones: la rúbrica pide un output parser, y es la única opción que deja ver el texto crudo del modelo, que es lo que hace posible el laboratorio, la reparación y las pruebas sin credenciales.

### Evidencia

| Evidencia | Ubicación | Tipo |
|---|---|---|
| Objeto validado desde tres solicitudes, con `invoke` y `batch` | [trazas/fase1_chain_llm.json](trazas/fase1_chain_llm.json) | **Ejecución real remota** (`gpt-4.1-mini`, temperatura 0) |
| Laboratorio: cinco reparaciones hechas por el modelo real, todas con datos finales correctos | Mismo archivo, `laboratorio_salidas_rotas`; [laboratorio.py](../src/pedro/laboratorio.py) | Real remoto para el reparador; el generador es un **doble** |
| `with_structured_output` igual que el parser en las tres solicitudes | Mismo archivo, `with_structured_output` | Ejecución real remota |
| Laboratorio y pérdida silenciosa de datos, reproducibles sin credenciales | [notebooks/01_chain_mvp.ipynb](../notebooks/01_chain_mvp.ipynb) §«R04» | Ejecución con **doble** (generador y reparador) |
| Cada defecto cae en su capa; la reparación recibe solicitud, salida y error; una reparación fallida no se publica; el parser simple pierde el plazo y la cadena robusta no | [tests/test_salida_estructurada.py](../tests/test_salida_estructurada.py) | Pruebas automáticas |

### Pendientes y limitaciones

- La cadena de extracción es didáctica: el chat extrae las restricciones con reglas deterministas ([dialogue.py](../src/pedro/dialogue.py)), no con esta cadena. El agente final sí usa `PydanticOutputParser` para `RespuestaCompra`.
- Las salidas rotas se escribieron a mano; no son fallos observados del modelo real, que en estas ejecuciones respondió siempre con JSON válido.
- Una sola reparación por diseño. No se midió con qué frecuencia el modelo real necesitaría reparación.

## R05 — Runnable (invoke, batch, stream) y composición con @chain

> ¿El alumno aplicó la interfaz Runnable (invoke, batch, stream) e implementó composición imperativa con el decorador @chain?

**Respuesta corta.** Sí. Los tres métodos se ejecutaron con el modelo real y se midió para qué sirve cada uno. Hay dos cadenas con `@chain`: una simple y otra con reparación de errores escrita paso a paso.

### 1. Los tres métodos, con el modelo real

Todo objeto de LangChain que sea `Runnable` ofrece los mismos tres métodos. Se usaron sobre la cadena de extracción:

| Método | Para qué sirve | Qué se observó |
|---|---|---|
| `invoke` | Una entrada, una salida | «Compara 2 unidades de PEC-01-0001 hasta R$ 5.000 en 7 días» → objeto validado |
| `batch` | Varias entradas a la vez | 3 solicitudes en **1,43 s**; las mismas 3 con `invoke` en serie tardaron **4,55 s**. Mismos resultados |
| `stream` | Recibir la salida a medida que se genera | **19 estados parciales**; el primero a los **0,45 s** de un total de 1,07 s |

Son una sola medición cada una: sirven para ver el efecto, no como benchmark.

### 2. Lo aprendido sobre `stream`

`stream` solo transmite si **todos** los pasos de la cadena saben transmitir. Se comprobó con dos cadenas:

- Con el parser Pydantic llega **un único fragmento**: necesita el JSON completo para validarlo.
- Con el parser de JSON parcial (`crear_lcel_parcial`) llega el objeto mientras se forma: `{}` → `{"intencion": "comparar", "solicitud": {"producto_id": "PEC"}}` → … → objeto completo.

La consecuencia práctica: para mostrar progreso al usuario sirve la segunda; para decidir una compra solo vale la primera, porque un estado parcial todavía no está validado.

### 3. Composición imperativa con `@chain`

`@chain` convierte una función de Python en un `Runnable`: dentro se escribe código normal y por fuera tiene `invoke`, `batch` y `stream`.

| Cadena | Qué hace |
|---|---|
| `crear_chain` | Envuelve la extracción en una función decorada |
| `crear_chain_robusta` | La extracción con reparación de R04, escrita con `try/except`: genera, intenta validar y, si falla, llama a la cadena reparadora |

```python
@chain
def extraer_con_reparacion(dato: dict) -> Extraccion:
    salida = generar.invoke(dato)
    try:
        extraccion = parser.parse(salida)
        if not _json_completo(salida):
            raise OutputParserException("JSON incompleto: la salida se cortó antes de cerrar")
    except OutputParserException as error:
        corregida = reparar.invoke({"texto": dato["texto"], "salida": salida, "error": error})
        extraccion = parser.parse(corregida)
    return _validar(extraccion)
```

Se pasó el laboratorio de salidas rotas de R04 por esta versión y por la declarativa: las dos resolvieron los ocho casos en la misma capa y con los mismos datos, también con el modelo real como reparador.

**Decisión técnica.** Se escribió la versión imperativa de la cadena con reparación, y no solo un envoltorio trivial, porque es donde `@chain` aporta algo: el control de errores se lee de arriba abajo y se puede depurar con un punto de parada. La comparación con la versión declarativa y la elección del patrón principal se justifican en R06.

### Evidencia

| Evidencia | Ubicación | Tipo |
|---|---|---|
| `invoke`, `batch` y `stream` con tiempos, estados parciales y resultado de `@chain` | [trazas/fase1_chain_llm.json](trazas/fase1_chain_llm.json); [scripts/demostrar_fase1.py](../scripts/demostrar_fase1.py) | **Ejecución real remota** (`gpt-4.1-mini`, temperatura 0); una medición |
| Cadena imperativa igual a la declarativa en los ocho casos del laboratorio, con el modelo real reparando | Mismo archivo, `laboratorio_con_chain_imperativa` | Real remoto para el reparador; generador **doble** |
| Los tres métodos sobre `@chain`, stream de 1 fragmento frente a estados parciales, y código de la cadena imperativa | [notebooks/01_chain_mvp.ipynb](../notebooks/01_chain_mvp.ipynb) §«R05» | Ejecución con **doble** (modelo que emite el JSON en trozos) |
| `@chain` expone los tres métodos; el stream parcial emite varios estados; imperativa y declarativa son equivalentes | [tests/test_salida_estructurada.py](../tests/test_salida_estructurada.py) | Pruebas automáticas |

### Pendientes y limitaciones

- Los tiempos son de una sola ejecución y dependen de la red.
- El chat de Streamlit no usa `stream`: muestra la respuesta completa porque debe pasar la verificación antes de publicarse.
- `batch` no se usa en el flujo del chat, que atiende una solicitud por turno; sí lo usaría una evaluación por lotes.

## R06 — Composición declarativa con LCEL y justificación

> ¿El alumno implementó la composición declarativa de la chain con LCEL y justificó la elección entre composición imperativa y declarativa?

**Respuesta corta.** Sí. Hay cuatro cadenas LCEL y la misma cadena con reparación existe en los dos estilos. La elección no se justifica con opiniones: se midió qué deja ver cada estilo. **LCEL es el patrón principal para las cadenas; el código imperativo se reserva para decidir el camino de cada turno.**

### 1. Las cadenas LCEL

| Cadena | Composición | Qué muestra de LCEL |
|---|---|---|
| `crear_lcel` | `plantilla \| modelo \| parser \| regla` | El operador `\|` como secuencia |
| `crear_lcel_robusta` | `assign(salida=…) \| analizar.with_fallbacks([reparar]) \| regla` | Tratamiento de errores declarativo |
| `crear_lcel_parcial` | `plantilla \| modelo \| JsonOutputParser` | Transmisión de estados parciales |
| `composicion_paralela` | `RunnableParallel({…}) \| resumen` | Ramas independientes en paralelo |

Todas están en [chains.py](../src/pedro/chains.py).

### 2. La misma cadena en los dos estilos

`crear_lcel_robusta` (declarativa) y `crear_chain_robusta` (imperativa) hacen lo mismo: extraer, validar y reparar una vez si hace falta. Dan **el mismo resultado** en los ocho casos del laboratorio, también con el modelo real. Lo que cambia es lo que se puede observar desde fuera. Esto se midió ejecutando las dos:

| Medida | Declarativa (LCEL) | Imperativa (`@chain`) |
|---|---|---|
| Pasos que registra la traza, sin fallo | 10 | 5 |
| Pasos que registra la traza, con reparación | 16 | 9 |
| El fallo del parser queda anotado en la traza | Sí | No |
| La validación de dominio queda anotada | Sí | No |
| El grafo muestra la reparación | Sí (`WithFallbacks`) | No |
| Resultado tras reparar | Correcto | Correcto |

La razón: en `@chain`, el `try/except` y la llamada a la regla de dominio son Python normal, y LangChain no puede verlos. En LCEL cada paso es un objeto con nombre.

### 3. Comparación

| Criterio | Declarativa (LCEL) | Imperativa (`@chain`) |
|---|---|---|
| Observabilidad | Cada paso y cada error aparecen en la traza | Solo se ven los componentes que se invocan dentro |
| Lectura | Se lee como una tubería; el error es una rama declarada | Se lee de arriba abajo, como cualquier función |
| Depuración | Por la traza | Con un punto de parada |
| Control de flujo | Secuencia, paralelo y fallback | Cualquiera: bucles, varias ramas, salidas anticipadas |
| Cambiar «una reparación» por «hasta tres» | Hay que reestructurar la cadena | Se cambia el `try` por un bucle |
| `invoke`, `batch`, `stream` | Los tres | Los tres |

### 4. Decisión

- **Patrón principal: LCEL**, para todo lo que sea una tubería: plantilla, modelo, parser, reparación y ramas paralelas. En este proyecto la trazabilidad importa más que la flexibilidad: la rúbrica y el dominio piden poder demostrar qué pasó en cada paso, y con LCEL un error o una reparación quedan registrados sin escribir código adicional.
- **Imperativo solo para orquestar el turno.** La función `turno` de `crear_flujo`, en [agent.py](../src/pedro/agent.py), es código imperativo envuelto como `Runnable`. Tiene salidas anticipadas (comando de diagnóstico, ruta directa, aclaración), un bucle de dos propuestas y condiciones que dependen del resultado anterior. Expresar eso con LCEL lo haría más difícil de leer. Lo que LangChain no ve ahí se anota a mano en la traza (`Traza`), como el anclaje de citas; las llamadas a herramientas las registra el callback.

En una frase: **declarativo para lo que es una tubería, imperativo para lo que es una decisión.**

### Evidencia

| Evidencia | Ubicación | Tipo |
|---|---|---|
| Medición de traza, error y grafo en los dos estilos, y diagrama Mermaid de la cadena LCEL | [notebooks/01_chain_mvp.ipynb](../notebooks/01_chain_mvp.ipynb) §«R06»; `comparar_estilos` en [laboratorio.py](../src/pedro/laboratorio.py) | Ejecución real local con **dobles** (sin modelo) |
| Los dos estilos dan el mismo resultado en el laboratorio, con el modelo real reparando | [trazas/fase1_chain_llm.json](trazas/fase1_chain_llm.json), `laboratorio_con_chain_imperativa` | Real remoto para el reparador; generador **doble** |
| Cadena LCEL con el modelo real: `invoke`, `batch` y `stream` | Mismo archivo | **Ejecución real remota** |
| Los estilos coinciden en resultado y difieren en lo que ve la traza | [tests/test_salida_estructurada.py](../tests/test_salida_estructurada.py) | Pruebas automáticas |
| Composición paralela ejecutada | [notebooks/02_react_herramientas.ipynb](../notebooks/02_react_herramientas.ipynb) | Ejecución real local |

### Pendientes y limitaciones

- Los recuentos de pasos corresponden a esta cadena y a la versión instalada de LangChain; pueden cambiar con otra versión.
- No se midió rendimiento: los dos estilos llaman al modelo las mismas veces.
- La función `turno` usa `RunnableLambda`, no el decorador `@chain`; el decorador se demuestra en las cadenas de extracción.

---

# Fase 2 — Agente con herramientas y ReAct

## R07 — Comparación de orquestadores y elección de LangChain

> ¿El alumno comparó orquestadores de agentes autónomos y justificó la elección de LangChain para el problema?

**Respuesta corta.** Sí. Se comparan los seis orquestadores vistos en clase con los criterios de clase (autonomía, abstracción y modularidad). LangChain se mantiene porque Pedro es **un solo agente** que necesita **muchas piezas distintas** bajo un control estricto, y LangChain las trae todas: el proyecto usa 13 tipos de componentes suyos.

### 1. Para qué sirve un orquestador

En clase (14-10-2026) se dieron cuatro razones para no programar el agente desde cero: escalabilidad, gestión de la complejidad, estandarización y confiabilidad. Se añadieron dos propiedades que un orquestador debe facilitar: **autonomía** (que el agente decida y no solo obedezca) y **modularidad** (poder añadir o quitar componentes).

### 2. Comparación

| Orquestador | Idea central | Autonomía | Abstracción | Modularidad | Encaje con Pedro |
|---|---|---|---|---|---|
| **LangChain** | Componentes que se encadenan: plantillas, modelos, parsers, herramientas, memoria | Media: el agente elige herramientas dentro de un ejecutor acotado | Media: se ve y se controla cada paso | Alta: cada pieza se cambia por separado | **Alto** |
| **LangGraph** | Grafo de estados con ciclos y puntos de control; misma familia que LangChain | Alta y controlable: el flujo es un grafo explícito | Baja-media: hay que definir estado, nodos y aristas | Alta | Alto, pero más de lo necesario |
| **LlamaIndex** | Centrado en datos: indexar documentos y consultarlos | Media | Alta para RAG | Media: gira en torno a índices | Parcial: Pedro es más que RAG |
| **AutoGen** | Varios agentes que conversan entre sí | Alta: los agentes se coordinan solos | Alta | Media | Bajo: aquí hay un solo agente |
| **Semantic Kernel** | Funciones («plugins») y planificadores, orientado a integrarse en aplicaciones de empresa | Media | Media | Alta | Medio: su ecosistema natural es otro |
| **Langflow** | Construcción visual, sin código o con poco código | La que tenga el flujo dibujado | Muy alta | Media: se trabaja con cajas | Bajo para un entregable de código probado |

La tabla es conceptual. **Solo LangChain se ejecutó en este proyecto**; no se atribuye ninguna prueba a los demás.

### 3. Por qué LangChain para este problema

1. **El problema es de un solo agente.** Recomendar una oferta verificada no necesita agentes que conversen. La coordinación multiagente de AutoGen añadiría mensajes que auditar sin resolver nada.
2. **Hacen falta muchas piezas distintas, no una sola.** El proyecto usa 13 tipos de componentes de LangChain (34 nombres importados): plantillas, parsers, composición LCEL, herramientas, agente y ejecutor, memoria, historial, callbacks, FAISS, embeddings, troceado, cadenas clásicas y el modelo de chat. Este inventario sale de leer los imports del código. Un orquestador centrado en datos como LlamaIndex cubriría bien la parte de políticas y dejaría fuera el resto.
3. **El control importa más que la autonomía.** El dominio maneja importes, stock y plazos: el agente debe ser auditable. La abstracción media de LangChain deja ver cada paso —la traza de R06 lo demostró— y permite intercalar la verificación antes de publicar.
4. **Se puede probar sin credenciales.** Cualquier componente se sustituye por un doble porque todos comparten la interfaz `Runnable`. Todas las pruebas automáticas del proyecto corren sin llamar a ningún modelo.
5. **La rúbrica nombra APIs de LangChain**: `initialize_agent`, `RouterChain`, `ConversationBufferMemory`, `create_openai_tools_agent`, `AgentExecutor` y `RunnableWithMessageHistory`.

### 4. Lo que LangChain no resuelve bien aquí

La elección tiene un coste, y conviene decirlo. Tres de las APIs que pide la rúbrica están marcadas como obsoletas por la propia biblioteca (`initialize_agent`, `ConversationBufferMemory` y `RunnableWithMessageHistory`), y sus avisos recomiendan pasar a LangGraph. En clase se usó la forma moderna, `create_agent` con memoria por `thread_id`.

Por eso las APIs clásicas están aisladas en [legacy.py](../src/pedro/legacy.py) y el flujo del turno —que tiene ramas, un bucle de dos propuestas y salidas anticipadas— está escrito a mano. Ese flujo es justamente lo que LangGraph modelaría como un grafo. **Si el proyecto siguiera creciendo, el paso natural sería migrar la orquestación del turno a LangGraph y conservar los componentes de LangChain.**

### Evidencia

| Evidencia | Ubicación | Tipo |
|---|---|---|
| Inventario de piezas de LangChain usadas, obtenido de los imports | [notebooks/02_react_herramientas.ipynb](../notebooks/02_react_herramientas.ipynb) §«R07»; `inventario_langchain` en [anatomia.py](../src/pedro/anatomia.py) | Ejecución real local (sin modelo) |
| Tabla comparativa y decisión | Esta sección; [comparaciones.md](comparaciones.md) | Documentación |
| El inventario refleja el código | [tests/test_anatomia.py](../tests/test_anatomia.py) | Prueba automática |

### Pendientes y limitaciones

- La comparación con LangGraph, LlamaIndex, AutoGen, Semantic Kernel y Langflow es conceptual: no se instalaron ni se ejecutaron.
- Las valoraciones de autonomía, abstracción y modularidad son cualitativas.

## R08 — Agente ReAct con initialize_agent, herramientas y memoria

> ¿El alumno construyó un agente con herramientas y memoria e implementó el patrón ReAct con initialize_agent?

**Respuesta corta.** Sí. Hay un agente ReAct construido con `initialize_agent` y `ZERO_SHOT_REACT_DESCRIPTION`, con dos herramientas y `ConversationBufferMemory`. Se ejecutó con el modelo real: razona, elige la herramienta y responde. Además se comprobó que la memoria solo sirve si el prompt la incluye.

### 1. El agente

Está en `crear_react_textual`, en [legacy.py](../src/pedro/legacy.py).

| Parte | En el código |
|---|---|
| Patrón ReAct | `initialize_agent(..., agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION)` |
| Herramientas | `buscar_pieza` (por nombre, SKU o ID) y `ofertas_de_pieza` (proveedor, precio, stock y plazo de un ID) |
| Memoria | `ConversationBufferMemory`, que guarda cada pregunta y respuesta |
| Límites | 5 iteraciones como máximo y tolerancia a errores de formato del modelo |

ReAct significa razonar y actuar en ciclo: el modelo escribe un pensamiento, elige una acción, recibe una observación y repite hasta tener la respuesta.

### 2. El ciclo ReAct, con el modelo real

Segundo turno de la conversación, tal como lo escribió `gpt-4.1-mini`:

```text
Pregunta:     ¿Cuál de sus proveedores entrega más rápido y en cuántos días?
Thought:      Para responder a esta pregunta, necesito obtener las ofertas de la pieza
              con ID PEC-01-0001 para ver los proveedores, precios, stock y plazos de entrega.
Action:       ofertas_de_pieza
Action Input: PEC-01-0001
Observation:  [ofertas del catálogo: proveedor, precio, stock y plazo]
Respuesta:    El proveedor que entrega más rápido es CentroPeças, con un plazo de entrega de 2 días.
```

El dato es correcto: en el catálogo, CentroPeças (BR-06) tiene plazo de 2 días para esa pieza.

### 3. Lo aprendido: la memoria no sirve si el prompt no la lee

El prompt zero-shot original solo tiene dos variables: la pregunta y el borrador de razonamiento. `ConversationBufferMemory` guarda la conversación, pero **el modelo nunca la ve**. Se ejecutó la misma conversación de dos turnos de las dos maneras:

| | Historial dentro del prompt | Prompt zero-shot original |
|---|---|---|
| Variables del prompt | `input`, `chat_history`, `agent_scratchpad` | `input`, `agent_scratchpad` |
| Turno 1: «Busca el compresor con SKU NEVE-COMP-0001 y dime su ID» | `buscar_pieza` → PEC-01-0001 | `buscar_pieza` → PEC-01-0001 |
| Turno 2: «¿Cuál de **sus** proveedores entrega más rápido…?» | `ofertas_de_pieza(PEC-01-0001)` → CentroPeças, 2 días | No sabe a qué pieza se refiere y pide el ID |

La corrección fue añadir `{chat_history}` al sufijo del prompt mediante `agent_kwargs`. En los dos casos la memoria guardó lo mismo; la diferencia está en si llega al modelo.

**Decisión técnica.** Este agente clásico se conserva aislado en `legacy.py` como demostración del patrón. El agente final de Pedro usa `create_openai_tools_agent` (R26) por tres motivos: las herramientas reciben argumentos con tipo en vez de un único texto; la decisión de llamar a una herramienta la devuelve la API del modelo y no hay que interpretarla de un texto libre; y `initialize_agent` está marcado como obsoleto por LangChain.

### Evidencia

| Evidencia | Ubicación | Tipo |
|---|---|---|
| Conversación de dos turnos con pensamiento, acción, observación y respuesta, con y sin historial en el prompt | [trazas/r08_react_llm.json](trazas/r08_react_llm.json); [scripts/demostrar_r08.py](../scripts/demostrar_r08.py) | **Ejecución real remota** (`gpt-4.1-mini`, temperatura 0) |
| El mismo agente con herramientas reales y memoria, reproducible sin credenciales | [notebooks/02_react_herramientas.ipynb](../notebooks/02_react_herramientas.ipynb) §«R08» | Ejecución con **doble** (`FakeListLLM` guionado) |
| El agente ejecuta las dos herramientas y guarda memoria; el historial solo entra al prompt si se configura | [tests/test_legacy.py](../tests/test_legacy.py) | Pruebas automáticas con doble |

### Pendientes y limitaciones

- Es una conversación; no mide con qué frecuencia el modelo elige bien la herramienta.
- `initialize_agent` y `ConversationBufferMemory` emiten avisos de obsolescencia en la versión instalada de LangChain.
- La memoria de buffer guarda todo el historial sin límite; el control de la ventana se trata en R14.

## R09 — Chains secuenciales o paralelas y RouterChain

*Pendiente de redactar.*

## R10 — API externa como herramienta vía function calling

*Pendiente de redactar.*

## R11 — Prompt PTCF, few-shot y chain-of-thought

*Pendiente de redactar.*

## R12 — Componentes de confiabilidad

*Pendiente de redactar.*

---

# Fase 3 — Chatbot con memoria

## R13 — Memoria de corto y largo plazo según CoALA

*Pendiente de redactar.*

## R14 — Ventana de contexto con búsqueda vectorial

*Pendiente de redactar.*

## R15 — Comparación de herramientas especializadas de memoria

*Pendiente de redactar.*

## R16 — Chatbot con ConversationBufferMemory

*Pendiente de redactar.*

## R17 — Reconocimiento de intención y extracción de entidades

*Pendiente de redactar.*

## R18 — Contexto y descomposición en una conversación real multi-turno

*Pendiente de redactar.*

---

# Fase 4 — SQL, APIs y RAG existente

## R19 — Herramientas hardcoded y semánticas

*Pendiente de redactar.*

## R20 — Integración con APIs internas o externas

*Pendiente de redactar.*

## R21 — Patrón text-to-query

*Pendiente de redactar.*

## R22 — Agente de recuperación sobre un índice FAISS existente

> ¿El alumno construyó un agente de recuperación usando un índice FAISS existente?

**Respuesta corta.** Sí. El índice está guardado en `knowledge/politicas/` y el agente solo lo **carga**; no lo reconstruye. Antes de abrirlo comprueba su manifiesto y sus huellas. Con el índice cargado, el modelo real respondió dos preguntas de política citando sus fuentes.

### 1. Indexar y recuperar son dos pasos separados

| Paso | Cuándo ocurre | Quién lo hace |
|---|---|---|
| **Indexar** | Una vez, fuera del agente | [construir_indice_politicas.py](../scripts/construir_indice_politicas.py): trocea el corpus, calcula embeddings, guarda `index.faiss`, `index.pkl` y `manifest.json` |
| **Recuperar** | En cada pregunta | `cargar_indice` en [rag.py](../src/pedro/rag.py) abre lo guardado; la herramienta `consultar_politicas` busca en él |

El índice tiene 75 fragmentos, 384 dimensiones y métrica L2, con el modelo de embeddings `paraphrase-multilingual-MiniLM-L12-v2`. Cargarlo tardó 0,03 s, porque no se calcula ningún embedding.

### 2. La puerta antes de cargar

El docstore de FAISS es un archivo pickle, y abrir un pickle ajeno puede ejecutar código. Por eso la carga exige tres cosas:

| Comprobación | Qué pasa si falla |
|---|---|
| Manifiesto completo: origen, modelo, dimensión, métrica y documentos | `ValueError: manifiesto incompleto` |
| Huella SHA-256 de `index.faiss` e `index.pkl` igual a la del manifiesto | `ValueError: huella incorrecta: index.pkl` |
| Confianza explícita del operador | `PermissionError: se requiere confianza explícita…` |

Tras cargar, se vuelve a comparar dimensión, recuento, métrica, identificadores y metadatos con el manifiesto. Una prueba adicional avisa si el corpus cambió después de indexar.

### 3. El agente recuperando

| Pregunta | Qué hizo | Respuesta publicada |
|---|---|---|
| «¿Cómo se comprueba la compatibilidad eléctrica antes de instalar una pieza?» | El LLM llamó a `consultar_politicas`; cita literal de `FIC-GAR-01-S03-C01`; pasó verificación y NLI | Resumen de la regla con su fuente |
| «¿Se puede mandar en varias cajas?» | Ruta de entrega: reformula la consulta y recupera `FIC-ENT-01-S05-C01` | Regla de entrega parcial con su fuente |

**Decisión técnica.** Se mantuvo el modelo de embeddings local (FastEmbed) en lugar de uno de OpenAI para que cargar y consultar el índice no dependa de credenciales ni de un servicio externo. El modelo queda escrito en el manifiesto y la carga se niega si el que se usa para consultar es otro, porque los vectores no serían comparables.

### Evidencia

| Evidencia | Ubicación | Tipo |
|---|---|---|
| Índice guardado con manifiesto y huellas | [knowledge/politicas/](../knowledge/politicas/) | Artefacto versionado |
| Carga desde disco, puerta de seguridad, herramienta y dos preguntas al agente | [trazas/r22_indice_existente.json](trazas/r22_indice_existente.json); [scripts/demostrar_r22.py](../scripts/demostrar_r22.py) | **Ejecución real remota** (`gpt-4.1-mini`), NLI real local |
| Carga del índice y recuperación sin credenciales | [notebooks/04_rag_text_to_query.ipynb](../notebooks/04_rag_text_to_query.ipynb) §«R22» | Ejecución real local |
| El índice se carga sin indexar, corresponde al corpus actual y la puerta rechaza carga sin confianza o con un archivo alterado | [tests/test_indice_existente.py](../tests/test_indice_existente.py) | Pruebas automáticas |

### Pendientes y limitaciones

- **El índice es propio.** La guía habla del «índice FAISS preexistente exigido por la actividad», pero el enunciado original no está en este workspace y no se recibió ningún índice del curso. Se construyó uno a partir del corpus ficticio y se guardó como artefacto. Si el profesor entrega un índice, basta con sustituir la carpeta: el cargador y las pruebas son los mismos.
- La app solo usa este índice si `PEDRO_TRUST_POLICY_INDEX=true` está en `.env`. Sin esa variable avisa y usa el índice de demostración en memoria, con el mismo contenido.
- El corpus son tres políticas ficticias; no hay políticas reales.

## R23 — Diagnóstico y corrección de un fallo real de recuperación

> ¿El alumno documentó una falla real de recuperación a partir de los documentos fuente retornados y justificó la técnica de corrección aplicada?

**Respuesta corta.** Sí. Una pregunta coloquial no recuperaba la regla correcta aunque estaba en el corpus. Se diagnosticó con los fragmentos devueltos y se corrigió reformulando la consulta. El antes y el después se midieron sobre el índice guardado en disco.

### 1. El fallo

Pregunta: «¿Se puede mandar en varias cajas?». La respuesta está en `entrega.md`, sección 5 («Entrega parcial y stock»), fragmento `FIC-ENT-01-S05-C01`. Con top-4, ese fragmento **no aparece**:

| Posición | Fragmento devuelto | Sección | Distancia L2 |
|---|---|---|---|
| 1 | `FIC-ENT-01-S04-C01` | Recepción y comprobación inmediata | 12,845 |
| 2 | `FIC-GAR-01-S06-C01` | Situaciones fuera de la cobertura | 13,336 |
| 3 | `FIC-DEV-01-S03-C01` | Daño visible y contenido incompleto | 13,389 |
| 4 | `FIC-GAR-01-S01-C01` | Propósito y piezas cubiertas | 14,045 |

### 2. Diagnóstico

Los cuatro fragmentos hablan de cajas y paquetes en sentido físico: recibirlos, abrirlos, daños. La pregunta dice «varias cajas» y la política dice «entrega parcial». Es un **desajuste de vocabulario**: el usuario y el documento nombran la misma idea con palabras distintas, y el embedding acerca la pregunta a los textos que comparten la palabra «caja».

No es un problema del corpus (la regla existe) ni del troceado (está entera en un fragmento).

### 3. Corrección: reformular la consulta

Se reescribe la pregunta con el término del dominio, **sin incluir la respuesta**: «¿Cuándo admite la política de entrega un envío parcial de las piezas solicitadas?». Mismo índice, mismo top-4:

| Posición | Fragmento devuelto | Distancia L2 |
|---|---|---|
| **1** | **`FIC-ENT-01-S05-C01`** | **10,216** |
| 2 | `FIC-ENT-01-S01-C01` | 11,819 |
| 3 | `FIC-ENT-01-S04-C01` | 12,317 |
| 4 | `FIC-DEV-01-S08-C02` | 12,437 |

**Por qué esta técnica.** El diagnóstico apunta al vocabulario de la consulta, así que se corrige la consulta. Las alternativas atacan otra causa: subir el top-k trae más ruido sin arreglar el orden, y cambiar el troceado no ayuda porque el fragmento ya estaba completo. El filtro por tema (`tema=entrega`) también recupera el fragmento, pero exige saber de antemano el tema; se dejó como prueba aparte.

En el agente, la herramienta `consultar_politicas` aplica esta reformulación a las preguntas sobre dividir un envío y devuelve los fragmentos de antes y de después, de modo que el diagnóstico queda en la traza de cada respuesta.

### Evidencia

| Evidencia | Ubicación | Tipo |
|---|---|---|
| Antes y después sobre el **índice guardado en disco**, con fuente, identificador y distancia L2 | [trazas/r23_t24_indice_existente.json](trazas/r23_t24_indice_existente.json); [scripts/diagnosticar_t24.py](../scripts/diagnosticar_t24.py) | Ejecución real local |
| El mismo contraste reproducible sin credenciales | [notebooks/04_rag_text_to_query.ipynb](../notebooks/04_rag_text_to_query.ipynb) §«T24» y §«R22» | Ejecución real local |
| La pregunta coloquial respondida por el agente con la regla correcta | [trazas/r22_indice_existente.json](trazas/r22_indice_existente.json) | Ejecución real remota |
| Diagnóstico ampliado y pruebas | [t24_recuperacion.md](t24_recuperacion.md); [tests/test_rag_diagnostics.py](../tests/test_rag_diagnostics.py) | Documentación y pruebas |

### Pendientes y limitaciones

- El fallo se localizó en un corpus ficticio propio; es real en el sentido de que se observó, no se fabricó alterando resultados.
- La reformulación está escrita como regla para las preguntas de envío dividido. No es una reescritura general hecha por el LLM.
- Es un caso; no se midió cuántas preguntas del corpus fallan del mismo modo.

---

# Fase 5 — Agente final verificado y evaluado

## R24 — Verificación de consistencia factual y coherencia lógica

*Pendiente de redactar.*

## R25 — Agente único con herramientas de RAG, SQL o API

*Pendiente de redactar.*

## R26 — Executor con create_openai_tools_agent y AgentExecutor

*Pendiente de redactar.*

## R27 — Historial con RunnableWithMessageHistory

*Pendiente de redactar.*

## R28 — Integración del agente en Streamlit

*Pendiente de redactar.*

## R29 — Evaluación de calidad y trayectoria con LangSmith

*Pendiente de redactar.*
