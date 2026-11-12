# Glossário da migração espanhol → português

Fonte única de nomes para a migração do projeto Pedro. Vale para código, testes, scripts,
notebooks, prompts, interface e documentos. Identificadores sem acentos; textos para pessoas
em português do Brasil com acentos.

## Regras gerais

- Tudo o que está em espanhol passa a português do Brasil: identificadores, comentários,
  docstrings, textos da interface, prompts, exemplos few-shot, mensagens de erro, chaves de
  dicionários/JSON, valores de `Literal`, nomes de testes.
- Não muda: o nome do pacote `pedro`, nomes de módulos já em inglês (`agent.py`, `business.py`…),
  nomes de tabelas e colunas do catálogo SQLite (já em inglês: `parts`, `offers`, `suppliers`,
  `price_history`, `min_order_qty`, `domestic`…), `dataset_id`, `user_id`, `session_id`, `cep`,
  `uf`, `cidade`, variáveis de ambiente (`PEDRO_*`, `OPENAI_API_KEY`…), IDs de peças e
  fornecedores (`PEC-01-0001`, `BR-06`), nomes de APIs de bibliotecas.
- Dinheiro continua em centavos inteiros. Nenhuma regra de negócio muda.
- Para uma palavra que não esteja nas tabelas, use o radical da tabela de radicais; se também
  não estiver, traduza de forma direta e literal (sem sinônimos criativos).

## Arquivos e pastas

| Antes | Depois |
|---|---|
| `src/pedro/orquestadores.py` | `src/pedro/orquestradores.py` |
| `src/pedro/anatomia.py`, `laboratorio.py` | sem mudança |
| `scripts/generar_catalogo_piezas.py` | `scripts/gerar_catalogo_pecas.py` |
| `scripts/crear_notebooks.py` | `scripts/criar_notebooks.py` |
| `scripts/ejecutar_notebooks.py` | `scripts/executar_notebooks.py` |
| `scripts/crear_casos_eval.py` | `scripts/criar_casos_eval.py` |
| `scripts/generar_informe_pdf.py` | `scripts/gerar_relatorio_pdf.py` |
| `scripts/demostrar_X.py` | `scripts/demonstrar_X.py` (`demostrar_precios` → `demonstrar_precos`) |
| `scripts/construir_indice_politicas.py`, `diagnosticar_t24.py` | sem mudança |
| `evals/evaluar_flujo.py` | `evals/avaliar_fluxo.py` |
| `evals/casos_derivados.json` | sem mudança |
| `datasets/piezas_electrodomesticos.sqlite3` | `datasets/pecas_eletrodomesticos.sqlite3` |
| `knowledge/politicas_demo/devoluciones.md` | `knowledge/politicas_demo/devolucoes.md` |
| `docs/trazas/` | `docs/rastros/` |
| `docs/informe.md`, `.pdf` | `docs/relatorio.md`, `.pdf` |
| `docs/respuestas_rubricas.md` | `docs/respostas_rubricas.md` |
| `docs/citas_ancladas.md` | `docs/citacoes_ancoradas.md` |
| `docs/comparaciones.md` | `docs/comparacoes.md` |
| `docs/guion_video.md` | `docs/roteiro_video.md` |
| `docs/rubricas_proyecto.mmd`, `.svg` | `docs/rubricas_projeto.mmd`, `.svg` |
| `docs/t24_recuperacion.md` | `docs/t24_recuperacao.md` |
| `notebooks/02_react_herramientas.ipynb` | `notebooks/02_react_ferramentas.ipynb` |
| `notebooks/05_integrador_evaluacion.ipynb` | `notebooks/05_integrador_avaliacao.ipynb` |
| `docs/arquitectura.mmd` | `docs/arquitetura.mmd` |
| rastros `X_antes.json`, `X_sin_plan.json` (execuções históricas em espanhol) | sem mudança de nome nem de conteúdo |
| `storage/catalogos`, `storage/memoria.sqlite3`, `storage/evidencias` | sem mudança |
| `tests/test_orquestadores.py` | `tests/test_orquestradores.py` |
| `tests/test_precios.py` | `tests/test_precos.py` |
| `tests/test_citas_ancladas.py` | `tests/test_citacoes_ancoradas.py` |
| `tests/test_salida_estructurada.py` | `tests/test_saida_estruturada.py` |

