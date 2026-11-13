# Relatório técnico — Pedro, assistente de compras

**Curso:** Agentes Cognitivos com LangChain (Infnet). **Atualizado:** 2026-11-13. **Modelo:** gpt-4.1-mini. **Testes automáticos:** 188, todos passando.

Este relatório explica como o projeto responde às 29 rubricas do enunciado, numeradas aqui de R01 a R29 na ordem em que aparecem nele. Cada rubrica tem aqui um resumo; a resposta completa, com suas tabelas e seus limites, está em docs/respostas_rubricas.md. As execuções com o modelo real estão salvas em docs/rastros/ e o registro do que foi executado, em docs/evidencias.md.

## 1. Resumo

Pedro é um assistente que ajuda a comprar peças de reposição de eletrodomésticos: compara as ofertas de vários fornecedores para uma peça e uma quantidade, e recomenda uma. Todos os dados são sintéticos.

- **O que faz bem.** Compara fornecedores com regras exatas, mantém uma conversa de vários turnos, responde perguntas sobre políticas com a fonte, confirma um CEP com uma API real e não publica nada sem verificar.
- **Resultado medido.** Na avaliação vigente no LangSmith, de 2026-11-13, acerta o vencedor e o valor em 14 de 14 recomendações, e as 24 propostas do modelo passam na verificação na primeira tentativa.
- **Como se trabalhou.** Cada rubrica tem uma execução salva. Várias execuções com o modelo real revelaram falhas que os testes não viam; elas foram diagnosticadas, corrigidas e medidas de novo, e o antes e o depois estão guardados.
- **Migração para português.** Em 2026-11-11 o projeto inteiro foi migrado do espanhol para o português (o glossário de nomes está em docs/glossario_migracao.md). As regras de negócio e os preços do catálogo não mudaram. Todas as demonstrações e a avaliação no LangSmith foram reexecutadas em português, com os mesmos números de qualidade. Só a pergunta do diagnóstico de recuperação T24 precisou ser medida de novo (ver R23).
- **Últimas mudanças (2026-11-13).** Uma guarda de entrada recusa assuntos alheios e tentativas de mudar as instruções antes de chamar o agente. O modelo de conversa passou a ser configurável: a OpenAI ou um servidor local. E quando o agente não redige uma resposta válida para um pedido completo ou para um CEP, o sistema publica o seu próprio cálculo, verificado. A avaliação no LangSmith e a maior parte das demonstrações com o modelo real foram refeitas nesse dia (seção 13).
- **O que fica em aberto.** O vídeo de demonstração e uma suposição declarada: a escala de maturidade de R01 é genérica. As rubricas foram conferidas com o enunciado original em 2026-11-13 (seção 14).
- **Uso de IA.** O projeto foi feito com o apoio do Claude Code, da Anthropic. O que foi usado, e para quê, está na seção 15.

## 2. Problema e domínio

Um comprador precisa de uma peça, em certa quantidade, às vezes com um orçamento e um prazo. Vários fornecedores a oferecem com preço, frete, estoque, prazo e pedido mínimo diferentes. O assistente deve dizer qual convém e por que as outras não.

O catálogo é uma base SQLite sintética e reproduzível (semente 20261107): 18 categorias de eletrodomésticos, 4.320 peças, 12.960 ofertas de 12 fornecedores, 12.960 compatibilidades e 77.760 preços históricos. Em 2026-11-11 ele foi ampliado de 11 para 18 categorias (antes eram 2.640 peças): entraram aspiradores de pó, liquidificadores, cafeteiras, purificadores de água, ventiladores, ferros de passar e fritadeiras elétricas, com IDs PEC-12 a PEC-18. As categorias novas são geradas depois das originais, com um gerador aleatório próprio. Por isso as peças PEC-01 a PEC-11 conservam IDs, preços, ofertas, estoque, prazos e histórico, conferidos tabela a tabela com a base anterior. Cada conversa trabalha sobre um cenário isolado: uma cópia da base com um identificador próprio e um manifesto com a sua impressão digital. O assistente só lê: não compra nem paga.

## 3. O núcleo: comparar fornecedores

Todo o resto existe para que esta comparação seja correta e confiável.

### Regras

| Regra | A oferta é descartada se… |
|---|---|
| Estoque | Não há unidades suficientes |
| Pedido mínimo | O fornecedor exige comprar mais unidades do que as pedidas |
| Prazo | Demora mais que o prazo máximo do usuário, se ele informou |
| Orçamento | O total passa do orçamento do usuário, se ele informou |

O total é quantidade vezes preço unitário mais frete, sempre em centavos inteiros. As ofertas são ordenadas assim: primeiro as que atendem; entre elas, as da origem que o usuário prefere (nacional ou internacional), se ele salvou essa preferência; depois por total, prazo e fornecedor. A preferência nunca faz ganhar uma oferta que não atende, e se respeitá-la custa mais, a resposta diz isso. Cada resposta mostra todas as ofertas, com a origem e o motivo do descarte.

### A descoberta que mudou a comparação

Durante quase todo o projeto a comparação ignorou o pedido mínimo, embora o dado estivesse no catálogo. O exemplo de todas as demonstrações, 2 unidades de PEC-01-0001, recomendava a CentroPeças por R$ 2.963,07, e esse fornecedor exige 5 unidades. Há 1.837 ofertas com estoque e pedido mínimo maior que 2 (1.151 antes da ampliação do catálogo). Nenhum teste nem métrica detectou o problema: a referência da avaliação tinha a mesma lacuna, então o agente e a referência concordavam. Ele foi encontrado ao revisar quais dados do fornecedor a comparação usava. Com a correção, mudaram 5 dos 14 casos de recomendação da avaliação. Hoje as demonstrações usam 5 unidades de PEC-01-0001: CentroPeças, R$ 7.279,83.

