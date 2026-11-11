# T24: diagnóstico de recuperação

## Corpus e método

O diagnóstico foi medido em dois índices do mesmo corpus fictício de `knowledge/politicas_demo/`: o **índice salvo em disco** em `knowledge/politicas/` (rastro [rastros/r23_t24_indice_existente.json](rastros/r23_t24_indice_existente.json)) e o **índice fictício em memória** (`scripts/diagnosticar_t24.py`). Os dois deram as mesmas posições e distâncias. A versão 1.1 do corpus, em português, contém 75 fragmentos com IDs, documento, tema e seção. Impressão digital SHA-256 do corpus: `027051d3ca4ed08b2d98130ce4ee5e1f3393975e49da113b1eac7ef81504ff8d`. Foram usados FastEmbed `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, FAISS com métrica **L2**, `k=4`, `fetch_k=20` e sem filtro nas duas consultas. Em L2, menor distância indica maior proximidade.

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

**Nota histórica (versão anterior, em espanhol).** Com o corpus em espanhol (SHA-256 `b9dec4509b36aa722e03bff45c14876339e52831e12f8b311de6287ed5bce6c3`), a pergunta «¿Se puede mandar en varias cajas?» deixava o fragmento esperado fora do top-4 (posição 1: `FIC-ENT-01-S04-C01`, L2 = 12,845). A reformulação em espanhol o colocava na posição 1 (L2 = 10,216). Essas medições não foram refeitas.

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

Para testar o **fluxo normal**, faça a pergunta inicial no chat. A rota de entrega do fluxo chama `consultar_politicas` de forma determinística para perguntas coloquiais sobre dividir pacotes e reformula a intenção como entrega parcial, sem acrescentar a regra. A resposta extrai duas frases do fragmento recuperado, verifica a procedência e usa o NLI local antes de publicá-las. O resumo de recuperação é gerado a partir dos resultados da ferramenta. Isso foi observado uma vez no fluxo com NLI real e índice salvo em disco ([rastros/r22_indice_existente.json](rastros/r22_indice_existente.json)) e uma vez no Streamlit ([rastros/r28_streamlit.json](rastros/r28_streamlit.json)). O teste `tests/test_policy_demo.py` repete a pergunta duas vezes na mesma sessão, com um rascunho de compra pendente e NLI de duplo de teste, e obtém a mesma resposta. A rota cobre essa intenção do corpus sintético; outras formulações precisam de testes próprios.

## Limite da evidência

Isso demonstra o método de T24 sobre dados fictícios. A falha e a correção foram repetidas no índice FAISS salvo em disco (`knowledge/politicas/`), carregado depois de conferir o manifesto. Esse índice é próprio, construído a partir do mesmo corpus fictício por `scripts/construir_indice_politicas.py`; não é um índice fornecido por terceiros.
