# Pedro Infnet reconstruído

Projeto independente em Python 3.13 para consultar peças fictícias, comparar ofertas e testar um agente com publicação verificada. O catálogo, os fornecedores, as compatibilidades, o estoque e os preços são sintéticos. O catálogo tem 18 categorias de eletrodomésticos, 4.320 peças e 12.960 ofertas de 12 fornecedores; as sete categorias PEC-12 a PEC-18 foram acrescentadas em 2026-11-11 sem mudar as peças PEC-01 a PEC-11. O gerador e a base sintética vieram do repositório de referência; o pacote da aplicação foi construído neste workspace. Código, interface e documentos estão em português do Brasil; os nomes seguem o [glossário da migração](docs/glossario_migracao.md).

## Reproduzir

```bash
uv sync --python 3.13 --all-extras --locked
uv run pytest -q
uv run python scripts/gerar_catalogo_pecas.py
uv run python scripts/criar_notebooks.py
uv run python scripts/executar_notebooks.py
uv run streamlit run app.py
```

Para administrar o app em segundo plano:

```bash
./project.sh start
./project.sh status
./project.sh restart
./project.sh stop
```

A porta padrão é 8501; use `PEDRO_PORT=8765 ./project.sh start` para iniciar em outra porta, ou `PEDRO_PORT=8765 ./project.sh restart` se ele já estiver ativo. O PID e o log ficam em `storage/run/`.

O app inicia em http://localhost:8501. A interface é só o chat. Copie .env.example para .env para usar o agente OpenAI e o LangSmith. Sem chave funcionam, no chat, a listagem de peças, a comparação de fornecedores e o comando `/t24`. Com a OpenAI, o chat também consulta as políticas fictícias de demonstração por meio do agente; a resposta é rotulada como fictícia e passa por verificação de fonte e NLI local. No chat basta informar a peça e a quantidade; orçamento e prazo são filtros opcionais. Se falta a quantidade, o Pedro pergunta uma vez e guarda a resposta na sessão. Você pode dizer «agora 3 unidades» para recalcular com os limites informados antes, ou «sem orçamento e sem prazo» para tirá-los. As recomendações do agente passam por verificação exata e NLI local antes de aparecer.

O primeiro acesso cria um cenário com dataset_id UUID, uma cópia de datasets/pecas_eletrodomesticos.sqlite3 e um manifesto com impressão digital SHA-256, data, semente e contagens. «Novo chat» mantém o cenário. Reabrir uma conversa restaura o dataset dela ou avisa se ele falta. Os arquivos de execução vão para storage/ e não são versionados.

## Componentes

- src/pedro/catalog.py: cenário e consultas SQLite de somente leitura.
- src/pedro/contracts.py e business.py: contratos e comparação de fornecedores em centavos. Uma oferta é descartada por estoque, pedido mínimo do fornecedor, prazo ou orçamento; as válidas são ordenadas pela preferência de origem salva do usuário (nacional ou internacional), total, prazo e fornecedor. Cada resposta mostra todas as ofertas com a origem e o motivo do descarte. Para as ofertas válidas entra o histórico de preços (mês anterior e média de cinco meses), que informa e não muda a ordem. Se o preço de hoje se afasta da média, entra um aviso de preço: um texto fixo ou, com o agente, um conselho redigido pelo modelo e verificado com NLI (src/pedro/precos.py). As respostas às 29 rubricas estão em docs/respostas_rubricas.md.
- src/pedro/resposta_direta.py: resposta direta a uma pergunta sobre a comparação em andamento («a mais barata?»). O sistema refaz a comparação, o modelo redige uma ou duas frases e elas só são publicadas se passam na verificação de números, fornecedor e NLI; se não, entra um resumo fixo calculado pelo sistema. Não muda a recomendação. A regra que reconhece a pergunta (src/pedro/dialogue.py) exige que ela fale de preço, prazo, estoque ou origem, ou nomeie um fornecedor comparado; perguntas sobre o catálogo inteiro vão para o agente. Evidência: `uv run python scripts/demonstrar_pergunta.py` (docs/rastros/pergunta_direta_llm.json).
- src/pedro/query.py: plano Pydantic para SELECT parametrizado com rastro; text-to-SQL validado para perguntas abertas.
- src/pedro/memory.py: mensagens completas, janela de 12, rascunhos de compra por sessão, preferências e episódios FastEmbed por usuário.
- src/pedro/dialogue.py: extração de restrições por turno e perguntas só para dados bloqueantes.
- src/pedro/prompts.py: PTCF e exemplos com ações observáveis.
- src/pedro/agent.py: seis ferramentas, um create_openai_tools_agent, uma correção interna e RunnableWithMessageHistory que salva só a resposta pública.
- src/pedro/verification.py e nli.py: verificação exata e porta NLI triclasse.
- src/pedro/rag.py: recuperação FAISS com filtro de metadados e inspeção do manifesto antes de permitir a desserialização.
- src/pedro/policy_demo.py e knowledge/politicas_demo/: corpus fictício extenso e índice FAISS local construído em memória para o T15.
- scripts/diagnosticar_t24.py: comparação reproduzível de uma falha de recuperação e da sua reformulação.
- notebooks/01–05: práticas executáveis. Os duplos de teste são identificados explicitamente. As comparações didáticas estão em docs/comparacoes.md.