### Histórico e aviso de preço

O catálogo guarda seis preços mensais por oferta. Para cada oferta válida a resposta situa o preço de hoje: o do mês anterior, a média dos cinco meses anteriores e se está no ponto mais baixo ou mais alto. O histórico informa e não decide: ganha o menor total de hoje.

Quando o preço de hoje se afasta pelo menos 10 % da sua média, é acrescentado um aviso. Esse aviso reúne as técnicas do curso sobre o problema central:

| Passo | Técnica | Rubrica |
|---|---|---|
| Sinal do preço, fatos e aviso fixo | Funções hardcoded | R19 |
| Conselho redigido pelo modelo | Prompt PTCF com few-shot | R11 |
| O conselho chega como objeto validado | Output parser Pydantic | R04 |
| Aviso e conselho são calculados em dois ramos, com plano B | RunnableParallel e with_fallbacks | R06, R09, R12 |
| O conselho só é publicado se os seus números saem dos fatos e o NLI o sustenta | Verificação exata e NLI | R24 |

Com o modelo e o NLI reais, sobre quinze peças: na versão anterior em espanhol, passaram na verificação 5 conselhos com o primeiro prompt (docs/rastros/precios_consejo_llm_antes.json) e 14 com o prompt ajustado. Em português passaram 14 de 15 na primeira execução (o que ficou de fora citava um número que não estava nos fatos; essa execução está no histórico do git) e 15 de 15 na reexecução de 2026-11-13 (docs/rastros/precos_conselho_llm.json). Com o primeiro prompt, o modelo acrescentava avaliações («una buena oportunidad», citação da execução em espanhol) imitando um exemplo few-shot, e o NLI as rejeitava. É aqui, ao verificar texto livre, que o modelo NLI faz um trabalho que o cálculo exato não consegue fazer.

### Perguntas sobre a comparação

Depois de uma comparação, o usuário pergunta «a mais barata?» ou «qual chega mais rápido?». Antes, o chat repetia o mesmo painel sem responder, e às vezes terminava em «Não posso confirmar…». Agora uma regra reconhece essa pergunta e deixa a solicitação como está. A regra exige que a pergunta fale de preço, prazo, estoque ou origem, ou nomeie um dos fornecedores comparados, e exclui perguntas sobre o catálogo inteiro: na primeira versão, «Quais categorias de peças existem?» recebia o resumo da comparação; agora vai para o agente. Depois, o sistema refaz a comparação e a verifica, sem depender de o modelo chamar a ferramenta de novo; e o modelo escreve uma ou duas frases que respondem à pergunta (src/pedro/resposta_direta.py). A frase só é publicada se os seus números estão nos fatos, se nomeia um fornecedor comparado e se o NLI a sustenta; se não, publica-se um resumo fixo calculado pelo sistema. A interface mostra a resposta em um quadro verde acima dos cartões. A recomendação e os números nunca mudam.

Com o modelo e o NLI reais, uma comparação e seis perguntas (docs/rastros/pergunta_direta_llm.json, de 2026-11-13): cinco foram respondidas com a frase do modelo verificada e uma com o resumo fixo. Nessa, «por que não a Litoral Parts?», o NLI classificou como contradição uma frase que era verdadeira. As duas execuções anteriores do mesmo script, que só estão no histórico do git, deram 5 frases verificadas e 1 resumo fixo (commit 4e0f6db) e depois 6 e 0. Limites: a regra é de vocabulário e o resumo fixo não se adapta à pergunta.

## 4. Arquitetura

Um turno segue sempre o mesmo percurso: guardar a entrada, interpretar a mensagem, decidir o caminho, consultar, verificar e responder.

- **Guardar a entrada.** Antes de tudo, uma guarda decide se a mensagem entra no fluxo (src/pedro/guardrails.py). Regras fixas resolvem o que é claro: tentativa de mudar as instruções ou de obter o prompt e as chaves, cumprimento, assunto claramente alheio, mensagem vazia ou longa demais (mais de 1.200 caracteres). Um classificador com o modelo decide só o que as regras deixam em aberto. Uma mensagem recusada recebe um texto fixo e não chega ao agente nem às ferramentas.
- **Interpretar.** As regras identificam a peça, que tem formato fixo; um intérprete com modelo decide se a mensagem é uma compra e o que ela muda. Se a mensagem traz várias intenções, um planejador a divide em pedidos.
- **Decidir.** O que é reconhecido sem ambiguidade vai por uma rota fixa (listagem, ficha, esclarecimento). O resto vai para o agente.
- **Consultar.** O agente, construído com create_openai_tools_agent e AgentExecutor, escolhe entre seis ferramentas: três de SQL, uma de RAG, uma de API e uma de memória.
- **Verificar.** Toda proposta passa por uma verificação exata e por um modelo NLI. Antes, um passo de ancoragem preenche com dados das ferramentas o que o modelo copiaria errado.
- **Quando o agente falha.** Se o agente não redige uma resposta válida para um pedido de compra completo, o sistema publica a comparação que ele mesmo calcula, verificada como as outras. Se a falha é em uma consulta de CEP, publica o que o ViaCEP devolveu. Nos dois casos o texto não vem do modelo.
- **Responder.** Só a pergunta e a resposta publicada são salvas na memória.

Um princípio atravessa o projeto: **o modelo decide o que responder; os dados quem põe é o sistema.** Valores, vencedor, citações, cidade de um CEP e tabelas de resultados saem sempre das ferramentas, nunca do que o modelo escreve.

A interface é Streamlit (app.py) e tem só o chat; toda a lógica fica em src/pedro/. Sem chave da OpenAI o chat funciona em modo degradado, com as rotas fixas e a comparação por regras. O modelo de conversa é escolhido pelo arquivo .env (src/pedro/modelos.py): por padrão é o gpt-4.1-mini da OpenAI; com PEDRO_BASE_URL aponta para um servidor compatível com a API da OpenAI, por exemplo um modelo local no Ollama.

