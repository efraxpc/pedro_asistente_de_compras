# Evaluación

`extra_scenarios.json` define los diez escenarios adicionales. No son resultados ejecutados. Los 20 escenarios derivados del kit se generarán en otro archivo cuando se reciba el kit; los 20 originales permanecerán intactos y separados. Así, el conjunto inicial del agente tendrá 20 derivados + 10 adicionales = 30, y los 20 originales conservarán su procedencia.

Las pruebas de componentes están en `tests/`. Una ejecución real de LangSmith requiere `LANGSMITH_API_KEY`, trazas activadas y un modelo configurado. No se han generado métricas de agente ni enlaces de experimentos.

`uv run python evals/evaluar_componentes.py` ejecuta tres casos de componentes con el SDK de LangSmith y `upload_results=False`. Guarda un registro local en `storage/evals/componentes.json`. Incluye la fixture del prompt y no sustituye los casos originales ni una evaluación de agente completo.
