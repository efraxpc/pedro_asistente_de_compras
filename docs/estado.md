# Estado verificable

## Implementado y probado localmente

- Catálogo aleatorio SQLite versionado con semilla y tres ofertas por producto.
- Reglas deterministas de comparación, contratos Pydantic y verificación contra todas las ofertas activas.
- Text-to-query por plan tipado y SQL parametrizado de solo lectura.
- Memoria SQLite por usuario/sesión, episodios con recuperación vectorial de demostración y `RunnableWithMessageHistory` como escritor de respuestas finales.
- Agente clásico con seis herramientas, verificación exacta y puerta NLI; una corrección como máximo.
- ReAct textual con buffer y RouterChain concreto para demostración.
- PTCF, cuatro ejemplos few-shot ajenos a evaluación y composición secuencial/paralela ejecutables.
- Streamlit local y chat online condicionado a credenciales.
- [ViaCEP real](evidencia_viacep.md) consultado una vez con respuesta `São Paulo/SP`.
- Evaluación offline de tres casos de **componentes** con el SDK de LangSmith: 3/3 correctos, `upload_results=False`, registro local en `storage/evals/componentes.json`.
- Cinco notebooks ejecutados en un kernel Jupyter local, todavía incompletos como evidencias académicas.

## Pendiente de integración o evidencia

- Enunciado/rúbrica, diseño, plan detallado, kit, 20 casos originales y FAISS preconstruido no están en el entorno.
- Importador del kit y escenario de referencia completo no se pueden acreditar sin los datos originales.
- Calibración semántica de recuerdos con embeddings reales, fallo real de RAG antes/después, evaluación de 30 escenarios del agente y experimentos remotos de LangSmith.
- Prueba real del modelo de chat y del NLI remoto; las pruebas de agentes usan respuestas guionadas.
- Informe técnico con métricas reales, PDF y video real de entrega.

Las pruebas simuladas de un componente no acreditan una integración externa. El informe EGM de la primera ronda está en `goldfish_review_report.md` y no ha convergido.
