# Guion del vídeo — versión de estudio en español

**Para qué sirve:** estudiar el guion en español. El vídeo se presenta en portugués con docs/roteiro_video.md; aquí cada frase aparece en portugués (lo que dices) y en español (lo que significa).

**Duración:** unos 6 minutos, 7 escenas (el enunciado no fija duración). **Necesitas:** pantalla y webcam visibles a la vez (Loom u OBS) y tu cuenta institucional.

**Lo que el enunciado pide en el vídeo (guide/infnet_agentes.pdf, p. 5):** interacción real con el agente en ejecución, no guionizada en texto; una consulta en la que el agente razona y decide usar una herramienta (escena 2); una llamada real a herramienta, incluida la API externa (escena 4); y memoria entre turnos en la misma conversación (escenas 3 y 6).

**El vídeo es una defensa:** el enunciado evalúa si sabes justificar tus decisiones. Cada escena termina con una frase de «porque». Dilo con tus palabras; no leas el texto.

## Antes de grabar

- Ejecuta `./project.sh restart` y abre http://localhost:8501. El sello debe decir «Agente ativo».
- Pulsa «Novo chat» para empezar con la pantalla limpia.
- Deja abiertas en otras pestañas: el experimento de LangSmith y docs/relatorio.pdf.
- Ensaya una vez. Las frases de Pedro pueden cambiar un poco; las cifras no.

## Escena 1 — Apertura (0:00 a 0:40)

**En pantalla:** tu webcam y el chat de Pedro abierto.

**Dices (portugués):** «Olá, eu sou o Efrain. Este é o Pedro, meu projeto da disciplina Agentes Cognitivos com LangChain. O Pedro é um assistente de compras de peças de eletrodomésticos. Todos os dados são fictícios. A função principal dele é comparar fornecedores e recomendar o melhor.»

**Significa:** Hola, soy Efrain. Este es Pedro, mi proyecto de la asignatura. Pedro es un asistente de compras de piezas de electrodomésticos. Todos los datos son ficticios. Su función principal es comparar proveedores y recomendar el mejor.

**Dices el porqué (portugués):** «Escolhi este domínio porque comparar fornecedores depende de dados que mudam, como preço e estoque. Por isso ele precisa de um agente com ferramentas, e não só de uma chain.»

**Significa:** Elegí este dominio porque comparar proveedores depende de datos que cambian, como precio y stock. Por eso necesita un agente con herramientas, y no solo una chain.

**La idea que transmites:** qué es el proyecto y cuál es su núcleo.

## Escena 2 — Interacción real: comparar proveedores (0:40 a 2:00)

**En pantalla:** pulsa la sugerencia «Compare 5 unidades de PEC-01-0001 com prazo de 7 dias». Espera las tarjetas. Abre «Como cheguei a esta resposta».

**Dices (portugués):** «Peço cinco unidades de uma peça, com prazo de sete dias. O agente escolhe a ferramenta de comparação. Ela descarta as ofertas sem estoque, abaixo do pedido mínimo ou fora do prazo. A recomendação é a CentroPeças, por 7.279 reais e 83 centavos, com entrega em dois dias. Na tabela aparecem as outras duas ofertas e o motivo do descarte.»

**Significa:** Pido cinco unidades de una pieza, con plazo de siete días. El agente elige la herramienta de comparación. Esta descarta las ofertas sin stock, por debajo del pedido mínimo o fuera de plazo. La recomendación es CentroPeças, por 7.279,83 reales, con entrega en dos días. En la tabla aparecen las otras dos ofertas y el motivo del descarte.

**Dices con los pasos abiertos (portugués):** «Aqui estão os passos do agente: leu a mensagem, comparou as ofertas, pegou os números do cálculo e verificou a resposta. O modelo decide o que responder, mas os números quem coloca é o sistema.»

**Significa:** Aquí están los pasos del agente: leyó el mensaje, comparó las ofertas, tomó las cifras del cálculo y verificó la respuesta. El modelo decide qué responder, pero las cifras las pone el sistema.

