# Comparaciones técnicas

## LangChain y Semantic Kernel

Ambos permiten que un modelo solicite funciones y que la aplicación ejecute código con argumentos estructurados. [Semantic Kernel](https://learn.microsoft.com/en-us/semantic-kernel/concepts/ai-services/chat-completion/function-calling) organiza funciones como plugins de un `Kernel`; LangChain usa `Runnable`, prompts, herramientas y agentes. ComprasLab usa LangChain porque la consigna exige sus APIs concretas y los notebooks deben demostrar sus cadenas, agentes y memoria. Semantic Kernel se documenta como alternativa arquitectónica; no se presenta como implementación del requisito.

## LangMem y Mem0

| Aspecto | LangMem | Mem0 | Decisión en ComprasLab |
|---|---|---|---|
| Arquitectura | Herramientas y gestores de memoria, con integración nativa a LangGraph | Capa de memoria que extrae, deduplica y recupera recuerdos | SQLite y un índice de recuerdos propio para distinguir explícitamente los tipos CoALA |
| Persistencia | Usa el almacén conectado; no obliga a un backend único | Ofrece plataforma administrada y opción abierta con almacenamiento configurable | SQLite local fuera de los catálogos |
| Recuperación | Búsqueda y gestión de recuerdos mediante herramientas/gestores | Búsqueda semántica e híbrida según configuración | Recuperación vectorial separada del índice de políticas, aún pendiente |
| Integración | Cercana al ecosistema LangChain/LangGraph | API de memoria independiente del agente | Ninguna dependencia adicional hasta validar el flujo base |

Fuentes primarias: [LangMem](https://github.com/langchain-ai/langmem/blob/main/README.md), [Mem0](https://github.com/mem0ai/mem0/blob/main/skills/mem0/references/architecture.md). La comparación describe sus interfaces documentadas; no es una medición de calidad.