## Contratos (`contracts.py`)

| Antes | Depois |
|---|---|
| `Solicitud` | `Solicitacao` |
| `.producto_id` / `.producto` | `.produto_id` / `.produto` |
| `.cantidad` | `.quantidade` |
| `.presupuesto_centavos` | `.orcamento_centavos` |
| `.plazo_max_dias` | `.prazo_max_dias` |
| `.origen_preferido` | `.origem_preferida` |
| `.validar_producto()` / `.faltantes()` | `.validar_produto()` / `.faltantes()` |
| valores de faltantes `"producto"`, `"cantidad"` | `"produto"`, `"quantidade"` |
| `Extraccion` / `ExtraccionRazonada` | `Extracao` / `ExtracaoRaciocinada` |
| `.intencion` / `.solicitud` / `.razonamiento` | `.intencao` / `.solicitacao` / `.raciocinio` |
| intenções `"consultar","comparar","politica","cep","preferencia","otro"` | `"consultar","comparar","politica","cep","preferencia","outro"` |
| `Oferta.proveedor_id` / `.proveedor_nombre` | `.fornecedor_id` / `.fornecedor_nome` |
| `.precio_unitario_centavos` / `.flete_centavos` | `.preco_unitario_centavos` / `.frete_centavos` |
| `.stock` / `.plazo_dias` / `.pedido_minimo` / `.nacional` | `.estoque` / `.prazo_dias` / `.pedido_minimo` / `.nacional` |
| `.meses_historial` | `.meses_historico` |
| `.precio_anterior_centavos`, `_medio_`, `_minimo_`, `_maximo_` | `.preco_anterior_centavos`, `preco_medio_centavos`, `preco_minimo_centavos`, `preco_maximo_centavos` |
| `Alternativa.cumple` / `.motivos` | `.atende` / `.motivos` |
| motivos `"stock","pedido_minimo","plazo","presupuesto"` | `"estoque","pedido_minimo","prazo","orcamento"` |
| `Evidencia.fuente_id` / `.texto` / `.tipo` | `.fonte_id` / `.texto` / `.tipo` |
| tipos de evidência `"catalogo","politica","viacep","memoria"` | sem mudança |
| `RespuestaCompra` | `RespostaCompra` |
| `.estado` / `.solicitud` / `.alternativas` / `.evidencias` / `.mensaje` | `.estado` / `.solicitacao` / `.alternativas` / `.evidencias` / `.mensagem` |
| estados `"aclaracion","recomendacion","sin_oferta","sin_evidencia","cep","politica","preferencia","catalogo"` | `"esclarecimento","recomendacao","sem_oferta","sem_evidencia","cep","politica","preferencia","catalogo"` |
| origem `"nacional","internacional"`; `modo_cep` `"real","simulado"` | sem mudança |

## Funções, classes e constantes públicas

