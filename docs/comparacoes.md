# Comparações didáticas

A comparação completa dos seis orquestradores vistos em aula (LangChain, LangGraph, LlamaIndex, AutoGen, Semantic Kernel e Langflow) e a justificativa de LangChain estão em [respostas_rubricas.md](respostas_rubricas.md) §R07. Lá está também a comparação executada entre LangChain e LangGraph ([rastros/r07_orquestradores_llm.json](rastros/r07_orquestradores_llm.json)): mesmo modelo, mesmas duas ferramentas e mesmo prompt; 25 linhas e 4,8 s para três turnos com LangChain clássico, 19 linhas e 3,9 s com LangGraph. Foi uma execução por orquestrador: os tempos não são um benchmark. A tabela a seguir conserva o contraste inicial com AutoGen.

## Agentes e composição

| Aspecto | LangChain clássico / LCEL neste projeto | AutoGen |
|---|---|---|
| Unidade demonstrada | Um agente com ferramentas tipadas e uma cadeia de publicação | Conversas coordenadas entre agentes |
| Rastro visível | Nome, argumentos e resultado das ferramentas; parser e verificador | Mensagens e ações entre participantes |
| Uso no Pedro | O integrador precisa de um só agente e de uma porta determinística | Estudado como alternativa; não foi executado aqui |
| Limite de evidência | ReAct clássico testado com FakeListLLM (notebook 02) e executado com o modelo real ([rastros/r08_react_llm.json](rastros/r08_react_llm.json)); uma execução | Sem experimento executado |

A comparação medida entre composição declarativa (LCEL) e imperativa (@chain), com a decisão do projeto, está em [respostas_rubricas.md](respostas_rubricas.md) §R06. A composição sequencial encadeia parser, modelo e validação; RunnableParallel consulta ramos independentes. RouterCompras envia consultas reais para catálogo ou comparação. Esses exemplos estão nos notebooks 01 e 02. Não se solicita nem se guarda raciocínio privado; os planos do prompt descrevem chamadas observáveis.

## Memória

| Camada | Pedro | Mem0 / Letta como referência |
|---|---|---|
| Trabalho | Últimas 12 mensagens da sessão | Gestão de contexto própria de cada sistema |
| Episódica | SQLite com vetores FastEmbed, modelo e versão; recuperação entre sessões do mesmo usuário | Abstrações de memória de terceiros |
| Preferências | Só mudanças explícitas, isoladas por user_id | A política concreta de cada um exigiria integração e avaliação |
| Procedimental | Prompt, ferramentas e regras de verificação | Configuração de agente própria |

A comparação com Mem0 e Letta é arquitetônica. Neste workspace foram executadas a memória do Pedro com FastEmbed e a do LangMem, com a mesma conversa de três mensagens ([rastros/r15_memoria_llm.json](rastros/r15_memoria_llm.json), uma execução). No Pedro, o código decide o que salvar: ficaram a preferência `fornecedor = nacionais` e 1 episódio. No LangMem, o modelo decide: ficou 1 lembrança («Prefere fornecedores nacionais para peças de reposição.»). Nos dois sistemas, outro usuário não recebeu nada. O detalhe está em [respostas_rubricas.md](respostas_rubricas.md) §R15. Os preços e o estoque dos episódios são tratados como históricos; o pedido atual e o cenário ativo governam a decisão.
