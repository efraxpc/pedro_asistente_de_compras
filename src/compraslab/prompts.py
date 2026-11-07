"""Instrucciones PTCF y ejemplos didácticos ajenos a evaluación."""
from langchain_core.prompts import FewShotPromptTemplate, PromptTemplate


EJEMPLOS = [
    {"pedido": "Necesito impresoras.",
     "conducta": "Pedir cantidad, presupuesto y plazo; no inventar valores."},
    {"pedido": "Ahora quiero cuatro unidades en vez de dos.",
     "conducta": "Actualizar cantidad explícita; conservar solo contexto pertinente y recalcular."},
    {"pedido": "Quiero un mouse inalámbrico.",
     "conducta": "Si hay varios modelos, mostrar candidatos y pedir el ID o modelo."},
    {"pedido": "¿La política permite pagar por adelantado?",
     "conducta": "Consultar políticas; si no hay documento pertinente, indicar falta de respaldo."},
]

EJEMPLO = PromptTemplate.from_template("Solicitud: {pedido}\nDecisión observable: {conducta}")
FEW_SHOT = FewShotPromptTemplate(examples=EJEMPLOS, example_prompt=EJEMPLO,
    prefix="Ejemplos de conducta; no son casos de evaluación ni respuestas finales:",
    suffix="Solicitud nueva: {input}\nDecisión observable:", input_variables=["input"])

PTCF = ("Persona: asistente de compras ficticias. "
        "Task: entender, aclarar, consultar, comparar y explicar. "
        "Context: catálogo activo, políticas y memoria pertinente. "
        "Format: respuesta comprensible y esquema validado.")

EJEMPLOS_TEXTO = "\n".join(f"Solicitud: {e['pedido']} Decisión: {e['conducta']}"
                             for e in EJEMPLOS)
