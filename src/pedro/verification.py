"""Puerta de publicación independiente del agente generador."""
from difflib import SequenceMatcher

from .business import comparar
from .catalog import Escenario, buscar, ofertas
from .contracts import Alternativa, RespuestaCompra


def verificar(respuesta: RespuestaCompra, escenario: Escenario, *, indice=None,
             observaciones: list[tuple[str, dict]] | None = None) -> list[str]:
    errores = []
    if respuesta.dataset_id != escenario.dataset_id:
        return ["dataset ajeno"]
    if respuesta.estado == "aclaracion":
        ambiguo = bool(respuesta.solicitud.producto and
                       len(buscar(escenario, respuesta.solicitud.producto, 2)) > 1)
        return [] if respuesta.solicitud.faltantes() or ambiguo else ["aclaración injustificada"]
    if respuesta.estado == "sin_evidencia":
        return []
    if respuesta.estado == "catalogo":
        consultas = [dato for nombre, dato in (observaciones or [])
                     if nombre == "consultar_catalogo" and dato.get("modo") == "sql"]
        if not consultas:
            return ["consulta al catálogo no observada"]
        ultima = consultas[-1]
        if ultima.get("dataset_id") != escenario.dataset_id:
            return ["dataset ajeno"]
        return [] if ultima.get("estado") in ("ok", "sin_filas") else ["consulta rechazada"]
    if respuesta.estado == "preferencia":
        guardada = any(nombre == "guardar_preferencia" and dato.get("estado") == "ok"
                       for nombre, dato in (observaciones or []))
        return [] if guardada else ["preferencia no guardada"]
    if respuesta.estado == "cep":
        cep = respuesta.solicitud.cep
        if not cep or not respuesta.cidade or not respuesta.uf or not respuesta.modo_cep:
            return ["ubicación incompleta"]
        fuentes = [e for e in respuesta.evidencias if e.tipo == "viacep"
                   and e.fuente_id == f"ViaCEP:{cep}"]
        if not fuentes:
            return ["falta evidencia ViaCEP"]
        if not any(nombre == "consultar_cep" and dato.get("estado") == "ok" and
                   dato.get("cep") == cep and dato.get("cidade") == respuesta.cidade and
                   dato.get("uf") == respuesta.uf and dato.get("modo") == respuesta.modo_cep
                   for nombre, dato in (observaciones or [])):
            return ["ubicación no coincide con ViaCEP"]
        return []
    if respuesta.estado == "politica":
        if indice is None or not respuesta.mensaje.strip():
            return ["política sin índice o afirmación"]
        fuentes = [e for e in respuesta.evidencias if e.tipo == "politica" and e.fuente_id]
        if not fuentes:
            return ["política sin evidencia"]
        for evidencia in fuentes:
            doc = indice.docstore.search(evidencia.fuente_id)
            if not hasattr(doc, "page_content") or not evidencia.texto or evidencia.texto not in doc.page_content:
                errores.append(f"fragmento no corresponde: {evidencia.fuente_id}")
        if observaciones is not None:
            recuperados = {
                fragmento.get("fuente_id"): fragmento.get("texto", "")
                for nombre, dato in observaciones if nombre == "consultar_politicas"
                for fragmento in dato.get("fragmentos", [])
                if isinstance(fragmento, dict)
            }
            if not recuperados:
                errores.append("política sin recuperación observada")
            for evidencia in fuentes:
                if evidencia.texto not in recuperados.get(evidencia.fuente_id, ""):
                    errores.append(f"fuente no recuperada: {evidencia.fuente_id}")
        return errores
    if respuesta.solicitud.faltantes() or not respuesta.producto_id:
        return ["solicitud incompleta"]
    if respuesta.producto_id != respuesta.solicitud.producto_id:
        errores.append("producto incoherente")
    oficiales = ofertas(escenario, respuesta.producto_id)
    esperadas = comparar(respuesta.solicitud, oficiales)
    por_id = {a.oferta.id: a for a in esperadas}
    actuales = {a.oferta.id: a for a in respuesta.alternativas}
    if not oficiales or len(actuales) != len(respuesta.alternativas) or set(actuales) != set(por_id):
        errores.append("ofertas incompletas")
    for oid, alternativa in actuales.items():
        if oid not in por_id or alternativa != por_id[oid]:
            errores.append(f"alternativa incoherente: {oid}")
    fuentes = {e.fuente_id for e in respuesta.evidencias
               if e.tipo == "catalogo" and e.dataset_id == escenario.dataset_id}
    if set(por_id) - fuentes:
        errores.append("evidencia incompleta")
    validas = [a for a in esperadas if a.cumple]
    if respuesta.estado == "recomendacion":
        if not validas:
            errores.append("no existe oferta válida")
        elif (respuesta.proveedor_id != validas[0].oferta.proveedor_id or
              respuesta.total_centavos != validas[0].total_centavos):
            errores.append("ganador o total incorrecto")
    elif respuesta.estado == "sin_oferta" and validas:
        errores.append("sí existe oferta válida")
    return errores


