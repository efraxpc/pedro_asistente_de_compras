"""Gera os cinco notebooks. Todos rodam sem credenciais, com duplos de teste identificados.

O primeiro tem também uma célula que roda a mesma cadeia com o modelo real quando há um modelo
configurado no arquivo .env; sem ele, a célula avisa e não chama nada.
"""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
PRE = "from pathlib import Path\nimport os\nif Path.cwd().name == 'notebooks': os.chdir('..')"


def salvar(nome, secoes):
    celulas = [nbf.v4.new_markdown_cell(texto) if tipo == "md"
               else nbf.v4.new_code_cell(texto) for tipo, texto in secoes]
    caderno = nbf.v4.new_notebook(cells=celulas)
    caderno.metadata.kernelspec = {"display_name": "Python 3", "language": "python", "name": "python3"}
    nbf.write(caderno, ROOT / "notebooks" / nome)


salvar("01_chain_mvp.ipynb", [
    ("md", "# Fase 1 · extração\nLCEL, @chain, invoke, batch e stream. As células usam um **modelo duplo determinístico** e rodam sem credenciais. Uma célula, marcada como **execução real remota**, roda a mesma cadeia de ponta a ponta com o modelo real quando há chave no arquivo `.env`."),
    ("code", PRE),
    ("code", """from langchain_core.runnables import RunnableLambda
from pedro.chains import criar_lcel, criar_chain
import json
modelo = RunnableLambda(lambda prompt: json.dumps({'intencao':'comparar',
    'solicitacao':{'produto_id':'PEC-01-0001','quantidade':2,'orcamento_centavos':100000,
    'prazo_max_dias':7},'faltantes':[]}, ensure_ascii=False))
lcel, decorada = criar_lcel(modelo), criar_chain(modelo)
entrada = {'texto':'Compare duas unidades de PEC-01-0001 até R$ 1.000 em 7 dias'}
print(lcel.invoke(entrada).model_dump_json())
print(decorada.invoke(entrada).model_dump_json())
print([x.model_dump() for x in lcel.batch([entrada, entrada])])
print(list(modelo.stream('etapa do modelo')))
print(lcel.get_graph().draw_mermaid())"""),
    ("md", "LCEL expõe etapas declarativas. @chain envolve a mesma extração. Os faltantes são recalculados depois do parser."),
    ("md", "## A mesma cadeia de ponta a ponta com o modelo real\n**Execução real remota** (OpenAI), só se houver um modelo configurado no arquivo `.env` (`OPENAI_API_KEY`, ou `PEDRO_BASE_URL` para um servidor local). O prompt estruturado, o modelo e o output parser de JSON rodam juntos, sem duplo, nos dois estilos de composição e com `invoke`, `batch` e `stream`. As solicitações são sintéticas. Sem modelo configurado, a célula avisa e não chama nada; a execução real salva está em `docs/rastros/fase1_chain_llm.json`."),
    ("code", """from dotenv import load_dotenv
from pedro.chains import criar_lcel_parcial
from pedro.modelos import criar_llm, ha_modelo, nome_do_modelo
load_dotenv()
if ha_modelo():
    real = criar_llm(temperature=0)
    lcel_real, decorada_real = criar_lcel(real), criar_chain(real)
    pedidos = [{'texto': 'Compare 2 unidades de PEC-01-0001 até R$ 5.000 em 7 dias'},
               {'texto': 'Preciso de um termostato para geladeira, sem pressa'},
               {'texto': 'A que cidade corresponde o CEP 01001000?'}]
    print('modelo real:', nome_do_modelo())
    print('LCEL   invoke:', lcel_real.invoke(pedidos[0]).model_dump_json())
    print('@chain invoke:', decorada_real.invoke(pedidos[0]).model_dump_json())
    for pedido, saida in zip(pedidos, lcel_real.batch(pedidos)):
        print('batch :', pedido['texto'], '->', saida.intencao, '| faltam:', saida.faltantes)
    estados = list(criar_lcel_parcial(real).stream(pedidos[0]))
    print('stream:', len(estados), 'estados parciais; o último:', estados[-1])
else:
    print('Sem modelo configurado: esta célula não chama nada.')
    print('A execução real salva está em docs/rastros/fase1_chain_llm.json')"""),
    ("md", "## R03 · modelo de prompt reutilizável com variáveis do domínio\nExecução real local, sem modelo: o mesmo `ChatPromptTemplate` é preenchido com três solicitações diferentes e as mensagens resultantes são mostradas. O modelo de prompt fica em `pedro.chains.PROMPT` e é reutilizado pela cadeia LCEL e pela cadeia `@chain`. A execução com o modelo real está em `docs/rastros/fase1_chain_llm.json`."),
    ("code", """from pedro.chains import PROMPT
print('classe:', type(PROMPT).__name__, '| variáveis:', sorted(PROMPT.input_variables))
print('mensagens:', [type(m).__name__ for m in PROMPT.messages])
parcial = PROMPT.partial(formato='Devolva JSON com intencao, solicitacao e faltantes.')
print('depois do partial -> variáveis livres:', sorted(parcial.input_variables))
for texto in ('Compare 2 unidades de PEC-01-0001 até R$ 5.000 em 7 dias',
              'Preciso de um termostato para geladeira, sem pressa',
              'A qual cidade corresponde o CEP 01001000?'):
    sistema, humano = parcial.format_messages(texto=texto)
    print(humano.type, '->', humano.content)
print(sistema.type, '->', sistema.content)
print('mesmo modelo de prompt na LCEL:', lcel.first.messages == PROMPT.messages)"""),
    ("md", "## R04 · laboratório de saídas quebradas\nOito saídas típicas de um modelo passam pela cadeia com reparo (`criar_lcel_robusta`). Cada defeito é resolvido por uma camada diferente: o **parser** (tolera cercas e texto ao redor), o **reparo** (outra cadeia corrige com a solicitação, a saída inválida e o erro) ou uma **regra de domínio** (os faltantes são calculados pelo código). **Duplo de teste:** o gerador emite a saída quebrada e o reparador devolve sempre o JSON correto; o reparo com o modelo real está em `docs/rastros/fase1_chain_llm.json`."),
    ("code", """from pedro.laboratorio import CORRETA, SAIDAS_QUEBRADAS, SOLICITACAO, ensaiar
reparador_duplo = RunnableLambda(lambda prompt: json.dumps(CORRETA))
print('solicitação:', SOLICITACAO)
for caso in ensaiar(reparador_duplo):
    print(f"{caso['caso']:28} camada: {caso['camada_observada']:17} reparos: {caso['reparos']}"
          f" -> {caso['resultado']['solicitacao']} faltam {caso['resultado']['faltantes']}")"""),
    ("md", "## R04 · um parser tolerante pode perder dados em silêncio\nAchado do laboratório. O parser do LangChain aceita JSON cortado. Com a cadeia simples, uma saída truncada vira um objeto válido ao qual falta o prazo, sem nenhum erro. A cadeia robusta confere que o JSON esteja inteiro e, se não estiver, manda reparar."),
    ("code", """truncada = SAIDAS_QUEBRADAS['JSON truncado'][0]
print('saída do modelo:', truncada)
simples = criar_lcel(RunnableLambda(lambda _: truncada)).invoke({'texto': SOLICITACAO})
print('cadeia simples  -> prazo:', simples.solicitacao.prazo_max_dias, '(perdeu-se sem erro)')
from pedro.chains import criar_lcel_robusta
robusta = criar_lcel_robusta(RunnableLambda(lambda _: truncada), reparador_duplo).invoke({'texto': SOLICITACAO})
print('cadeia robusta -> prazo:', robusta.solicitacao.prazo_max_dias, '(detectado e reparado)')"""),
    ("md", "## R05 · invoke, batch e stream sobre uma cadeia @chain\n**Duplo de teste:** o modelo é um gerador que entrega o JSON em pedaços de 12 caracteres, para que `stream()` tenha algo a transmitir. Os três métodos são executados sobre a cadeia imperativa. `stream()` só transmite se todos os passos permitirem: com o parser Pydantic chega um único fragmento; com o parser de JSON parcial o objeto chega à medida que se forma. As medições com o modelo real estão em `docs/rastros/fase1_chain_llm.json`."),
    ("code", """from pedro.chains import criar_chain_robusta, criar_lcel_parcial
texto_json = json.dumps(CORRETA)
def modelo_em_pedacos(_):
    for i in range(0, len(texto_json), 12):
        yield texto_json[i:i + 12]
duplo = RunnableLambda(modelo_em_pedacos)
imperativa = criar_chain(duplo)
entrada = {'texto': SOLICITACAO}
print('invoke:', imperativa.invoke(entrada).solicitacao.model_dump(exclude_none=True))
print('batch :', [r.intencao for r in imperativa.batch([entrada] * 3)])
print('stream com @chain e Pydantic:', len(list(imperativa.stream(entrada))), 'fragmento')
estados = list(criar_lcel_parcial(duplo).stream(entrada))
print('stream com JSON parcial:', len(estados), 'estados')
for estado in estados[::3]:
    print('  ', estado)"""),
    ("md", "## R05 · a cadeia com reparo, escrita com @chain\n`criar_chain_robusta` faz o mesmo que a versão declarativa de R04, mas o controle de erros é um `try/except` à vista. O mesmo laboratório passa pelas duas versões."),
    ("code", """import inspect
print(inspect.getsource(criar_chain_robusta).split('    @chain\\n')[1].split('    return extrair_com_reparo')[0])
print('imperativa = declarativa nos 8 casos:',
      ensaiar(reparador_duplo, criar_chain_robusta) == ensaiar(reparador_duplo))"""),
    ("md", "## R06 · a mesma cadeia em LCEL e em @chain: o que cada uma deixa ver\nSem modelo (duplos). As duas versões da cadeia com reparo dão o mesmo resultado. Aqui se mede o que muda: os passos que o rastro registra, se o erro fica anotado e se o grafo mostra o reparo."),
    ("code", """from pedro.laboratorio import comparar_estilos
medidas = comparar_estilos()
for estilo, dado in medidas.items():
    print(estilo)
    for chave, valor in dado.items():
        if chave != 'passos_com_reparo':
            print('  ', chave, '=', valor)
    print('   passos:', ' > '.join(dado['passos_com_reparo']))
print(criar_lcel_robusta(RunnableLambda(lambda _: ''), reparador_duplo).get_graph().draw_mermaid())"""),
    ("md", "Leitura: na LCEL o rastro registra a falha do parser, o reparo e a validação de domínio como passos com nome, e o grafo mostra o `WithFallbacks`. Em `@chain` o resultado é idêntico, mas o `try/except` e a chamada a `_validar` são Python normal: o rastro não os vê."),
    ("md", "## R01 · anatomia do agente\nA anatomia é lida dos objetos reais do agente final (`pedro.anatomia`), não é escrita à mão. Nenhum modelo é chamado: o executor é construído com um modelo de preenchimento que nunca é invocado."),
    ("code", """import json
from pedro.catalog import criar_cenario
from pedro.anatomia import descrever_anatomia
cenario = criar_cenario(Path('storage/notebooks/catalogos'))
memoria = Path('storage/notebooks/r01.sqlite3')
anatomia = descrever_anatomia(cenario, memoria)
for chave in ('motor_cognitivo', 'orquestrador', 'system_message', 'memoria',
              'base_conhecimento', 'porta_publicacao'):
    print(chave, json.dumps(anatomia[chave], ensure_ascii=False))
for f in anatomia['ferramentas']:
    print('ferramenta', f['nome'], '|', f['papel'], '|', f['logica'], '|', f['argumentos'])"""),
    ("md", "## R01 · agente híbrido: camada reativa e camada deliberativa\nTrês turnos sobre o mesmo fluxo final. **Duplo de teste:** o modelo é um roteiro determinístico (não é OpenAI) e o ViaCEP está simulado. O real é o fluxo: as regras, o `AgentExecutor`, a ferramenta executada e a verificação antes de publicar. Os dois primeiros turnos são resolvidos por uma regra sem passar pelo agente; no segundo, o intérprete de turno lê a mensagem e a regra pergunta a quantidade. O terceiro passa pelo agente, que recebe as seis ferramentas e solicita uma."),
    ("code", """from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from pedro.agent import Rastro, criar_fluxo
from pedro.memory import nova_sessao
sessao = nova_sessao(memoria, 'aluna', cenario.dataset_id)
final = json.dumps({'estado': 'cep', 'dataset_id': cenario.dataset_id,
    'solicitacao': {'cep': '01001000'}, 'cidade': 'Cidade Simulada', 'uf': 'SP',
    'modo_cep': 'simulado', 'evidencias': [{'tipo': 'viacep',
    'fonte_id': 'ViaCEP:01001000', 'texto': 'Cidade Simulada/SP'}]})
roteiro = [AIMessage(content='', tool_calls=[{'name': 'consultar_cep',
                                               'args': {'cep': '01001000'}, 'id': 'c1'}]),
           AIMessage(content=final)]
chamadas, leituras = [], []
def modelo_duplo(prompt, **kwargs):
    if 'tools' not in kwargs:  # quem chama é o intérprete de turno, não o agente
        leituras.append(1)
        return json.dumps({'e_compra': 'CEP' not in prompt.to_messages()[-1].content})
    chamadas.append(sorted(t['function']['name'] for t in kwargs['tools']))
    return roteiro[len(chamadas) - 1]
rastro = Rastro()
fluxo = criar_fluxo(cenario, memoria, llm=RunnableLambda(modelo_duplo),
                    cep_simulado=True, rastro=rastro)
config = {'configurable': {'user_id': 'aluna', 'session_id': sessao}}
for pergunta in ('lista peças', 'Compare PEC-01-0001',
                 'A qual cidade corresponde o CEP 01001000?'):
    antes = (len(chamadas), len(rastro.eventos), len(leituras))
    resposta = fluxo.invoke({'input': pergunta}, config=config).content
    usadas = [e['ferramenta'] for e in rastro.eventos[antes[1]:] if e['evento'] == 'tool_start']
    n = len(chamadas) - antes[0]
    print('turno:', pergunta)
    print('  camada:', 'deliberativa' if n else 'reativa', '| chamadas ao agente:', n,
          '| leituras do intérprete:', len(leituras) - antes[2], '| ferramentas executadas:', usadas)
    print('  resposta:', resposta[:100].replace('\\n', ' '))
print('ferramentas oferecidas ao modelo:', chamadas[0])
assert len(chamadas) == 2 and [e['ferramenta'] for e in rastro.eventos
                               if e['evento'] == 'tool_start'] == ['consultar_cep']"""),
    ("md", "Leitura: «lista peças» e «Compare PEC-01-0001» são resolvidas por regra (0 chamadas ao agente); na segunda o intérprete confirma que é uma compra. A pergunta de CEP não tem regra: o modelo escolhe `consultar_cep` entre seis ferramentas e a resposta só é publicada depois de coincidir com a observação da ferramenta. Com um modelo real a escolha é feita pelo LLM; essa execução remota corresponde a R26."),
    ("md", "## R02 · planejamento: uma solicitação complexa dividida em passos\nExecução real local, sem modelo. A solicitação é dividida em cinco subtarefas, cada uma com uma saída observável: extrair restrições, consultar ofertas, comparar, verificar e publicar."),
    ("code", """from pedro.agent import renderizar
from pedro.business import comparar
from pedro.catalog import ofertas
from pedro.dialogue import interpretar_compra
from pedro.verification import resposta_local, verificar
mensagem = 'Preciso de 5 unidades de PEC-01-0001 até R$ 10.000 em 7 dias'
estado, esclarecimento = interpretar_compra(cenario, None, mensagem)
print('1 extrair  ', estado.solicitacao.model_dump(exclude_none=True), '| falta:', esclarecimento)
disponiveis = ofertas(cenario, estado.solicitacao.produto_id)
print('2 consultar', [o.id for o in disponiveis])
alternativas = comparar(estado.solicitacao, disponiveis)
print('3 comparar ', [(a.oferta.fornecedor_id, a.total_centavos, a.atende, a.motivos)
                      for a in alternativas])
proposta = resposta_local(cenario, estado.solicitacao)
print('4 verificar', 'erros:', verificar(proposta, cenario))
print('5 publicar ', renderizar(proposta).splitlines()[0])"""),
    ("md", "## R02 · memória aumentada: o que vai para o curto e para o longo prazo\nExecução real local, sem modelo. Curto prazo: o rascunho de compra e a janela de 12 mensagens vivem na sessão. Longo prazo: a preferência vive no usuário e aparece em uma sessão nova; outro usuário não a vê. Os episódios vetoriais são demonstrados no notebook 03."),
    ("code", """from pedro.memory import Historico, salvar_preferencia, ler_rascunho, preferencias
sessao_a = nova_sessao(memoria, 'aluna', cenario.dataset_id)
local = criar_fluxo(cenario, memoria)
def cfg(usuario, sessao):
    return {'configurable': {'user_id': usuario, 'session_id': sessao}}
for texto in ('Preciso de 5 unidades de PEC-01-0001 em 7 dias', 'agora 6 unidades'):
    saida = local.invoke({'input': texto}, config=cfg('aluna', sessao_a)).content
    print(texto, '->', saida.splitlines()[0])
    print('  rascunho (curto prazo):', {k: v for k, v in
          ler_rascunho(memoria, 'aluna', sessao_a)['solicitacao'].items() if v is not None})
for _ in range(7):
    local.invoke({'input': 'lista peças'}, config=cfg('aluna', sessao_a))
historico = Historico(memoria, 'aluna', sessao_a)
print('mensagens salvas:', len(historico.todos()), '| janela que o agente vê:', len(historico.messages))
salvar_preferencia(memoria, 'aluna', 'fornecedor', 'nacional', explicita=True)
sessao_b = nova_sessao(memoria, 'aluna', cenario.dataset_id)
print('sessão nova -> rascunho:', ler_rascunho(memoria, 'aluna', sessao_b),
      '| preferência (longo prazo):', preferencias(memoria, 'aluna'),
      '| outro usuário:', preferencias(memoria, 'outro'))"""),
    ("md", "Leitura: ao mudar a quantidade para 6, o prazo de 7 dias é conservado no rascunho. O histórico guarda 18 mensagens, mas o agente só vê 12. A sessão nova começa sem rascunho e conserva a preferência do usuário."),
])