| Módulo | Antes → Depois |
|---|---|
| catalog | `Escenario`→`Cenario` (`.ruta`→`.caminho`); `crear_escenario`→`criar_cenario`; `abrir_escenario`→`abrir_cenario`; `conectar`; `buscar`; `listar`; `ficha`; `ofertas`; `_resumen_historial`→`_resumo_historico` |
| business | `comparar`; `brl`; `describir_motivos`→`descrever_motivos`; `describir_precio`→`descrever_preco`; `origen_preferido`→`origem_preferida`; `variacion_porcentual`→`variacao_percentual`; `ETIQUETAS_MOTIVO`→`ROTULOS_MOTIVO` |
| verification | `verificar`; `respuesta_local`→`resposta_local`; `mejor_sin_preferencia`→`melhor_sem_preferencia`; `anclar_cita(s)`→`ancorar_citacao`/`ancorar_citacoes`; `anclar_cep`→`ancorar_cep`; `anclar_preferencia`→`ancorar_preferencia`; `anclar_recomendacion`→`ancorar_recomendacao`; `anclar_catalogo`→`ancorar_catalogo`; `CAMPOS_DEL_SISTEMA`→`CAMPOS_DO_SISTEMA`; `CAMPOS_SOLICITUD`→`CAMPOS_SOLICITACAO`; `COBERTURA_MINIMA_CITA`→`COBERTURA_MINIMA_CITACAO`; `LONGITUD_MINIMA_CITA`→`COMPRIMENTO_MINIMO_CITACAO`; `FILAS_VISIBLES`→`LINHAS_VISIVEIS` |
| nli | `Clasificador`→`Classificador` (`.clasificar`→`.classificar`); `ModeloNLI`; `verificar_nli`; `MODELO`; `REVISION`→`REVISAO` |
| precios → **o módulo passa a `precos.py`** | `senal_precio`→`sinal_preco`; `SenalPrecio`→`SinalPreco` (`.proveedor`→`.fornecedor`, `.nivel`, `.frente_a_media`, `.frente_a_mes_anterior`, `.en_minimo`→`.no_minimo`, `.en_maximo`→`.no_maximo`); `hechos_de_precio`→`fatos_de_preco`; `aviso_de_precio`→`aviso_de_preco`; `ConsejoCompra`→`ConselhoCompra` (`.consejo`→`.conselho`); `crear_consejero`→`criar_conselheiro`; `verificar_consejo`→`verificar_conselho`; `aconsejar`→`aconselhar`; `UMBRAL_NOTABLE`→`LIMIAR_NOTAVEL`; `UMBRAL_FUERTE`→`LIMIAR_FORTE`; `MARGEN_ALTERNATIVA`→`MARGEM_ALTERNATIVA`; fontes `"consejo verificado"`→`"conselho verificado"`, `"aviso fijo"`→`"aviso fixo"`, `"nada que avisar"`→`"nada a avisar"` |
| query | `PlanConsulta`→`PlanoConsulta` (`.objetivo`, `.produto_id`, `.limite`); `ConsultaSQL` (`.sql`, `.explicacion`→`.explicacao`); `ConsultaRechazada`→`ConsultaRejeitada`; `planear`→`planejar`; `ejecutar`→`executar`; `validar_sql`; `consultar_sql`; `crear_generador_sql`→`criar_gerador_sql`; `responder_sql`; `describir_esquema`→`descrever_esquema`; `ESQUEMA_PERMITIDO`; `FUNCIONES_PERMITIDAS`→`FUNCOES_PERMITIDAS`; `MAX_FILAS`→`MAX_LINHAS`; `MAX_PASOS`→`MAX_PASSOS`; estado `"sin_filas"`→`"sem_linhas"`; chave `"filas"`→`"linhas"` |
| rag | `cargar_indice`→`carregar_indice` (`origen_confiable`→`origem_confiavel`); `consultar`; `inspeccionar_indice`→`inspecionar_indice`; `diagnosticar_reescritura`→`diagnosticar_reescrita` |
| policy_demo | `crear_indice_demo`→`criar_indice_demo`; `fragmentos_demo`; `huella_corpus`→`impressao_corpus`; `reescribir_consulta_entrega`→`reescrever_consulta_entrega`; `FRAGMENTO_T24_ESPERADO`; `PREGUNTA_T24_ORIGINAL`→`PERGUNTA_T24_ORIGINAL`; `PREGUNTA_T24_REESCRITA`→`PERGUNTA_T24_REESCRITA`; `SOLAPAMIENTO`→`SOBREPOSICAO`; `TAMANO_FRAGMENTO`→`TAMANHO_FRAGMENTO`; `ORIGEN`→`ORIGEM`; `POLITICAS`; `CORPUS` |
| integrations | `consultar_cep(cep, cliente, simulado)` sem mudança |
| memory | `Historial`→`Historico` (`.todos()`); `nueva_sesion`→`nova_sessao`; `sesiones`→`sessoes`; `dataset_sesion`→`dataset_sessao`; `guardar_borrador`→`salvar_rascunho`; `leer_borrador`→`ler_rascunho`; `guardar_preferencia`→`salvar_preferencia` (`clave`→`chave`, `valor`, `explicita`); `preferencias`; `guardar_episodio`→`salvar_episodio`; `actualizar_episodio`→`atualizar_episodio`; `recuperar`; `tiene_episodios`→`tem_episodios`; `mapa_memorias`; `preparar`; `Embedder`/`FastEmbedder` (`.modelo`, `.version`→`.versao`); `MODELO_RECUERDOS`→`MODELO_LEMBRANCAS`; `VERSION_RECUERDOS`→`VERSAO_LEMBRANCAS`; `VENTANA_MENSAJES`→`JANELA_MENSAGENS`; tabelas da memória `sesiones`→`sessoes`, `mensajes`→`mensagens`, `preferencias`, `episodios`, `borradores`→`rascunhos`; a preferência de origem é salva com uma chave que contém `"fornecedor"` (antes `"proveedor"`) |
| dialogue | `EstadoCompra` (`.solicitacao`, `.esperando`); `CambioSolicitud`→`MudancaSolicitacao` (`.es_compra`→`.e_compra`, `.quantidade`, `.orcamento_centavos`, `.prazo_max_dias`, `.quitar`→`.remover`); `crear_interprete`→`criar_interprete`; `interpretar_compra`; `interpretar_turno`; `PALABRAS_IGNORADAS`→`PALAVRAS_IGNORADAS`; fonte `"reglas"`→`"regras"` |
| planner | `Peticion`→`Pedido` (`.tipo`, `.peticion`→`.pedido`); `PlanTurno`→`PlanoTurno` (`.peticiones`→`.pedidos`); `crear_planificador`→`criar_planejador`; `intenciones_detectadas`→`intencoes_detectadas`; `planificar_turno`→`planejar_turno`; `validar_plan`→`validar_plano`; `MAX_PETICIONES`→`MAX_PEDIDOS`; `SENALES`→`SINAIS` |
| prompts | `PLANTILLA_X`→`MODELO_X`: `MODELO_EXTRACAO`, `MODELO_EXTRACAO_FEWSHOT`, `MODELO_EXTRACAO_COT`, `MODELO_REPARO`, `MODELO_SQL`, `MODELO_MUDANCA`, `MODELO_CONSELHO`, `MODELO_PLANO`, `MODELO_AGENTE`; `EJEMPLOS_ACCIONES`→`EXEMPLOS_ACOES`; `EJEMPLOS_CAMBIO`→`EXEMPLOS_MUDANCA`; `EJEMPLOS_EXTRACCION`→`EXEMPLOS_EXTRACAO`; `_SISTEMA_EXTRACCION`→`_SISTEMA_EXTRACAO` |
| agent | `Traza`→`Rastro` (`.eventos`, `.registrar_citas`→`.registrar_citacoes`, `.registrar_verificacion`→`.registrar_verificacao`, `._seguro`); `herramientas`→`ferramentas`; `crear_agente`→`criar_agente`; `crear_flujo`→`criar_fluxo`; `renderizar`; `renderizar_citas`→`renderizar_citacoes`; `renderizar_diagnostico_t24`; `resumen_recuperacion_t24`→`resumo_recuperacao_t24`; `resolver_entrega_parcial`; `consulta_directa`→`consulta_direta`; `es_diagnostico_t24`→`e_diagnostico_t24`; `mensaje_publico`→`mensagem_publica`; `partes_de`; `CLAVE_PARTES`→`CHAVE_PARTES`; `ESTADOS_SIN_DATOS_DE_CATALOGO`→`ESTADOS_SEM_DADOS_DE_CATALOGO`; parâmetros `escenario`→`cenario`, `memoria_db`, `mensaje_actual`→`mensagem_atual`, `clasificador`→`classificador`, `indice`, `cep_simulado`, `traza`→`rastro`, `consejo`→`conselho`, `titulo`, `respuesta`→`resposta`, `pregunta`→`pergunta` |
| agent · ferramentas do modelo | `buscar_productos`→`buscar_produtos`; `consultar_catalogo`; `comparar_ofertas`; `consultar_politicas`; `consultar_cep`; `guardar_preferencia`→`salvar_preferencia` (`clave`→`chave`, `valor`, `cita_usuario`→`citacao_usuario`) |
| agent · partes da mensagem | chaves `"partes"`, `"titulo"`, `"texto"`, `"comparacion"`→`"comparacao"`, `"consejo"`→`"conselho"` |
| chains | `crear_chain`→`criar_chain`; `crear_chain_robusta`→`criar_chain_robusta`; `crear_lcel`→`criar_lcel`; `crear_lcel_parcial`→`criar_lcel_parcial`; `crear_lcel_robusta`→`criar_lcel_robusta`; `crear_variantes_de_prompt`→`criar_variantes_de_prompt`; `composicion_paralela`→`composicao_paralela`; `_json_completo`; `_validar` |
| laboratorio | `ensayar`→`ensaiar`; `comparar_estilos`; `SALIDAS_ROTAS`→`SAIDAS_QUEBRADAS`; `CORRECTA`→`CORRETA`; `DATOS`→`DADOS`; `SOLICITUD`→`SOLICITACAO` |
| legacy | `crear_react_textual`→`criar_react_textual` (`memoria_en_prompt`→`memoria_no_prompt`); `crear_chatbot_buffer`→`criar_chatbot_buffer`; `crear_router_llm`→`criar_router_llm`; `ejecutar_ruta`→`executar_rota`; `RouterCompras`; `DESTINOS`; `PLANTILLA_CHATBOT`→`MODELO_CHATBOT`; `SUFIJO_CON_MEMORIA`→`SUFIXO_COM_MEMORIA`; rotas `"comparacion"`→`"comparacao"`, `"catalogo"`, `"cep"`; chave `"ruta"`→`"rota"` |
| orquestradores | `herramientas_basicas`→`ferramentas_basicas`; `agente_langchain`; `agente_langgraph`; `agente_con_langmem`→`agente_com_langmem`; `SISTEMA` |
| anatomia | `describir_anatomia`→`descrever_anatomia`; `inventario_langchain(raiz)`; `MODELO_LLM_POR_DEFECTO`→`MODELO_LLM_PADRAO`; `PAPELES`→`PAPEIS`; `PIEZAS_LANGCHAIN`→`PECAS_LANGCHAIN`; chave `"base_conocimiento"`→`"base_conhecimento"` |
| app | `nuevo_chat`→`novo_chat`; `nuevo_escenario`→`novo_cenario`; `reabrir`; `sugerir`; `origen`→`origem`; `frente_a_media`; `tabla_de_ofertas`→`tabela_de_ofertas`; `mostrar_comparacion`→`mostrar_comparacao`; `mostrar_mensaje`→`mostrar_mensagem`; `describir_paso`→`descrever_passo`; `mostrar_paso`→`mostrar_passo`; `PasosEnVivo`→`PassosAoVivo`; `preparar_agente`; `indice_politicas`; `indice_politicas_demo`; `modelo_nli`; `ANCLAJES`→`ANCORAGENS`; `HERRAMIENTAS`→`FERRAMENTAS`; `CATALOGOS`; `MEMORIA`; `USUARIO`; `CONVERSACIONES_VISIBLES`→`CONVERSAS_VISIVEIS`; chaves de `st.session_state`: `escenario`→`cenario`, `sesion`→`sessao`, `error_escenario`→`erro_cenario`, `pasos`→`passos`, `sugerida`, `pregunta`→`pergunta` |