COBERTURA_MINIMA_CITA = 0.8
LONGITUD_MINIMA_CITA = 20


def anclar_cita(cita: str, fragmento: str) -> tuple[str | None, float]:
    """Localiza en el fragmento el tramo literal que corresponde a una cita casi literal.

    Devuelve el tramo copiado del fragmento y la cobertura de la cita (0 a 1). El texto
    devuelto procede siempre del fragmento, nunca de la cita.
    """
    cita = " ".join(cita.split())
    if len(cita) < LONGITUD_MINIMA_CITA or not fragmento:
        return None, 0.0
    bloques = [b for b in SequenceMatcher(None, fragmento, cita, autojunk=False)
               .get_matching_blocks() if b.size >= 4]
    cobertura = sum(b.size for b in bloques) / len(cita)
    if not bloques or cobertura < COBERTURA_MINIMA_CITA:
        return None, cobertura
    tramo = fragmento[bloques[0].a:bloques[-1].a + bloques[-1].size]
    if len(tramo) > 1.5 * len(cita) + 20:
        return None, cobertura
    return tramo, cobertura


def anclar_citas(respuesta: RespuestaCompra,
                 observaciones: list[tuple[str, dict]] | None) -> list[dict]:
    """Sustituye cada cita de política por el texto literal del fragmento recuperado.

    El modelo propone qué fuente respalda la respuesta; el texto de la evidencia lo pone
    el sistema. Una cita que no se puede anclar queda intacta y la rechazará `verificar`.
    """
    recuperados = {
        fragmento.get("fuente_id"): fragmento.get("texto", "")
        for nombre, dato in (observaciones or []) if nombre == "consultar_politicas"
        for fragmento in dato.get("fragmentos", []) if isinstance(fragmento, dict)
    }
    informe = []
    for evidencia in respuesta.evidencias:
        if evidencia.tipo != "politica":
            continue
        fragmento = recuperados.get(evidencia.fuente_id, "")
        if not fragmento:
            estado, cobertura = "fuente_no_recuperada", 0.0
        elif evidencia.texto and evidencia.texto in fragmento:
            estado, cobertura = "literal", 1.0
        elif not evidencia.texto.strip():
            evidencia.texto, estado, cobertura = fragmento, "por_identificador", 1.0
        else:
            tramo, cobertura = anclar_cita(evidencia.texto, fragmento)
            if tramo is None:
                estado = "rechazada"
            else:
                evidencia.texto, estado = tramo, "reanclada"
        informe.append({"fuente_id": evidencia.fuente_id, "estado": estado,
                        "cobertura": round(cobertura, 3)})
    return informe