salvar("02_react_ferramentas.ipynb", [
    ("md", "# Fase 2 · ferramentas\nO ReAct clássico fica isolado. O AutoGen organiza conversas entre agentes; aqui o integrador usa um agente com ferramentas verificáveis."),
    ("code", PRE),
    ("code", """from pedro.catalog import criar_cenario
from pedro.legacy import RouterCompras, executar_rota
from pedro.chains import composicao_paralela
from pedro.integrations import consultar_cep
cenario = criar_cenario(Path('storage/notebooks/catalogos'))
router = RouterCompras()
print(executar_rota(router, cenario, 'preço de PEC-01-0001'))
print(executar_rota(router, cenario, 'PEC-01-0001'))
print(composicao_paralela(cenario).invoke({'produto':'Compressor'}))
print(consultar_cep('01001000', simulado=True))"""),
    ("md", "## R09 · roteamento dinâmico e composição\nA primeira célula deste notebook executa `RouterCompras` (uma `RouterChain` com regras), `executar_rota` (cadeia sequencial: decidir a rota e executar a cadeia dela) e `composicao_paralela` (`RunnableParallel`). Aqui se acrescenta o router decidido por um modelo (`LLMRouterChain`). **Duplo de teste:** `FakeListLLM` devolve o destino já escrito; a comparação com o modelo real está em `docs/rastros/r09_router_llm.json`."),
    ("code", """from langchain_core.language_models.fake import FakeListLLM
from pedro.legacy import DESTINOS, criar_router_llm
print('destinos:', DESTINOS)
for pergunta, destino in (('Quanto custa o compressor PEC-01-0001?', 'comparacao'),
                          ('A qual cidade corresponde o CEP 01001-000?', 'cep'),
                          ('Olá, bom dia', 'DEFAULT')):
    duplo = FakeListLLM(responses=['```json\\n{"destination": "' + destino + '", "next_inputs": "x"}\\n```'])
    saida = executar_rota(criar_router_llm(duplo), cenario, pergunta)
    print(pergunta, '->', saida['rota'], '|', str(saida['resultado'])[:110])
    print('   o router por regras teria escolhido:', executar_rota(router, cenario, pergunta)['rota'])"""),
    ("md", "## R08 · agente ReAct com initialize_agent, ferramentas e memória\n**Duplo de teste:** `FakeListLLM` devolve um roteiro fixo de pensamentos e ações; não decide nada. O real é o agente (`initialize_agent` com `ZERO_SHOT_REACT_DESCRIPTION`), as duas ferramentas executadas sobre o catálogo e `ConversationBufferMemory`. A mesma conversa com o modelo real, em que o LLM de fato escolhe, está em `docs/rastros/r08_react_llm.json`."),
    ("code", """from langchain_core.language_models.fake import FakeListLLM
from pedro.legacy import criar_react_textual
llm = FakeListLLM(responses=[
    'Thought: devo buscar a peça\\nAction: buscar_peca\\nAction Input: GELA-COMP-0001',
    'Thought: já a tenho\\nFinal Answer: o ID é PEC-01-0001',
    'Thought: o histórico diz PEC-01-0001\\nAction: ofertas_da_peca\\nAction Input: PEC-01-0001',
    'Thought: comparo os prazos\\nFinal Answer: CentroPeças entrega em 2 dias'])
react, buffer = criar_react_textual(llm, cenario)
print('variáveis do prompt:', sorted(react.agent.llm_chain.prompt.input_variables))
for pergunta in ('Busque o compressor com SKU GELA-COMP-0001 e me diga o ID dele.',
                 'Qual dos fornecedores dele entrega mais rápido?'):
    saida = react.invoke({'input': pergunta})
    for acao, observacao in saida['intermediate_steps']:
        print('  ação:', acao.tool, '| entrada:', acao.tool_input, '| observação:', str(observacao)[:150])
    print('  resposta:', saida['output'])
print('memória de buffer:')
print(buffer.load_memory_variables({})['chat_history'])"""),
    ("md", "A chamada real ao ViaCEP é registrada separadamente em docs/evidencias.md."),
    ("md", "## R12 · registro de um turno com erro e recuperação\nOs quatro componentes de confiabilidade em um único turno do fluxo final. **Duplo de teste:** o modelo é um roteiro; o ViaCEP está simulado. A primeira proposta do roteiro é texto que não é JSON (erro do parser); a segunda é válida. O callback `Rastro` registra cada chamada de ferramenta e cada verificação, e `RunnableWithMessageHistory` salva na memória só a pergunta e a resposta publicada."),
    ("code", """import json
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from pedro.agent import Rastro, criar_fluxo
from pedro.memory import Historico, nova_sessao
memoria = Path('storage/notebooks/r12.sqlite3')
sessao = nova_sessao(memoria, 'aluna', cenario.dataset_id)
chamar = AIMessage(content='', tool_calls=[{'name': 'consultar_cep', 'args': {'cep': '01001000'}, 'id': 'c1'}])
valida = json.dumps({'estado': 'cep', 'dataset_id': cenario.dataset_id, 'solicitacao': {'cep': '01001000'}})
roteiro = iter([chamar, AIMessage(content='A cidade é São Paulo, acho.'), chamar, AIMessage(content=valida)])
rastro = Rastro()
fluxo = criar_fluxo(cenario, memoria, llm=RunnableLambda(lambda prompt, **kw: next(roteiro)),
                    cep_simulado=True, rastro=rastro)
resposta = fluxo.invoke({'input': 'A qual cidade corresponde o CEP 01001000?'},
                        config={'configurable': {'user_id': 'aluna', 'session_id': sessao}})
for evento in rastro.eventos:
    print({k: (str(v)[:70] if isinstance(v, str) else v) for k, v in evento.items()})
print('publicado:', resposta.content)
print('memória:', [(m.type, m.content[:60]) for m in Historico(memoria, 'aluna', sessao).todos()])"""),
    ("md", "Leitura: o registro mostra a ferramenta chamada duas vezes, a primeira tentativa rejeitada com `OutputParserException`, a segunda aceita e o CEP preenchido a partir da observação. A proposta rejeitada não chega à memória: só são salvas a pergunta e a resposta publicada."),
    ("md", "## R07 · o que o orquestrador traz: inventário de peças do LangChain no Pedro\nSem modelo. O inventário é obtido lendo os imports do código (`pedro.anatomia.inventario_langchain`), não é escrito à mão. Serve para argumentar a escolha com fatos: cada linha é uma peça que o projeto não precisou construir. A comparação com outros orquestradores está em `docs/respostas_rubricas.md` §R07 e é conceitual: aqui só o LangChain foi executado."),
    ("code", """from pedro.anatomia import inventario_langchain
inventario = inventario_langchain()
for peca, dado in inventario.items():
    print(f"{peca:38} {', '.join(dado['nomes'])}")
    print(f"{'':38} usado em: {', '.join(dado['arquivos'])}")
print('peças:', len(inventario), '| nomes importados:', sum(len(d['nomes']) for d in inventario.values()))"""),
])

