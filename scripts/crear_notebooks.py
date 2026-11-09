"""Genera los cinco notebooks ejecutables sin credenciales."""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
PRE = "from pathlib import Path\nimport os\nif Path.cwd().name == 'notebooks': os.chdir('..')"


def guardar(nombre, secciones):
    celdas = [nbf.v4.new_markdown_cell(texto) if tipo == "md"
              else nbf.v4.new_code_cell(texto) for tipo, texto in secciones]
    libro = nbf.v4.new_notebook(cells=celdas)
    libro.metadata.kernelspec = {"display_name": "Python 3", "language": "python", "name": "python3"}
    nbf.write(libro, ROOT / "notebooks" / nombre)


guardar("01_chain_mvp.ipynb", [
    ("md", "# Fase 1 · extracción\nModelo doble determinista. LCEL, @chain, invoke, batch y stream."),
    ("code", PRE),
    ("code", """from langchain_core.runnables import RunnableLambda
from pedro.chains import crear_lcel, crear_chain
import json
modelo = RunnableLambda(lambda prompt: json.dumps({'intencion':'comparar',
    'solicitud':{'producto_id':'PEC-01-0001','cantidad':2,'presupuesto_centavos':100000,
    'plazo_max_dias':7},'faltantes':[]}, ensure_ascii=False))
lcel, decorada = crear_lcel(modelo), crear_chain(modelo)
entrada = {'texto':'Compara dos unidades de PEC-01-0001 hasta R$ 1.000 en 7 días'}
print(lcel.invoke(entrada).model_dump_json())
print(decorada.invoke(entrada).model_dump_json())
print([x.model_dump() for x in lcel.batch([entrada, entrada])])
print(list(modelo.stream('etapa del modelo')))
print(lcel.get_graph().draw_mermaid())"""),
    ("md", "LCEL expone etapas declarativas. @chain envuelve la misma extracción. Los faltantes se recalculan tras el parser."),
])

guardar("02_react_herramientas.ipynb", [
    ("md", "# Fase 2 · herramientas\nReAct clásico queda aislado. AutoGen organiza conversaciones entre agentes; aquí el integrador usa un agente con herramientas verificables."),
    ("code", PRE),
    ("code", """from pedro.catalog import crear_escenario
from pedro.legacy import RouterCompras, ejecutar_ruta
from pedro.chains import composicion_paralela
from pedro.integrations import consultar_cep
escenario = crear_escenario(Path('storage/notebooks/catalogos'))
router = RouterCompras()
print(ejecutar_ruta(router, escenario, 'precio de PEC-01-0001'))
print(ejecutar_ruta(router, escenario, 'PEC-01-0001'))
print(composicion_paralela(escenario).invoke({'producto':'Compresor'}))
print(consultar_cep('01001000', simulado=True))"""),
    ("code", """from langchain_core.language_models.fake import FakeListLLM
from pedro.legacy import crear_react_textual
llm = FakeListLLM(responses=['Action: buscar_pieza\\nAction Input: PEC-01-0001',
                             'Final Answer: candidato localizado'])
react, buffer = crear_react_textual(llm, escenario)
print(react.invoke({'input':'Busca PEC-01-0001'})['output'])
print(buffer.load_memory_variables({})['chat_history'])"""),
    ("md", "La llamada real a ViaCEP se registra por separado en docs/evidencias.md."),
])

guardar("03_memoria_chatbot.ipynb", [
    ("md", "# Fase 3 · CoALA\nTrabajo: 12 mensajes; episodios: FastEmbed multilingüe; preferencias explícitas; procedimiento: verificación. Mem0 y Letta administran memoria con abstracciones propias; aquí SQLite conserva identidad y versión vectorial."),
    ("code", PRE),
    ("code", """from pedro.memory import (FastEmbedder, Historial, nueva_sesion, guardar_episodio,
                          actualizar_episodio, recuperar, guardar_preferencia, preferencias)
from langchain_core.messages import HumanMessage, AIMessage
ruta = Path('storage/notebooks/memoria.sqlite3')
sesion = nueva_sesion(ruta, 'alumna', 'demo')
historia = Historial(ruta, 'alumna', sesion)
historia.add_messages([HumanMessage(content='Quiero dos piezas'), AIMessage(content='¿Qué plazo?')])
historia.add_messages([HumanMessage(content='Siete días'), AIMessage(content='Entendido')])
guardar_preferencia(ruta, 'alumna', 'proveedor', 'nacional', explicita=True)
emb = FastEmbedder()
eid = guardar_episodio(ruta, 'alumna', sesion, 'prefiere proveedor nacional', emb)
print([m.content for m in historia.todos()], preferencias(ruta, 'alumna'))
print('antes', recuperar(ruta, 'alumna', 'proveedor nacional', emb))
actualizar_episodio(ruta, 'alumna', eid, 'corrigió: acepta proveedor internacional', emb)
print('después', recuperar(ruta, 'alumna', 'proveedor internacional', emb))"""),
    ("md", "Precio y stock guardados en episodios son históricos. La petición actual prevalece."),
])

guardar("04_rag_text_to_query.ipynb", [
    ("md", "# Fase 4 · SQL y FAISS\nPlan Pydantic a SELECT parametrizado. La prueba de fallo y reescritura exige el índice autorizado, mismo corpus y top-k."),
    ("code", PRE),
    ("code", """from pedro.catalog import crear_escenario
from pedro.query import planear, ejecutar
escenario = crear_escenario(Path('storage/notebooks/catalogos'))
pregunta = 'ofertas PEC-01-0001'
plan = planear(pregunta)
print(plan.model_dump())
print(ejecutar(escenario, pregunta, plan))"""),
    ("code", """from pedro.rag import inspeccionar_indice
carpeta = Path('knowledge/politicas')
if (carpeta / 'manifest.json').is_file():
    print(inspeccionar_indice(carpeta))
else:
    print('PENDIENTE: índice FAISS autorizado; sin prueba antes/después')"""),
])

guardar("05_integrador_evaluacion.ipynb", [
    ("md", "# Fase 5 · publicación verificada\nFormulario y agente usan el verificador. El chat usa el mismo flujo final. Agent y LangSmith remotos esperan credenciales."),
    ("code", PRE),
    ("code", """from pedro.catalog import crear_escenario
from pedro.contracts import Solicitud
from pedro.verification import respuesta_local, verificar
from pedro.agent import renderizar, crear_flujo
from pedro.memory import nueva_sesion, Historial
escenario = crear_escenario(Path('storage/notebooks/catalogos'))
solicitud = Solicitud(producto_id='PEC-01-0001', cantidad=2,
    presupuesto_centavos=1_000_000, plazo_max_dias=7)
respuesta = respuesta_local(escenario, solicitud)
print('errores', verificar(respuesta, escenario))
if not verificar(respuesta, escenario): print(renderizar(respuesta))
memoria = Path('storage/notebooks/final.sqlite3')
sesion = nueva_sesion(memoria, 'alumna', escenario.dataset_id)
flujo = crear_flujo(escenario, memoria)
print(flujo.invoke({'input':'lista piezas'}, config={'configurable':{
    'user_id':'alumna','session_id':sesion}}).content[:300])
print([m.type for m in Historial(memoria, 'alumna', sesion).todos()])"""),
    ("md", "La evaluación remota se ejecuta con evals/evaluar_flujo.py. No se reportan métricas sin esa corrida."),
])
print("Cinco notebooks creados")
