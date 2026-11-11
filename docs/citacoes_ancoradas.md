# Citas ancladas: diagnóstico y corrección de un fallo de respaldo

Fecha: 2026-11-10. Modelo: ChatOpenAI `gpt-4.1-mini`. NLI real local. Corpus de políticas ficticio.

Este documento registra un fallo real observado con el modelo remoto, su diagnóstico y la corrección. Sirve de evidencia para **R24** (verificación integrada), **R12** (confiabilidad con tratamiento de errores) y, como apoyo, para el tema **T26** (qué hace el agente cuando los documentos recuperados no respaldan la respuesta). No sustituye a R23, que trata un fallo de *recuperación*.

## 1. Fallo observado

Pregunta: «¿Qué dice la política de devoluciones sobre piezas dañadas?»

| | Antes |
|---|---|
| Herramienta llamada | `consultar_politicas` (dos propuestas) |
| Fragmentos recuperados | Correctos, de `devoluciones.md` |
| Respuesta publicada | «No pude verificar la respuesta sobre políticas…» |
| Traza | [trazas/r02_planificacion_llm_antes.json](trazas/r02_planificacion_llm_antes.json) |

## 2. Diagnóstico

La recuperación **no** falló: el fragmento correcto estaba entre los devueltos. Falló el paso siguiente, el respaldo de la cita.

- La verificación exigía que el texto citado por el modelo fuera idéntico, carácter por carácter, al fragmento.
- El modelo copió el fragmento casi entero, con una diferencia mínima (cobertura observada después: 0,998). Los fragmentos se cortan a 700 caracteres y terminan sin punto final; el modelo tiende a «completarlos».
- Resultado: errores `fragmento no corresponde` y `fuente no recuperada` en las dos propuestas. No se publicó nada falso, pero el usuario se quedó sin respuesta.

El defecto de diseño era pedirle al modelo una tarea mecánica (copiar texto sin cambiar un carácter) y castigarlo con un rechazo total.

## 3. Corrección: el modelo elige la fuente, el sistema pone el texto

Se añadieron tres piezas, todas deterministas:

1. **Anclaje de citas** (`anclar_citas` en [verification.py](../src/pedro/verification.py)). Antes de verificar, cada cita se busca dentro del fragmento que la herramienta recuperó en ese turno. Si coincide al menos en un 80 %, se sustituye por el tramo literal del fragmento. El texto final siempre sale de la fuente, nunca del modelo.
2. **Cuatro estados registrados en la traza**: `literal`, `reanclada`, `por_identificador` (cita vacía con fuente válida) y `rechazada` o `fuente_no_recuperada`. Una cita inventada no alcanza el umbral y la verificación exacta la sigue bloqueando.
3. **Degradación extractiva.** Si las citas son válidas pero el resumen del modelo no obtiene *entailment* en NLI tras la corrección, se publica solo el texto literal de la fuente con su identificador, sin el resumen.

La verificación exacta y el NLI no se relajaron: siguen siendo la puerta. El anclaje solo evita rechazar citas que ya eran correctas.

| Situación | Antes | Ahora |
|---|---|---|
| Cita literal y resumen respaldado | Publica | Publica |
| Cita casi literal y resumen respaldado | **Rechaza** | Reancla y publica |
| Cita válida y resumen sin respaldo NLI | Rechaza | Publica solo la cita textual |
| Cita inventada | Rechaza | Rechaza |

## 4. Resultado tras la corrección

Misma pregunta, mismo índice, mismo modelo.

| | Después |
|---|---|
| Primera propuesta | 3 citas `reanclada` (cobertura 0,998); el resumen no pasó NLI |
| Segunda propuesta | 2 citas `literal`; el resumen obtuvo *entailment* |
| Respuesta publicada | Resumen de la política con fuentes `FIC-DEV-01-S05-C01` y `FIC-GAR-01-S05-C01` |
| Traza | [trazas/r02_planificacion_llm.json](trazas/r02_planificacion_llm.json) |

## 5. Evidencia

| Evidencia | Tipo |
|---|---|
| Trazas antes y después con el modelo real | Real remoto puntual (una ejecución cada una) |
| [tests/test_citas_ancladas.py](../tests/test_citas_ancladas.py): cita casi literal se reancla; cita inventada o muy corta se rechaza; el chat publica, degrada a cita textual o bloquea según el caso | Pruebas con doble (executor y NLI guionados) |

## 6. Limitaciones

- Una ejecución antes y otra después no miden una tasa de éxito; la medición corresponde a R29.
- La degradación extractiva está probada con dobles; no se observó en la ejecución real.
- El umbral del 80 % se fijó por criterio, sin calibrarlo con datos.
- El modelo NLI admite 512 tokens: con varias citas largas la premisa se trunca (se observó un aviso de 652 tokens).
- Cuando se escribió este diagnóstico, una solicitud mixta en un solo turno no se publicaba; se resolvió después con el planificador de turno (R02).
