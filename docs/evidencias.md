# Registro de evidencias

Fecha de ejecución: 2026-11-08, America/Sao_Paulo. Plataforma: Linux 6.6.114.1 WSL2 x86_64, Python 3.13.9. Versiones: Streamlit 1.67.0, langchain-core 1.7.6, langchain-classic 1.0.8, FastEmbed 0.9.1, Transformers 4.57.6, PyTorch 2.15.0. Los comandos se ejecutaron en este proyecto independiente. La base de origen es sintética, semilla 20261107; SHA-256 de la base regenerada: `2494d0c5173dc2914e8dfe487f43572dbef51bc6496e6e3d82e714e38333348b`.

| IDs provisionales | Modo | Entrada y comando | Salida observada | Fuente / traza |
|---|---|---|---|---|
| R1.1–R1.3 | local | uv run pytest -q; creación de escenario | 2640 piezas, 7920 ofertas, 7920 compatibilidades, 47520 precios históricos; UUID y SHA-256 en manifiesto | tests/test_core.py; storage/catalogos o almacenamiento temporal |
| R1.4–R1.5 | prueba | NB01, doble RunnableLambda | @chain y LCEL devuelven JSON; invoke, batch y stream ejecutados | notebooks/01_chain_mvp.ipynb |
| R2.1 | prueba | cantidad 2, presupuesto 220 centavos y plazo 7 | total 220; empate resuelto por proveedor; límites inclusivos | tests/test_core.py |
| R2.2–R2.3 | prueba | NB02, FakeListLLM y RouterCompras | ruta catálogo/comparación y trayectoria ReAct con herramienta | notebooks/02_react_herramientas.ipynb |
| R2.4 | real | uv run python -c 'from pedro.integrations import consultar_cep; print(consultar_cep("01001000"))' | estado ok; São Paulo/SP; modo real; ViaCEP:01001000 | ViaCEP, respuesta HTTP observada en consola |
| R2.4 | prueba | consultar_cep("01001000", simulado=True) | Cidade Simulada/SP; modo simulado | notebooks/02_react_herramientas.ipynb |
| R3.1–R3.3 | prueba | uv run pytest -q | aislamiento usuario, 12 mensajes visibles al agente, historial completo y preferencias | tests/test_memory_nli.py |
| R3.4–R3.5 | real local | FastEmbed multilingual-MiniLM-L12-v2, guardar/actualizar/recuperar | dimensión 384; antes «prefiero proveedor nacional» similitud 0.633; después «acepto proveedor internacional» 0.674; otro usuario vacío; recuperación entre sesiones 0.674 frente a 0.113 | storage/evidencias/recuerdos.sqlite3; notebooks/03_memoria_chatbot.ipynb |
| R4.1–R4.2 | prueba | planear y ejecutar «ofertas PEC-01-0001» | SELECT parametrizado, 3 filas; seis herramientas tipadas | tests/test_tools_flow.py; notebooks/04_rag_text_to_query.ipynb |
| R5.2, R5.4 | prueba | JSON inválido seguido de propuesta válida | dos intentos; solo petición y respuesta final en historial | tests/test_tools_flow.py |
| R5.3 | real local | ModeloNLI, tres pares: entrega en 5 días igual, en 10 días, pieza azul | entailment, contradiction, neutral | modelo MoritzLaurer/mDeBERTa-v3-base-mnli-xnli, revisión 8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c |
| R5.2–R5.3 | real local | RespuestaCompra calculada para 2 × PEC-01-0001, presupuesto R$ 100000 y plazo 60 días | verificador sin errores; BR-06; NLI true | modelo NLI fijado y escenario activo; consola local |
| R5.3 | prueba | clasificador guionado con tres etiquetas | solo entailment permite publicar recomendación | tests/test_memory_nli.py |
| R5.5 | local | Streamlit Agent API en 127.0.0.1:8767; chat «lista piezas»; catálogo; comparación PEC-01-0001, 2 unidades, R$ 100000, 60 días | status ready en tres vistas; listado 20; BR-06 R$ 2.963,07; sin excepciones | snapshot de Agent API; consola Streamlit |
| R3.1, R5.5 | local y prueba | Agent API: «Compara PEC-01-0001» → «2» → «ahora 3 unidades»; uv run pytest -q | pregunta solo cantidad; BR-06 R$ 2.963,07 para dos y R$ 4.401,99 para tres; borrador aislado por sesión; 24/24 pruebas | snapshot Agent API; tests/test_dialogue.py; tests/test_tools_flow.py |
| R4.3–R5.5 | prueba | 30 referencias derivadas; verificación de políticas y CEP con dobles | 30 casos preparados (14 recomendaciones, 5 sin oferta, 4 aclaraciones, 3 catálogo, 2 CEP, 2 políticas sin índice); ningún resultado remoto | evals/casos_derivados.json; tests/test_policy_cep.py; tests/test_evals.py |
| R1–R5 | local | uv sync --python 3.13 --all-extras --locked; uv run pytest -q; ejecución NotebookClient | sincronización correcta; 24/24 pruebas actuales; 5/5 notebooks en la ejecución anterior | uv.lock; tests/; notebooks/ |

La prueba NLI real verifica solo tres pares ilustrativos; no mide exactitud general. La clasificación real y la verificación exacta son puertas separadas. El modelo y la revisión corresponden a la ficha oficial: https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-mnli-xnli .

## Dependencias aún pendientes

- PDF oficial infnet_agentes.pdf: no disponible; la matriz sigue provisional y no se afirma cotejo de las páginas 1–8.
- Índice FAISS autorizado: no disponible; sin prueba de recuperación fallida, reescrita ni consulta sin cobertura.
- OPENAI_API_KEY y LANGSMITH_API_KEY en este workspace: ausentes; no hay chat real ni experimento remoto. El script evals/evaluar_flujo.py terminó explícitamente con «Faltan OPENAI_API_KEY y LANGSMITH_API_KEY; sin evaluación remota».
- Vídeo con webcam y enlace Drive institucional: requieren grabación y acceso del alumno.