O notebook 04 demonstra o T15 sem credenciais: divide três políticas fictícias em fragmentos, cria embeddings FastEmbed, indexa com FAISS e compara buscas com e sem filtro por tema. As políticas incluem exemplos tirados da SQLite sintética (SKU, compatibilidade, garantia por peça e ofertas), datados pela semente `20261107`; pedidos e entregas continuam hipotéticos. O chat usa esse índice de demonstração quando não tem um autorizado. O índice salvo de R22/T24 fica em knowledge/politicas/ (index.faiss, index.pkl e manifest.json com origem, embedding_model, dimension, metrica, documentos e sha256 por arquivo); é um índice próprio, feito do corpus fictício com `uv run python scripts/construir_indice_politicas.py`. Revise a procedência dele antes de definir PEDRO_TRUST_POLICY_INDEX=true. O docstore pickle exige confiança explícita; o índice fictício em memória não usa essa variável.

O T24 tem uma falha e uma correção observadas nesse corpus fictício. **Para testar o fluxo normal no Chat**, pergunte «Posso receber em várias caixas?»; você pode repetir a pergunta na mesma conversa. A rota de entrega do fluxo chama `consultar_politicas`, reformula a pergunta como «envio parcial», verifica o fragmento e publica uma regra citada só se o NLI a sustenta. A resposta mostra `FIC-ENT-01-S05-C01` e o contraste do top-4. A rota funciona com o índice fictício carregado no app (o salvo, se PEDRO_TRUST_POLICY_INDEX=true, ou o de demonstração em memória) e não depende de o LLM decidir usar uma ferramenta a cada repetição; a interface carrega o índice quando há `OPENAI_API_KEY`. `/t24` mostra o diagnóstico controlado sem OpenAI. Para repetir o teste no console e salvar o JSON: `uv run python scripts/diagnosticar_t24.py --saida storage/evidencias/t24_demo.json`. O [diagnóstico](docs/t24_recuperacao.md) documenta os resultados. Para rodar sobre um índice salvo, use `--indice knowledge/politicas --confiar-indice --original '...' --reescrita '...' --fonte-esperada '...'` depois de revisar a procedência. O carregador e o app aceitam o modelo FastEmbed local conhecido ou um modelo OpenAI declarado no manifesto; para outro modelo, escolha o embedder compatível no script. R22 e R23 foram demonstradas sobre o índice próprio salvo; a atividade não entregou um índice oficial.

## Avaliação e entregáveis

A matriz de evidências, conferida com as 29 rubricas do guia integrado em guide/ (rótulos R01–R29), está em docs/matriz.md e o seu mapa visual em [Mermaid](docs/rubricas_projeto.mmd) e [SVG](docs/rubricas_projeto.svg). O registro de verificações está em docs/evidencias.md e o relatório editável e em PDF em docs/relatorio.md e docs/relatorio.pdf. Há 30 casos derivados e congelados em evals/casos_derivados.json; não equivalem aos casos oficiais. Para avaliar o mesmo fluxo final com o LangSmith: uv run python evals/avaliar_fluxo.py. O script exige OPENAI_API_KEY e LANGSMITH_API_KEY; não publica métricas simuladas.

O guia integrado de fases, temas e rubricas está em guide/Fases_Temas_Tareas_Rubricas_ComprasLab_Leyendas.pdf; o enunciado original em português ainda não está no workspace para a conferência de fechamento. O chat com o agente e a avaliação no LangSmith já foram executados com o modelo real e estão registrados em docs/evidencias.md, com os rastros em docs/rastros/. Falta confirmar com o professor se a atividade entrega um índice FAISS e casos oficiais. A gravação com webcam, o envio ao Drive institucional e a verificação do link exigem o acesso do aluno.
