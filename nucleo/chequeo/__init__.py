"""Chequeos que cada app corre en sus tests (los trae herramientas/sincronizar.py en tests/test_pantallas.py)."""
import json
import shutil
import subprocess
from pathlib import Path

from ..aplicacion import FRONTEND, MENU_NUCLEO

CARPETA = Path(__file__).resolve().parent


def scripts_de_la_pagina(modulos) -> list[Path]:
    """Los scripts en el mismo orden que los carga index.html: los del núcleo y después los de cada módulo."""
    return [FRONTEND / "nucleo.js", FRONTEND / "ayuda.js",
            *(m.carpeta / "frontend" / s for m in modulos for s in m.scripts)]


def pantallas(modulos) -> list[str] | None:
    """Carga los scripts con Node sobre un DOM de mentira (ver pantallas.js): nombres globales repetidos, errores al
    cargar y pestañas sin pantalla. Devuelve la lista de errores, o None si no hay Node en esta PC (el test se saltea)."""
    node = shutil.which("node")
    if not node:
        return None
    vistas = [m.vista for m in [*MENU_NUCLEO, *(x for mod in modulos for x in mod.menu)]]
    r = subprocess.run([node, str(CARPETA / "pantallas.js"), *map(str, scripts_de_la_pagina(modulos)), "--vistas", ",".join(vistas)],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    if r.returncode != 0 and not r.stdout:
        return [f"node falló: {r.stderr[-500:]}"]
    return json.loads(r.stdout)["errores"]
