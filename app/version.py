"""Versión de la app y de dónde se bajan las actualizaciones.

VERSION se sube a mano antes de publicar una versión nueva, y el tag del release de GitHub tiene que ser
"v" + VERSION (herramientas/compilar.py lo controla). REPO es "usuario/repositorio" en GitHub. MANT_REPO lo
reemplaza (útil para probar con otro repositorio); vacío desactiva la búsqueda de actualizaciones (así corren los tests)."""
import os
import sys

VERSION = "1.0.7"
APP = "UltraMantenimiento"   # identifica a la app (User-Agent, /api/version): NO es el nombre que se cambia en Opciones
NOMBRE = "UltraMantenimiento"   # el nombre de fábrica que muestra la página (se cambia en Opciones)
PREFIJO = "MANT"   # de las variables de entorno: MANT_DB, MANT_PUERTO, MANT_REPO...
PUERTO = 8095   # el de fábrica (se cambia en Opciones)
REPO = os.environ.get("MANT_REPO", "ledesmamatiasarispe/super-duper-lamp")

# la versión compilada (PyInstaller) es la única que se actualiza sola: en desarrollo se usa git
COMPILADA = bool(getattr(sys, "frozen", False))
