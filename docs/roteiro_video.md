# Roteiro do vídeo de entrega

Duração sugerida: 4–6 minutos. Exige webcam e conta institucional do aluno.

1. Mostrar o README, a semente 20261107 e o manifesto do cenário. A interface é só o chat: mostrar o selo «Cenário …» e clicar na sugestão «Liste as peças» para ver PEC-01-0001 no catálogo.
2. Sem chave (selo «Modo local, sem modelo»), clicar na sugestão «Compare 5 unidades de PEC-01-0001 com prazo de 7 dias». Mostrar as três ofertas, o vencedor (CentroPeças, R$ 7.279,83) e os descartes por estoque e prazo.
3. Com OPENAI_API_KEY (selo «Agente ativo»), pedir a mesma comparação no chat e abrir «Como cheguei a esta resposta» para mostrar a ferramenta, a verificação exata e a porta NLI. Dizer «Agora que sejam 6 e mantenha o prazo»; mostrar a continuidade e a nova comparação (R$ 8.718,75). Evidência real: docs/rastros/r28_streamlit.json.
4. Clicar em «A que cidade corresponde o CEP 01001000?» e mostrar a resposta do ViaCEP, São Paulo/SP. Distinguir a localização real das ofertas fictícias.
5. Mostrar os cinco notebooks, os 143 testes e a matriz. Clicar em «Posso receber em várias caixas?» e mostrar a regra de entrega parcial com a fonte `FIC-ENT-01-S05-C01`; digitar `/t24` para mostrar a consulta que falha e a reescrita no mesmo índice e top-k.
6. Mostrar o experimento remoto do LangSmith (pedro-infnet-fluxo-gpt-4.1-mini-portugues-235aa9f1) com os denominadores e o rastro docs/rastros/r29_langsmith_gpt-4.1-mini_portugues.json; apresentar o relatório em PDF. Enviar o vídeo ao Drive institucional e verificar se o link abre com as permissões indicadas pela rubrica.