salvar("03_memoria_chatbot.ipynb", [
    ("md", "# Fase 3 · CoALA\nTrabalho: 12 mensagens; episódios: FastEmbed multilíngue; preferências explícitas; procedimento: verificação. Mem0 e Letta administram memória com abstrações próprias; aqui o SQLite conserva identidade e versão vetorial."),
    ("code", PRE),
    ("code", """from pedro.memory import (FastEmbedder, Historico, nova_sessao, salvar_episodio,
                          atualizar_episodio, recuperar, salvar_preferencia, preferencias)
from langchain_core.messages import HumanMessage, AIMessage
caminho = Path('storage/notebooks/memoria.sqlite3')
sessao = nova_sessao(caminho, 'aluna', 'demo')
historico = Historico(caminho, 'aluna', sessao)
historico.add_messages([HumanMessage(content='Quero duas peças'), AIMessage(content='Qual prazo?')])
historico.add_messages([HumanMessage(content='Sete dias'), AIMessage(content='Entendido')])
salvar_preferencia(caminho, 'aluna', 'fornecedor', 'nacional', explicita=True)
emb = FastEmbedder()
eid = salvar_episodio(caminho, 'aluna', sessao, 'prefere fornecedor nacional', emb)
print([m.content for m in historico.todos()], preferencias(caminho, 'aluna'))
print('antes', recuperar(caminho, 'aluna', 'fornecedor nacional', emb))
atualizar_episodio(caminho, 'aluna', eid, 'corrigiu: aceita fornecedor internacional', emb)
print('depois', recuperar(caminho, 'aluna', 'fornecedor internacional', emb))"""),
    ("md", "Preço e estoque guardados em episódios são históricos. O pedido atual prevalece."),
    ("md", "## R13 · mapa de memórias (CoALA)\nExecução real local, sem modelo. Depois de dois turnos de compra e uma preferência, `mapa_memorias` mostra o que há em cada tipo de memória. A conversa equivalente com o modelo real está em `docs/rastros/fase3_memoria_llm.json`."),
    ("code", """import json
from pedro.agent import criar_fluxo
from pedro.catalog import criar_cenario
from pedro.memory import mapa_memorias
cenario = criar_cenario(Path('storage/notebooks/catalogos'))
caminho13 = Path('storage/notebooks/r13.sqlite3')
sessao13 = nova_sessao(caminho13, 'aluna', cenario.dataset_id)
local = criar_fluxo(cenario, caminho13)
for texto in ('Preciso de 5 unidades de PEC-01-0001 com prazo 7 dias', 'Agora que sejam 6 e mantenha o prazo'):
    print(texto, '->', local.invoke({'input': texto}, config={'configurable': {
        'user_id': 'aluna', 'session_id': sessao13}}).content.splitlines()[0])
salvar_preferencia(caminho13, 'aluna', 'fornecedor', 'nacionais', explicita=True)
salvar_episodio(caminho13, 'aluna', sessao13, 'pediu 6 unidades de PEC-01-0001 com prazo 7 dias', emb)
for memoria_coala, conteudo in mapa_memorias(caminho13, 'aluna', sessao13).items():
    print(memoria_coala, '->', json.dumps(conteudo, ensure_ascii=False))"""),
    ("md", "## R16 · chatbot com ConversationBufferMemory\n**Duplo de teste:** `FakeListLLM` devolve respostas fixas. O real é `ConversationChain` com `ConversationBufferMemory`: o prompt do último turno é impresso para ver que ele leva a conversa inteira. A conversa com o modelo real está em `docs/rastros/fase3_memoria_llm.json`."),
    ("code", """from langchain_core.language_models.fake import FakeListLLM
from pedro.legacy import criar_chatbot_buffer
chatbot, buffer = criar_chatbot_buffer(FakeListLLM(responses=[
    'Olá, Ana, de quantas unidades você precisa?', 'Anotado: 2 unidades. Orçamento e prazo?',
    'Ana, você pediu 2 termostatos, até R$ 900, em 5 dias.']))
for texto in ('Olá, sou a Ana. Preciso de um termostato para a minha geladeira.', 'Que sejam 2 unidades.',
              'Tenho até R$ 900 e preciso dele em 5 dias. Resuma a minha solicitação.'):
    print('Usuário:', texto)
    print('Pedro  :', chatbot.invoke({'input': texto})['response'])
    print('   caracteres na memória:', len(buffer.load_memory_variables({})['history']))
print('--- memória de buffer ---')
print(buffer.load_memory_variables({})['history'])"""),
])

