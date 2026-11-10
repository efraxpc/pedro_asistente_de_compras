"""PTCF y ejemplos de acciones observables, ajenos a los casos de evaluación."""

EJEMPLOS_ACCIONES = """
Ejemplo A — «Necesito un filtro para lavadora; el plazo no está indicado».
Plan observable: buscar candidatos por nombre; si hay varios, pedir ID; pedir cantidad
si falta. Presupuesto y plazo son opcionales. Salida: aclaracion, sin inventar ceros.

Ejemplo B — «Compara 3 unidades de PEC-10-0123 hasta R$ 900 en 12 días».
Plan observable: consultar catálogo de PEC-10-0123; llamar comparar_ofertas con
cantidad=3, presupuesto_centavos=90000 y plazo_max_dias=12 si el usuario indicó esos límites; citar cada oferta.
Salida: recomendacion solo si una oferta cumple; de lo contrario sin_oferta.

Ejemplo C — «¿Qué dice la política sobre piezas dañadas?».
Plan observable: consultar_politicas; citar fuente_id y fragmento exacto.
Salida: politica solo si el fragmento respalda la afirmación; sin_evidencia si no hay cobertura.

Ejemplo D — «¿Se puede mandar en varias cajas?».
Plan observable: tratar como pregunta de entrega; llamar consultar_politicas con la pregunta
original. La herramienta puede reformular «varias cajas» como «envío parcial» y devuelve
fragmentos antes/después. Citar la regla recuperada; no pedir ID de pieza ni cantidad.
"""
