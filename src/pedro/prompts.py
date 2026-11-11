"""Plantillas reutilizables (PTCF) y ejemplos de acciones observables.

Los ejemplos son ajenos a los casos de evaluación.
"""
from langchain_core.prompts import (ChatPromptTemplate, FewShotChatMessagePromptTemplate,
                                    MessagesPlaceholder)

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

Ejemplo E — «Prefiero proveedores nacionales, recuérdalo».
Plan observable: llamar guardar_preferencia con clave=proveedor, valor=nacionales y la cita
literal del usuario. Salida: preferencia. No comparar ofertas ni pedir datos en ese turno.
"""

# Interpreta una solicitud de compra. Variables: texto (solicitud) y formato (parser).
PLANTILLA_EXTRACCION = ChatPromptTemplate.from_messages([
    ("system", "Persona: Pedro. Tarea: extraer intención y solicitud de compra ficticia. "
     "Contexto: ninguna cifra ausente se infiere como cero. Formato: JSON válido. {formato}"),
    ("human", "{texto}"),
])

# Ejemplos few-shot de extracción. Cubren los errores típicos: cantidades en palabras, importes
# abreviados, correcciones dentro de la frase y datos ausentes (null, nunca cero ni uno).
EJEMPLOS_EXTRACCION = [
    {"texto": "Quiero una decena de PEC-09-0009 por hasta R$ 2,5 mil",
     "razonamiento": ["«una decena» son 10 unidades", "«R$ 2,5 mil» son 250000 centavos",
                      "no menciona plazo: queda null"],
     "solicitud": {"producto_id": "PEC-09-0009", "cantidad": 10, "presupuesto_centavos": 250000},
     "faltantes": []},
    {"texto": "Compara PEC-09-0010 en 5 días",
     "razonamiento": ["no dice cuántas unidades: cantidad queda null, no 1", "plazo máximo 5 días",
                      "no menciona presupuesto: queda null"],
     "solicitud": {"producto_id": "PEC-09-0010", "plazo_max_dias": 5},
     "faltantes": ["cantidad"]},
    {"texto": "Tres PEC-09-0011... perdón, cuatro. Sin tope de dinero, en tres semanas",
     "razonamiento": ["se corrige: valen 4 unidades, no 3", "«sin tope de dinero»: presupuesto null",
                      "«tres semanas» son 21 días"],
     "solicitud": {"producto_id": "PEC-09-0011", "cantidad": 4, "plazo_max_dias": 21},
     "faltantes": []},
]


def _ejemplos_como_mensajes(con_razonamiento: bool) -> FewShotChatMessagePromptTemplate:
    import json

    filas = []
    for ejemplo in EJEMPLOS_EXTRACCION:
        salida = {"intencion": "comparar", "solicitud": ejemplo["solicitud"],
                  "faltantes": ejemplo["faltantes"]}
        if con_razonamiento:
            salida = {"razonamiento": ejemplo["razonamiento"], **salida}
        filas.append({"texto": ejemplo["texto"],
                      "salida": json.dumps(salida, ensure_ascii=False)})
    return FewShotChatMessagePromptTemplate(
        examples=filas,
        example_prompt=ChatPromptTemplate.from_messages([("human", "{texto}"), ("ai", "{salida}")]))


_SISTEMA_EXTRACCION = ("Persona: Pedro. Tarea: extraer intención y solicitud de compra ficticia. "
                       "Contexto: ninguna cifra ausente se infiere como cero. Formato: JSON válido. "
                       "{formato}")

# Misma tarea con ejemplos resueltos (few-shot).
PLANTILLA_EXTRACCION_FEWSHOT = ChatPromptTemplate.from_messages([
    ("system", _SISTEMA_EXTRACCION), _ejemplos_como_mensajes(False), ("human", "{texto}")])

# Few-shot con chain-of-thought visible: cada ejemplo razona antes de dar los datos.
PLANTILLA_EXTRACCION_COT = ChatPromptTemplate.from_messages([
    ("system", _SISTEMA_EXTRACCION + " Razona paso a paso en el campo razonamiento antes de "
     "rellenar los datos."),
    _ejemplos_como_mensajes(True), ("human", "{texto}")])

# Repara una salida que no cumple el esquema. Variables: texto, salida, error y formato.
PLANTILLA_REPARACION = ChatPromptTemplate.from_messages([
    ("system", "Persona: revisor de formato de Pedro. Tarea: corregir una salida que no cumple "
     "el esquema. Contexto: usa solo la solicitud original; lo que la solicitud no diga queda "
     "null, nunca cero ni un valor supuesto. Formato: solo JSON válido. {formato}"),
    ("human", "Solicitud original: {texto}\nSalida inválida: {salida}\nError de validación: {error}"),
])

# Text-to-SQL: convierte una pregunta en un SELECT. Variables: esquema, max_filas, formato,
# pregunta y error (vacío salvo en el intento de corrección).
PLANTILLA_SQL = ChatPromptTemplate.from_messages([
    ("system", "Persona: analista de datos del catálogo ficticio de Pedro. "
     "Tarea: escribir UNA consulta SELECT de SQLite que responda la pregunta. "
     "Contexto: solo existen estas tablas y columnas:\n{esquema}\n"
     "Los importes están en centavos de real (estimated_brl_cents, shipping_brl_cents). "
     "suppliers.domestic vale 1 si el proveedor es nacional. Hay stock si stock_qty > 0. "
     "Formatos de los valores: parts.id y offers.part_id son como PEC-01-0001; parts.sku es como "
     "NEVE-COMP-0001; suppliers.id es como BR-06. "
     "Reglas: solo lectura; una sola sentencia; sin comentarios; no uses tablas ni columnas "
     "que no estén en la lista; no uses SELECT *, nombra las columnas; no añadas filtros que la "
     "pregunta no pida; añade siempre LIMIT con {max_filas} filas como máximo. "
     "Si la pregunta pide modificar datos, escribe un SELECT que muestre los datos afectados, "
     "nunca una modificación. Formato: {formato}"),
    ("human", "Pregunta: {pregunta}\n{error}"),
])

# System message del agente final. Variables: dataset_id, ejemplos, formato, input,
# chat_history (opcional) y agent_scratchpad.
PLANTILLA_AGENTE = ChatPromptTemplate.from_messages([
    ("system", "Persona: Pedro, asistente de compras ficticias. "
     "Tarea: en compras, aclara solo producto y cantidad cuando falten; presupuesto y plazo son filtros opcionales. "
     "Las preguntas sobre políticas, entrega o envíos en varias cajas no requieren ID de pieza ni cantidad: "
     "llama consultar_politicas y responde con la fuente recuperada. "
     "Consulta herramientas y compara ofertas del dataset {dataset_id}. "
     "Contexto: los mensajes anteriores y recuerdos son históricos; la solicitud actual prevalece. "
     "Formato: JSON RespuestaCompra válido. No inventes datos ni fuentes. "
     "Plan visible: usa buscar_productos para resolver ID, consultar_catalogo para ofertas y "
     "comparar_ofertas para todos los importes. Una política sin fragmento implica sin_evidencia. "
     "Para políticas usa estado=politica solo con fragmento y fuente_id del índice; "
     "en mensaje resume la regla en una o dos frases usando solo lo que dice el fragmento, y en cada "
     "evidencia copia la frase del fragmento que la respalda; "
     "si el metadato origen es ficticio_demo, indica que la política es ficticia. "
     "Si el usuario declara una preferencia y pide recordarla, llama guardar_preferencia con su cita "
     "literal y usa estado=preferencia; no compares ofertas en ese turno. "
     "para CEP usa estado=cep con cidade, uf, modo_cep y evidencia ViaCEP. "
     "Si dos piezas coinciden, pide el ID. Ejemplos de acciones observables: "
     "{ejemplos} {formato}"),
    MessagesPlaceholder("chat_history", optional=True),
    ("human", "{input}"), MessagesPlaceholder("agent_scratchpad")
])
