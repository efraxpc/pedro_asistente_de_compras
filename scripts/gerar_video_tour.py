"""Gera o vídeo narrado do tour das rubricas a partir de docs/tour/tour_rubricas.html.

Captura os 30 passos da página (10 paradas x 3 painéis), narra cada passo com uma voz
sintética e monta um MP4 com legendas. A narração é o texto `voz` de cada parada, em espanhol.

Voz, por ordem de preferência:
- ElevenLabs, se houver ELEVENLABS_API_KEY (voz em ELEVENLABS_VOICE_ID; padrão: uma voz pré-definida);
- OpenAI (`gpt-4o-mini-tts`), se houver OPENAI_API_KEY.
O texto da narração é enviado ao serviço escolhido.

Uso (precisa de ffmpeg e de um Chromium do Playwright):
    uv run --with playwright python scripts/gerar_video_tour.py
"""
import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
PAGINA = ROOT / "docs/tour/tour_rubricas.html"
PAUSA = 0.7  # segundos de silêncio depois de cada passo
# Fator de velocidade por serviço: a voz da OpenAI sai um pouco lenta; a da ElevenLabs fica como vem.
RITMO = {"OpenAI": 1.1, "ElevenLabs": 1.0}
ESTILO = ("Habla en español latinoamericano neutro, como una profesora cercana que explica con "
          "claridad a un estudiante. Tono cálido y natural, ritmo de conversación normal, sin sonar a locutor.")


def narrar_elevenlabs(texto: str, destino: Path) -> None:
    import httpx

    voz = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
    resposta = httpx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voz}",
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Accept": "audio/mpeg"},
        json={"text": texto, "model_id": "eleven_multilingual_v2"}, timeout=120)
    resposta.raise_for_status()
    destino.write_bytes(resposta.content)


def narrar_openai(texto: str, destino: Path) -> None:
    from openai import OpenAI

    with OpenAI().audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts", voice=os.getenv("PEDRO_TTS_VOICE", "coral"), input=texto,
            instructions=ESTILO, response_format="mp3") as resposta:
        resposta.stream_to_file(destino)


def escolher_voz():
    if os.getenv("ELEVENLABS_API_KEY"):
        return "ElevenLabs (eleven_multilingual_v2)", narrar_elevenlabs
    if os.getenv("OPENAI_API_KEY"):
        return "OpenAI (gpt-4o-mini-tts)", narrar_openai
    raise SystemExit("Falta ELEVENLABS_API_KEY ou OPENAI_API_KEY para gerar a narração")


def duracao(arquivo: Path) -> float:
    saida = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", str(arquivo)], capture_output=True, text=True, check=True)
    return float(saida.stdout)


def capturar(pasta: Path, chromium: str | None) -> list[list[str]]:
    """Abre a página, guarda uma imagem por passo e devolve os textos da narração."""
    from playwright.sync_api import sync_playwright

    completa = pasta / "tour.html"
    completa.write_text('<!doctype html><html lang="es"><head><meta charset="utf-8">'
                        '<meta name="viewport" content="width=device-width, initial-scale=1">'
                        "<style>body{margin:0}</style></head><body>"
                        + PAGINA.read_text(encoding="utf-8") + "</body></html>", encoding="utf-8")
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path=chromium) if chromium else p.chromium.launch()
        pagina = navegador.new_context(viewport={"width": 1280, "height": 720}, color_scheme="light",
                                       device_scale_factor=1.5).new_page()
        pagina.goto(completa.as_uri())
        pagina.wait_for_function("document.fonts.status === 'loaded' && window.tour")
        pagina.add_style_tag(content=".mandos button{visibility:hidden} *{transition:none!important}")
        vozes = pagina.evaluate("tour.voces")
        for i, passos in enumerate(vozes):
            for n, texto in enumerate(passos, 1):
                pagina.evaluate("([i, n, t]) => tour.pintar(i, n, t)", [i, n, texto])
                time.sleep(0.12)
                pagina.screenshot(path=str(pasta / f"{i + 1:02d}_{n}.png"))
        navegador.close()
    return vozes


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    argumentos.add_argument("--saida", type=Path, default=ROOT / "docs/tour/tour_rubricas.mp4")
    argumentos.add_argument("--chromium", help="caminho do executável do Chromium, se o Playwright não o encontrar")
    opcoes = argumentos.parse_args()
    load_dotenv(ROOT / ".env")
    nome_voz, narrar = escolher_voz()
    ritmo = RITMO[nome_voz.split()[0]]
    chromium = opcoes.chromium
    if chromium is None:
        instalados = sorted(Path.home().glob(".cache/ms-playwright/chromium-*/chrome-linux*/chrome"))
        chromium = str(instalados[-1]) if instalados else None

    with tempfile.TemporaryDirectory() as temporaria:
        pasta = Path(temporaria)
        vozes = capturar(pasta, chromium)
        quadros, audios, caracteres = [], [], 0
        for i, passos in enumerate(vozes):
            for n, texto in enumerate(passos, 1):
                bruto, pronto = pasta / f"{i + 1:02d}_{n}.mp3", pasta / f"{i + 1:02d}_{n}.wav"
                narrar(texto, bruto)
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(bruto), "-af",
                                f"atempo={ritmo},loudnorm=I=-16:TP=-1.5:LRA=11,apad=pad_dur={PAUSA}", "-ar", "44100", "-ac", "1", str(pronto)], check=True)
                quadros.append((pasta / f"{i + 1:02d}_{n}.png", duracao(pronto)))
                audios.append(pronto)
                caracteres += len(texto)
            print(f"parada {i + 1} narrada")
        (pasta / "quadros.txt").write_text(
            "".join(f"file '{arquivo}'\nduration {segundos:.3f}\n" for arquivo, segundos in quadros)
            + f"file '{quadros[-1][0]}'\n")
        (pasta / "audios.txt").write_text("".join(f"file '{arquivo}'\n" for arquivo in audios))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i",
                        str(pasta / "audios.txt"), "-c:a", "pcm_s16le", str(pasta / "narracao.wav")], check=True)
        opcoes.saida.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i",
                        str(pasta / "quadros.txt"), "-i", str(pasta / "narracao.wav"), "-vf",
                        "scale=1920:1080:flags=lanczos,fps=10,format=yuv420p", "-c:v", "libx264", "-crf", "24",
                        "-preset", "slow", "-tune", "stillimage", "-c:a", "aac", "-b:a", "96k", "-ac", "1",
                        "-shortest", "-movflags", "+faststart", str(opcoes.saida)], check=True)
    print(json.dumps({"voz": nome_voz, "passos": len(quadros), "caracteres_narrados": caracteres,
                      "duracao_segundos": round(duracao(opcoes.saida), 1), "saida": str(opcoes.saida)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