salvar("04_rag_text_to_query.ipynb", [
    ("md", "# Fase 4 · SQL e FAISS\nPlano Pydantic para SELECT parametrizado. T15 usa um corpus de políticas fictícias e FastEmbed local. T24 demonstra uma falha e uma reformulação com o mesmo índice e top-k, primeiro em memória e ao final sobre o índice salvo em disco (R22/R23)."),
    ("code", PRE),
    ("code", """from pedro.catalog import criar_cenario
from pedro.query import planejar, executar
cenario = criar_cenario(Path('storage/notebooks/catalogos'))
pergunta = 'ofertas PEC-01-0001'
plano = planejar(pergunta)
print(plano.model_dump())
print(executar(cenario, pergunta, plano))"""),
    ("md", "## R21 · text-to-SQL: o modelo escreve a consulta e o motor decide\nA célula anterior mostra a versão conservadora (um plano com dois modelos fixos de SQL), que é a que a ferramenta do agente usa. Aqui está a versão com modelo: gera um `SELECT`, a forma dele é validada, e o **autorizador do SQLite** só deixa ler as tabelas e colunas permitidas. **Duplo de teste:** o gerador devolve consultas escritas à mão, a primeira com um erro de propósito, para ver a correção. A execução com o modelo real está em `docs/rastros/fase4_sql_llm.json`."),
    ("code", """import json
from langchain_core.runnables import RunnableLambda
from pedro.query import ConsultaRejeitada, consultar_sql, criar_gerador_sql, descrever_esquema, responder_sql
print(descrever_esquema())
roteiro = iter(['SELECT * FROM suppliers WHERE domestic = 1',
                'SELECT id, name FROM suppliers WHERE domestic = 1 ORDER BY id LIMIT 3'])
gerador = criar_gerador_sql(RunnableLambda(lambda p: json.dumps({'sql': next(roteiro), 'explicacao': 'fornecedores nacionais'})))
resultado = responder_sql(cenario, 'Quais fornecedores nacionais existem?', gerador)
for tentativa in resultado['tentativas']:
    print('SQL :', tentativa['sql'])
    print('erro:', tentativa['erro'])
print('estado:', resultado['estado'], '| linhas:', resultado['linhas'])
for sql in ('DROP TABLE offers', 'SELECT 1; DELETE FROM offers', 'SELECT name FROM sqlite_master',
            'SELECT id, website FROM suppliers', 'SELECT count(*) FROM parts a, parts b, parts c'):
    try:
        consultar_sql(cenario, sql)
        print('EXECUTADA:', sql)
    except ConsultaRejeitada as erro:
        print('rejeitada:', sql, '->', erro)"""),
    ("md", "## T15 · embeddings, FAISS e filtros\nAs três políticas são sintéticas e citam campos e exemplos da base gerada com a semente 20261107. Cada seção produz vários fragmentos com ID e metadados estáveis; o índice é construído em memória e nenhum pickle é carregado. Os exemplos datados não substituem os dados do cenário ativo."),
    ("code", """from collections import Counter
from pedro.policy_demo import fragmentos_demo, criar_indice_demo, impressao_corpus
from pedro.rag import consultar
fragmentos = fragmentos_demo()
indice_demo = criar_indice_demo()
print('corpus_sha256', impressao_corpus())
print('fragmentos_por_tema', dict(Counter(d.metadata['tema'] for d in fragmentos)))
print('dimension', indice_demo.index.d, 'total', indice_demo.index.ntotal)
perguntas = [
    ('Quais fotografias devem ser anexadas para relatar uma carcaça quebrada ao abrir a caixa?', 'devolucoes'),
    ('Como se verifica a compatibilidade elétrica antes de instalar uma peça?', 'garantia'),
    ('O que acontece se o rastreamento não muda depois do despacho?', 'entrega'),
    ('Quantos meses de garantia fictícia tem o compressor PEC-01-0001?', 'garantia'),
    ('Qual oferta de PEC-01-0001 está descontinuada e sem estoque?', 'entrega'),
]
for texto, tema in perguntas:
    geral = consultar(indice_demo, texto, k=1)[0]
    filtrado = consultar(indice_demo, texto, k=1, filtro={'tema': tema},
                        fetch_k=indice_demo.index.ntotal)[0]
    print('pergunta', texto)
    print('sem_filtro', geral['fonte_id'], geral['metadados']['secao'], round(geral['score'], 3))
    print('com_filtro', filtrado['fonte_id'], filtrado['metadados']['secao'], round(filtrado['score'], 3))
    print('fragmento', filtrado['texto'][:180].replace('\\n', ' '))
print('filtro_sem_coincidencias', consultar(indice_demo, perguntas[0][0],
      filtro={'tema': 'inexistente'}, fetch_k=indice_demo.index.ntotal))"""),
    ("md", "## T24 · falha observada e reformulação\nSobre o mesmo índice sintético e com top-4, uma pergunta coloquial sobre várias caixas não recupera a regra de entregas parciais. A resposta existe em `entrega.md`, seção 5. A intenção é reformulada sem incluir a resposta. O filtro por tema é um segundo teste, separado da comparação antes/depois. A distância só é interpretada como L2 porque o índice informa essa métrica. Esta evidência local não substitui o índice preexistente exigido por R22."),
    ("code", """from pedro.policy_demo import FRAGMENTO_T24_ESPERADO, PERGUNTA_T24_ORIGINAL, PERGUNTA_T24_REESCRITA
from pedro.rag import diagnosticar_reescrita
original, reescrita, esperado = PERGUNTA_T24_ORIGINAL, PERGUNTA_T24_REESCRITA, FRAGMENTO_T24_ESPERADO
print('original :', original)
print('reescrita:', reescrita)
relatorio = diagnosticar_reescrita(indice_demo, original, reescrita, esperado, k=4)
print('métrica', relatorio['metrica'], 'fragmentos', relatorio['total_fragmentos'],
      'top_k', relatorio['k'], 'fetch_k', relatorio['fetch_k'])
print('fonte_esperada', esperado, relatorio['evidencia_esperada']['metadados'])
for etapa in ('antes', 'depois'):
    print(etapa, 'posição', relatorio['posicao_' + etapa])
    for fragmento in relatorio[etapa]:
        print(fragmento['posicao'], fragmento['fonte_id'],
              fragmento['metadados']['fonte'], fragmento['metadados']['secao'],
              round(fragmento['score'], 3))
print('correcao_observada', relatorio['correcao_observada'])
com_filtro = consultar(indice_demo, original, k=4, filtro={'tema': 'entrega'},
                      fetch_k=indice_demo.index.ntotal)
print('filtro_entrega', [(x['fonte_id'], round(x['score'], 3)) for x in com_filtro])
assert relatorio['correcao_observada']
assert any(x['fonte_id'] == esperado for x in com_filtro)"""),
    ("md", "## R22 · índice FAISS existente: é carregado, não construído\nO índice de `knowledge/politicas/` foi criado uma vez com `scripts/construir_indice_politicas.py` e está salvo com o seu manifesto. Aqui ele só é **carregado** do disco: primeiro conferem-se o manifesto e as impressões digitais, e sem confiança explícita o docstore não é aberto. Depois repete-se T24 sobre o índice carregado. O corpus é fictício e próprio."),
    ("code", """from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from pedro.rag import carregar_indice, inspecionar_indice
pasta = Path('knowledge/politicas')
meta = inspecionar_indice(pasta)
print({k: meta[k] for k in ('origem', 'criado_utc', 'embedding_model', 'dimension', 'metrica')})
print('fragmentos no manifesto:', len(meta['documentos']), '| sha256:', meta['sha256'])
print('corpus sem mudanças desde a indexação:', meta['corpus_sha256'] == impressao_corpus())
embeddings = FastEmbedEmbeddings(model_name=meta['embedding_model'], doc_embed_type='passage')
try:
    carregar_indice(pasta, embeddings, origem_confiavel=False)
except PermissionError as erro:
    print('sem confiança explícita ->', erro)
existente, _ = carregar_indice(pasta, embeddings, origem_confiavel=True)
print('carregado do disco:', existente.index.ntotal, 'fragmentos')
relatorio = diagnosticar_reescrita(existente, original, reescrita, esperado, k=4)
for etapa in ('antes', 'depois'):
    print(etapa, 'posição', relatorio['posicao_' + etapa],
          [(f['fonte_id'], round(f['score'], 3)) for f in relatorio[etapa]])
assert relatorio['correcao_observada']"""),
])

