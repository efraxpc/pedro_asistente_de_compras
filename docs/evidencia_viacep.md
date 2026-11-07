# Evidencia de ViaCEP real

Fecha de ejecución: 2026-11-07. Comando:

```bash
uv run python - <<'PY'
from compraslab.integrations import consultar_cep
print(consultar_cep('01001000').model_dump())
PY
```

Resultado observado: `estado=ok`, `cep=01001000`, `cidade=São Paulo`, `uf=SP`, `simulado=False`, fuente `ViaCEP:01001000`. La consulta confirma destino; no obtiene flete, plazo ni datos comerciales. Esta ejecución prueba una llamada real puntual, no disponibilidad permanente del servicio.
