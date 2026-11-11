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
    ("md", "## R03 · plantilla reutilizable con variables del dominio\nEjecución real local, sin modelo: se rellena la misma `ChatPromptTemplate` con tres solicitudes distintas y se muestran los mensajes resultantes. La plantilla vive en `pedro.chains.PROMPT` y la reutilizan la cadena LCEL y la cadena `@chain`. La ejecución con el modelo real está en `docs/trazas/fase1_chain_llm.json`."),
    ("code", """from pedro.chains import PROMPT
print('clase:', type(PROMPT).__name__, '| variables:', sorted(PROMPT.input_variables))
print('mensajes:', [type(m).__name__ for m in PROMPT.messages])
parcial = PROMPT.partial(formato='Devuelve JSON con intencion, solicitud y faltantes.')
print('tras partial -> variables libres:', sorted(parcial.input_variables))
for texto in ('Compara 2 unidades de PEC-01-0001 hasta R$ 5.000 en 7 días',
              'Necesito un termostato para nevera, sin prisa',
              '¿A qué ciudad corresponde el CEP 01001000?'):
    sistema, humano = parcial.format_messages(texto=texto)
    print(humano.type, '->', humano.content)
print(sistema.type, '->', sistema.content)
print('misma plantilla en LCEL:', lcel.first.messages == PROMPT.messages)"""),
    ("md", "## R04 · laboratorio de salidas rotas\nOcho salidas típicas de un modelo pasan por la cadena con reparación (`crear_lcel_robusta`). Cada defecto lo resuelve una capa distinta: el **parser** (tolera cercas y texto alrededor), la **reparación** (otra cadena corrige con la solicitud, la salida inválida y el error) o una **regla de dominio** (los faltantes los calcula el código). **Doble de prueba:** el generador emite la salida rota y el reparador devuelve siempre el JSON correcto; la reparación con el modelo real está en `docs/trazas/fase1_chain_llm.json`."),
    ("code", """from pedro.laboratorio import CORRECTA, SALIDAS_ROTAS, SOLICITUD, ensayar
reparador_doble = RunnableLambda(lambda prompt: json.dumps(CORRECTA))
print('solicitud:', SOLICITUD)
for caso in ensayar(reparador_doble):
    print(f"{caso['caso']:28} capa: {caso['capa_observada']:17} reparaciones: {caso['reparaciones']}"
          f" -> {caso['resultado']['solicitud']} faltan {caso['resultado']['faltantes']}")"""),
    ("md", "## R04 · un parser tolerante puede perder datos en silencio\nHallazgo del laboratorio. El parser de LangChain acepta JSON cortado. Con la cadena simple, una salida truncada se convierte en un objeto válido al que le falta el plazo, sin ningún error. La cadena robusta comprueba que el JSON esté entero y, si no, lo manda a reparar."),
    ("code", """truncada = SALIDAS_ROTAS['JSON truncado'][0]
print('salida del modelo:', truncada)
simple = crear_lcel(RunnableLambda(lambda _: truncada)).invoke({'texto': SOLICITUD})
print('cadena simple  -> plazo:', simple.solicitud.plazo_max_dias, '(se perdió sin error)')
from pedro.chains import crear_lcel_robusta
robusta = crear_lcel_robusta(RunnableLambda(lambda _: truncada), reparador_doble).invoke({'texto': SOLICITUD})
print('cadena robusta -> plazo:', robusta.solicitud.plazo_max_dias, '(detectado y reparado)')"""),
    ("md", "## R05 · invoke, batch y stream sobre una cadena @chain\n**Doble de prueba:** el modelo es un generador que entrega el JSON en trozos de 12 caracteres, para que `stream()` tenga algo que transmitir. Se ejecutan los tres métodos sobre la cadena imperativa. `stream()` solo transmite si todos los pasos lo permiten: con el parser Pydantic llega un único fragmento; con el parser de JSON parcial llega el objeto a medida que se forma. Las mediciones con el modelo real están en `docs/trazas/fase1_chain_llm.json`."),
    ("code", """from pedro.chains import crear_chain_robusta, crear_lcel_parcial
texto_json = json.dumps(CORRECTA)
def modelo_por_trozos(_):
    for i in range(0, len(texto_json), 12):
        yield texto_json[i:i + 12]
doble = RunnableLambda(modelo_por_trozos)
imperativa = crear_chain(doble)
entrada = {'texto': SOLICITUD}
print('invoke:', imperativa.invoke(entrada).solicitud.model_dump(exclude_none=True))
print('batch :', [r.intencion for r in imperativa.batch([entrada] * 3)])
print('stream con @chain y Pydantic:', len(list(imperativa.stream(entrada))), 'fragmento')
estados = list(crear_lcel_parcial(doble).stream(entrada))
print('stream con JSON parcial:', len(estados), 'estados')
for estado in estados[::3]:
    print('  ', estado)"""),
    ("md", "## R05 · la cadena con reparación, escrita con @chain\n`crear_chain_robusta` hace lo mismo que la versión declarativa de R04, pero el control de errores es un `try/except` a la vista. Se pasa el mismo laboratorio por las dos versiones."),
    ("code", """import inspect
print(inspect.getsource(crear_chain_robusta).split('    @chain\\n')[1].split('    return extraer_con_reparacion')[0])
print('imperativa = declarativa en los 8 casos:',
      ensayar(reparador_doble, crear_chain_robusta) == ensayar(reparador_doble))"""),
    ("md", "## R06 · la misma cadena en LCEL y en @chain: qué deja ver cada una\nSin modelo (dobles). Las dos versiones de la cadena con reparación dan el mismo resultado. Aquí se mide lo que cambia: los pasos que registra la traza, si el error queda anotado y si el grafo muestra la reparación."),
    ("code", """from pedro.laboratorio import comparar_estilos
medidas = comparar_estilos()
for estilo, dato in medidas.items():
    print(estilo)
    for clave, valor in dato.items():
        if clave != 'pasos_con_reparacion':
            print('  ', clave, '=', valor)
    print('   pasos:', ' > '.join(dato['pasos_con_reparacion']))
print(crear_lcel_robusta(RunnableLambda(lambda _: ''), reparador_doble).get_graph().draw_mermaid())"""),
    ("md", "Lectura: en LCEL la traza registra el fallo del parser, la reparación y la validación de dominio como pasos con nombre, y el grafo muestra el `WithFallbacks`. En `@chain` el resultado es idéntico, pero el `try/except` y la llamada a `_validar` son Python normal: la traza no los ve."),
    ("md", "## R01 · anatomía del agente\nLa anatomía se lee de los objetos reales del agente final (`pedro.anatomia`), no se escribe a mano. No se llama a ningún modelo: el executor se construye con un modelo de relleno que nunca se invoca."),
    ("code", """import json
from pedro.catalog import crear_escenario
from pedro.anatomia import describir_anatomia
escenario = crear_escenario(Path('storage/notebooks/catalogos'))
memoria = Path('storage/notebooks/r01.sqlite3')
anatomia = describir_anatomia(escenario, memoria)
for clave in ('motor_cognitivo', 'orquestador', 'system_message', 'memoria',
              'base_conocimiento', 'puerta_publicacion'):
    print(clave, json.dumps(anatomia[clave], ensure_ascii=False))
for h in anatomia['herramientas']:
    print('herramienta', h['nombre'], '|', h['papel'], '|', h['logica'], '|', h['argumentos'])"""),
    ("md", "## R01 · agente híbrido: capa reactiva y capa deliberativa\nTres turnos sobre el mismo flujo final. **Doble de prueba:** el modelo es un guion determinista (no es OpenAI) y ViaCEP está simulado. Lo real es el flujo: las reglas, el `AgentExecutor`, la herramienta ejecutada y la verificación antes de publicar. Los dos primeros turnos los resuelve una regla sin llamar al modelo; el tercero pasa por el modelo, que recibe las seis herramientas y solicita una."),
    ("code", """from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from pedro.agent import Traza, crear_flujo
from pedro.memory import nueva_sesion
sesion = nueva_sesion(memoria, 'alumna', escenario.dataset_id)
final = json.dumps({'estado': 'cep', 'dataset_id': escenario.dataset_id,
    'solicitud': {'cep': '01001000'}, 'cidade': 'Cidade Simulada', 'uf': 'SP',
    'modo_cep': 'simulado', 'evidencias': [{'tipo': 'viacep',
    'fuente_id': 'ViaCEP:01001000', 'texto': 'Cidade Simulada/SP'}]})
guion = [AIMessage(content='', tool_calls=[{'name': 'consultar_cep',
                                             'args': {'cep': '01001000'}, 'id': 'c1'}]),
         AIMessage(content=final)]
llamadas = []
def modelo_doble(prompt, **kwargs):
    llamadas.append(sorted(t['function']['name'] for t in kwargs.get('tools', [])))
    return guion[len(llamadas) - 1]
traza = Traza()
flujo = crear_flujo(escenario, memoria, llm=RunnableLambda(modelo_doble),
                    cep_simulado=True, traza=traza)
config = {'configurable': {'user_id': 'alumna', 'session_id': sesion}}
for pregunta in ('lista piezas', 'Compara PEC-01-0001',
                 '¿A qué ciudad corresponde el CEP 01001000?'):
    antes = (len(llamadas), len(traza.eventos))
    respuesta = flujo.invoke({'input': pregunta}, config=config).content
    usadas = [e['herramienta'] for e in traza.eventos[antes[1]:] if e['evento'] == 'tool_start']
    n = len(llamadas) - antes[0]
    print('turno:', pregunta)
    print('  capa:', 'deliberativa' if n else 'reactiva', '| llamadas al modelo:', n,
          '| herramientas ejecutadas:', usadas)
    print('  respuesta:', respuesta[:100].replace('\\n', ' '))
print('herramientas ofrecidas al modelo:', llamadas[0])
assert len(llamadas) == 2 and [e['herramienta'] for e in traza.eventos
                               if e['evento'] == 'tool_start'] == ['consultar_cep']"""),
    ("md", "Lectura: «lista piezas» y «Compara PEC-01-0001» se resuelven por regla (0 llamadas al modelo). La pregunta de CEP no tiene regla: el modelo elige `consultar_cep` entre seis herramientas y la respuesta solo se publica tras coincidir con la observación de la herramienta. Con un modelo real la elección la hace el LLM; esa ejecución remota corresponde a R26."),
    ("md", "## R02 · planificación: una solicitud compleja dividida en pasos\nEjecución real local, sin modelo. La solicitud se divide en cinco subtareas, cada una con una salida observable: extraer restricciones, consultar ofertas, comparar, verificar y publicar."),
    ("code", """from pedro.agent import renderizar
from pedro.business import comparar
from pedro.catalog import ofertas
from pedro.dialogue import interpretar_compra
from pedro.verification import respuesta_local, verificar
mensaje = 'Necesito 2 unidades de PEC-01-0001 hasta R$ 5.000 en 7 días'
estado, aclaracion = interpretar_compra(escenario, None, mensaje)
print('1 extraer  ', estado.solicitud.model_dump(exclude_none=True), '| falta:', aclaracion)
disponibles = ofertas(escenario, estado.solicitud.producto_id)
print('2 consultar', [o.id for o in disponibles])
alternativas = comparar(estado.solicitud, disponibles)
print('3 comparar ', [(a.oferta.proveedor_id, a.total_centavos, a.cumple, a.motivos)
                      for a in alternativas])
propuesta = respuesta_local(escenario, estado.solicitud)
print('4 verificar', 'errores:', verificar(propuesta, escenario))
print('5 publicar ', renderizar(propuesta).splitlines()[0])"""),
    ("md", "## R02 · memoria aumentada: qué va a corto y a largo plazo\nEjecución real local, sin modelo. Corto plazo: el borrador de compra y la ventana de 12 mensajes viven en la sesión. Largo plazo: la preferencia vive en el usuario y aparece en una sesión nueva; otro usuario no la ve. Los episodios vectoriales se demuestran en el notebook 03."),
    ("code", """from pedro.memory import Historial, guardar_preferencia, leer_borrador, preferencias
sesion_a = nueva_sesion(memoria, 'alumna', escenario.dataset_id)
local = crear_flujo(escenario, memoria)
def cfg(usuario, sesion):
    return {'configurable': {'user_id': usuario, 'session_id': sesion}}
for texto in ('Necesito 2 unidades de PEC-01-0001 en 7 días', 'ahora 3 unidades'):
    salida = local.invoke({'input': texto}, config=cfg('alumna', sesion_a)).content
    print(texto, '->', salida.splitlines()[0])
    print('  borrador (corto plazo):', {k: v for k, v in
          leer_borrador(memoria, 'alumna', sesion_a)['solicitud'].items() if v is not None})
for _ in range(7):
    local.invoke({'input': 'lista piezas'}, config=cfg('alumna', sesion_a))
historial = Historial(memoria, 'alumna', sesion_a)
print('mensajes guardados:', len(historial.todos()), '| ventana que ve el agente:', len(historial.messages))
guardar_preferencia(memoria, 'alumna', 'proveedor', 'nacional', explicita=True)
sesion_b = nueva_sesion(memoria, 'alumna', escenario.dataset_id)
print('sesión nueva -> borrador:', leer_borrador(memoria, 'alumna', sesion_b),
      '| preferencia (largo plazo):', preferencias(memoria, 'alumna'),
      '| otro usuario:', preferencias(memoria, 'otro'))"""),
    ("md", "Lectura: al cambiar la cantidad a 3 el plazo de 7 días se conserva en el borrador. El historial guarda 18 mensajes pero el agente solo ve 12. La sesión nueva empieza sin borrador y conserva la preferencia del usuario."),
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
    ("md", "## R09 · routing dinámico y composición\nLa primera celda de este notebook ejecuta `RouterCompras` (una `RouterChain` con reglas), `ejecutar_ruta` (cadena secuencial: decidir la ruta y ejecutar su cadena) y `composicion_paralela` (`RunnableParallel`). Aquí se añade el router decidido por un modelo (`LLMRouterChain`). **Doble de prueba:** `FakeListLLM` devuelve el destino ya escrito; la comparación con el modelo real está en `docs/trazas/r09_router_llm.json`."),
    ("code", """from langchain_core.language_models.fake import FakeListLLM
from pedro.legacy import DESTINOS, crear_router_llm
print('destinos:', DESTINOS)
for pregunta, destino in (('¿Cuánto cuesta el compresor PEC-01-0001?', 'comparacion'),
                          ('¿A qué ciudad corresponde el CEP 01001-000?', 'cep'),
                          ('Hola, buenos días', 'DEFAULT')):
    doble = FakeListLLM(responses=['```json\\n{"destination": "' + destino + '", "next_inputs": "x"}\\n```'])
    salida = ejecutar_ruta(crear_router_llm(doble), escenario, pregunta)
    print(pregunta, '->', salida['ruta'], '|', str(salida['resultado'])[:110])
    print('   el router por reglas habría elegido:', ejecutar_ruta(router, escenario, pregunta)['ruta'])"""),
    ("md", "## R08 · agente ReAct con initialize_agent, herramientas y memoria\n**Doble de prueba:** `FakeListLLM` devuelve un guion fijo de pensamientos y acciones; no decide nada. Lo real es el agente (`initialize_agent` con `ZERO_SHOT_REACT_DESCRIPTION`), las dos herramientas ejecutadas sobre el catálogo y `ConversationBufferMemory`. La misma conversación con el modelo real, donde el LLM sí elige, está en `docs/trazas/r08_react_llm.json`."),
    ("code", """from langchain_core.language_models.fake import FakeListLLM
from pedro.legacy import crear_react_textual
llm = FakeListLLM(responses=[
    'Thought: debo buscar la pieza\\nAction: buscar_pieza\\nAction Input: NEVE-COMP-0001',
    'Thought: ya la tengo\\nFinal Answer: el ID es PEC-01-0001',
    'Thought: el historial dice PEC-01-0001\\nAction: ofertas_de_pieza\\nAction Input: PEC-01-0001',
    'Thought: comparo los plazos\\nFinal Answer: CentroPeças entrega en 2 días'])
react, buffer = crear_react_textual(llm, escenario)
print('variables del prompt:', sorted(react.agent.llm_chain.prompt.input_variables))
for pregunta in ('Busca el compresor con SKU NEVE-COMP-0001 y dime su ID.',
                 '¿Cuál de sus proveedores entrega más rápido?'):
    salida = react.invoke({'input': pregunta})
    for accion, observacion in salida['intermediate_steps']:
        print('  acción:', accion.tool, '| entrada:', accion.tool_input, '| observación:', str(observacion)[:150])
    print('  respuesta:', salida['output'])
print('memoria de buffer:')
print(buffer.load_memory_variables({})['chat_history'])"""),
    ("md", "La llamada real a ViaCEP se registra por separado en docs/evidencias.md."),
    ("md", "## R12 · bitácora de un turno con error y recuperación\nLos cuatro componentes de confiabilidad en un solo turno del flujo final. **Doble de prueba:** el modelo es un guion; ViaCEP está simulado. La primera propuesta del guion es texto que no es JSON (error del parser); la segunda es válida. El callback `Traza` registra cada llamada a herramienta y cada verificación, y `RunnableWithMessageHistory` guarda en memoria solo la pregunta y la respuesta publicada."),
    ("code", """import json
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from pedro.agent import Traza, crear_flujo
from pedro.memory import Historial, nueva_sesion
memoria = Path('storage/notebooks/r12.sqlite3')
sesion = nueva_sesion(memoria, 'alumna', escenario.dataset_id)
llamar = AIMessage(content='', tool_calls=[{'name': 'consultar_cep', 'args': {'cep': '01001000'}, 'id': 'c1'}])
valida = json.dumps({'estado': 'cep', 'dataset_id': escenario.dataset_id, 'solicitud': {'cep': '01001000'}})
guion = iter([llamar, AIMessage(content='La ciudad es São Paulo, creo.'), llamar, AIMessage(content=valida)])
traza = Traza()
flujo = crear_flujo(escenario, memoria, llm=RunnableLambda(lambda prompt, **kw: next(guion)),
                    cep_simulado=True, traza=traza)
respuesta = flujo.invoke({'input': '¿A qué ciudad corresponde el CEP 01001000?'},
                         config={'configurable': {'user_id': 'alumna', 'session_id': sesion}})
for evento in traza.eventos:
    print({k: (str(v)[:70] if isinstance(v, str) else v) for k, v in evento.items()})
print('publicado:', respuesta.content)
print('memoria:', [(m.type, m.content[:60]) for m in Historial(memoria, 'alumna', sesion).todos()])"""),
    ("md", "Lectura: la bitácora muestra la herramienta llamada dos veces, el primer intento rechazado con `OutputParserException`, el segundo aceptado y el CEP rellenado desde la observación. La propuesta rechazada no llega a la memoria: solo se guardan la pregunta y la respuesta publicada."),
    ("md", "## R07 · qué aporta el orquestador: inventario de piezas de LangChain en Pedro\nSin modelo. El inventario se obtiene leyendo los imports del código (`pedro.anatomia.inventario_langchain`), no se escribe a mano. Sirve para argumentar la elección con hechos: cada fila es una pieza que el proyecto no tuvo que construir. La comparación con otros orquestadores está en `docs/respuestas_rubricas.md` §R07 y es conceptual: aquí solo se ejecutó LangChain."),
    ("code", """from pedro.anatomia import inventario_langchain
inventario = inventario_langchain()
for pieza, dato in inventario.items():
    print(f"{pieza:38} {', '.join(dato['nombres'])}")
    print(f"{'':38} usado en: {', '.join(dato['archivos'])}")
print('piezas:', len(inventario), '| nombres importados:', sum(len(d['nombres']) for d in inventario.values()))"""),
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
    ("md", "## R13 · mapa de memorias (CoALA)\nEjecución real local, sin modelo. Tras dos turnos de compra y una preferencia, `mapa_memorias` muestra qué hay en cada tipo de memoria. La conversación equivalente con el modelo real está en `docs/trazas/fase3_memoria_llm.json`."),
    ("code", """import json
from pedro.agent import crear_flujo
from pedro.catalog import crear_escenario
from pedro.memory import mapa_memorias
escenario = crear_escenario(Path('storage/notebooks/catalogos'))
ruta13 = Path('storage/notebooks/r13.sqlite3')
sesion13 = nueva_sesion(ruta13, 'alumna', escenario.dataset_id)
local = crear_flujo(escenario, ruta13)
for texto in ('Necesito 2 unidades de PEC-01-0001 con plazo 7 días', 'Ahora que sean 3 y mantén el plazo'):
    print(texto, '->', local.invoke({'input': texto}, config={'configurable': {
        'user_id': 'alumna', 'session_id': sesion13}}).content.splitlines()[0])
guardar_preferencia(ruta13, 'alumna', 'proveedor', 'nacionales', explicita=True)
guardar_episodio(ruta13, 'alumna', sesion13, 'pidió 3 unidades de PEC-01-0001 con plazo 7 días', emb)
for memoria_coala, contenido in mapa_memorias(ruta13, 'alumna', sesion13).items():
    print(memoria_coala, '->', json.dumps(contenido, ensure_ascii=False))"""),
    ("md", "## R16 · chatbot con ConversationBufferMemory\n**Doble de prueba:** `FakeListLLM` devuelve respuestas fijas. Lo real es `ConversationChain` con `ConversationBufferMemory`: se imprime el prompt del último turno para ver que lleva la conversación entera. La conversación con el modelo real está en `docs/trazas/fase3_memoria_llm.json`."),
    ("code", """from langchain_core.language_models.fake import FakeListLLM
from pedro.legacy import crear_chatbot_buffer
chatbot, buffer = crear_chatbot_buffer(FakeListLLM(responses=[
    'Hola Ana, ¿cuántas unidades necesitas?', 'Anotado: 2 unidades. ¿Presupuesto y plazo?',
    'Ana, pediste 2 termostatos, hasta R$ 900, en 5 días.']))
for texto in ('Hola, soy Ana. Necesito un termostato para mi nevera.', 'Que sean 2 unidades.',
              'Tengo hasta R$ 900 y lo necesito en 5 días. Resume mi solicitud.'):
    print('Usuario:', texto)
    print('Pedro  :', chatbot.invoke({'input': texto})['response'])
    print('   caracteres en memoria:', len(buffer.load_memory_variables({})['history']))
print('--- memoria de buffer ---')
print(buffer.load_memory_variables({})['history'])"""),
])