salvar("05_integrador_avaliacao.ipynb", [
    ("md", "# Fase 5 · publicação verificada\nFormulário e agente usam o verificador. O chat usa o mesmo fluxo final. Agent e LangSmith remotos esperam credenciais."),
    ("code", PRE),
    ("code", """from pedro.catalog import criar_cenario
from pedro.contracts import Solicitacao
from pedro.verification import resposta_local, verificar
from pedro.agent import renderizar, criar_fluxo
from pedro.memory import nova_sessao, Historico
cenario = criar_cenario(Path('storage/notebooks/catalogos'))
solicitacao = Solicitacao(produto_id='PEC-01-0001', quantidade=5,
    orcamento_centavos=1_000_000, prazo_max_dias=7)
resposta = resposta_local(cenario, solicitacao)
print('erros', verificar(resposta, cenario))
if not verificar(resposta, cenario): print(renderizar(resposta))
memoria = Path('storage/notebooks/final.sqlite3')
sessao = nova_sessao(memoria, 'aluna', cenario.dataset_id)
fluxo = criar_fluxo(cenario, memoria)
print(fluxo.invoke({'input':'lista peças'}, config={'configurable':{
    'user_id':'aluna','session_id':sessao}}).content[:300])
print([m.type for m in Historico(memoria, 'aluna', sessao).todos()])"""),
    ("md", "## Comparação de fornecedores: pedido mínimo, origem e preferência\nExecução real local, sem modelo. É o núcleo do assistente: para cada oferta conferem-se estoque, **pedido mínimo**, prazo e orçamento, e mostra-se se o fornecedor é nacional ou internacional. Uma preferência salva do usuário ordena as ofertas válidas, nunca faz vencer uma que não atende, e a resposta diz quanto custa respeitá-la."),
    ("code", """from pedro.business import origem_preferida
casos = [('2 unidades: o fornecedor mais barato com estoque exige um pedido mínimo de 5',
          Solicitacao(produto_id='PEC-01-0001', quantidade=2)),
         ('5 unidades: o pedido mínimo já é alcançado',
          Solicitacao(produto_id='PEC-01-0001', quantidade=5)),
         ('sem preferência: vence a mais barata',
          Solicitacao(produto_id='PEC-11-0001', quantidade=2)),
         ('com a preferência salva «fornecedor = nacionais»',
          Solicitacao(produto_id='PEC-11-0001', quantidade=2,
                      origem_preferida=origem_preferida({'fornecedor': 'nacionais'})))]
for titulo, pedido in casos:
    comparacao = resposta_local(cenario, pedido)
    print('###', titulo, '| erros de verificação:', verificar(comparacao, cenario))
    print(renderizar(comparacao))
    print()"""),
    ("md", "## Aviso de preço: função hardcoded, conselho do modelo e verificação\nO histórico de preços não muda o vencedor, mas gera um aviso quando o preço de hoje se afasta da sua média. O sinal, os fatos e o aviso de modelo fixo são funções *hardcoded* e são executados aqui de verdade. **Duplo de teste:** o conselho é devolvido por um modelo roteirizado e o NLI é um classificador roteirizado, para ver os três desfechos: conselho respaldado, conselho com um número inventado e conselho sem respaldo NLI. A medição com o modelo e o NLI reais está em `docs/rastros/precos_conselho_llm.json`."),
    ("code", """import json
from langchain_core.runnables import RunnableLambda
from pedro.precos import aconselhar, aviso_de_preco, criar_conselheiro, fatos_de_preco, sinal_preco
cara = resposta_local(cenario, Solicitacao(produto_id='PEC-02-0189', quantidade=5))
for alternativa in cara.alternativas:
    if alternativa.atende:
        print('sinal:', sinal_preco(alternativa.oferta).model_dump())
print('fatos:')
for fato in fatos_de_preco(cara):
    print('  -', fato)
print('aviso de modelo fixo:', aviso_de_preco(cara))
class NLIRoteirizado:
    def __init__(self, rotulo): self.rotulo = rotulo
    def classificar(self, premissa, hipotese): return self.rotulo
bom = ('O preço de CentroPeças está 11 % acima da sua média de 5 meses. Atlantic Repair Parts '
       'custa 1 % a mais que a recomendada e está 10 % abaixo da sua média.')
casos = [('conselho respaldado', bom, 'entailment'),
         ('número inventado', bom.replace('11 %', '40 %'), 'entailment'),
         ('sem respaldo NLI', bom + ' É uma grande oportunidade.', 'neutral')]
for titulo, texto, rotulo in casos:
    conselheiro = criar_conselheiro(RunnableLambda(lambda _, t=texto: json.dumps({'conselho': t})))
    resultado = aconselhar(cara, conselheiro, NLIRoteirizado(rotulo))
    print('###', titulo, '->', resultado['fonte'], '| erros:', resultado['erros'])
    print('    publica-se:', resultado['texto'])
print(renderizar(cara).splitlines()[-2])"""),
    ("md", "A avaliação remota é executada com evals/avaliar_fluxo.py. Não se reportam métricas sem essa execução."),
])
print("Cinco notebooks criados")