A guarda de entrada foi medida com o modelo real em 28 mensagens (docs/rastros/guardrails_llm.json): as regras decidiram 21, todas corretas, e o modelo classificou as outras 7, também corretas. No chat, nenhuma mensagem recusada chamou ferramentas.

O modelo local foi testado com o llama3.2 no Ollama, em CPU, sem chamar a OpenAI (docs/rastros/modelo_local_llm.json, cinco mensagens). A guarda recusou na hora as duas mensagens alheias. Na comparação e no CEP o modelo não conseguiu redigir uma resposta no formato exigido, e o sistema publicou o seu cálculo e a resposta do ViaCEP, depois de três a cinco minutos por turno. A pergunta sobre a comparação foi respondida com uma frase verificada em 38 segundos. As medições deste relatório e a demonstração em vídeo usam o gpt-4.1-mini.

## 5. Fase 1 — Chain executável e arquitetura (R01–R06)

| Rubrica | O que foi feito | Resultado principal |
|---|---|---|
| R01 | Anatomia, tipo e maturidade do agente | Agente híbrido; maturidade nível 4 demonstrada |
| R02 | Planejamento e memória aumentada | Cinco passos observáveis e planejador de turno |
| R03 | Modelos de prompt reutilizáveis | Doze ChatPromptTemplate com nome próprio |
| R04 | Saída estruturada em JSON | Laboratório de oito saídas quebradas |
| R05 | invoke, batch, stream e @chain | Os três medidos com o modelo real |
| R06 | LCEL e justificativa | Os dois estilos comparados pelo que o rastro deixa ver |

### R01 — Anatomia, tipo e maturidade

A anatomia é lida dos objetos reais do agente, não é escrita à mão: modelo, executor, prompt PTCF, seis ferramentas, memória, base de conhecimento e porta de publicação. Pedro é um agente **híbrido**: uma camada reativa de regras resolve o que não deve ficar a critério do modelo, e uma camada deliberativa escolhe ferramentas, mantém estado e revisa a sua proposta. A maturidade fica no nível 4 de uma escala genérica de cinco (agente com memória e autoverificação) e está demonstrada com medições. Não se busca o nível 5: o problema não exige vários agentes nem executar compras. A escala é uma suposição declarada, porque a da primeira aula não está disponível.

### R02 — Planejamento e memória aumentada

Uma solicitação é dividida em cinco passos com saída observável: extrair, consultar, comparar, verificar e publicar. Uma mensagem com várias intenções passa antes por um planejador de turno: o modelo escreve um plano com um pedido por intenção, o plano é validado (não pode acrescentar dados que o usuário não escreveu) e cada pedido é resolvido e verificado separadamente. Com o modelo real, uma mensagem que misturava compra, política e CEP gerou três pedidos, os três publicados (docs/rastros/r02_planejamento_llm.json). Antes do planejador, na versão anterior em espanhol, nada era publicado (docs/rastros/r02_planificacion_llm_sin_plan.json). A memória é dividida em dois níveis: a sessão guarda o que só serve para a compra em andamento e o usuário guarda o que deve sobreviver. Preços e estoque não são memória: são sempre relidos.

### R03 — Modelos de prompt reutilizáveis

Os modelos de prompt estão reunidos em src/pedro/prompts.py, todos ChatPromptTemplate: extração (em três variantes), reparo, text-to-SQL, planejador, intérprete, conselho de preço, resposta direta, resposta sobre a política de entrega parcial, classificador da guarda de entrada e agente. São doze. O de extração é reutilizado na cadeia declarativa e na imperativa, e foi executado com o modelo real sobre três solicitações do domínio. Escolheu-se ChatPromptTemplate porque separa as regras (mensagem de sistema) do que o usuário escreve (mensagem humana).

### R04 — Saída estruturada em JSON

A cadeia converte uma solicitação em um objeto validado com Pydantic. Para testar a robustez foi construído um laboratório com oito saídas típicas de um modelo; cada defeito é resolvido por uma camada diferente: o parser (cercas de markdown), uma segunda cadeia que repara (JSON truncado, tipos incorretos, texto livre) ou uma regra de domínio (os faltantes são calculados pelo código). Com o modelo real como reparador, os cinco reparos devolveram os dados corretos. O laboratório revelou que o parser aceita JSON truncado e perde um dado sem avisar; a cadeia robusta confere isso. Também foi executado with_structured_output: deu o mesmo resultado que o parser em 2 das 3 solicitações; na terceira, sem ID de peça, classificou a intenção e os faltantes de outro jeito. Mantém-se o parser porque deixa ver e reparar a saída bruta.

### R05 — Runnable e composição imperativa

Com o modelo real: invoke produz um objeto validado; batch processou três solicitações em 1,47 s, contra 4,83 s de três invoke em série; stream entregou 20 estados parciais, o primeiro aos 0,59 s. O que se aprendeu: stream só transmite se todos os passos sabem transmitir, e com o parser Pydantic chega um único fragmento. A composição imperativa usa @chain em duas cadeias; uma repete com try/except o reparo de R04 e dá o mesmo resultado no laboratório. São medições únicas, não um benchmark.

### R06 — Composição declarativa e escolha

Há quatro cadeias LCEL (sequência, fallback, stream parcial e paralelo). A cadeia com reparo existe nos dois estilos e dá o mesmo resultado; o que muda é o que se observa: na versão declarativa o rastro registra 16 passos quando há reparo, incluído o erro, e na imperativa 9, sem o erro. Decisão: LCEL para o que é um encadeamento, e imperativo para decidir o caminho de cada turno, que tem ramos e saídas antecipadas.

## 6. Fase 2 — Agente com ferramentas e ReAct (R07–R12)

