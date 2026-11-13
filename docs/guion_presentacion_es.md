# Guion para entender y presentar Pedro

**Para qué sirve:** es lo que tienes que saber para explicar el proyecto con tus palabras. Está escrito fácil, sin tecnicismos de más.

**Cómo usarlo:** lee una parte cada vez. Cada parte termina con una frase lista para decir.

## 1. Pedro en 30 segundos

Pedro es un asistente de compras. Vende piezas de electrodomésticos, pero todos los datos son inventados.

Tú le dices qué pieza quieres y cuántas. Él mira qué proveedores la tienen, descarta los que no sirven y te recomienda el mejor.

**Frase para decir:** «Pedro compara proveedores y recomienda el mejor, y nunca inventa un precio.»

## 2. Las cinco ideas que sí o sí debes saber

### Idea 1: el corazón es comparar proveedores

Para cada pieza hay tres ofertas: dos de proveedores de Brasil y una de un proveedor de fuera.

Pedro descarta una oferta por cuatro motivos:

- No hay stock suficiente.
- Pides menos unidades que el pedido mínimo del proveedor.
- Tarda más días que tu plazo.
- Cuesta más que tu presupuesto.

Con las que quedan, elige la más barata. Si empatan, la que llega antes.

**Frase para decir:** «Primero descarta, después ordena por precio.»

### Idea 2: el modelo decide, el sistema pone los datos

El modelo de inteligencia artificial es bueno entendiendo lo que le pides. Pero puede equivocarse con los números.

Por eso en Pedro el modelo solo decide qué hacer. Los precios, los totales y las citas los pone el programa, con cálculos fijos.

**Frase para decir:** «El modelo elige qué responder; las cifras las pone el sistema.»

### Idea 3: nada se publica sin revisar

Antes de mostrarte una respuesta, Pedro la revisa dos veces:

- **Revisión exacta:** el proveedor, el total y las fuentes tienen que coincidir con el cálculo.
- **Revisión de sentido:** un segundo modelo pequeño comprueba que la frase dice lo mismo que los datos.

Si falla, Pedro tiene una sola oportunidad de corregir. Si vuelve a fallar, no inventa: dice que no puede confirmar.

**Frase para decir:** «Prefiere no responder antes que responder mal.»

### Idea 4: Pedro tiene memoria

- **Memoria corta:** recuerda tu pedido mientras hablas. Si dices «ahora que sean 6», no tienes que repetir la pieza.
- **Memoria larga:** recuerda tus preferencias entre conversaciones. Si dices «prefiero proveedores nacionales», lo guarda.

**Frase para decir:** «Recuerda el pedido dentro de la conversación y tus preferencias entre conversaciones.»

### Idea 5: está medido, no solo demostrado

Pedro se probó con 30 casos de examen. Acertó el proveedor ganador en 14 de 14 y el importe en 14 de 14.

**Frase para decir:** «No digo que funciona: lo medí.»

## 3. Las palabras difíciles, en fácil

| Palabra | Qué significa |
|---|---|
| **LLM** | El modelo de lenguaje. Aquí es `gpt-4.1-mini`. Es el «cerebro» que entiende el texto |
| **Agente** | Un programa que usa el modelo para decidir qué hacer y qué herramienta usar |
| **Herramienta** | Una función que el agente puede llamar. Ejemplo: comparar ofertas |
| **Prompt** | Las instrucciones que le escribes al modelo |
| **Plantilla de prompt** | Un prompt con huecos, que se reutiliza |
| **Few-shot** | Darle al modelo ejemplos ya resueltos para que copie la forma |
| **Parser** | Lo que convierte la respuesta del modelo en datos ordenados y revisa que estén bien |
| **Cadena (chain)** | Varios pasos unidos: plantilla, modelo, parser |
| **LCEL** | La forma de unir esos pasos con el símbolo de barra vertical |
| **ReAct** | El ciclo del agente: pensar, usar una herramienta, mirar el resultado |
| **Memoria** | Lo que se guarda para no empezar de cero en cada mensaje |
| **Embedding** | Convertir un texto en números, para buscar textos parecidos |
| **FAISS** | El buscador que encuentra los textos más parecidos |
| **RAG** | Buscar primero en documentos y responder con lo que se encontró |
| **NLI** | Un modelo pequeño que dice si una frase está respaldada por otra |
| **Anclar** | Cambiar lo que escribió el modelo por el dato real del sistema |
| **LangChain** | La librería que une modelo, herramientas y memoria |
| **Streamlit** | La librería con la que está hecha la pantalla del chat |
| **LangSmith** | El servicio donde se hizo el examen de 30 casos |

