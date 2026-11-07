# Revisión EGM Goldfish, ronda 1

Dos revisores independientes leyeron `docs/implementation_plan.md` con las personas `implementation_readiness` y `codebase_details` y el estándar de preparación para implementar. Ambos informaron **no aprobado**. La revisión no ha convergido ni acredita el plan completo.

| ID | Severidad | Hallazgo | Resolución |
|---|---|---|---|
| readiness-1 / codebase-1 | Bloqueante | Enunciado, kit e índice FAISS ausentes impiden aceptación académica completa. | Registrar bloqueo; implementar y probar solo componentes independientes; cotejar la rúbrica al recibir insumos. |
| readiness-2 / codebase-3 | Bloqueante | Contratos Pydantic, herramientas e interfaces agente-verificador sin campos. | Definir contratos concretos antes de integrar. |
| readiness-3 / codebase-4 | Mayor | Esquema, generación y ciclo de datos insuficientes. | Especificar y probar DDL, semilla y reglas de identidad. |
| readiness-4 / codebase-5 | Mayor | Flujo, errores, corrección y publicación insuficientes. | Definir estados y punto único de publicación. |
| readiness-5 / codebase-6 | Mayor | Índice, SQL y NLI sin contrato reproducible. | Aislar como puertas de aceptación pendientes y definir validadores. |
| readiness-7 / codebase-2 | Mayor | Hitos carecen de pasos y archivos precisos. | Añadir inventario de archivos y seguimiento por hito. |
| readiness-8 / codebase-8 | Mayor | Pruebas sin entradas/salidas concretas. | Crear pruebas de reglas y escenario local; evaluación real sigue pendiente. |
| codebase-9 | Mayor | El conteo de 30 escenarios era ambiguo. | Son 20 derivados + 10 adicionales; los 20 originales se conservan aparte. |

La primera revisión alimenta la implementación. No se simula una segunda ronda limpia: requerirá documento actualizado y revisión nueva.
