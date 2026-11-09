"""ViaCEP confirma ubicación; no calcula transporte."""
import re

import httpx


def consultar_cep(cep: str, *, cliente: httpx.Client | None = None,
                  simulado: bool = False) -> dict:
    if not re.fullmatch(r"\d{8}", cep):
        return {"estado": "invalido", "error": "CEP debe tener ocho dígitos"}
    if simulado:
        return {"estado": "ok", "cep": cep, "cidade": "Cidade Simulada",
                "uf": "SP", "modo": "simulado"}
    try:
        if cliente is None:
            with httpx.Client(timeout=5.0) as temporal:
                respuesta = temporal.get(f"https://viacep.com.br/ws/{cep}/json/")
        else:
            respuesta = cliente.get(f"https://viacep.com.br/ws/{cep}/json/")
        respuesta.raise_for_status()
        dato = respuesta.json()
        if dato.get("erro"):
            return {"estado": "no_encontrado", "cep": cep}
        return {"estado": "ok", "cep": cep, "cidade": dato["localidade"],
                "uf": dato["uf"], "modo": "real", "fuente": f"ViaCEP:{cep}"}
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        return {"estado": "indisponible", "error": type(exc).__name__}