## 4. Qué pasa cuando escribes un mensaje

Ejemplo: «Compare 5 unidades de PEC-01-0001 com prazo de 7 dias».

- **Paso 1. Entender.** Pedro saca los datos: pieza `PEC-01-0001`, cantidad 5, plazo 7 días.
- **Paso 2. Decidir.** El agente decide usar la herramienta de comparar ofertas.
- **Paso 3. Calcular.** La herramienta revisa las tres ofertas y descarta dos.
- **Paso 4. Anclar.** El sistema pone las cifras del cálculo en la respuesta.
- **Paso 5. Revisar.** Pasa la revisión exacta y la revisión de sentido.
- **Paso 6. Mostrar.** El chat dibuja las tarjetas y la tabla.

El resultado de ese ejemplo:

| Proveedor | Total | Qué pasa |
|---|---|---|
| CentroPeças | R$ 7.279,83 | Cumple. Entrega en 2 días. Es el recomendado |
| Litoral Parts | R$ 1.930,40 | Descartado: no tiene stock y tarda 12 días |
| Atlantic Repair Parts | R$ 7.344,92 | Descartado: tarda 35 días |

**Ojo con esto:** la oferta más barata no gana, porque no cumple. Es un buen ejemplo para explicar por qué primero se descarta.

## 5. Las cinco fases, en fácil

El curso tiene 29 rúbricas, agrupadas en cinco fases. Cada fase añade algo a la anterior.

### Fase 1: una cadena que entiende el pedido (R01 a R06)

- **Qué es:** convertir una frase en datos, con una plantilla, el modelo y un parser.
- **Ejemplo:** de «Compare 5 unidades…» salen pieza, cantidad y plazo.
- **Para decir:** «Empecé por lo más simple: entender el pedido.»
- **Dónde está:** `src/pedro/chains.py` y `src/pedro/prompts.py`.

### Fase 2: el agente usa herramientas (R07 a R12)

- **Qué es:** el modelo ya no solo entiende; decide qué herramienta llamar.
- **Ejemplo:** para un código postal, llama a la herramienta que consulta ViaCEP y responde São Paulo/SP.
- **Para decir:** «El agente no se sabe los datos: los pide a sus herramientas.»
- **Dónde está:** `src/pedro/agent.py` y `src/pedro/integrations.py`.

### Fase 3: el agente recuerda (R13 a R18)

- **Qué es:** memoria corta y memoria larga.
- **Ejemplo:** «Agora que sejam 6 e mantenha o prazo» cambia solo la cantidad: R$ 8.718,75.
- **Para decir:** «No tengo que repetirle el pedido en cada mensaje.»
- **Dónde está:** `src/pedro/memory.py` y `src/pedro/dialogue.py`.

### Fase 4: el agente consulta datos (R19 a R23)

- **Qué es:** tres fuentes. El catálogo (con SQL), las políticas (con RAG) y una API externa.
- **Ejemplo:** «Posso receber em várias caixas?» no encontraba la regla. Pedro reformula la pregunta y la regla aparece primera.
- **Para decir:** «Encontré un fallo real de búsqueda, lo medí y lo corregí.»
- **Dónde está:** `src/pedro/query.py`, `src/pedro/rag.py` y `src/pedro/policy_demo.py`.

### Fase 5: todo junto, revisado y medido (R24 a R29)

- **Qué es:** las revisiones antes de publicar, el chat y el examen de 30 casos.
- **Ejemplo:** ganador correcto en 14 de 14.
- **Para decir:** «El agente final está verificado y evaluado.»
- **Dónde está:** `src/pedro/verification.py`, `app.py` y `evals/avaliar_fluxo.py`.

## 6. Los números que debes saber de memoria

| Número | Qué es |
|---|---|
| **29** | Rúbricas del curso, en 5 fases |
| **4.320** | Piezas del catálogo, de 18 electrodomésticos |
| **12** | Proveedores: 6 de Brasil y 6 de fuera |
| **3** | Ofertas por pieza |
| **6** | Herramientas del agente |
| **12** | Mensajes que el modelo ve a la vez |
| **1** | Corrección permitida si la revisión falla |
| **159** | Pruebas automáticas |
| **5** | Notebooks, uno por fase |
| **30** | Casos del examen en LangSmith |
| **14 de 14** | Ganador correcto, y también importe correcto |
| **R$ 7.279,83** | El ejemplo principal: 5 unidades de PEC-01-0001 |