guardar("04_rag_text_to_query.ipynb", [
    ("md", "# Fase 4 · SQL y FAISS\nPlan Pydantic a SELECT parametrizado. T15 usa un corpus de políticas ficticias y FastEmbed local. T24 demuestra un fallo y una reformulación con el mismo índice y top-k, primero en memoria y al final sobre el índice guardado en disco (R22/R23)."),
    ("code", PRE),
    ("code", """from pedro.catalog import crear_escenario
from pedro.query import planear, ejecutar
escenario = crear_escenario(Path('storage/notebooks/catalogos'))
pregunta = 'ofertas PEC-01-0001'
plan = planear(pregunta)
print(plan.model_dump())
print(ejecutar(escenario, pregunta, plan))"""),
    ("md", "## T15 · embeddings, FAISS y filtros\nLas tres políticas son sintéticas y citan campos y ejemplos de la base generada con semilla 20261107. Cada sección produce varios fragmentos con ID y metadatos estables; el índice se construye en memoria y no se carga ningún pickle. Los ejemplos fechados no sustituyen los datos del escenario activo."),
    ("code", """from collections import Counter
from pedro.policy_demo import fragmentos_demo, crear_indice_demo, huella_corpus
from pedro.rag import consultar
fragmentos = fragmentos_demo()
indice_demo = crear_indice_demo()
print('corpus_sha256', huella_corpus())
print('fragmentos_por_tema', dict(Counter(d.metadata['tema'] for d in fragmentos)))
print('dimension', indice_demo.index.d, 'total', indice_demo.index.ntotal)
preguntas = [
    ('¿Qué fotografías se deben adjuntar para reportar una carcasa rota al abrir la caja?', 'devoluciones'),
    ('¿Cómo se comprueba la compatibilidad eléctrica antes de instalar una pieza?', 'garantia'),
    ('¿Qué ocurre si el seguimiento no cambia después del despacho?', 'entrega'),
    ('¿Cuántos meses de garantía ficticia tiene el compresor PEC-01-0001?', 'garantia'),
    ('¿Qué oferta de PEC-01-0001 está descatalogada y sin stock?', 'entrega'),
]
for texto, tema in preguntas:
    general = consultar(indice_demo, texto, k=1)[0]
    filtrado = consultar(indice_demo, texto, k=1, filtro={'tema': tema},
                        fetch_k=indice_demo.index.ntotal)[0]
    print('pregunta', texto)
    print('sin_filtro', general['fuente_id'], general['metadatos']['seccion'], round(general['score'], 3))
    print('con_filtro', filtrado['fuente_id'], filtrado['metadatos']['seccion'], round(filtrado['score'], 3))
    print('fragmento', filtrado['texto'][:180].replace('\\n', ' '))
print('filtro_sin_coincidencias', consultar(indice_demo, preguntas[0][0],
      filtro={'tema': 'inexistente'}, fetch_k=indice_demo.index.ntotal))"""),
    ("md", "## T24 · fallo observado y reformulación\nSobre el mismo índice sintético y con top-4, una pregunta coloquial sobre varias cajas no recupera la regla de entregas parciales. La respuesta existe en `entrega.md`, sección 5. Se reformula la intención sin incluir la respuesta. El filtro por tema es una segunda prueba, separada de la comparación antes/después. La distancia solo se interpreta como L2 porque el índice informa esa métrica. Esta evidencia local no sustituye el índice preexistente exigido por R22."),
    ("code", """from pedro.rag import diagnosticar_reescritura
original = '¿Se puede mandar en varias cajas?'
reescrita = '¿Cuándo admite la política de entrega un envío parcial de las piezas solicitadas?'
esperado = 'FIC-ENT-01-S05-C01'
informe = diagnosticar_reescritura(indice_demo, original, reescrita, esperado, k=4)
print('métrica', informe['metrica'], 'fragmentos', informe['total_fragmentos'],
      'top_k', informe['k'], 'fetch_k', informe['fetch_k'])
print('fuente_esperada', esperado, informe['evidencia_esperada']['metadatos'])
for etapa in ('antes', 'despues'):
    print(etapa, 'posición', informe['posicion_' + etapa])
    for fragmento in informe[etapa]:
        print(fragmento['posicion'], fragmento['fuente_id'],
              fragmento['metadatos']['fuente'], fragmento['metadatos']['seccion'],
              round(fragmento['score'], 3))
print('correccion_observada', informe['correccion_observada'])
con_filtro = consultar(indice_demo, original, k=4, filtro={'tema': 'entrega'},
                      fetch_k=indice_demo.index.ntotal)
print('filtro_entrega', [(x['fuente_id'], round(x['score'], 3)) for x in con_filtro])
assert informe['correccion_observada']
assert any(x['fuente_id'] == esperado for x in con_filtro)"""),
    ("md", "## R22 · índice FAISS existente: se carga, no se construye\nEl índice de `knowledge/politicas/` se creó una vez con `scripts/construir_indice_politicas.py` y está guardado con su manifiesto. Aquí solo se **carga** desde disco: primero se comprueban el manifiesto y las huellas, y sin confianza explícita el docstore no se abre. Después se repite T24 sobre el índice cargado. El corpus es ficticio y propio."),
    ("code", """from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from pedro.rag import cargar_indice, inspeccionar_indice
carpeta = Path('knowledge/politicas')
meta = inspeccionar_indice(carpeta)
print({k: meta[k] for k in ('origen', 'creado_utc', 'embedding_model', 'dimension', 'metrica')})
print('fragmentos en el manifiesto:', len(meta['documentos']), '| sha256:', meta['sha256'])
print('corpus sin cambios desde la indexación:', meta['corpus_sha256'] == huella_corpus())
embeddings = FastEmbedEmbeddings(model_name=meta['embedding_model'], doc_embed_type='passage')
try:
    cargar_indice(carpeta, embeddings, origen_confiable=False)
except PermissionError as error:
    print('sin confianza explícita ->', error)
existente, _ = cargar_indice(carpeta, embeddings, origen_confiable=True)
print('cargado de disco:', existente.index.ntotal, 'fragmentos')
informe = diagnosticar_reescritura(existente, original, reescrita, esperado, k=4)
for etapa in ('antes', 'despues'):
    print(etapa, 'posición', informe['posicion_' + etapa],
          [(f['fuente_id'], round(f['score'], 3)) for f in informe[etapa]])
assert informe['correccion_observada']"""),
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
