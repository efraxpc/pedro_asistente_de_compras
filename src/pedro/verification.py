"""Puerta de publicación independiente del agente generador."""
from difflib import SequenceMatcher

from .business import comparar
from .catalog import Escenario, buscar, ofertas
from .contracts import RespuestaCompra


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