## 7. Cuatro resultados que demuestran que aprendiste

Son mediciones reales del proyecto. Sirven para responder «¿y eso por qué lo hiciste así?».

- **Dar ejemplos al modelo funciona.** Sin ejemplos entendió bien 6 de 10 pedidos. Con ejemplos, 10 de 10.
- **Reglas más modelo es mejor que solo reglas.** Con solo reglas entendía 8 de 14 mensajes. Con reglas y modelo, 14 de 14.
- **Varias peticiones a la vez es más rápido.** Tres pedidos juntos tardaron unas tres veces menos que uno por uno.
- **El consejo de precio se revisa.** De 15 consejos escritos por el modelo, 14 pasaron la revisión y 1 se cambió por un aviso fijo.

## 8. Preguntas que te pueden hacer

**¿Qué tipo de agente es?**
Híbrido. Tiene reglas fijas para lo simple y usa el modelo para lo abierto.

**¿Por qué no dejas que el modelo calcule el precio?**
Porque puede equivocarse con los números. El cálculo lo hace el programa, con centavos enteros.

**¿Qué pasa si el modelo inventa algo?**
La revisión lo detecta. Tiene una corrección; si falla otra vez, Pedro dice que no puede confirmar.

**¿Por qué usaste LangChain?**
Construí el mismo agente con LangChain y con LangGraph. Respondieron igual, pero LangGraph guardó el resultado de una herramienta y no la volvió a llamar. En Pedro los precios y el stock se deben leer de nuevo cada vez. Además, la rúbrica pide las funciones de LangChain.

**¿Qué es RAG en tu proyecto?**
Buscar en las políticas de la tienda por significado y responder citando la fuente.

**¿Cómo sabes que funciona?**
Por tres cosas: 159 pruebas automáticas, demostraciones guardadas con el modelo real y el examen de 30 casos.

**¿Qué memoria tiene?**
Corta: el pedido en curso y los últimos 12 mensajes. Larga: tus preferencias y recuerdos de conversaciones pasadas.

**¿Los datos son reales?**
No. Catálogo, proveedores, precios y políticas son inventados. Lo único real es la consulta de códigos postales.

**¿Qué mejorarías?**
Usar casos de evaluación oficiales, un índice de políticas dado por el curso y que Pedro sepa conversar de temas que no son compras.

## 9. Lo que no funciona perfecto, dicho por ti

Decirlo tú primero da confianza. Son límites reales del proyecto:

- **Los 30 casos de examen los generé yo.** No son los oficiales del curso.
- **El examen se hizo antes de ampliar el catálogo.** Usó las mismas 30 preguntas, con 2.640 piezas.
- **El índice de políticas es propio.** Lo construí con el corpus inventado.
- **Una respuesta de políticas varía.** A veces Pedro publica su resumen y a veces solo la cita literal, según pase o no la revisión.
- **Pedro no charla.** Si le dices «hola, ¿qué tal?», no tiene una buena respuesta.
- **La revisión de sentido se equivoca a veces.** Puede rechazar una frase que era correcta. Cuando pasa, se muestra un texto fijo.

## 10. Cómo estudiar esto en tres ratos cortos

- **Rato 1 (20 minutos):** partes 1, 2 y 3. Repite en voz alta las cinco frases para decir.
- **Rato 2 (20 minutos):** partes 4 y 5. Abre el chat y haz el ejemplo de PEC-01-0001.
- **Rato 3 (20 minutos):** partes 6, 7, 8 y 9. Tapa las respuestas e intenta contestar.

Para ver lo mismo con imágenes, usa el vídeo del recorrido: docs/tour/tour_rubricas.mp4.

## 11. El día de la presentación

- Ejecuta `./project.sh restart` y comprueba que el chat diga «Agente ativo».
- Pulsa «Novo chat» para empezar limpio.
- Ten abierto el guion del vídeo: docs/roteiro_video.md.
- Empieza por la frase de la parte 1.
- Si Pedro responde con otras palabras, no pasa nada: mira solo las cifras.