def anclar_cep(respuesta: RespuestaCompra, observaciones: list[tuple[str, dict]] | None,
               dataset_id: str) -> dict | None:
    """Rellena una respuesta de CEP con lo que devolvió ViaCEP en este turno.

    El modelo decide que la respuesta es un CEP; ciudad, estado, modo y evidencia los pone
    el sistema a partir de la observación de la herramienta. Sin una observación válida la
    respuesta queda intacta y la rechazará `verificar`.
    """
    if respuesta.estado != "cep":
        return None
    validas = [dato for nombre, dato in (observaciones or [])
               if nombre == "consultar_cep" and dato.get("estado") == "ok"]
    pedido = respuesta.solicitud.cep
    dato = next((d for d in validas if d.get("cep") == pedido), None)
    if dato is None and not pedido and len({d.get("cep") for d in validas}) == 1:
        dato = validas[0]
    if dato is None:
        return {"estado": "sin_observacion_valida", "cep": pedido}
    from .contracts import Evidencia
    respuesta.solicitud.cep = dato["cep"]
    respuesta.cidade, respuesta.uf, respuesta.modo_cep = dato["cidade"], dato["uf"], dato["modo"]
    respuesta.evidencias = [Evidencia(tipo="viacep", fuente_id=f"ViaCEP:{dato['cep']}",
                                      texto=f"{dato['cidade']}/{dato['uf']}")]
    # Una respuesta de CEP no usa datos del catálogo: el escenario lo fija el sistema.
    respuesta.dataset_id = dataset_id
    return {"estado": "anclada", "cep": dato["cep"]}


CAMPOS_SOLICITUD = ("producto_id", "cantidad", "presupuesto_centavos", "plazo_max_dias")
# Lo que el sistema añade a la solicitud y el modelo no tiene por qué repetir.
CAMPOS_DEL_SISTEMA = ("origen_preferido",)


def anclar_recomendacion(respuesta: RespuestaCompra,
                         observaciones: list[tuple[str, dict]] | None) -> dict | None:
    """Sustituye las cifras de una comparación por las que calculó `comparar_ofertas`.

    El modelo decide que la respuesta es la comparación de una solicitud; el ganador, el total,
    las alternativas y las evidencias los pone el sistema con el resultado de la herramienta
    para esa misma solicitud. Si la herramienta no se llamó con esa solicitud, no se toca nada
    y la verificación exacta decide.
    """
    if respuesta.estado not in ("recomendacion", "sin_oferta"):
        return None
    pedido = tuple(getattr(respuesta.solicitud, campo) for campo in CAMPOS_SOLICITUD)
    for nombre, dato in reversed(observaciones or []):
        if nombre != "comparar_ofertas":
            continue
        try:
            calculada = RespuestaCompra.model_validate(dato)
        except ValueError:
            continue
        if tuple(getattr(calculada.solicitud, campo) for campo in CAMPOS_SOLICITUD) != pedido:
            continue
        cambios = [campo for campo in ("estado", "proveedor_id", "total_centavos", "alternativas")
                   if getattr(respuesta, campo) != getattr(calculada, campo)]
        for campo in ("estado", "dataset_id", "producto_id", "proveedor_id", "total_centavos",
                      "alternativas", "evidencias"):
            setattr(respuesta, campo, getattr(calculada, campo))
        for campo in CAMPOS_DEL_SISTEMA:
            setattr(respuesta.solicitud, campo, getattr(calculada.solicitud, campo))
        return {"estado": "anclada", "campos_corregidos": cambios}
    return {"estado": "sin_calculo_para_esa_solicitud"}


FILAS_VISIBLES = 10