| Rubrica | O que foi feito | Resultado principal |
|---|---|---|
| R07 | Comparação de orquestradores | Seis comparados; LangChain e LangGraph executados |
| R08 | ReAct com initialize_agent | Responde bem com memória e falha sem ela |
| R09 | Chains e RouterChain | Router por regras 2 de 7; router LLM 6 de 7 |
| R10 | API externa por function calling | ViaCEP real em três casos |
| R11 | PTCF, few-shot e chain-of-thought | Zero-shot 6 de 10; few-shot 10 de 10 |
| R12 | Componentes de confiabilidade | Os quatro, com caso normal e de erro |

### R07 — Orquestradores

São comparados LangChain, LangGraph, LlamaIndex, AutoGen, Semantic Kernel e Langflow por autonomia, abstração e modularidade. O mesmo agente pequeno foi executado no LangChain e no LangGraph: deram as mesmas respostas, mas o LangGraph guardou no seu estado o resultado de uma ferramenta e não a chamou de novo. Para o Pedro, em que preços e estoque devem ser relidos, essa diferença importa. O LangChain é mantido porque o projeto usa 13 tipos de componentes dele e porque a rubrica cita as suas APIs. Três delas estão marcadas como obsoletas; a migração natural seria para o LangGraph. Os outros quatro orquestradores são comparados de forma conceitual.

### R08 — ReAct

Um agente com initialize_agent e ZERO_SHOT_REACT_DESCRIPTION, duas ferramentas e ConversationBufferMemory foi executado com o modelo real e deixou escrito o seu ciclo de pensamento, ação e observação. O que se aprendeu: o prompt zero-shot original não lê a memória. Com o histórico dentro do prompt resolveu uma pergunta de continuação (CentroPeças, 2 dias); sem ele, pediu de novo a peça.

### R09 — Chains e routing

Há cadeias sequenciais e uma paralela, e dois routers sobre RouterChain. Em sete perguntas, o router por regras acertou 2 rotas e o decidido pelo modelo, 6. As perguntas foram escolhidas para pôr as regras à prova. O chat não usa nenhum deles como porta de entrada: o agente já roteia ao escolher a ferramenta.

### R10 — API externa

O agente chama o ViaCEP, uma API pública real, por function calling. Estão salvos o esquema que o modelo recebe, os argumentos que ele envia, a resposta da API e o que foi publicado, em três casos: válido (São Paulo/SP), inexistente e inválido. A primeira execução, na versão anterior em espanhol, não publicou a cidade porque o modelo copiava errado um identificador (docs/rastros/r10_viacep_llm_antes.json); agora a resposta é preenchida com o que a ferramenta devolveu. Na reexecução de 2026-11-13, o CEP válido foi publicado na primeira tentativa; nos outros dois as duas propostas do modelo foram rejeitadas e o sistema publicou as mensagens fixas «O ViaCEP não tem registro do CEP 99999999.» e «Um CEP deve ter oito dígitos.».

### R11 — Prompts

O prompt do agente segue PTCF (Persona, Tarefa, Contexto, Formato) e leva exemplos few-shot. Foram medidas três técnicas em dez solicitações difíceis: sem exemplos 6 acertos, com few-shot 10 e com few-shot e chain-of-thought 10. O raciocínio é escrito em um campo antes dos dados, de modo que é observável. No agente, o pensamento passo a passo são as suas chamadas de ferramentas, que ficam registradas. O aviso de preço trouxe outra lição: o modelo imita o estilo do exemplo, não só o formato.

### R12 — Confiabilidade

Os quatro componentes têm um caso normal e um de erro: parser com reparo, memória que guarda só o que foi publicado, busca FAISS com filtro e um callback que registra cada ferramenta e cada verificação. Esse registro é o que permitiu encontrar as falhas do agente com o modelo real.

## 7. Fase 3 — Chatbot com memória (R13–R18)

| Rubrica | O que foi feito | Resultado principal |
|---|---|---|
| R13 | Memórias segundo CoALA | As quatro, com o seu conteúdo após uma conversa real |
| R14 | Janela e busca vetorial | Janela de 12 sobre 16 mensagens; três lembranças recuperadas |
| R15 | Ferramentas de memória | LangMem executado frente à memória própria |
| R16 | ConversationBufferMemory | Chatbot de quatro turnos que lembra tudo |
| R17 | Intenção e entidades | Regras sozinhas 8 de 14; regras e modelo 14 de 14 |
| R18 | Conversa real multi-turno | Oito turnos com o estado correto |

### R13 — Memórias

Pedro tem as quatro memórias de CoALA: de trabalho (mensagem, rascunho de compra e janela, por sessão), episódica (comparações passadas com vetor, por usuário), semântica (preferências, catálogo e políticas) e procedimental (prompt e regras). Uma preferência é um fato e é aplicada: ordena as ofertas de cada comparação. Um episódio é um acontecimento e só é lembrado, porque os seus dados podem ter vencido.

### R14 — Janela de contexto

O agente recebe uma janela deslizante das últimas 12 mensagens mais os três episódios mais parecidos com a pergunta. Depois de uma conversa real havia 16 mensagens salvas e 12 na janela; em uma sessão nova foram recuperados três episódios (similaridade entre 0,22 e 0,27) e nenhum para outro usuário. Escolheu-se janela e não resumo porque a janela não pode alterar um número.

### R15 — Ferramentas de memória

São comparados Mem0, Letta/MemGPT e LangMem com a memória própria. O LangMem foi executado com a mesma conversa: as duas salvaram a preferência e isolaram por usuário. O LangMem deixa o modelo decidir o que lembrar e soube responder o que lembrava; o agente dele, sem verificação, deu uma resposta contraditória sobre estoque e prazo. Mantém-se a memória própria porque o que entra deve poder ser conferido. Mem0 e Letta são comparados de forma conceitual.