## Radicais (para variáveis locais, chaves e textos)

| Espanhol | Português |
|---|---|
| solicitud | solicitacao |
| respuesta | resposta |
| pregunta | pergunta |
| mensaje(s) | mensagem / mensagens |
| producto(s) | produto(s) |
| pieza(s) | peca(s) / peça(s) |
| proveedor(es) | fornecedor(es) |
| cantidad | quantidade |
| presupuesto | orcamento / orçamento |
| plazo | prazo |
| flete | frete |
| stock | estoque |
| precio(s) | preco(s) / preço(s) |
| importe | valor |
| ganador | vencedor |
| descartada | descartada |
| cumple | atende |
| origen | origem |
| historial | historico / histórico |
| consejo | conselho |
| aviso | aviso |
| señal / senal | sinal |
| hechos | fatos |
| cifras | numeros / números |
| escenario | cenario / cenário |
| sesion | sessao / sessão |
| borrador | rascunho |
| recuerdo(s) | lembranca(s) / lembrança(s) |
| herramienta(s) | ferramenta(s) |
| traza | rastro |
| paso(s) | passo(s) |
| turno | turno |
| petición / peticion | pedido |
| plan | plano |
| planificador | planejador |
| intención | intencao / intenção |
| extracción | extracao / extração |
| razonamiento | raciocinio / raciocínio |
| aclaración | esclarecimento |
| cita(s) | citacao / citacoes (citação / citações) |
| anclar / anclaje | ancorar / ancoragem |
| fuente | fonte |
| fragmento | fragmento |
| huella | impressao (impressão digital) |
| índice | indice / índice |
| política(s) | politica(s) / política(s) |
| devoluciones | devolucoes / devoluções |
| garantía | garantia |
| entrega parcial | entrega parcial |
| consulta | consulta |
| fila(s) | linha(s) |
| clave | chave |
| valor | valor |
| salida | saida / saída |
| entrada | entrada |
| error(es) | erro(s) |
| rechazada / rechazo | rejeitada / rejeicao |
| reparación / reparador | reparo / reparador |
| plantilla | modelo (de prompt) |
| ejemplo(s) | exemplo(s) |
| cadena | cadeia |
| crear | criar |
| guardar | salvar |
| leer | ler |
| cargar | carregar |
| ejecutar | executar |
| describir | descrever |
| mostrar | mostrar |
| evaluar / evaluación | avaliar / avaliacao |
| caso(s) | caso(s) |
| trayectoria | trajetoria / trajetória |
| doble (de prueba) | duplo (de teste) |
| prueba(s) | teste(s) |
| evidencia(s) | evidencia(s) / evidência(s) |
| rúbrica(s) | rubrica(s) / rubrica(s) |
| informe | relatorio / relatório |
| nevera(s) | geladeira(s) |
| lavadora | lavadora |
| ruta (de arquivo) | caminho |
| ruta (do router) | rota |
| carpeta | pasta |
| usuario | usuario / usuário |
| sin / con | sem / com |
| antes / después | antes / depois |

