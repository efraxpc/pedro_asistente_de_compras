"""ViaCEP confirma a localização; não calcula transporte."""
import re

import httpx


def consultar_cep(cep: str, *, cliente: httpx.Client | None = None,
                  simulado: bool = False) -> dict:
    if not re.fullmatch(r"\d{8}", cep):
        return {"estado": "invalido", "erro": "CEP deve ter oito dígitos"}
    if simulado:
        return {"estado": "ok", "cep": cep, "cidade": "Cidade Simulada",
                "uf": "SP", "modo": "simulado"}
    try:
        if cliente is None:
            with httpx.Client(timeout=5.0) as temporario:
                resposta = temporario.get(f"https://viacep.com.br/ws/{cep}/json/")
        else:
            resposta = cliente.get(f"https://viacep.com.br/ws/{cep}/json/")
        resposta.raise_for_status()
        dado = resposta.json()
        if dado.get("erro"):
            return {"estado": "nao_encontrado", "cep": cep}
        return {"estado": "ok", "cep": cep, "cidade": dado["localidade"],
                "uf": dado["uf"], "modo": "real", "fonte": f"ViaCEP:{cep}"}
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        return {"estado": "indisponivel", "erro": type(exc).__name__}