### R16 — Chatbot com buffer

Um chatbot com ConversationChain e ConversationBufferMemory lembrou em quatro turnos o nome, a quantidade, o orçamento e o prazo. A memória cresceu de 313 para 954 caracteres: o buffer não tem limite, e por isso o agente final usa a janela.

### R17 — Intenção e entidades

O chat reconhece seis intenções e cinco entidades. As regras identificam a peça e um intérprete few-shot decide se a mensagem é uma compra e o que ela muda. Em catorze mensagens difíceis, as regras sozinhas acertaram 8 e com o modelo 14: ele entende «Suba para meia dúzia», «Esqueça o prazo» ou «Dobre a quantidade». Uma regra nova reconhece as perguntas sobre a comparação em andamento («a mais barata?») e deixa a solicitação como está; o intérprete ganhou dois exemplos few-shot para esse caso, e a medição refeita deu o mesmo resultado. Quando falta a peça ou a quantidade, pergunta em vez de inventar.

### R18 — Conversa real

Em oito turnos com o modelo real o agente descartou uma compra de 2 unidades por pedido mínimo, recalculou com 5 mantendo o prazo, trocou o prazo por um orçamento, salvou uma preferência, respondeu um CEP e uma política sem mexer na compra, voltou a comparar com o estado correto e aplicou a preferência a outra peça, em que o fornecedor nacional ganhou custando mais. A primeira versão desta conversa, na versão anterior em espanhol, falhou em três turnos (docs/rastros/fase3_memoria_llm_antes.json); os dois rastros estão guardados. Na reexecução de 2026-11-13, no turno da preferência o agente salvou a preferência e refez a comparação: a primeira proposta foi rejeitada pela verificação exata e a segunda foi publicada.

## 8. Fase 4 — SQL, APIs e RAG (R19–R23)

| Rubrica | O que foi feito | Resultado principal |
|---|---|---|
| R19 | Ferramentas hardcoded e semânticas | Seis ferramentas catalogadas |
| R20 | APIs por tipo de uso | Três externas e quatro internas |
| R21 | Text-to-query | 5 de 5 perguntas; 7 de 7 consultas hostis rejeitadas |
| R22 | Índice FAISS existente | O agente o carrega, não o constrói |
| R23 | Falha de recuperação | Diagnosticada e corrigida, com antes e depois |

### R19 — Ferramentas

Seis ferramentas: quatro de lógica fixa, uma semântica (políticas) e uma mista (catálogo). A regra de divisão: tudo o que é um número ou uma regra é feito por código fixo; o semântico busca por significado e nunca decide um valor.

### R20 — APIs

Três externas (ViaCEP para confirmar o destino, OpenAI como motor e LangSmith para avaliar) e quatro internas (catálogo em somente leitura, políticas em FAISS, memória isolada e verificação). O tipo de uso define a integração: o que lê é somente leitura, o que chama um terceiro tem limite de tempo e estados de erro, e a verificação fica fora do alcance do modelo. Nenhuma API compra nem modifica o catálogo.

### R21 — Text-to-query

A ferramenta de catálogo tem dois modos. Com um ID de peça usa modelos fixos de consulta. Para perguntas abertas há um text-to-SQL completo: o modelo escreve um SELECT e o motor decide se o executa. Três barreiras: a forma (uma única instrução SELECT), o autorizador do SQLite (só as tabelas e colunas de uma lista) e os limites (somente leitura, 50 linhas). Com o modelo real respondeu bem 5 de 5 perguntas. Na versão anterior em espanhol, antes de melhorar o prompt, eram 3 de 5 (docs/rastros/fase4_sql_llm_antes.json): duas consultas eram válidas, mas estavam mal formuladas. Válida não significa correta, e por isso o chat mostra sempre a consulta executada. A tabela de resultados é montada pelo sistema.

### R22 — Índice FAISS existente

O índice é construído uma vez, fora do agente, e salvo com um manifesto. O agente só o carrega, em menos de um décimo de segundo (0,09 s na última execução). Como o seu armazenamento é um arquivo pickle, a carga exige um manifesto completo, impressões digitais que coincidam e confiança explícita; foi testado que ele rejeita um arquivo alterado. O índice é próprio: o enunciado pede usar um índice já construído, sem refazer a indexação, e não entrega um.

### R23 — Falha de recuperação

A pergunta «Posso receber em várias caixas?» não recuperava a regra correta, que está no corpus. Diagnóstico: desajuste de vocabulário; o usuário diz «várias caixas» e a política diz «entrega parcial». Correção: reformular a consulta com o termo do domínio. Com o mesmo índice e os mesmos quatro resultados, o fragmento FIC-ENT-01-S05-C01 passou de não aparecer para a primeira posição (docs/rastros/r23_t24_indice_existente.json).

Esta pergunta foi medida de novo na migração. A tradução literal da pergunta espanhola, «Pode mandar em várias caixas?», deixou de falhar no corpus em português: o fragmento esperado ficou na posição 4 de 4. Foram medidas oito formulações naturais e escolhida uma que falha de verdade.

No chat, perguntas diferentes sobre receber em várias caixas recebiam exatamente o mesmo texto, porque a rota copiava sempre as mesmas duas frases da política. Agora a regra literal e a sua fonte continuam fixas e são publicadas sempre, e o modelo redige uma ou duas frases que respondem à pergunta feita, só com o fragmento recuperado. A frase só é publicada se não traz números fora da fonte e se o NLI a sustenta; se não, fica só a regra literal. Se o modelo julga que a política não responde e a pergunta pede um detalhe («quais», «quanto»), a resposta avisa: «A política não responde exatamente ao que você perguntou.» A rota também deixou de recusar quando a pergunta original já recuperava a regra: responde e diz a posição observada, sem afirmar uma correção. Com o modelo real e cinco perguntas diferentes: 4 frases verificadas, 1 rejeitada pelo NLI (publicou-se a regra literal), as 5 respostas citam a regra, 2 mostram a recuperação corrigida e as 5 primeiras linhas são diferentes (docs/rastros/r23_resposta_llm.json). Limites: a rota é ativada só por vocabulário, a frase usa só o fragmento da regra e o julgamento «responde ao perguntado» é do modelo e não é verificado.