## Dados do catálogo (já regenerados)

O catálogo foi regenerado em português com a mesma semente: preços, ofertas, estoque, prazos e
fornecedores são idênticos; mudam só nomes, famílias e SKUs.

| Antes | Depois |
|---|---|
| categoria `Neveras` | `Geladeiras` |
| `Compresor para Neveras NEVE-COMP-0001` (PEC-01-0001) | `Compressor para Geladeiras GELA-COMP-0001` |
| SKU `NEVE-XXXX-nnnn` | `GELA-XXXX-nnnn` |
| famílias: compresor, puerta, sello, bisagra, cajon, correa, polea, quemador, perilla, rejilla, encendedor, horno, vidrio, cable, brazo, manguera, plato, fusible, control | compressor, porta, vedacao, dobradica, gaveta, correia, polia, queimador, botao, grade, acendedor, forno, vidro, cabo, braco, mangueira, prato, fusivel, controle |
| categorias: Hornos, Secadoras de ropa, Lavalouças, Forno micro-ondas, Ar condicionados | Fornos, Secadoras de roupa, Lava-louças, Fornos micro-ondas, Ar-condicionados |
| `PEC-02-0189` | `Ventilador para Congeladores CONG-VENT-0189` (igual) |

Em 2026-11-11 o catálogo foi ampliado com sete categorias, que já nasceram em português (não
têm nome anterior em espanhol). As peças PEC-01 a PEC-11 não mudaram.

| ID | Categoria (`slug`) | Prefixo do SKU |
|---|---|---|
| PEC-12 | Aspiradores de pó (`aspiradores`) | `ASPI` |
| PEC-13 | Liquidificadores (`liquidificadores`) | `LIQU` |
| PEC-14 | Cafeteiras (`cafeteiras`) | `CAFE` |
| PEC-15 | Purificadores de água (`purificadores`) | `PURI` |
| PEC-16 | Ventiladores (`ventiladores`) | `VENT` |
| PEC-17 | Ferros de passar (`ferros`) | `FERR` |
| PEC-18 | Fritadeiras elétricas (`fritadeiras`) | `FRIT` |

Famílias novas: bocal, escova, interruptor, rodizio, saco, acoplamento, base, copo, lamina, tampa,
jarra, reservatorio, suporte, torneira, bucha, eixo, helice, cesto.

## Fonte de verdade para o resto

Os nomes que não aparecem aqui (chaves de dicionários, eventos do rastro, textos de erro) estão definidos no código já traduzido de `src/pedro/` e `app.py`: leia o módulo antes de escrever um teste, script ou documento que os use.