def anclar_catalogo(respuesta: RespuestaCompra,
                    observaciones: list[tuple[str, dict]] | None) -> dict | None:
    """Redacta una respuesta de catálogo con las filas que devolvió la consulta SQL.

    El modelo decide que la respuesta es una consulta al catálogo; la tabla, el recuento y la
    consulta ejecutada los pone el sistema. Ningún número lo escribe el modelo.
    """
    if respuesta.estado != "catalogo":
        return None
    consulta = next((dato for nombre, dato in reversed(observaciones or [])
                     if nombre == "consultar_catalogo" and dato.get("modo") == "sql"), None)
    if consulta is None or consulta.get("estado") not in ("ok", "sin_filas"):
        return {"estado": "sin_consulta_valida"}
    from .contracts import Evidencia
    sql = consulta["intentos"][-1]["sql"]
    filas = consulta.get("filas", [])
    if not filas:
        cuerpo = "La consulta no devolvió ninguna fila; puede que esté mal planteada."
    else:
        columnas = list(filas[0])
        cuerpo = "\n".join(
            ["| " + " | ".join(columnas) + " |", "|" + "---|" * len(columnas)]
            + ["| " + " | ".join(str(fila[c]) for c in columnas) + " |"
               for fila in filas[:FILAS_VISIBLES]])
        if len(filas) > FILAS_VISIBLES or consulta.get("truncado"):
            cuerpo += f"\n\nSe muestran {min(len(filas), FILAS_VISIBLES)} de {len(filas)} filas" + (
                " (el resultado se cortó en el límite)." if consulta.get("truncado") else ".")
    respuesta.mensaje = (f"{consulta.get('explicacion', 'Consulta al catálogo.')}\n\n{cuerpo}\n\n"
                         f"Consulta ejecutada (solo lectura): `{sql}`\n"
                         "Los importes están en centavos de real. La consulta la escribió un modelo "
                         "y solo se comprobó que es segura, no que responda exactamente a la pregunta.")
    respuesta.dataset_id = consulta["dataset_id"]
    respuesta.evidencias = [Evidencia(tipo="catalogo", fuente_id="SQL", texto=sql,
                                      dataset_id=consulta["dataset_id"])]
    return {"estado": "anclada", "filas": len(filas), "sql": sql}


def anclar_preferencia(respuesta: RespuestaCompra,
                       observaciones: list[tuple[str, dict]] | None) -> dict | None:
    """Redacta la confirmación de una preferencia con lo que la herramienta guardó de verdad."""
    if respuesta.estado != "preferencia":
        return None
    guardada = next((dato for nombre, dato in (observaciones or [])
                     if nombre == "guardar_preferencia" and dato.get("estado") == "ok"), None)
    if guardada is None:
        return {"estado": "sin_guardado"}
    respuesta.mensaje = f"Guardé tu preferencia: {guardada['clave']} = {guardada['valor']}."
    return {"estado": "anclada", "clave": guardada["clave"], "valor": guardada["valor"]}


def respuesta_local(escenario: Escenario, solicitud) -> RespuestaCompra:
    if solicitud.faltantes() or not solicitud.producto_id:
        return RespuestaCompra(estado="aclaracion", dataset_id=escenario.dataset_id, solicitud=solicitud)
    alternativas = comparar(solicitud, ofertas(escenario, solicitud.producto_id))
    validas = [a for a in alternativas if a.cumple]
    from .contracts import Evidencia
    return RespuestaCompra(
        estado="recomendacion" if validas else "sin_oferta", dataset_id=escenario.dataset_id,
        solicitud=solicitud, producto_id=solicitud.producto_id,
        proveedor_id=validas[0].oferta.proveedor_id if validas else None,
        total_centavos=validas[0].total_centavos if validas else None,
        alternativas=alternativas,
        evidencias=[Evidencia(tipo="catalogo", fuente_id=a.oferta.id,
                             dataset_id=escenario.dataset_id,
                             texto=(f"{a.oferta.proveedor_nombre} stock {a.oferta.stock} "
                                    f"entrega {a.oferta.plazo_dias} días")) for a in alternativas])


def mejor_sin_preferencia(respuesta: RespuestaCompra) -> Alternativa | None:
    """La oferta válida más barata, si la preferencia del usuario hizo ganar a otra más cara."""
    if respuesta.solicitud.origen_preferido is None or respuesta.estado != "recomendacion":
        return None
    validas = [a for a in respuesta.alternativas if a.cumple]
    barata = min(validas, key=lambda a: (a.total_centavos, a.oferta.plazo_dias, a.oferta.proveedor_id))
    ganadora = validas[0]
    return barata if barata.total_centavos < ganadora.total_centavos else None
