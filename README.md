# Pedro — assistente de compras

O Pedro é um assistente de compras de peças de eletrodomésticos. Ele compara fornecedores e recomenda o melhor. É um projeto do curso da Infnet e **todos os dados são fictícios**.

## Instalação em 4 passos

**Você precisa de:** Git e o [uv](https://docs.astral.sh/uv/). O uv instala o Python 3.13 sozinho.

Se ainda não tem o uv:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**1. Baixe o projeto**

```bash
git clone https://github.com/efraxpc/pedro_asistente_de_compras.git
cd pedro_asistente_de_compras
```

**2. Instale as dependências**

```bash
uv sync --python 3.13 --all-extras --locked
```

**3. Configure a chave**

```bash
cp .env.example .env
```

Abra o arquivo `.env` e preencha `OPENAI_API_KEY=` com a sua chave da OpenAI. As outras linhas são opcionais.

**4. Abra o chat**

```bash
./project.sh start
```

Acesse http://localhost:8501. O selo no topo deve dizer «Agente ativo».

## Primeiro teste

No chat, clique na sugestão «Compare 5 unidades de PEC-01-0001 com prazo de 7 dias». A resposta esperada é CentroPeças, R$ 7.279,83, entrega em 2 dias.

A primeira resposta demora mais: o Pedro baixa dois modelos locais (verificação e busca). Depois fica rápido.

## Sem chave da OpenAI

O chat abre mesmo sem chave, com o selo «Modo local, sem modelo». Funcionam a listagem de peças, a comparação de fornecedores e o comando `/t24`. Políticas, CEP e perguntas abertas precisam da chave.

## Comandos do dia a dia

| Para | Comando |
|---|---|
| Abrir o chat | `./project.sh start` |
| Ver se está ativo | `./project.sh status` |
| Reiniciar (depois de mudar o código ou o `.env`) | `./project.sh restart` |
| Parar | `./project.sh stop` |
| Usar outra porta | `PEDRO_PORT=8765 ./project.sh start` |
| Rodar os testes | `uv run pytest -q` |
| Executar os 5 notebooks | `uv run python scripts/executar_notebooks.py` |

## Variáveis do arquivo .env

| Variável | Para que serve | Obrigatória |
|---|---|---|
| `OPENAI_API_KEY` | Liga o agente, as políticas e o CEP | Sim, para o agente |
| `PEDRO_MODEL` | Modelo de conversa (padrão: `gpt-4.1-mini`) | Não |
| `PEDRO_BASE_URL` | Usa um servidor compatível com a API da OpenAI no lugar da OpenAI; por exemplo, um modelo local no Ollama: `PEDRO_BASE_URL=http://localhost:11434/v1` e `PEDRO_MODEL=llama3.2`. Em CPU cada resposta pode levar minutos | Não |
| `LANGSMITH_API_KEY` | Só para a avaliação com `evals/avaliar_fluxo.py` | Não |
| `PEDRO_TRUST_POLICY_INDEX` | `true` usa o índice de políticas salvo em `knowledge/politicas/`; `false` usa o índice de demonstração em memória, com o mesmo conteúdo | Não |
| `ELEVENLABS_API_KEY` | Só para narrar o vídeo do tour (`scripts/gerar_video_tour.py`) | Não |

Nunca envie o arquivo `.env` para o repositório.

## Se algo der errado

- **O selo diz «Modo local, sem modelo»:** falta a `OPENAI_API_KEY` no `.env`. Preencha e rode `./project.sh restart`.
- **Mudei o código e o chat mostra um erro de importação:** rode `./project.sh restart`. O Streamlit não recarrega sozinho os módulos de `src/pedro/`.
- **A porta 8501 está ocupada:** use `PEDRO_PORT=8765 ./project.sh start`.
- **O chat não abre:** veja o log em `storage/run/streamlit.log`.
- **Quero começar do zero:** apague a pasta `storage/`. Ela guarda só dados de execução (conversas e cópias do catálogo) e não é versionada.

## Como funciona, em resumo

A interface é só o chat. Na barra lateral você abre um chat novo, reabre uma conversa ou a apaga (a lixeira ao lado de cada conversa, ou «Apagar todas»; as duas pedem confirmação). Basta informar a peça e a quantidade; orçamento e prazo são filtros opcionais. Se falta a quantidade, o Pedro pergunta uma vez e guarda a resposta na sessão.

O catálogo tem 18 categorias de eletrodomésticos, 4.320 peças e 12.960 ofertas de 12 fornecedores. O primeiro acesso cria um cenário: uma cópia do catálogo com um identificador próprio, na pasta `storage/`. «Novo chat» mantém o cenário, e reabrir uma conversa restaura o cenário dela.

Para regenerar os dados e os notebooks:

```bash
uv run python scripts/gerar_catalogo_pecas.py
uv run python scripts/criar_notebooks.py
uv run python scripts/executar_notebooks.py
```

Para entender o projeto, comece por docs/guia_estudo.md (ou docs/guia_estudio_es.md, em espanhol).

## Componentes

- src/pedro/catalog.py: cenário e consultas SQLite de somente leitura.
- src/pedro/contracts.py e business.py: contratos e comparação de fornecedores em centavos. Uma oferta é descartada por estoque, pedido mínimo do fornecedor, prazo ou orçamento; as válidas são ordenadas pela preferência de origem salva do usuário (nacional ou internacional), total, prazo e fornecedor. Cada resposta mostra todas as ofertas com a origem e o motivo do descarte. Para as ofertas válidas entra o histórico de preços (mês anterior e média de cinco meses), que informa e não muda a ordem. Se o preço de hoje se afasta da média, entra um aviso de preço: um texto fixo ou, com o agente, um conselho redigido pelo modelo e verificado com NLI (src/pedro/precos.py). As respostas às 29 rubricas estão em docs/respostas_rubricas.md.
- src/pedro/resposta_direta.py: resposta direta a uma pergunta sobre a comparação em andamento («a mais barata?»). O sistema refaz a comparação, o modelo redige uma ou duas frases e elas só são publicadas se passam na verificação de números, fornecedor e NLI; se não, entra um resumo fixo calculado pelo sistema. Não muda a recomendação. A regra que reconhece a pergunta (src/pedro/dialogue.py) exige que ela fale de preço, prazo, estoque ou origem, ou nomeie um fornecedor comparado; perguntas sobre o catálogo inteiro vão para o agente. Evidência: `uv run python scripts/demonstrar_pergunta.py` (docs/rastros/pergunta_direta_llm.json). O mesmo arquivo tem a resposta a uma pergunta sobre a regra de entrega parcial: o modelo redige uma ou duas frases só com o fragmento recuperado, e elas só são publicadas se não trazem números fora da fonte e se o NLI as sustenta; se não, fica só a regra literal, que é citada sempre. Evidência: `uv run python scripts/demonstrar_r23.py` (docs/rastros/r23_resposta_llm.json).
- src/pedro/query.py: plano Pydantic para SELECT parametrizado com rastro; text-to-SQL validado para perguntas abertas.
- src/pedro/memory.py: mensagens completas, janela de 12, rascunhos de compra por sessão, preferências e episódios FastEmbed por usuário.
- src/pedro/dialogue.py: extração de restrições por turno e perguntas só para dados bloqueantes.
- src/pedro/prompts.py: PTCF e exemplos com ações observáveis.
- src/pedro/agent.py: seis ferramentas, um create_openai_tools_agent, uma correção interna e RunnableWithMessageHistory que salva só a resposta pública.
- src/pedro/guardrails.py: guarda de entrada. Antes de chamar o agente, regras fixas e um classificador com o modelo recusam assuntos alheios e tentativas de mudar as instruções.
- src/pedro/modelos.py: escolha do modelo de conversa pelo arquivo .env (OpenAI ou um servidor compatível, como o Ollama).
- src/pedro/verification.py e nli.py: verificação exata e porta NLI triclasse.
- src/pedro/rag.py: recuperação FAISS com filtro de metadados e inspeção do manifesto antes de permitir a desserialização.
- src/pedro/policy_demo.py e knowledge/politicas_demo/: corpus fictício extenso e índice FAISS local construído em memória para o T15.
- scripts/diagnosticar_t24.py: comparação reproduzível de uma falha de recuperação e da sua reformulação.
- notebooks/01–05: práticas executáveis. Os duplos de teste são identificados explicitamente; o primeiro tem também uma célula que roda a cadeia com o modelo real, se houver chave. As comparações didáticas estão em docs/comparacoes.md.

O notebook 04 demonstra o T15 sem credenciais: divide três políticas fictícias em fragmentos, cria embeddings FastEmbed, indexa com FAISS e compara buscas com e sem filtro por tema. As políticas incluem exemplos tirados da SQLite sintética (SKU, compatibilidade, garantia por peça e ofertas), datados pela semente `20261107`; pedidos e entregas continuam hipotéticos. O chat usa esse índice de demonstração quando não tem um autorizado. O índice salvo de R22/T24 fica em knowledge/politicas/ (index.faiss, index.pkl e manifest.json com origem, embedding_model, dimension, metrica, documentos e sha256 por arquivo); é um índice próprio, feito do corpus fictício com `uv run python scripts/construir_indice_politicas.py`. Revise a procedência dele antes de definir PEDRO_TRUST_POLICY_INDEX=true. O docstore pickle exige confiança explícita; o índice fictício em memória não usa essa variável.

O T24 tem uma falha e uma correção observadas nesse corpus fictício. **Para testar o fluxo normal no Chat**, pergunte «Posso receber em várias caixas?»; você pode repetir a pergunta na mesma conversa. A rota de entrega do fluxo chama `consultar_politicas`, reformula a pergunta como «envio parcial», verifica o fragmento e publica uma regra citada só se o NLI a sustenta. Com o modelo, a resposta começa por uma frase verificada que responde à pergunta feita: «Quais produtos posso receber em várias caixas?» recebe outra primeira linha, com a mesma regra citada. A resposta mostra `FIC-ENT-01-S05-C01` e o contraste do top-4; se a pergunta original já recupera a regra, diz a posição observada, sem afirmar uma correção. A rota funciona com o índice fictício carregado no app (o salvo, se PEDRO_TRUST_POLICY_INDEX=true, ou o de demonstração em memória) e não depende de o LLM decidir usar uma ferramenta a cada repetição; a interface carrega o índice quando há `OPENAI_API_KEY`. `/t24` mostra o diagnóstico controlado sem OpenAI. Para repetir o teste no console e salvar o JSON: `uv run python scripts/diagnosticar_t24.py --saida storage/evidencias/t24_demo.json`. O [diagnóstico](docs/t24_recuperacao.md) documenta os resultados. Para rodar sobre um índice salvo, use `--indice knowledge/politicas --confiar-indice --original '...' --reescrita '...' --fonte-esperada '...'` depois de revisar a procedência. O carregador e o app aceitam o modelo FastEmbed local conhecido ou um modelo OpenAI declarado no manifesto; para outro modelo, escolha o embedder compatível no script. R22 e R23 foram demonstradas sobre o índice próprio salvo; a atividade não entregou um índice oficial.

## Avaliação e entregáveis

A matriz de evidências, conferida com as 29 rubricas do enunciado original (rótulos R01–R29), está em docs/matriz.md e o seu mapa visual em [Mermaid](docs/rubricas_projeto.mmd) e [SVG](docs/rubricas_projeto.svg). O registro de verificações está em docs/evidencias.md e o relatório editável e em PDF em docs/relatorio.md e docs/relatorio.pdf (com uma cópia no nome de entrega, docs/efrain_colmenares_ai-agents_langchain-agents.pdf). Há 30 casos derivados e congelados em evals/casos_derivados.json; o enunciado não entrega casos de teste. Para avaliar o mesmo fluxo final com o LangSmith: uv run python evals/avaliar_fluxo.py. O script exige OPENAI_API_KEY e LANGSMITH_API_KEY; não publica métricas simuladas.

O guia integrado de fases, temas e rubricas está em guide/Fases_Temas_Tareas_Rubricas_ComprasLab_Leyendas.pdf; em 2026-11-13 as rubricas foram conferidas com o enunciado original em português: as 29 perguntas coincidem com R01–R29, e o enunciado não entrega um índice FAISS nem casos de avaliação. O chat com o agente e a avaliação no LangSmith já foram executados com o modelo real e estão registrados em docs/evidencias.md, com os rastros em docs/rastros/. Faltam a gravação com webcam, o envio ao Google Drive de aluno e a verificação do link, que exigem o acesso do aluno, e dar ao professor acesso ao experimento do LangSmith.
