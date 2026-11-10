# T24: diagnóstico de recuperación

## Corpus y método

Esta prueba local usa el **índice ficticio en memoria** de `knowledge/politicas_demo/`, no un índice preexistente autorizado. La versión 1.1 contiene 75 fragmentos con IDs, documento, tema y sección. Huella SHA-256 del corpus: `b9dec4509b36aa722e03bff45c14876339e52831e12f8b311de6287ed5bce6c3`. Se usó FastEmbed `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, FAISS con métrica **L2**, `k=4`, `fetch_k=20` y sin filtro en ambas consultas. En L2, menor distancia indica mayor cercanía.

El fragmento esperado, `FIC-ENT-01-S05-C01`, existe en el docstore: `entrega.md`, sección «5. Entrega parcial y stock». Su texto exige un acuerdo simulado explícito para describir una entrega parcial, con unidades, proveedor y plazos de cada envío.

## Fallo observado

Pregunta inicial: **«¿Se puede mandar en varias cajas?»**

| Posición | Fragmento | Fuente / sección | Distancia L2 |
|---:|---|---|---:|
| 1 | `FIC-ENT-01-S04-C01` | `entrega.md` / recepción | 12,845 |
| 2 | `FIC-GAR-01-S06-C01` | `garantia.md` / exclusiones | 13,336 |
| 3 | `FIC-DEV-01-S03-C01` | `devoluciones.md` / daño visible | 13,389 |
| 4 | `FIC-GAR-01-S01-C01` | `garantia.md` / propósito | 14,045 |

El fragmento que contiene la regla de entrega parcial quedó fuera del top 4. **Diagnóstico inferido:** «varias cajas» se relacionó con embalaje y daño, mientras la regla se expresa como «entrega parcial»; las coincidencias de otros temas ocuparon dos posiciones.

## Corrección y contraste

Pregunta reformulada: **«¿Cuándo admite la política de entrega un envío parcial de las piezas solicitadas?»** La reformulación aclara la intención sin incluir la respuesta. Se mantuvieron índice, modelo, métrica, `k`, `fetch_k` y ausencia de filtro.

| Posición | Fragmento | Fuente / sección | Distancia L2 |
|---:|---|---|---:|
| 1 | `FIC-ENT-01-S05-C01` | `entrega.md` / entrega parcial | 10,216 |
| 2 | `FIC-ENT-01-S01-C01` | `entrega.md` / plazos | 11,819 |
| 3 | `FIC-ENT-01-S04-C01` | `entrega.md` / recepción | 12,317 |
| 4 | `FIC-DEV-01-S08-C02` | `devoluciones.md` / catálogo | 12,437 |

Como prueba separada, aplicar `tema=entrega` a la pregunta inicial sitúa el fragmento esperado en la posición 2 (L2 = 14,982); ese filtro **no** forma parte de la comparación antes/después. El [notebook 04](../notebooks/04_rag_text_to_query.ipynb) conserva la ejecución y `scripts/diagnosticar_t24.py` reproduce el informe JSON en `storage/evidencias/t24_demo.json`. En el chat de Streamlit, `/t24` muestra el mismo contraste sin invocar un LLM.

Para probar el **flujo normal**, haga la pregunta inicial en el chat con el índice ficticio cargado. La ruta de entrega del flujo llama `consultar_politicas` de forma determinista para preguntas coloquiales sobre dividir paquetes y reformula la intención como entrega parcial sin añadir la regla. La respuesta extrae dos frases del fragmento recuperado, verifica su procedencia y usa NLI local antes de publicarlas. El resumen de recuperación se genera a partir de los resultados de la herramienta. Se verificaron tres repeticiones en la misma sesión, incluso con un borrador de compra pendiente, tanto en el flujo local con NLI real como en Streamlit. La ruta cubre esta intención del corpus sintético; otras formulaciones y el índice preexistente necesitan pruebas propias.

## Límite de la evidencia

Esto demuestra el método de T24 sobre datos ficticios. Para acreditar R22/R23 de la guía aún falta obtener el índice FAISS **preexistente y autorizado**, verificar su manifiesto y repetir allí un fallo y una corrección observables sobre el mismo corpus.
