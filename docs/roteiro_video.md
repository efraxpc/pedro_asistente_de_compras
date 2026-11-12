# Roteiro do vídeo de entrega

**Duração:** 5 minutos (entre 4 e 6). **Exige:** webcam ligada e a conta institucional do aluno.

**O que a rubrica pede no vídeo:** interação real com o agente, uso de uma ferramenta ou API externa e evidência de memória entre turnos. As cenas 2, 3, 4 e 6 cobrem os três pontos.

## Antes de gravar

- Rodar `./project.sh restart` e abrir http://localhost:8501. O selo deve dizer «Agente ativo».
- Clicar em «Novo chat» para começar com a tela limpa.
- Deixar abertas, em outras abas: o experimento do LangSmith e o arquivo docs/relatorio.pdf.
- Ensaiar uma vez. As frases do Pedro podem variar um pouco; os números não variam.

## Cena 1 — Abertura (0:00 a 0:30)

**Na tela:** webcam e o chat do Pedro aberto.

**Dizer:** «Olá, eu sou o Efrain. Este é o Pedro, meu projeto da disciplina Agentes Cognitivos com LangChain. O Pedro é um assistente de compras de peças de eletrodomésticos. Todos os dados são fictícios. A função principal dele é comparar fornecedores e recomendar o melhor.»

## Cena 2 — Interação real: comparar fornecedores (0:30 a 1:40)

**Na tela:** clicar na sugestão «Compare 5 unidades de PEC-01-0001 com prazo de 7 dias». Esperar os cartões. Abrir «Como cheguei a esta resposta».

**Dizer:** «Peço cinco unidades de uma peça, com prazo de sete dias. O agente escolhe a ferramenta de comparação. Ela descarta as ofertas sem estoque, abaixo do pedido mínimo ou fora do prazo. A recomendação é a CentroPeças, por 7.279 reais e 83 centavos, com entrega em dois dias. Na tabela aparecem as outras duas ofertas e o motivo do descarte.»

**Dizer (com os passos abertos):** «Aqui estão os passos do agente: leu a mensagem, comparou as ofertas, pegou os números do cálculo e verificou a resposta. O modelo decide o que responder, mas os números quem coloca é o sistema.»

## Cena 3 — Memória entre turnos (1:40 a 2:20)

**Na tela:** digitar «Agora que sejam 6 e mantenha o prazo».

**Dizer:** «Agora mudo só a quantidade. Não repito a peça nem o prazo. O Pedro lembra da solicitação anterior e recalcula: 8.718 reais e 75 centavos para seis unidades. Isso é memória de curto prazo: o rascunho da compra fica guardado na sessão.»

## Cena 4 — API externa (2:20 a 2:50)

**Na tela:** clicar na sugestão «A que cidade corresponde o CEP 01001000?». Abrir os passos.

**Dizer:** «Esta pergunta não é uma compra. O agente decide chamar outra ferramenta, que consulta a API pública do ViaCEP. A resposta é São Paulo, SP. A cidade publicada vem da resposta da API, não da memória do modelo.»

## Cena 5 — Políticas com RAG (2:50 a 3:25)

**Na tela:** clicar na sugestão «Posso receber em várias caixas?». Mostrar a fonte `FIC-ENT-01-S05-C01`.

**Dizer:** «Aqui o agente busca em um corpus de políticas, com um índice FAISS. A pergunta fala em caixas e o documento fala em entrega parcial. Sem ajuda, a busca não encontrava a regra. O sistema reescreve a pergunta e a regra aparece em primeiro lugar. A resposta cita a fonte.»

## Cena 6 — Memória de longo prazo: preferência (3:25 a 4:10)

**Na tela:** digitar «Prefiro fornecedores nacionais, lembre-se disso». Depois digitar «Compare 2 unidades de PEC-11-0001».

**Dizer:** «Agora digo uma preferência. O Pedro salva, porque eu pedi de forma explícita. Na comparação seguinte, ele recomenda a Casa Técnica Brasil, que é nacional, por 1.970 reais e 38 centavos. Havia uma oferta internacional mais barata, e o Pedro avisa que aplicou a minha preferência. Essa preferência vale também em outras conversas.»

## Cena 7 — Evidências e encerramento (4:10 a 5:00)

**Na tela:** a aba do LangSmith com o experimento `pedro-infnet-fluxo-gpt-4.1-mini-portugues-235aa9f1`. Depois o arquivo docs/relatorio.pdf.

**Dizer:** «O agente foi avaliado no LangSmith com trinta casos. O vencedor ficou correto em 14 de 14 e o valor em 14 de 14. Em nove experimentos, nenhuma recomendação contrária à regra foi publicada. O projeto tem 153 testes automáticos e cinco notebooks, um por fase. As 29 rubricas estão respondidas no documento respostas_rubricas, com a evidência de cada uma. Obrigado.»

## Depois de gravar

- Enviar o vídeo ao Drive institucional.
- Abrir o link em uma janela anônima e conferir que ele abre com as permissões que a rubrica pede.

## Se algo sair diferente durante a gravação

- **O Pedro respondeu com outras palavras:** normal. Confira só os números: R$ 7.279,83, R$ 8.718,75 e R$ 1.970,38.
- **O selo diz «Modo local, sem modelo»:** falta a chave `OPENAI_API_KEY` no arquivo .env. Corrija e rode `./project.sh restart`.
- **O CEP demorou ou falhou:** o ViaCEP é um serviço externo. Espere alguns segundos e repita a pergunta.