**Dices el porqué (portugués):** «Fiz assim porque um modelo de linguagem pode errar contas. O cálculo fica no código, em centavos inteiros, e a resposta só é publicada depois de verificada.»

**Significa:** Lo hice así porque un modelo de lenguaje puede equivocarse en las cuentas. El cálculo está en el código, en centavos enteros, y la respuesta solo se publica después de verificarla.

**La idea que transmites:** el agente usa herramientas (R08, R19, R26) y nada se publica sin verificar (R24).

**Si te preguntan:** las otras dos ofertas son Litoral Parts (sin stock y 12 días de plazo) y Atlantic Repair Parts (35 días de plazo).

## Escena 3 — Memoria entre turnos (2:00 a 2:45)

**En pantalla:** escribe «Agora que sejam 6 e mantenha o prazo».

**Dices (portugués):** «Agora mudo só a quantidade. Não repito a peça nem o prazo. O Pedro lembra da solicitação anterior e recalcula: 8.718 reais e 75 centavos para seis unidades. Isso é memória de curto prazo: o rascunho da compra fica guardado na sessão.»

**Significa:** Ahora cambio solo la cantidad. No repito la pieza ni el plazo. Pedro recuerda la solicitud anterior y recalcula: 8.718,75 reales por seis unidades. Eso es memoria de corto plazo: el borrador de la compra queda guardado en la sesión.

**Dices el porqué (portugués):** «Guardei o rascunho porque, em uma compra, a pessoa ajusta um dado por vez. Sem isso, ela teria de repetir tudo a cada mensagem.»

**Significa:** Guardé el borrador porque, en una compra, la persona ajusta un dato cada vez. Sin eso, tendría que repetirlo todo en cada mensaje.

**La idea que transmites:** memoria entre turnos (R13, R17, R18, R27).

## Escena 4 — API externa (2:45 a 3:25)

**En pantalla:** pulsa la sugerencia «A que cidade corresponde o CEP 01001000?». Abre los pasos.

**Dices (portugués):** «Esta pergunta não é uma compra. O agente decide chamar outra ferramenta, que consulta a API pública do ViaCEP. A resposta é São Paulo, SP. A cidade publicada vem da resposta da API, não da memória do modelo.»

**Significa:** Esta pregunta no es una compra. El agente decide llamar a otra herramienta, que consulta la API pública de ViaCEP. La respuesta es São Paulo, SP. La ciudad publicada viene de la respuesta de la API, no de la memoria del modelo.

**Dices el porqué (portugués):** «Usei uma API porque o modelo não tem como saber um CEP com certeza. Esse dado tem de vir de uma fonte externa.»

**Significa:** Usé una API porque el modelo no puede saber un código postal con certeza. Ese dato tiene que venir de una fuente externa.

**La idea que transmites:** uso de una API externa por function calling (R10, R20).

## Escena 5 — Políticas con RAG (3:25 a 4:10)

**En pantalla:** pulsa la sugerencia «Posso receber em várias caixas?». Señala la fuente `FIC-ENT-01-S05-C01`.

**Dices (portugués):** «Aqui o agente busca em um corpus de políticas, com um índice FAISS. A pergunta fala em caixas e o documento fala em entrega parcial. Sem ajuda, a busca não encontrava a regra. O sistema reescreve a pergunta e a regra aparece em primeiro lugar. A resposta cita a fonte.»

**Significa:** Aquí el agente busca en un corpus de políticas, con un índice FAISS. La pregunta habla de cajas y el documento habla de entrega parcial. Sin ayuda, la búsqueda no encontraba la regla. El sistema reescribe la pregunta y la regla aparece en primer lugar. La respuesta cita la fuente.

**Dices el porqué (portugués):** «Escolhi reescrever a pergunta porque o problema era de vocabulário, não do índice. Assim não precisei indexar nada de novo.»

**Significa:** Elegí reescribir la pregunta porque el problema era de vocabulario, no del índice. Así no tuve que indexar nada de nuevo.

**La idea que transmites:** RAG y un fallo real de recuperación corregido (R22, R23).

## Escena 6 — Memoria de largo plazo: preferencia (4:10 a 5:05)

