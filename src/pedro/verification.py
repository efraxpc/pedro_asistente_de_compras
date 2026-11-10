"""Puerta de publicación independiente del agente generador."""
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
