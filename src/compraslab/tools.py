"""Adaptadores con resultados explícitos y acceso al dataset fijado por la aplicación."""
import json
import uuid
from pathlib import Path
from .business import comparar_ofertas
from .data import Catalogo, buscar_productos as buscar, ofertas_producto
from .integrations import consultar_cep
from .schemas import Evidencia, ResultadoHerramienta, SolicitudCompra, RespuestaCompra
from .verification import verificar


def buscar_productos(catalogo: Catalogo, texto: str) -> ResultadoHerramienta:
    try:
        productos = buscar(catalogo, texto)
    except ValueError as exc:
        return ResultadoHerramienta(nombre="buscar_productos", estado="invalido", error=str(exc))
    return ResultadoHerramienta(nombre="buscar_productos",
        estado="ok" if productos else "no_encontrado",
        datos=[p.model_dump() for p in productos],
        evidencias=[Evidencia(tipo="catalogo", fuente_id=p.id, dataset_id=catalogo.dataset_id,
                              texto=f"{p.nombre} {p.modelo} ({p.unidad})") for p in productos])


def consultar_catalogo(catalogo: Catalogo, producto_id: str) -> ResultadoHerramienta:
    ofertas = ofertas_producto(catalogo, producto_id)
    return ResultadoHerramienta(nombre="consultar_catalogo", estado="ok" if ofertas else "no_encontrado",
        datos=[o.model_dump() for o in ofertas],
        evidencias=[Evidencia(tipo="catalogo", fuente_id=o.id, dataset_id=catalogo.dataset_id,
                              texto=f"{o.proveedor_nombre}: {o.precio_unitario_centavos} centavos, "
                                    f"flete {o.flete_centavos}, stock {o.stock}, plazo {o.plazo_dias}")
                    for o in ofertas])


def comparar(catalogo: Catalogo, solicitud: SolicitudCompra) -> ResultadoHerramienta:
    if solicitud.faltantes():
        return ResultadoHerramienta(nombre="comparar_ofertas", estado="invalido",
                                   error="faltan " + ", ".join(solicitud.faltantes()))
    ofertas = ofertas_producto(catalogo, solicitud.producto_id or "")
    alternativas = comparar_ofertas(solicitud, ofertas)
    return ResultadoHerramienta(nombre="comparar_ofertas",
        estado="ok" if alternativas else "no_encontrado",
        datos=[a.model_dump() for a in alternativas],
        evidencias=[Evidencia(tipo="catalogo", fuente_id=a.oferta.id, dataset_id=catalogo.dataset_id,
                              texto=f"Total {a.total_centavos}; motivos {','.join(a.motivos)}")
                    for a in alternativas])


def consultar_politicas(indice, pregunta: str, *, k: int = 4) -> ResultadoHerramienta:
    if indice is None:
        return ResultadoHerramienta(nombre="consultar_politicas", estado="indisponible",
                                   error="índice FAISS preconstruido ausente")
    docs = indice.similarity_search(pregunta, k=min(max(k, 1), 10))
    evidencias = [Evidencia(tipo="politica", fuente_id=str(d.metadata.get("id", "")),
                           texto=d.page_content) for d in docs if d.metadata.get("id")]
    return ResultadoHerramienta(nombre="consultar_politicas",
        estado="ok" if evidencias else "no_encontrado", evidencias=evidencias,
        datos=[e.model_dump() for e in evidencias])


def preparar_borrador(catalogo: Catalogo, respuesta: RespuestaCompra,
                     carpeta: Path) -> ResultadoHerramienta:
    """Solo guarda una propuesta local después de verificar su recomendación."""
    resultado = verificar(respuesta, catalogo)
    if not resultado.aprobado or respuesta.estado != "recomendacion":
        return ResultadoHerramienta(nombre="preparar_borrador", estado="invalido",
                                   error="respuesta no verificada")
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{uuid.uuid4()}.json"
    ruta.write_text(json.dumps({"estado": "pendiente_revision", "respuesta": respuesta.model_dump()},
                                ensure_ascii=False, indent=2), encoding="utf-8")
    return ResultadoHerramienta(nombre="preparar_borrador", estado="ok",
                               datos={"ruta": str(ruta), "estado": "pendiente_revision"})
