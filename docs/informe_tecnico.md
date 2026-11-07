# Informe técnico — Pedro — Asistente de Compras

## Estado del informe

Borrador editable. No se ha generado PDF final ni se han inventado métricas. El enunciado, kit de referencia e índice FAISS originales siguen pendientes.

## Objetivo y arquitectura

Pedro — Asistente de Compras estudia interpretación de solicitudes, agentes con herramientas, memoria, RAG, verificación y evaluación. Véase [diagrama](diagramas.md) y [matriz provisional](matriz_R01_R29.md).

## Resultados observados

- La suite local aprobó 15 pruebas el 7 de noviembre de 2026 con Python 3.13. Abarca reglas, límites inclusivos, identidades, SQL tipado, memoria, ViaCEP simulado en errores, ReAct didáctico, few-shot, composición, NLI guionado y puerta de publicación. Las pruebas guionadas no miden calidad de un modelo remoto.
- Los cinco notebooks ejecutaron sus celdas en un kernel Jupyter local. NB04 identifica expresamente la ausencia del índice FAISS de políticas.
- ViaCEP real respondió `São Paulo/SP` para `01001000`; detalle en [evidencia](evidencia_viacep.md).
- `AppTest` inició Streamlit sin excepciones. No se ejecutó un turno real del chat con modelo.
- El SDK de LangSmith evaluó localmente tres casos de componentes con `upload_results=False`: 3/3. Registro real en `storage/evals/componentes.json`; no es un experimento remoto ni una evaluación del agente completo.

## Evaluación pendiente

Registrar aquí versión del modelo, dataset de referencia, 30 escenarios del agente, métricas por grupo, trayectorias y enlaces reales de LangSmith. Añadir comparación antes/después de recuperación sobre el mismo índice. Exportar el PDF solo después de adjuntar resultados observados y cotejar los 29 criterios con la rúbrica.

## Fuentes y herramientas de IA

Se utilizó Codex para planificación, revisión EGM y desarrollo asistido. Dos revisores Goldfish independientes auditaron el plan; hallazgos en `goldfish_review_report.md`. Las bibliotecas y documentación técnica se citan en `comparaciones.md`, el README y el código.
