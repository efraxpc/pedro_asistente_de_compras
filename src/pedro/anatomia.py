"""Anatomía observable del agente: se lee de los objetos reales, no se redacta a mano."""
import os
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from .agent import crear_agente
from .catalog import Escenario, listar
from .memory import MODELO_RECUERDOS, VENTANA_MENSAJES
from .nli import MODELO as MODELO_NLI, REVISION as REVISION_NLI
from .policy_demo import ORIGEN as ORIGEN_DEMO, fragmentos_demo

MODELO_LLM_POR_DEFECTO = "gpt-4.1-mini"
# Papel de cada herramienta en la anatomía y tipo de lógica que ejecuta.
PAPELES = {
    "buscar_productos": ("sensor", "determinista (SQL de lectura)"),
    "consultar_catalogo": ("sensor", "text-to-query"),
    "consultar_politicas": ("sensor", "semántica (FAISS)"),
    "consultar_cep": ("sensor", "API externa (ViaCEP)"),
    "comparar_ofertas": ("cálculo", "determinista (centavos enteros)"),
    "guardar_preferencia": ("escritura", "determinista (solo cita explícita)"),
}


def describir_anatomia(escenario: Escenario, memoria_db: Path, user_id: str = "anatomia") -> dict:
    """Devuelve los componentes del agente final tal como quedan construidos."""
    # El modelo de relleno nunca se invoca: solo permite construir el executor sin credenciales.
    executor = crear_agente(escenario, memoria_db, user_id, "", RunnableLambda(lambda x: x))
    pasos = getattr(executor.agent, "runnable").steps
    prompt = next(paso for paso in pasos if isinstance(paso, ChatPromptTemplate))
    sistema = prompt.messages[0].prompt.template
    return {
        "motor_cognitivo": {"clase": "ChatOpenAI",
                            "modelo": os.getenv("PEDRO_MODEL", MODELO_LLM_POR_DEFECTO),
                            "disponible": bool(os.getenv("OPENAI_API_KEY"))},
        "orquestador": {"agente": "create_openai_tools_agent", "ejecutor": type(executor).__name__,
                        "max_iteraciones": executor.max_iterations,
                        "historial": "RunnableWithMessageHistory"},
        "system_message": {
            "ptcf": {parte: f"{parte}:" in sistema
                     for parte in ("Persona", "Tarea", "Contexto", "Formato")},
            "variables": sorted(prompt.input_variables),
            "variables_fijadas": sorted(prompt.partial_variables),
            "mensajes": [type(m).__name__ for m in prompt.messages],
        },
        "herramientas": [{"nombre": h.name, "papel": PAPELES[h.name][0],
                          "logica": PAPELES[h.name][1], "descripcion": h.description,
                          "argumentos": sorted(h.args)} for h in executor.tools],
        "memoria": {"corto_plazo": f"ventana de {VENTANA_MENSAJES} mensajes + borrador por sesión",
                    "largo_plazo": "preferencias explícitas + episodios vectoriales por usuario",
                    "modelo_embeddings": MODELO_RECUERDOS},
        "base_conocimiento": {"dataset_id": escenario.dataset_id,
                              "piezas": listar(escenario)[0],
                              "fragmentos_politicas": len(fragmentos_demo()),
                              "origen_politicas": ORIGEN_DEMO},
        "puerta_publicacion": {"verificacion": "exacta (total, stock, presupuesto, plazo, IDs, fuentes)",
                               "nli": MODELO_NLI, "revision_nli": REVISION_NLI},
    }
