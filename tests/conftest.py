"""Los tests nunca salen a internet: sin repositorio, la app no busca actualizaciones en GitHub al arrancar.
Tiene que estar antes de importar app (version.py lee MANT_REPO al cargarse)."""
import os

os.environ["MANT_REPO"] = ""