## 9. Fase 5 — Agente final verificado e avaliado (R24–R29)

| Rubrica | O que foi feito | Resultado principal |
|---|---|---|
| R24 | Verificação factual e lógica | Nenhuma recomendação contrária à regra publicada |
| R25 | Agente único | SQL, RAG e API sob o mesmo executor |
| R26 | create_openai_tools_agent e AgentExecutor | Executado em conversa, avaliação e interface |
| R27 | RunnableWithMessageHistory | Só se salva o que foi publicado |
| R28 | Streamlit | O app executado com o agente real |
| R29 | LangSmith | Dez experimentos com seis métricas |

### R24 — Verificação

Nenhuma resposta é mostrada sem passar por duas portas dentro do fluxo. A verificação exata recalcula a resposta com os dados do cenário: total, estoque, pedido mínimo, orçamento, prazo, vencedor, identificadores e procedência. O modelo NLI classifica a relação entre evidência e afirmação em três classes, e só entailment permite publicar. Um passo anterior de ancoragem preenche com dados das ferramentas as citações, o CEP, as preferências, os números da comparação e as tabelas do catálogo. Se a verificação falha há uma correção; se falha de novo, não se publica. O conselho de preço e a resposta direta a uma pergunta sobre a comparação passam por uma porta própria (números exatos, fornecedor e NLI); se falham, publica-se o texto fixo do sistema. A frase que responde a uma pergunta sobre a entrega parcial passa por uma porta parecida (números e NLI contra o fragmento recuperado); se falha, publica-se só a regra literal. Limite importante: a verificação confere contra a regra de negócio, não confere a regra; enquanto a comparação ignorou o pedido mínimo, aprovou recomendações que um fornecedor não aceitaria.

### R25 e R26 — Agente único e executor

Um único agente, construído com create_openai_tools_agent e AgentExecutor (seis iterações no máximo), reúne ferramentas de SQL, RAG e API. Na conversa de oito turnos usou as três categorias com o mesmo executor, a mesma memória e o mesmo verificador.

### R27 — Histórico

O agente está envolvido em RunnableWithMessageHistory, com o histórico em SQLite por usuário e sessão. Só se salva o que foi publicado: depois de oito turnos havia 16 mensagens, oito do usuário e oito respostas. O histórico sobrevive à recriação do fluxo.

### R28 — Interface

app.py conecta o Streamlit ao mesmo fluxo. Executado com a ferramenta de testes do Streamlit e o modelo real, respondeu quatro turnos de chat, abriu um chat novo e reabriu a conversa anterior com as suas 8 mensagens, sem erros. A interface é só o chat: o catálogo e a comparação são pedidos ali, com as ferramentas do agente. Cada resposta de compra é desenhada com dados: os passos que o agente seguiu, quatro cartões (fornecedor, total, entrega e origem), o conselho ou aviso de preço em destaque e a tabela de ofertas com a descartada e o motivo. Esses dados viajam com a mensagem já verificada, então a interface não relê o texto e, ao reabrir uma conversa, os cartões são redesenhados. Tudo usa componentes nativos do Streamlit, sem CSS; as capturas estão na seção 16. No chat, a compra de 6 unidades de PEC-01-0001 deu R$ 8.718,75, o mesmo valor da demonstração de R02.

### R29 — Avaliação com LangSmith

O fluxo final foi avaliado sobre 30 casos com seis métricas. Os casos são derivados do catálogo por uma regra independente da comparação; o enunciado não entrega casos de teste. Eles cobrem as categorias de ferramenta e a verificação: 14 recomendações e 5 pedidos sem oferta válida (SQL), 3 consultas de catálogo, 2 de CEP (API externa), 2 de política sem índice (RAG; a resposta certa é não confirmar) e 4 esclarecimentos.

O resultado vigente é o de 2026-11-13, com a guarda de entrada ativa (experimento pedro-infnet-fluxo-gpt-4.1-mini-guardrails-2726b884, dataset pedro-infnet-casos-derivados-bd7b0c2b, registro em docs/rastros/r29_langsmith_gpt-4.1-mini_portugues_guardrails.json). Ao lado está a execução anterior em português, de 2026-11-11 (experimento pedro-infnet-fluxo-gpt-4.1-mini-portugues-235aa9f1, registro em docs/rastros/r29_langsmith_gpt-4.1-mini_portugues.json):

| Métrica | 2026-11-11 | 2026-11-13 (vigente) |
|---|---|---|
| Vencedor correto | 14 de 14 | 14 de 14 |
| Valor correto | 14 de 14 | 14 de 14 |
| Conteúdo correto | 16 de 16 | 16 de 16 |
| Ferramenta decisiva | 23 de 23 | 23 de 23 |
| Primeira proposta aceita | 24 de 24 | 24 de 24 |
| Erros de verificação | 0 | 0 |
| Trajetória completa | 26 de 30 | 15 de 30 |

**Análise comparativa das duas execuções.** Entre elas mudaram o catálogo (de 2.640 para 4.320 peças), a resposta direta, a rota de entrega parcial, a guarda de entrada e o prompt do agente. A qualidade não mudou: mesmos vencedores, mesmos valores e nenhuma proposta rejeitada. O que mudou foi a trajetória: em 15 dos 19 casos de compra o agente chamou só a ferramenta de comparação, sem consultar antes o catálogo; na execução anterior isso aconteceu em 4 de 19. A referência exige os dois passos, e por isso a métrica caiu de 26 para 15. A ferramenta decisiva foi chamada em todos os casos. Não se isolou qual das mudanças causou a diferença: é uma execução de cada.

