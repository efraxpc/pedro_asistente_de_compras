"""Planificador de turno: divide un mensaje con varias intenciones en peticiones independientes.

Cada petición se resuelve después con el flujo normal de una sola intención, de modo que cada
parte pasa por su propia verificación.
"""
import re
from typing import Literal

from pydantic import BaseModel, Field

# Señales baratas de cada intención. Sirven para decidir si vale la pena llamar al planificador.
SENALES = {
    "compra": r"\bPEC-[0-9]{2}-[0-9]{4}\b|\b(compara|comparar|cotiza|necesito|quiero|ofertas?|precio)\b",
    "politica": r"\b(pol[ií]ticas?|garant[ií]a|devoluci[oó]n|devolver|reembolso|compatibilidad|"
                r"instalar|instalaci[oó]n|varias\s+cajas|env[ií]o\s+parcial|entrega\s+parcial)\b",
    "cep": r"\bcep\b|\b\d{5}-?\d{3}\b",
    "preferencia": r"\b(prefiero|recu[eé]rda(?:lo|me)|recuerda\s+que|guarda\s+mi\s+preferencia)\b",
}
MAX_PETICIONES = 4


class Peticion(BaseModel):
    tipo: Literal["compra", "politica", "cep", "preferencia"]
    peticion: str = Field(min_length=3, description="Petición completa y autónoma, con sus datos")


class PlanTurno(BaseModel):
    """Plan observable de un turno: una petición por intención, en el orden del mensaje."""
    peticiones: list[Peticion] = Field(min_length=1, max_length=MAX_PETICIONES)


def intenciones_detectadas(texto: str) -> set[str]:
    return {nombre for nombre, patron in SENALES.items() if re.search(patron, texto, re.I)}


def _datos(texto: str) -> set[str]:
    """Identificadores y cifras de un texto, para comprobar que el plan no añade ninguno."""
    return set(re.findall(r"PEC-[0-9]{2}-[0-9]{4}|\d+(?:[.,]\d+)*", texto.upper()))


def validar_plan(plan: PlanTurno, original: str) -> list[Peticion]:
    """Acepta el plan solo si cada petición es coherente con el mensaje del usuario.

    Reglas: un tipo no se repite, cada petición muestra la señal de su tipo y no contiene
    ningún identificador ni cifra que el usuario no escribiera.
    """
    tipos = [p.tipo for p in plan.peticiones]
    if len(set(tipos)) != len(tipos):
        raise ValueError("el plan repite un tipo de petición")
    permitidos = _datos(original)
    for peticion in plan.peticiones:
        if not re.search(SENALES[peticion.tipo], peticion.peticion, re.I):
            raise ValueError(f"la petición de {peticion.tipo} no lo parece")
        if _datos(peticion.peticion) - permitidos:
            raise ValueError("el plan añade datos que el usuario no escribió")
    return plan.peticiones


def crear_planificador(modelo):
    """Cadena que propone un `PlanTurno`. No ejecuta nada."""
    from langchain_core.output_parsers import PydanticOutputParser

    from .prompts import PLANTILLA_PLAN

    parser = PydanticOutputParser(pydantic_object=PlanTurno)
    return PLANTILLA_PLAN.partial(formato=parser.get_format_instructions()) | modelo | parser


def planificar_turno(mensaje: str, modelo) -> list[Peticion] | None:
    """Devuelve las peticiones de un mensaje mixto, o None si debe tratarse como una sola.

    Solo se consulta al modelo cuando el mensaje muestra señales de dos o más intenciones; un
    plan inválido, ilegible o de una sola petición equivale a no planificar.
    """
    if modelo is None or len(intenciones_detectadas(mensaje)) < 2:
        return None
    try:
        peticiones = validar_plan(crear_planificador(modelo).invoke({"mensaje": mensaje}), mensaje)
    except Exception:
        return None
    return peticiones if len(peticiones) > 1 else None
