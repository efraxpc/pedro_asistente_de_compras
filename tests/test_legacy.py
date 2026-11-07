from langchain_core.language_models.fake import FakeListLLM

from compraslab.legacy import RouterCompras, crear_react_textual
from compraslab.chains import composicion_demo
from compraslab.prompts import FEW_SHOT


def test_routerchain_concreto():
    router = RouterCompras()
    assert router.route({"input": "¿Qué ofertas hay?"}).destination == "comparacion"
    assert router.route({"input": "¿Cuál es la política?"}).destination == "politicas"
    assert router.route({"input": "Necesito algo"}).destination == "aclaracion"


def test_react_clasico_con_buffer():
    llm = FakeListLLM(responses=["Final Answer: Necesito más datos."])
    agente, memoria = crear_react_textual(llm)
    assert agente.invoke({"input": "Quiero comprar"})["output"] == "Necesito más datos."
    assert "Quiero comprar" in memoria.load_memory_variables({})["chat_history"]


def test_few_shot_y_composicion():
    texto = FEW_SHOT.invoke({"input": "Quiero cables"}).to_string()
    assert "impresoras" in texto and "mouse inalámbrico" in texto
    assert composicion_demo().invoke({"producto": "cable"}).startswith("cable: faltan")
