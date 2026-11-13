# Roteiro do vídeo de entrega

**Duração:** cerca de 6 minutos (o enunciado não fixa duração). **Exige:** tela e webcam visíveis ao mesmo tempo (Loom ou OBS) e a conta institucional do aluno.

**O que o enunciado pede no vídeo (guide/infnet_agentes.pdf, p. 5):** interação real com o agente em execução, não roteirizada em texto; uma consulta em que o agente raciocina e decide usar uma ferramenta (cena 2); uma chamada real de ferramenta, incluindo a API externa (cena 4); e memória entre turnos na mesma conversa (cenas 3 e 6).

**O vídeo é uma defesa:** o enunciado avalia a capacidade de justificar escolhas. Cada cena termina com uma frase de «porque». Fale com as suas palavras; não leia o texto.

## Antes de gravar

- Rodar `./project.sh restart` e abrir http://localhost:8501. O selo deve dizer «Agente ativo».
- Clicar em «Novo chat» para começar com a tela limpa.
- Deixar abertas, em outras abas: o experimento do LangSmith e o arquivo docs/relatorio.pdf.
- Ensaiar uma vez. As frases do Pedro podem variar um pouco; os números não variam.

## Cena 1 — Abertura (0:00 a 0:40)

**Na tela:** webcam e o chat do Pedro aberto.

**Dizer:** «Olá, eu sou o Efrain. Este é o Pedro, meu projeto da disciplina Agentes Cognitivos com LangChain. O Pedro é um assistente de compras de peças de eletrodomésticos. Todos os dados são fictícios. A função principal dele é comparar fornecedores e recomendar o melhor.»

**Dizer o porquê:** «Escolhi este domínio porque comparar fornecedores depende de dados que mudam, como preço e estoque. Por isso ele precisa de um agente com ferramentas, e não só de uma chain.»

## Cena 2 — Interação real: comparar fornecedores (0:40 a 2:00)

**Na tela:** clicar na sugestão «Compare 5 unidades de PEC-01-0001 com prazo de 7 dias». Esperar os cartões. Abrir «Como cheguei a esta resposta».

**Dizer:** «Peço cinco unidades de uma peça, com prazo de sete dias. O agente escolhe a ferramenta de comparação. Ela descarta as ofertas sem estoque, abaixo do pedido mínimo ou fora do prazo. A recomendação é a CentroPeças, por 7.279 reais e 83 centavos, com entrega em dois dias. Na tabela aparecem as outras duas ofertas e o motivo do descarte.»

**Dizer (com os passos abertos):** «Aqui estão os passos do agente: leu a mensagem, comparou as ofertas, pegou os números do cálculo e verificou a resposta. O modelo decide o que responder, mas os números quem coloca é o sistema.»

**Dizer o porquê:** «Fiz assim porque um modelo de linguagem pode errar contas. O cálculo fica no código, em centavos inteiros, e a resposta só é publicada depois de verificada.»

## Cena 3 — Memória entre turnos (2:00 a 2:45)

**Na tela:** digitar «Agora que sejam 6 e mantenha o prazo».

**Dizer:** «Agora mudo só a quantidade. Não repito a peça nem o prazo. O Pedro lembra da solicitação anterior e recalcula: 8.718 reais e 75 centavos para seis unidades. Isso é memória de curto prazo: o rascunho da compra fica guardado na sessão.»

**Dizer o porquê:** «Guardei o rascunho porque, em uma compra, a pessoa ajusta um dado por vez. Sem isso, ela teria de repetir tudo a cada mensagem.»

## Cena 4 — API externa (2:45 a 3:25)

**Na tela:** clicar na sugestão «A que cidade corresponde o CEP 01001000?». Abrir os passos.

**Dizer:** «Esta pergunta não é uma compra. O agente decide chamar outra ferramenta, que consulta a API pública do ViaCEP. A resposta é São Paulo, SP. A cidade publicada vem da resposta da API, não da memória do modelo.»

**Dizer o porquê:** «Usei uma API porque o modelo não tem como saber um CEP com certeza. Esse dado tem de vir de uma fonte externa.»

## Cena 5 — Políticas com RAG (3:25 a 4:10)

**Na tela:** clicar na sugestão «Posso receber em várias caixas?». Mostrar a fonte `FIC-ENT-01-S05-C01`.

**Dizer:** «Aqui o agente busca em um corpus de políticas, com um índice FAISS. A pergunta fala em caixas e o documento fala em entrega parcial. Sem ajuda, a busca não encontrava a regra. O sistema reescreve a pergunta e a regra aparece em primeiro lugar. A resposta cita a fonte.»

**Dizer o porquê:** «Escolhi reescrever a pergunta porque o problema era de vocabulário, não do índice. Assim não precisei indexar nada de novo.»

## Cena 6 — Memória de longo prazo: preferência (4:10 a 5:05)

**Na tela:** digitar «Prefiro fornecedores nacionais, lembre-se disso». Depois digitar «Compare 2 unidades de PEC-11-0001».

**Dizer:** «Agora digo uma preferência. O Pedro salva, porque eu pedi de forma explícita. Na comparação seguinte, ele recomenda a Casa Técnica Brasil, que é nacional, por 1.970 reais e 38 centavos. Havia uma oferta internacional mais barata, e o Pedro avisa que aplicou a minha preferência. Essa preferência vale também em outras conversas.»

**Dizer o porquê:** «Só salvo preferência explícita porque o agente não deve guardar o que a pessoa não pediu. E quem aplica a preferência é o sistema, não o modelo, porque assim a ordem das ofertas é sempre a mesma.»

## Cena 7 — Evidências e encerramento (5:05 a 6:00)

**Na tela:** a aba do LangSmith com o experimento `pedro-infnet-fluxo-gpt-4.1-mini-portugues-235aa9f1`. Depois o arquivo docs/relatorio.pdf.

**Dizer:** «Avaliei com casos porque ver o agente funcionar em alguns exemplos não prova que ele acerta. O agente foi avaliado no LangSmith com trinta casos. O vencedor ficou correto em 14 de 14 e o valor em 14 de 14. Em nove experimentos, nenhuma recomendação contrária à regra foi publicada. O projeto tem 156 testes automáticos e cinco notebooks, um por fase. As 29 rubricas estão respondidas no documento respostas_rubricas, com a evidência de cada uma. Obrigado.»

## Depois de gravar

- Assistir à gravação e conferir vídeo e áudio.
- Enviar o vídeo ao Google Drive de aluno Infnet.
- Compartilhar como «qualquer pessoa com o link» pode visualizar.
- Abrir o link em uma janela anônima, conferir que ele abre e enviar o link na atividade.

## Se algo sair diferente durante a gravação

- **O Pedro respondeu com outras palavras:** normal. Confira só os números: R$ 7.279,83, R$ 8.718,75 e R$ 1.970,38.
- **O selo diz «Modo local, sem modelo»:** falta a chave `OPENAI_API_KEY` no arquivo .env. Corrija e rode `./project.sh restart`.
- **O CEP demorou ou falhou:** o ViaCEP é um serviço externo. Espere alguns segundos e repita a pergunta.