O experimento fica na conta do LangSmith do autor. A cópia versionável é o arquivo de registro, que traz o resumo e, para cada caso, a pergunta, a resposta, as ferramentas chamadas, as verificações e as notas.

Conclusões, cada uma com o seu dado. Os oito primeiros experimentos são da versão em espanhol do projeto e mantêm os seus números:

- **Mantém-se gpt-4.1-mini.** Em igualdade de condições, na versão em espanhol, gpt-4o-mini acertou 13 de 14 vencedores e 19 de 23 propostas na primeira tentativa.
- **A verificação cumpre o papel.** Quando um modelo propôs um vencedor errado, a proposta foi rejeitada e não foi publicada.
- **A avaliação encontrou um defeito do agente** (o CEP não era publicado) e **um erro de método**: os experimentos compartilhavam memória, e com 73 lembranças acumuladas a trajetória caiu de 25 para 15 de 30 (versão em espanhol).
- **A trajetória completa é uma métrica instável.** Variou entre 13 e 25 de 30 nas execuções da versão em espanhol; em português ficou em 26 e depois em 15 de 30, porque a referência exige um passo que o agente pode pular com o mesmo resultado.
- **Uma métrica perfeita não garante uma regra correta.** Durante seis experimentos, na versão em espanhol, o agente obteve 14 de 14 recomendando ofertas que descumpriam o pedido mínimo, porque a referência compartilhava o erro.

## 10. O que as execuções reais ensinaram

Estas falhas só apareceram ao executar com o modelo real. Os testes automáticos já passavam. Elas foram observadas na versão anterior do projeto, em espanhol; na reexecução em português de 2026-11-11 as correções continuaram funcionando.

| Falha observada | Causa | Correção |
|---|---|---|
| As perguntas de política não eram publicadas | O modelo citava o fragmento quase literal | O sistema ancora a citação no texto da fonte |
| A cidade de um CEP não era publicada | O modelo copiava errado um identificador | A resposta é preenchida com a observação da API |
| Uma compra válida não era publicada | O modelo transcrevia errado o vencedor | Os números quem põe é a ferramenta |
| Uma mensagem com várias intenções não era publicada | A resposta admite um só tipo | Planejador de turno |
| Não entendia «Suba para meia dúzia» nem «Esqueça o prazo» | Regras de diálogo estreitas demais | Intérprete com modelo |
| O parser perdia um dado com JSON truncado | Tolerância do parser | Conferência estrita |
| Duas consultas SQL válidas davam o resultado errado | O modelo confundia ID e SKU | Formato dos valores no prompt |
| A trajetória mudava entre experimentos | Memória compartilhada | Memória nova em cada experimento |
| Recomendava ofertas que o fornecedor não aceitaria | A comparação ignorava o pedido mínimo | Regra nova e casos regenerados |
| Os conselhos de preço eram rejeitados | Um exemplo few-shot convidava a avaliar | Exemplos que só enunciam fatos |

## 11. Limitações

- **Suposições declaradas.** A escala de maturidade de R01 é genérica, porque a da primeira aula não está disponível. O índice FAISS e os 30 casos de avaliação são próprios: o enunciado não entrega um índice nem casos de teste.
- **Medições de uma única execução.** O modelo não é determinístico; as diferenças de um ou dois casos não são conclusivas.
- **Pedro não conversa.** Não responde «o que você lembra de mim?» nem sabe responder a um comentário sem pedido. A cumprimentos e a assuntos alheios a guarda de entrada responde com um texto fixo.
- **A verificação confere se a resposta é verdadeira, não se ela vem ao caso**, e confere contra a regra de negócio, não confere a regra.
- **O aviso de preço dispara muito** (em quatro de cada dez recomendações); os seus limiares não estão calibrados.
- **O modelo NLI não é exato.** Na versão em espanhol rejeitou um conselho que era verdadeiro; falha para o lado seguro. Na execução em português o mesmo caso foi barrado antes, pela verificação exata dos números. Na resposta sobre a entrega parcial rejeitou uma de cinco frases do modelo, e foi publicada a regra literal. Na resposta direta classificou como contradição uma de seis frases, que era verdadeira, e foi publicado o resumo fixo. O NLI admite 512 tokens.
- **Comparações conceituais.** LlamaIndex, AutoGen, Semantic Kernel, Langflow, Mem0 e Letta não foram executados.
- **Sem credenciais** o chat interpreta só com regras, que são frágeis diante de formas de falar não previstas.
- **A comparação não divide um pedido entre fornecedores** nem calcula o frete conforme o destino.
- **O que não foi refeito depois das últimas mudanças.** As demonstrações da fase 1 (R03 a R06) e as de R07, R08, R09, R11 e R17 são de 2026-11-11, anteriores à ampliação do catálogo e à guarda de entrada. As categorias novas do catálogo usam os mesmos 12 fornecedores, e os nomes das peças saem de uma lista fixa de famílias.
- **A guarda de entrada depende em parte de vocabulário.** As regras reconhecem formas conhecidas de pedir para mudar as instruções; uma forma nova depende do classificador com o modelo, que foi medido em sete mensagens.
- **Modelo local.** Com um modelo pequeno em CPU (llama3.2), cada turno com ferramenta levou minutos e o texto do agente não passou no formato exigido; o que se publicou foi o cálculo do sistema. É uma execução, com cinco mensagens.

## 12. Melhorias futuras

