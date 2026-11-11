# Citações ancoradas: diagnóstico e correção de uma falha de respaldo

Data do diagnóstico: 2026-11-10 (versão anterior do projeto, em espanhol). Reexecução em português: 2026-11-11. Modelo: ChatOpenAI `gpt-4.1-mini`. NLI real local. Corpus de políticas fictício.

Este documento registra uma falha real observada com o modelo remoto, o diagnóstico e a correção. Serve de evidência para **R24** (verificação integrada), **R12** (confiabilidade com tratamento de erros) e, como apoio, para o tema **T26** (o que o agente faz quando os documentos recuperados não respaldam a resposta). Não substitui R23, que trata de uma falha de *recuperação*.

## 1. Falha observada

A falha foi observada na versão anterior, em espanhol. Essa execução não foi refeita; a pergunta e a resposta ficam em espanhol, como estão no rastro.

Pergunta: «¿Qué dice la política de devoluciones sobre piezas dañadas?»

| | Antes |
|---|---|
| Ferramenta chamada | `consultar_politicas` (duas propostas) |
| Fragmentos recuperados | Corretos, de `devoluciones.md` (hoje `devolucoes.md`) |
| Resposta publicada | «No pude verificar la respuesta sobre políticas…» |
| Rastro | [rastros/r02_planificacion_llm_antes.json](rastros/r02_planificacion_llm_antes.json) (versão anterior, em espanhol) |

## 2. Diagnóstico

A recuperação **não** falhou: o fragmento correto estava entre os devolvidos. Falhou o passo seguinte, o respaldo da citação.

- A verificação exigia que o texto citado pelo modelo fosse idêntico, caractere por caractere, ao fragmento.
- O modelo copiou o fragmento quase inteiro, com uma diferença mínima (cobertura observada depois: 0,998). Os fragmentos são cortados em 700 caracteres e terminam sem ponto final; o modelo tende a «completá-los».
- Resultado: erros de fragmento que não corresponde e de fonte não recuperada (hoje `fragmento não corresponde` e `fonte não recuperada`) nas duas propostas. Nada falso foi publicado, mas o usuário ficou sem resposta.

O defeito de projeto era pedir ao modelo uma tarefa mecânica (copiar texto sem mudar um caractere) e puni-lo com uma rejeição total.

## 3. Correção: o modelo escolhe a fonte, o sistema põe o texto

Foram acrescentadas três peças, todas determinísticas:

1. **Ancoragem de citações** (`ancorar_citacoes` em [verification.py](../src/pedro/verification.py)). Antes de verificar, cada citação é procurada dentro do fragmento que a ferramenta recuperou naquele turno. Se coincide em pelo menos 80 %, é substituída pelo trecho literal do fragmento. O texto final sempre sai da fonte, nunca do modelo.
2. **Quatro estados registrados no rastro**: `literal`, `reancorada`, `por_identificador` (citação vazia com fonte válida) e `rejeitada` ou `fonte_nao_recuperada`. Uma citação inventada não atinge o limiar e a verificação exata continua bloqueando.
3. **Degradação extrativa.** Se as citações são válidas, mas o resumo do modelo não obtém *entailment* no NLI depois da correção, publica-se só o texto literal da fonte com o seu identificador, sem o resumo.

A verificação exata e o NLI não foram afrouxados: continuam sendo a porta. A ancoragem só evita rejeitar citações que já estavam corretas.

| Situação | Antes | Agora |
|---|---|---|
| Citação literal e resumo respaldado | Publica | Publica |
| Citação quase literal e resumo respaldado | **Rejeita** | Reancora e publica |
| Citação válida e resumo sem respaldo NLI | Rejeita | Publica só a citação textual |
| Citação inventada | Rejeita | Rejeita |

## 4. Resultado após a correção

**Versão anterior, em espanhol** (execução histórica, não refeita). Mesma pergunta, mesmo índice, mesmo modelo.

| | Depois |
|---|---|
| Primeira proposta | 3 citações `reanclada` (hoje `reancorada`; cobertura 0,998); o resumo não passou no NLI |
| Segunda proposta | 2 citações `literal`; o resumo obteve *entailment* |
| Resposta publicada | Resumo da política com as fontes `FIC-DEV-01-S05-C01` e `FIC-GAR-01-S05-C01` |
| Rastro | [rastros/r02_planificacion_llm_sin_plan.json](rastros/r02_planificacion_llm_sin_plan.json) (versão anterior, em espanhol) |

**Versão atual, em português** (2026-11-11, uma execução de cada). Nenhuma citação precisou ser reancorada nestas execuções: o modelo copiou os trechos de forma literal.

