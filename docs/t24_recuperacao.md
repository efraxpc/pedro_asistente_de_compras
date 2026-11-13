# T24: diagnóstico de recuperação

## Corpus e método

O diagnóstico foi medido em dois índices do mesmo corpus fictício de `knowledge/politicas_demo/`: o **índice salvo em disco** em `knowledge/politicas/` (rastro [rastros/r23_t24_indice_existente.json](rastros/r23_t24_indice_existente.json)) e o **índice fictício em memória** (`scripts/diagnosticar_t24.py`). Os dois deram as mesmas posições e distâncias. A versão 1.1 do corpus, em português, contém 75 fragmentos com IDs, documento, tema e seção. Impressão digital SHA-256 do corpus: `e5c71773d122aeb24ef010ed35e562999892b26fa0a5c282f5574f9a879b1142` (o índice foi reconstruído em 2026-11-11, depois da correção de uma frase de `entrega.md`; posições, fragmentos e distâncias ficaram idênticos). Foram usados FastEmbed `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, FAISS com métrica **L2**, `k=4`, `fetch_k=20` e sem filtro nas duas consultas. Em L2, menor distância indica maior proximidade.

O fragmento esperado, `FIC-ENT-01-S05-C01`, existe no docstore: `entrega.md`, seção «5. Entrega parcial e estoque». O texto exige um acordo simulado explícito para descrever uma entrega parcial, com unidades, fornecedor e prazos de cada envio.

## Falha observada

Pergunta inicial: **«Posso receber em várias caixas?»**

| Posição | Fragmento | Fonte / seção | Distância L2 |
|---:|---|---|---:|
| 1 | `FIC-GAR-01-S01-C01` | `garantia.md` / propósito | 13,556 |
| 2 | `FIC-ENT-01-S04-C01` | `entrega.md` / recebimento | 13,598 |
| 3 | `FIC-DEV-01-S03-C01` | `devolucoes.md` / dano visível | 13,891 |
| 4 | `FIC-ENT-01-S05-C00` | `entrega.md` / só o título da seção 5 | 14,344 |

O fragmento que contém a regra de entrega parcial ficou fora do top-4: está na posição 8 (L2 = 14,734). A posição 4 é o fragmento `C00`, que traz só o título «5. Entrega parcial e estoque», sem a regra. **Diagnóstico inferido:** «receber» e «várias caixas» ficaram perto de recebimento, embalagem e dano, enquanto a regra se expressa como «entrega parcial»; os outros temas ocuparam duas posições.

**Como a pergunta foi escolhida.** A tradução literal da pergunta da versão em espanhol, «Pode mandar em várias caixas?», deixou de falhar no corpus em português: o fragmento esperado fica na posição 4 do top-4 (L2 = 15,354). Com o filtro `tema=entrega`, fica na posição 2. Por isso foram medidas oito formulações naturais e foi escolhida «Posso receber em várias caixas?», que falha de verdade.

**Nota histórica (versão anterior, em espanhol).** Com o corpus em espanhol (SHA-256 `b9dec4509b36aa722e03bff45c14876339e52831e12f8b311de6287ed5bce6c3`), a pergunta original, feita em espanhol (traduzida: «Pode mandar em várias caixas?»), deixava o fragmento esperado fora do top-4 (posição 1: `FIC-ENT-01-S04-C01`, L2 = 12,845). A reformulação em espanhol o colocava na posição 1 (L2 = 10,216). Essas medições não foram refeitas.

## Correção e contraste

Pergunta reformulada: **«Quando a política de entrega admite um envio parcial das peças solicitadas?»** A reformulação esclarece a intenção sem incluir a resposta. Foram mantidos índice, modelo, métrica, `k`, `fetch_k` e ausência de filtro.

| Posição | Fragmento | Fonte / seção | Distância L2 |
|---:|---|---|---:|
| 1 | `FIC-ENT-01-S05-C01` | `entrega.md` / entrega parcial | 8,566 |
| 2 | `FIC-ENT-01-S01-C01` | `entrega.md` / prazos | 10,385 |
| 3 | `FIC-ENT-01-S04-C01` | `entrega.md` / recebimento | 10,765 |
| 4 | `FIC-DEV-01-S05-C01` | `devolucoes.md` / inspeção e resolução | 11,550 |

A reformulação é feita pela regra `reescrever_consulta_entrega`, em [policy_demo.py](../src/pedro/policy_demo.py), que agora também reconhece o verbo «receber». Ela leva o fragmento esperado de fora do top-4 (posição 8) para a posição 1.

Como teste separado, aplicar `tema=entrega` à pergunta inicial coloca o fragmento esperado na posição 3 (L2 = 14,734); esse filtro **não** faz parte da comparação antes/depois. O [notebook 04](../notebooks/04_rag_text_to_query.ipynb) conserva a execução e `scripts/diagnosticar_t24.py --saida storage/evidencias/t24_demo.json` reproduz o relatório JSON do índice em memória. No chat do Streamlit, `/t24` mostra o mesmo contraste sem chamar um LLM.

Para testar o **fluxo normal**, faça a pergunta inicial no chat. A rota de entrega do fluxo chama `consultar_politicas` de forma determinística para perguntas coloquiais sobre dividir pacotes e reformula a intenção como entrega parcial, sem acrescentar a regra. A resposta extrai duas frases do fragmento recuperado, verifica a procedência e usa o NLI local antes de publicá-las. Com o modelo, a resposta começa por uma frase verificada que responde à pergunta feita (seção seguinte). O resumo de recuperação é gerado a partir dos resultados da ferramenta. Isso foi observado no fluxo com NLI real e índice salvo em disco ([rastros/r22_indice_existente.json](rastros/r22_indice_existente.json)), no Streamlit ([rastros/r28_streamlit.json](rastros/r28_streamlit.json)) e em cinco perguntas diferentes com o índice em memória ([rastros/r23_resposta_llm.json](rastros/r23_resposta_llm.json)). O teste `tests/test_policy_demo.py` repete a pergunta duas vezes na mesma sessão, com um rascunho de compra pendente, NLI de duplo de teste e um modelo de duplo que não redige nada, e obtém a mesma resposta (a regra literal). A rota cobre essa intenção do corpus sintético; outras formulações precisam de testes próprios.

## O que o chat publica para perguntas diferentes

**O problema.** «Posso receber em várias caixas?» e «quais produtos posso receber em varias caixas?» recebiam exatamente o mesmo texto: a rota copiava sempre as mesmas duas frases da política.

**Agora.** A recuperação com a reformulação e a regra citada continuam fixas e verificadas. O que muda de uma pergunta para outra é a primeira frase.

| Parte | Regra |
|---|---|
| Frase que responde à pergunta | O modelo a redige só com o fragmento recuperado (prompt `MODELO_RESPOSTA_POLITICA`, saída Pydantic, temperatura 0). Só é publicada se não traz números fora da fonte e se o NLI devolve *entailment* com o fragmento como premissa |
| «Regra citada: …» e a fonte | As duas frases literais do fragmento. São publicadas sempre. Se a frase do modelo não passa, ou se não há modelo, a resposta é só a regra literal, como antes |
| Aviso «A política não responde exatamente ao que você perguntou. O que ela diz sobre envios divididos:» | Só quando o modelo julga que a política não responde **e** a pergunta pede um detalhe (quais, qual, quanto, quantos, quantas, onde, quem). Em perguntas de sim ou não o julgamento do modelo variou entre execuções (3 de 6 para «Posso receber em várias caixas?», com temperatura 0; medição sem rastro salvo); em perguntas de detalhe foi estável (6 de 6) |

**Quando não há falha a corrigir.** Algumas formulações já recuperam a regra sem a reformulação. Antes, a rota recusava nesses casos («Não consegui confirmar uma recuperação corrigida para esta pergunta.»). Agora responde, e a linha de recuperação diz só o que foi observado, sem afirmar uma correção:

| Caso observado pela ferramenta | Linha publicada |
|---|---|
| A pergunta inicial deixou a regra fora do top-4 e a reformulação a recuperou | «Recuperação T24: a pergunta inicial deixou `FIC-ENT-01-S05-C01` fora do top-4; a reformulação o colocou na posição 1 com o mesmo índice e top-k.» |
| A pergunta inicial já trazia a regra | «Recuperação: a pergunta inicial já trazia `FIC-ENT-01-S05-C01` na posição 2 do top-4; com a reformulação ficou na posição 1.» |

**Execução com o modelo real** (`gpt-4.1-mini`, NLI real local, índice de demonstração em memória; 2026-11-13T03:37:01 UTC, com a guarda de entrada ativa; `uv run python scripts/demonstrar_r23.py`; [rastros/r23_resposta_llm.json](rastros/r23_resposta_llm.json)):

| Pergunta | Primeira frase publicada | Recuperação observada |
|---|---|---|
| Posso receber em várias caixas? | Frase do modelo verificada | Fora do top-4 → posição 1 |
| Quais produtos posso receber em várias caixas? | Aviso «A política não responde exatamente…» e a frase do modelo verificada | Fora do top-4 → posição 1 |
| Quanto custa receber o pedido em duas caixas? | Aviso e a frase do modelo verificada (sobre o frete) | Posição 2 → posição 1 |
| Sem um acordo, o pedido pode chegar em caixas separadas? | Regra literal: a frase do modelo foi rejeitada (`NLI: neutral`) | Posição 1 → posição 1 |
| O pedido pode chegar em vários pacotes de fornecedores diferentes? | Frase do modelo verificada | Posição 1 → posição 1 |

Resumo do rastro: 5 perguntas, 4 respostas verificadas, 1 regra literal, 5 citam a regra, 2 mostram a recuperação corrigida, 5 primeiras linhas diferentes. As frases completas estão em [respostas_rubricas.md](respostas_rubricas.md), R23, seção 4.

**Limites.** A rota continua sendo ativada só por vocabulário (caixas ou pacotes, vários ou parcial, e um verbo de envio). A frase usa só o fragmento `FIC-ENT-01-S05-C01`: o que o corpus responde em outro lugar recebe o aviso. O julgamento «responde ao perguntado» é do modelo e não é verificado. É uma única execução de cinco perguntas.

## Limite da evidência

Isso demonstra o método de T24 sobre dados fictícios. A falha e a correção foram repetidas no índice FAISS salvo em disco (`knowledge/politicas/`), carregado depois de conferir o manifesto. Esse índice é próprio, construído a partir do mesmo corpus fictício por `scripts/construir_indice_politicas.py`; não é um índice fornecido por terceiros.
