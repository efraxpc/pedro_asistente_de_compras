"""Ejecuta y guarda salidas observadas de las cinco prácticas."""
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
for ruta in sorted((ROOT / "notebooks").glob("*.ipynb")):
    libro = nbformat.read(ruta, as_version=4)
    NotebookClient(libro, timeout=120, kernel_name="python3",
                   resources={"metadata": {"path": str(ROOT)}}).execute()
    nbformat.write(libro, ruta)
    print(ruta.name, "OK")