| Pergunta | Citações | Resposta publicada | Rastro |
|---|---|---|---|
| «O que a política de devoluções diz sobre peças danificadas?» | 2 `literal` (cobertura 1,0), uma só proposta, sem erros de verificação | Resumo da política com as fontes `FIC-DEV-01-S05-C01` e `FIC-DEV-01-S06-C01` | [rastros/r02_planejamento_llm.json](rastros/r02_planejamento_llm.json) |
| A mesma pergunta dentro de uma mensagem com três pedidos | 1 `literal` (cobertura 1,0) | Resumo com a fonte `FIC-DEV-01-S05-C01` | [rastros/r02_planejamento_llm.json](rastros/r02_planejamento_llm.json) |
| «Como se verifica a compatibilidade elétrica antes de instalar uma peça?» (índice em memória) | Uma proposta, sem erros de verificação | Resumo com a fonte `FIC-DEV-01-S06-C01` | [rastros/fase3_memoria_llm.json](rastros/fase3_memoria_llm.json) |
| A mesma pergunta (índice salvo em disco) | Quatro citações registradas, nesta ordem: `FIC-DEV-01-S06-C01` `literal` (cobertura 1,0), `FIC-DEV-01-S02-C01` `rejeitada` (cobertura 0,71), `FIC-DEV-01-S06-C01` `literal` (1,0) e `FIC-DEV-01-S02-C01` `literal` (1,0) | Resumo do modelo com as fontes `FIC-DEV-01-S06-C01` e `FIC-DEV-01-S02-C01` | [rastros/r22_indice_existente.json](rastros/r22_indice_existente.json) |

Resposta publicada na última linha (resumo do modelo, verificado):

> Política fictícia de demonstração. Antes de selecionar uma peça para instalação, deve-se conferir a marca, modelo, voltagem e dimensões com a ficha técnica para assegurar a compatibilidade elétrica. Uma peça incompatível pode ser devolvida dentro de 30 dias se mantiver suas condições originais, incluindo não mostrar marcas de montagem ou conexões elétricas usadas.
> Fontes: FIC-DEV-01-S06-C01, FIC-DEV-01-S02-C01

A degradação extrativa não aparece neste rastro. Ela foi observada na execução anterior do mesmo script, em português (2026-11-11T17:20:51 UTC), com uma citação de `FIC-DEV-01-S02-C01` rejeitada (cobertura 0,474). Essa execução foi substituída pela atual e só está no histórico do git (commit `c92ba32`). A resposta publicada naquela execução foi:

> Política fictícia de demonstração. Não consegui verificar um resumo próprio, então cito o texto literal da fonte:
> - «Antes de selecionar uma peça, o usuário deve conferir marca, modelo, voltagem e dimensões com a ficha técnica fictícia. Uma compra simulada de uma peça incompatível, ainda sem instalar, pode seguir o procedimento de devolução de 30 dias se conserva suas condições originais.» [FIC-DEV-01-S06-C01]

## 5. Evidência

| Evidência | Tipo |
|---|---|
| Rastros de antes e depois com o modelo real (versão anterior, em espanhol) | Real remoto pontual (uma execução de cada) |
| Rastros da versão atual, em português (tabela da seção 4) | Real remoto pontual (uma execução de cada) |
| [tests/test_citacoes_ancoradas.py](../tests/test_citacoes_ancoradas.py): citação quase literal é reancorada; citação inventada ou curta demais é rejeitada; o chat publica, degrada para citação textual ou bloqueia conforme o caso | Testes com duplo (executor e NLI roteirizados) |

## 6. Limitações

- Uma execução antes e outra depois não medem uma taxa de sucesso; a medição corresponde a R29.
- A degradação extrativa está testada com duplos. Com o modelo real foi observada uma vez, em uma execução anterior de R22 em português que foi substituída (só está no histórico do git, commit `c92ba32`). No rastro R22 salvo hoje ela não ocorre: o resumo do modelo foi publicado. O estado `reancorada` só foi observado com o modelo real na versão anterior, em espanhol; nas execuções em português todas as citações aceitas foram `literal`.
- O limiar de 80 % foi fixado por critério, sem calibração com dados.
- O modelo NLI aceita 512 tokens: com várias citações longas a premissa é truncada (observou-se um aviso de 539 tokens na execução em português de R02; na versão anterior, em espanhol, de 652 tokens).
- Quando este diagnóstico foi escrito, uma solicitação mista em um só turno não era publicada; isso foi resolvido depois com o planejador de turno (R02).
