# Informe técnico — Pedro Infnet

**Fecha:** 2026-11-08. **Proyecto:** reconstrucción independiente de asistente de compras sobre piezas ficticias. **Estado:** núcleo local ejecutado; integraciones dependientes de insumos y credenciales identificadas como pendientes.

## Objetivo y datos

Pedro consulta y compara ofertas sintéticas de repuestos de electrodomésticos. El generador usa semilla 20261107 y produce 2640 piezas, 7920 ofertas, 7920 compatibilidades y 47520 precios históricos. Cada escenario copia la base a un SQLite propio con UUID y manifiesto SHA-256. La ficha técnica identifica la fuente sintética; precios y stock vigentes se leen siempre del escenario. No se hacen compras ni pagos.

## Arquitectura

La interfaz conserva user_id, session_id y dataset_id. El flujo del chat carga los 12 mensajes previos y recuerdos por usuario, crea un agente OpenAI tools con seis herramientas, analiza una RespuestaCompra Pydantic, verifica todas las ofertas activas y sus evidencias, aplica NLI local a las afirmaciones publicables y solo entonces renderiza. Se permite una corrección interna total. RunnableWithMessageHistory escribe la petición y la respuesta pública; las propuestas rechazadas solo viven en la traza de ejecución.

La comparación local usa el mismo cálculo y el mismo verificador exacto. Presupuesto, precio unitario, flete y total son enteros en centavos. La regla exige stock suficiente, plazo no superior al máximo y total no superior al presupuesto; desempata por total, plazo e ID de proveedor. La vista de catálogo presenta 20 piezas por página.

Text-to-query valida un PlanConsulta y compila exclusivamente plantillas SELECT con parámetros; SQLite se abre en modo solo lectura. El índice FAISS de políticas se carga solo tras revisar manifiesto, hashes, dimensión, métrica, recuento, modelo y confianza explícita para el docstore pickle. El índice oficial no estaba disponible y ninguna respuesta de políticas se presenta como verificada.

## Enseñanza y comparación

Los notebooks 01–05 cubren extracción LCEL y @chain; ReAct clásico y RouterChain; memoria CoALA; SQL y la ranura de FAISS; y el integrador. El ReAct textual, ConversationBufferMemory y FakeListLLM son demostraciones didácticas. El integrador usa herramientas ligadas al escenario y una puerta de publicación. AutoGen, Mem0 y Letta se comparan conceptualmente en docs/comparaciones.md; no se atribuyen pruebas ejecutadas a esas bibliotecas. Los ejemplos few-shot del prompt describen acciones observables y no incluyen casos de evaluación.

## Verificación observada

La sincronización bloqueada de dependencias terminó correctamente. Dieciocho pruebas pasaron y los cinco notebooks se ejecutaron con NotebookClient. Streamlit respondió ready por Agent API en Chat, Catálogo y Comparación local; la comparación de dos unidades de PEC-01-0001 con R$ 100000 y 60 días eligió BR-06 por R$ 2.963,07. Una llamada HTTP real a ViaCEP para 01001000 devolvió São Paulo/SP. FastEmbed produjo vectores de 384 dimensiones y recuperó un episodio actualizado entre sesiones. El modelo NLI fijado clasificó tres pares ilustrativos como entailment, contradiction y neutral; una recomendación local completa obtuvo verificación exacta sin errores y NLI positivo. Las pruebas de reparación del agente usaron un executor guionado y no demuestran calidad de un LLM remoto.

## Riesgos y trabajo dependiente

El PDF oficial, el índice FAISS y las credenciales remotas no están en este workspace. Por ello la matriz de 30 identificadores es provisional, la evaluación LangSmith remota no tiene tasas y el fallo de recuperación sobre el corpus oficial no está acreditado. Se prepararon 30 casos derivados sintéticos con referencias congeladas para LangSmith, sin ejecutar evaluación remota. La búsqueda semántica opcional de piezas no se implementó; la búsqueda actual es SQL. El modelo NLI se ejecuta en CPU y su descarga inicial puede tardar. Antes de entregar, cotejar la rúbrica de 29 criterios, incorporar el índice autorizado, ejecutar chat y LangSmith reales con referencias y denominadores, grabar el vídeo con webcam y verificar el enlace Drive.
