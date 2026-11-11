"""Executa e salva as saídas observadas das cinco práticas."""
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
for caminho in sorted((ROOT / "notebooks").glob("*.ipynb")):
    caderno = nbformat.read(caminho, as_version=4)
    NotebookClient(caderno, timeout=120, kernel_name="python3",
                   resources={"metadata": {"path": str(ROOT)}}).execute()
    nbformat.write(caderno, caminho)
    print(caminho.name, "OK")
