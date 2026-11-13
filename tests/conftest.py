"""Los tests nunca salen a internet (sin repositorio la app no busca actualizaciones) y NUNCA tocan la base real.

Orden importante: las variables van antes de importar la app, y la app se importa ACÁ, antes de cualquier test.
nucleo.configurar() (lo llama app/main.py al importarse) fija db.DB_PATH: si la importara un test después de cambiar
DB_PATH, lo pisaría con la base real. MANT_DB apunta a una carpeta temporal por las dudas."""
import os
import tempfile
from pathlib import Path

os.environ["MANT_REPO"] = ""
os.environ["MANT_DB"] = str(Path(tempfile.mkdtemp(prefix="mant_tests_")) / "no_usar.db")

import app.main  # noqa: E402,F401