- Acrescentar um tipo de resposta conversacional, para comentários e «o que você lembra de mim?».
- Migrar a orquestração do turno para o LangGraph e manter os componentes do LangChain.
- Calibrar com dados os limiares do aviso de preço e da ancoragem de citações.
- Revisar a referência de trajetória: hoje ela exige a consulta ao catálogo antes da comparação, um passo que o agente pula sem mudar o resultado.
- Usar o CEP para estimar frete e prazo conforme o destino.
- Resumir o histórico que sai da janela de 12 mensagens.

## 13. Como reproduzir as evidências

- Instalar: uv sync --python 3.13 --all-extras --locked
- Testes: uv run pytest -q
- Catálogo sintético: uv run python scripts/gerar_catalogo_pecas.py
- Índice de políticas: uv run python scripts/construir_indice_politicas.py
- Notebooks: uv run python scripts/criar_notebooks.py e uv run python scripts/executar_notebooks.py. Rodam sem credenciais; com a chave no arquivo .env, uma célula do primeiro usa o modelo real
- Execuções com o modelo real (exigem OPENAI_API_KEY): os scripts scripts/demonstrar_*.py, que escrevem em docs/rastros/
- Avaliação (exige também LANGSMITH_API_KEY): uv run python evals/avaliar_fluxo.py --saida docs/rastros/r29_langsmith_gpt-4.1-mini_portugues_guardrails.json --rotulo guardrails
- Interface: uv run streamlit run app.py
- Guarda de entrada: uv run python scripts/demonstrar_guardrails.py. Modelo local (exige o Ollama com o modelo llama3.2 baixado): uv run python scripts/demonstrar_modelo_local.py
- Este relatório em PDF: uv run python scripts/gerar_relatorio_pdf.py, que grava docs/relatorio.pdf e a cópia com o nome de entrega, docs/efrain_colmenares_ai-agents_langchain-agents.pdf

Os cinco notebooks foram reexecutados em 2026-11-13. Eles usam duplos de teste e dizem isso em cada célula. A exceção é uma célula do primeiro, marcada como execução real remota: ela roda a cadeia de ponta a ponta com o gpt-4.1-mini (prompt, modelo e parser de JSON, nos dois estilos de composição, com invoke, batch e stream), e a saída está salva no notebook.

Em 2026-11-13, com a guarda de entrada ativa, foram refeitas a avaliação no LangSmith e as demonstrações da conversa de oito turnos (fase 3), do text-to-SQL (fase 4), da resposta direta, do aviso de preço e de R02, R10, R15, R22, R23 no chat e R28; são novas as da guarda de entrada e do modelo local.

Os rastros de docs/rastros/ com sufixo «antes» ou «sin_plan» e os oito experimentos do LangSmith anteriores aos dois em português são execuções da versão anterior do projeto, em espanhol. Não foram refeitos e ficam guardados como registro.

## 14. Conferência com o enunciado e pendências de entrega

Em 2026-11-13 as rubricas foram conferidas com o enunciado original da atividade (a página «Projeto da Disciplina» do Moodle). As 29 perguntas da rubrica coincidem, uma a uma e na mesma ordem, com R01–R29. Duas dúvidas anteriores ficaram resolvidas: o enunciado não entrega um índice FAISS (pede usar um já construído, sem refazer a indexação) nem casos de avaliação (pede comparar o que o agente fez com o esperado em cada caso de teste).

O que falta:

- Gravar o vídeo de demonstração, enviá-lo ao Google Drive de aluno e compartilhar o link.
- Dar ao professor acesso ao experimento do LangSmith, que está na conta do autor.
- R01: trocar a escala de maturidade genérica pela da aula 1, se ela definir outra.

## 15. Uso de ferramentas de IA

O enunciado incentiva o uso de ferramentas de IA e exige que elas sejam citadas. Esta seção diz o que foi usado e para quê.

| Ferramenta | Para que foi usada |
|---|---|
| Claude Code, da Anthropic (modelo Claude Fable 5.2) | Apoio para escrever e revisar o código, os testes, os scripts de demonstração, a documentação e este relatório |
| ElevenLabs (voz sintética) | Narração do vídeo de estudo docs/tour/tour_rubricas.mp4. Esse vídeo não é o vídeo de entrega |

- **Como reconhecer no repositório.** Os commits feitos com esse apoio levam a linha Co-Authored-By: Claude no histórico do git; são a maioria dos commits. Para listá-los: git log --grep="Co-Authored-By".
- **O que não é apoio de redação.** O gpt-4.1-mini (OpenAI), o modelo de NLI mDeBERTa e o modelo de embeddings MiniLM são componentes do próprio agente. Eles estão descritos nas seções 4 a 9.
- **De onde vêm os números.** Os resultados citados neste relatório vêm de execuções salvas em docs/rastros/ e dos experimentos no LangSmith. Nenhuma métrica foi simulada. O comportamento do código é coberto pelos testes automáticos.
- **Responsabilidade.** A responsabilidade pelo conteúdo entregue é do autor.

## 16. Evidência de execução

Três capturas do chat, tiradas em 2026-11-13 em um navegador, com o agente real (gpt-4.1-mini). Os registros completos de cada execução, com as ferramentas chamadas, as verificações e as respostas, estão em docs/rastros/. Os resultados do LangSmith estão na seção 9 (R29).

![Figura 1. Comparação de fornecedores, com os passos do agente abertos: 5 unidades de PEC-01-0001 com prazo de 7 dias. O aviso amarelo é a porta de segurança do índice de políticas salvo: sem a confiança explícita no arquivo .env, o chat usa o índice de demonstração em memória, com o mesmo conteúdo.](capturas/chat_comparacao.png)

![Figura 2. Pergunta sobre uma política, na mesma conversa: a frase do modelo, já verificada, a regra citada com a fonte e a linha da recuperação corrigida.](capturas/chat_politica.png)

![Figura 3. Guarda de entrada: uma pergunta fora do tema e uma tentativa de mudar as instruções, as duas recusadas sem chamar o agente.](capturas/chat_guarda.png)
