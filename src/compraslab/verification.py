"""Comprobación exacta independiente de la prosa del agente."""
from .business import comparar_ofertas
from .data import Catalogo, buscar_productos, ofertas_producto
from .schemas import RespuestaCompra, ResultadoVerificacion


def verificar(respuesta: RespuestaCompra, catalogo: Catalogo | None = None) -> ResultadoVerificacion:
    errores = []
    if catalogo is None or catalogo.dataset_id != respuesta.dataset_id:
        errores.append("catálogo activo no disponible")
        return ResultadoVerificacion(aprobado=False, errores=errores)
    if respuesta.estado == "aclaracion":
        ambiguo = bool(respuesta.solicitud.producto and
                       len(buscar_productos(catalogo, respuesta.solicitud.producto)) > 1)
        if not respuesta.solicitud.faltantes() and not ambiguo:
            errores.append("aclaración sin faltante ni ambigüedad")
    if respuesta.estado == "sin_oferta":
        if (respuesta.solicitud.faltantes() or not respuesta.producto_id or
            respuesta.producto_id != respuesta.solicitud.producto_id):
            errores.append("sin_oferta sin solicitud completa")
        else:
            oficiales = ofertas_producto(catalogo, respuesta.producto_id)
            calculadas = comparar_ofertas(respuesta.solicitud, oficiales)
            if any(a.cumple for a in calculadas):
                errores.append("existe una oferta válida")
            if {a.oferta.id for a in respuesta.alternativas} != {o.id for o in oficiales}:
                errores.append("faltan alternativas descartadas")
            por_id = {a.oferta.id: a for a in calculadas}
            if any(a.oferta.id not in por_id or a != por_id[a.oferta.id]
                   for a in respuesta.alternativas):
                errores.append("descarte incoherente")
    if respuesta.estado == "recomendacion":
        if respuesta.solicitud.faltantes():
            errores.append("solicitud incompleta")
        if respuesta.producto_id != respuesta.solicitud.producto_id:
            errores.append("producto distinto de la solicitud")
        if not respuesta.alternativas:
            errores.append("faltan ofertas")
        if not any(e.tipo == "catalogo" and e.dataset_id == respuesta.dataset_id
                   for e in respuesta.evidencias):
            errores.append("falta evidencia del catálogo activo")
        if not errores:
            oficiales = ofertas_producto(catalogo, respuesta.producto_id or "")
            if not oficiales or {o.id for o in oficiales} != {a.oferta.id for a in respuesta.alternativas}:
                errores.append("conjunto de ofertas incompleto")
            if any(a.oferta != next((o for o in oficiales if o.id == a.oferta.id), None)
                   for a in respuesta.alternativas):
                errores.append("oferta distinta del catálogo activo")
            ordenadas = comparar_ofertas(respuesta.solicitud, oficiales)
            validas = [a for a in ordenadas if a.cumple]
            if not validas:
                errores.append("ninguna oferta válida")
            elif (respuesta.proveedor_id != validas[0].oferta.proveedor_id or
                  respuesta.total_centavos != validas[0].total_centavos):
                errores.append("proveedor o total incorrecto")
            calculadas = {a.oferta.id: a for a in ordenadas}
            for anterior in respuesta.alternativas:
                calculada = calculadas.get(anterior.oferta.id)
                if calculada is None:
                    continue
                if (anterior.total_centavos != calculada.total_centavos or
                        anterior.motivos != calculada.motivos or anterior.cumple != calculada.cumple):
                    errores.append("alternativa incoherente")
            if any(a.oferta.dataset_id != respuesta.dataset_id for a in respuesta.alternativas):
                errores.append("oferta de otro dataset")
            fuentes = {e.fuente_id for e in respuesta.evidencias if e.tipo == "catalogo"
                       and e.dataset_id == respuesta.dataset_id}
            if not {o.id for o in oficiales}.issubset(fuentes):
                errores.append("faltan fuentes para ofertas")
    return ResultadoVerificacion(aprobado=not errores, errores=errores)
