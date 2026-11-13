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

Abra o arquivo `.env` e preencha as duas chaves:

| Chave | Para que serve | Onde criar |
|---|---|---|
| `OPENAI_API_KEY` | Liga o agente. Sem ela o chat abre só em modo local | https://platform.openai.com/api-keys |
| `LANGSMITH_API_KEY` | Permite repetir a avaliação do agente no LangSmith | https://smith.langchain.com (Settings, API Keys) |

**Importante:** o projeto não traz nenhuma chave. Quem for rodar (por exemplo, o professor) precisa usar as suas próprias chaves da OpenAI e do LangSmith. O uso da API da OpenAI é cobrado na conta de quem é dono da chave. As outras linhas do `.env` são opcionais.

**4. Abra o chat**

```bash
./project.sh start
```

Acesse http://localhost:8501. O selo no topo deve dizer «Agente ativo».

## Primeiro teste

No chat, clique na sugestão «Compare 5 unidades de PEC-01-0001 com prazo de 7 dias». A resposta esperada é CentroPeças, R$ 7.279,83, entrega em 2 dias.

A primeira resposta demora mais: o Pedro baixa dois modelos locais (verificação e busca). Depois fica rápido.

## Sem chave da OpenAI

O chat abre mesmo sem chave, com o selo «Modo local, sem modelo». Funcionam a listagem de peças e a comparação de fornecedores. Políticas, CEP e perguntas abertas precisam da chave.

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
| `LANGSMITH_API_KEY` | Repetir a avaliação com `evals/avaliar_fluxo.py` | Sim, para a avaliação |
| `PEDRO_TRUST_POLICY_INDEX` | `true` usa o índice de políticas salvo em `knowledge/politicas/`; `false` usa o índice de demonstração em memória, com o mesmo conteúdo | Não |

Nunca envie o arquivo `.env` para o repositório.

## Se algo der errado

- **O selo diz «Modo local, sem modelo»:** falta a `OPENAI_API_KEY` no `.env`. Preencha e rode `./project.sh restart`.
- **Mudei o código e o chat mostra um erro de importação:** rode `./project.sh restart`. O Streamlit não recarrega sozinho os módulos de `src/pedro/`.
- **A porta 8501 está ocupada:** use `PEDRO_PORT=8765 ./project.sh start`.
- **O chat não abre:** veja o log em `storage/run/streamlit.log`.
- **Quero começar do zero:** apague a pasta `storage/`. Ela guarda só dados de execução (conversas e cópias do catálogo) e não é versionada.

## Como funciona

A interface é um chat. Você informa a peça e a quantidade; orçamento e prazo são opcionais. Se falta a quantidade, o Pedro pergunta uma vez e guarda a resposta.

Para cada peça há três ofertas de fornecedores. O Pedro descarta as que não servem (sem estoque, abaixo do pedido mínimo, fora do prazo ou acima do orçamento) e recomenda a mais barata entre as que sobram. A resposta mostra todas as ofertas e o motivo de cada descarte.

Na barra lateral você abre um chat novo, reabre uma conversa ou a apaga.

## O que o Pedro faz

- **Compara fornecedores.** O cálculo é feito em código, com valores em centavos. O modelo decide o que responder, mas os números quem coloca é o sistema.
- **Lembra do pedido.** Se você diz «Agora que sejam 6», ele mantém a peça e o prazo e refaz a conta.
- **Guarda preferências.** Se você diz que prefere fornecedores nacionais, ele leva isso em conta nas próximas comparações.
- **Responde perguntas sobre a comparação.** Por exemplo: «a mais barata?» ou «qual chega antes?».
- **Consulta o catálogo.** Para perguntas abertas, o modelo escreve uma consulta SQL de leitura, que só roda se passar por uma validação.
- **Consulta as políticas da loja** (entrega, garantia e devolução) por busca semântica e cita a fonte.
- **Consulta um CEP** na API pública do ViaCEP.
- **Avisa sobre o preço** quando o valor de hoje se afasta da média dos últimos meses.
- **Confere antes de publicar.** Cada resposta passa por uma verificação exata e por um segundo modelo, que confere se o texto bate com os dados. Se não passa, o Pedro não publica.
- **Recusa o que não é do tema.** Pedidos alheios a compras de peças e tentativas de mudar as instruções são recusados antes de chegar ao agente.