**En pantalla:** escribe «Prefiro fornecedores nacionais, lembre-se disso». Después escribe «Compare 2 unidades de PEC-11-0001».

**Dices (portugués):** «Agora digo uma preferência. O Pedro salva, porque eu pedi de forma explícita. Na comparação seguinte, ele recomenda a Casa Técnica Brasil, que é nacional, por 1.970 reais e 38 centavos. Havia uma oferta internacional mais barata, e o Pedro avisa que aplicou a minha preferência. Essa preferência vale também em outras conversas.»

**Significa:** Ahora digo una preferencia. Pedro la guarda, porque lo pedí de forma explícita. En la comparación siguiente recomienda Casa Técnica Brasil, que es nacional, por 1.970,38 reales. Había una oferta internacional más barata, y Pedro avisa de que aplicó mi preferencia. Esa preferencia vale también en otras conversaciones.

**Dices el porqué (portugués):** «Só salvo preferência explícita porque o agente não deve guardar o que a pessoa não pediu. E quem aplica a preferência é o sistema, não o modelo, porque assim a ordem das ofertas é sempre a mesma.»

**Significa:** Solo guardo una preferencia explícita porque el agente no debe guardar lo que la persona no pidió. Y quien aplica la preferencia es el sistema, no el modelo, porque así el orden de las ofertas es siempre el mismo.

**La idea que transmites:** memoria de largo plazo que cambia la recomendación (R13, R14).

**Si te preguntan:** la oferta internacional más barata era de Atlantic Repair Parts, por R$ 619,38.

## Escena 7 — Evidencias y cierre (5:05 a 6:00)

**En pantalla:** la pestaña de LangSmith con el experimento `pedro-infnet-fluxo-gpt-4.1-mini-portugues-235aa9f1`. Después docs/relatorio.pdf.

**Dices (portugués):** «Avaliei com casos porque ver o agente funcionar em alguns exemplos não prova que ele acerta. O agente foi avaliado no LangSmith com trinta casos. O vencedor ficou correto em 14 de 14 e o valor em 14 de 14. Em nove experimentos, nenhuma recomendação contrária à regra foi publicada. O projeto tem 159 testes automáticos e cinco notebooks, um por fase. As 29 rubricas estão respondidas no documento respostas_rubricas, com a evidência de cada uma. Obrigado.»

**Significa:** Evalué con casos porque ver al agente funcionar en algunos ejemplos no prueba que acierte. El agente se evaluó en LangSmith con treinta casos. El ganador fue correcto en 14 de 14 y el importe en 14 de 14. En nueve experimentos no se publicó ninguna recomendación contraria a la regla. El proyecto tiene 159 pruebas automáticas y cinco notebooks, uno por fase. Las 29 rúbricas están respondidas en el documento respostas_rubricas, con la evidencia de cada una. Gracias.

**La idea que transmites:** el agente está medido, no solo demostrado (R29).

## Vocabulario que más se repite

| Portugués | Español |
|---|---|
| fornecedor | proveedor |
| peça | pieza |
| prazo | plazo |
| estoque | stock |
| pedido mínimo | pedido mínimo |
| ferramenta | herramienta |
| rascunho | borrador |
| lembrar / salvar | recordar / guardar |
| vencedor / valor | ganador / importe |
| fonte | fuente |
| caixas | cajas |
| rubrica | rúbrica |

## Después de grabar

- Mira la grabación y comprueba vídeo y audio.
- Sube el vídeo a tu Google Drive de alumno Infnet.
- Compártelo como «qualquer pessoa com o link» puede ver.
- Abre el enlace en una ventana de incógnito, comprueba que se abre y envía el enlace en la actividad.

## Si algo sale distinto durante la grabación

- **Pedro respondió con otras palabras:** es normal. Mira solo las cifras: R$ 7.279,83, R$ 8.718,75 y R$ 1.970,38.
- **El sello dice «Modo local, sem modelo»:** falta la clave `OPENAI_API_KEY` en el archivo .env. Corrígelo y ejecuta `./project.sh restart`.
- **El CEP tardó o falló:** ViaCEP es un servicio externo. Espera unos segundos y repite la pregunta.
