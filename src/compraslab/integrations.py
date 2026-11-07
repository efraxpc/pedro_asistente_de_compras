"""CEP externo. Esta integración no calcula flete ni plazo."""
import re
import httpx
from .schemas import ResultadoHerramienta, Evidencia


def consultar_cep(cep: str, *, simulado: bool = False,
                  cliente: httpx.Client | None = None) -> ResultadoHerramienta:
    if not re.fullmatch(r"[0-9]{8}", cep):
        return ResultadoHerramienta(nombre="consultar_cep", estado="invalido",
                                   error="CEP debe tener ocho dígitos")
    if simulado:
        return ResultadoHerramienta(nombre="consultar_cep", estado="ok",
                                   datos={"cep": cep, "cidade": "Cidade Simulada", "uf": "SP",
                                          "simulado": True})
    try:
        if cliente is None:
            with httpx.Client(timeout=5.0) as temporal:
                respuesta = temporal.get(f"https://viacep.com.br/ws/{cep}/json/")
        else:
            respuesta = cliente.get(f"https://viacep.com.br/ws/{cep}/json/")
        respuesta.raise_for_status()
        dado = respuesta.json()
        if dado.get("erro"):
            return ResultadoHerramienta(nombre="consultar_cep", estado="no_encontrado",
                                       error="CEP inexistente")
        return ResultadoHerramienta(nombre="consultar_cep", estado="ok",
            datos={"cep": cep, "cidade": dado["localidade"], "uf": dado["uf"], "simulado": False},
            evidencias=[Evidencia(tipo="viacep", fuente_id=f"ViaCEP:{cep}",
                                 texto=f"{dado['localidade']}/{dado['uf']}")])
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        return ResultadoHerramienta(nombre="consultar_cep", estado="indisponible",
                                   error=type(exc).__name__)
