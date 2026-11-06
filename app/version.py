"""Versión de la app y de dónde se bajan las actualizaciones.

VERSION se sube a mano antes de publicar una versión nueva, y el tag del release de GitHub tiene que ser
"v" + VERSION (herramientas/compilar.py lo controla). REPO es "usuario/repositorio" en GitHub. MANT_REPO lo
reemplaza (útil para probar con otro repositorio); vacío desactiva la búsqueda de actualizaciones (así corren los tests)."""
import os
import sys

VERSION = "1.0.3"
REPO = os.environ.get("MANT_REPO", "ledesmamatiasarispe/super-duper-lamp")

# la versión compilada (PyInstaller) es la única que se actualiza sola: en desarrollo se usa git
COMPILADA = bool(getattr(sys, "frozen", False))