## Estrutura do projeto

| Pasta ou arquivo | O que tem |
|---|---|
| `app.py` | A interface do chat (Streamlit) |
| `src/pedro/` | A lógica do assistente |
| `tests/` | Testes automáticos |
| `notebooks/` | Cinco notebooks já executados, que mostram o projeto passo a passo |
| `scripts/` | Geração dos dados e demonstrações com o modelo real |
| `evals/` | Casos de avaliação e o avaliador do LangSmith |
| `datasets/` | Catálogo de peças (SQLite) |
| `knowledge/` | Textos das políticas da loja e o índice de busca |
| `docs/` | Relatório, execuções salvas e capturas da interface |

Os módulos principais de `src/pedro/`:

| Módulo | O que faz |
|---|---|
| `business.py` | A comparação de fornecedores |
| `agent.py` | O agente, as suas ferramentas e o fluxo de cada mensagem |
| `guardrails.py` | A checagem da mensagem antes de chamar o agente |
| `dialogue.py` | A leitura do pedido: peça, quantidade, orçamento e prazo |
| `memory.py` | Conversas, preferências e lembranças, em SQLite |
| `query.py` | As consultas ao catálogo |
| `rag.py` | A busca nas políticas da loja |
| `verification.py` e `nli.py` | A conferência de cada resposta antes de publicar |
| `precos.py` | O aviso de preço |
| `modelos.py` | A escolha do modelo pelo arquivo `.env` |

## Dados

O catálogo tem 18 categorias de eletrodomésticos, 4.320 peças e 12.960 ofertas de 12 fornecedores. Tudo é gerado por um script, com uma semente fixa.

No primeiro acesso, o app cria uma cópia do catálogo na pasta `storage/`. Cada conversa usa a sua cópia.

Para gerar de novo os dados e os notebooks:

```bash
uv run python scripts/gerar_catalogo_pecas.py
uv run python scripts/criar_notebooks.py
uv run python scripts/executar_notebooks.py
```

## Políticas da loja

Os textos das políticas estão em `knowledge/politicas_demo/`. O Pedro monta o índice de busca sozinho, em memória, na primeira vez que precisa. Não é preciso rodar nada.

O repositório também traz esse índice já salvo, em `knowledge/politicas/`. Para usá-lo, defina `PEDRO_TRUST_POLICY_INDEX=true` no `.env`. Faça isso só com um índice de origem conhecida: o arquivo salvo usa o formato pickle, e por isso o Pedro confere a origem e as impressões digitais antes de abrir.

Para testar no chat, pergunte «Posso receber em várias caixas?». A resposta cita a regra de entrega parcial e a sua fonte.

## Avaliação

O agente foi avaliado no LangSmith com 30 casos. Na última execução, o fornecedor recomendado ficou certo em 14 de 14 casos e o valor em 14 de 14. O experimento é público:

https://smith.langchain.com/public/c2c2892d-f604-4764-b987-f53c2fd321e5/d

Para repetir a avaliação (precisa de `OPENAI_API_KEY` e `LANGSMITH_API_KEY`):

```bash
uv run python evals/avaliar_fluxo.py
```

As execuções salvas com o modelo real estão em `docs/rastros/` e as capturas da interface em `docs/capturas/`.

## Relatório e vídeo

- **Relatório:** docs/efrain_colmenares_ai-agents_langchain-agents.pdf
- **Vídeo de demonstração:** https://www.youtube.com/watch?v=SpeCHaVVK58
- **Vídeo no Google Drive da Infnet**, caso o YouTube não abra: https://drive.google.com/file/d/1nt-cUSmVtYK_p4XGprDvhlTowE2eXwaw/view
