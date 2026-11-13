"""Identidad de la app que usa el núcleo. La app llama a configurar() UNA vez, antes de crear la aplicación.

Los módulos del núcleo leen estos valores como atributos (ajustes.APP, ajustes.NOMBRE...), así que una app distinta no
toca el núcleo: solo cambia lo que pasa acá.
"""
import os
import sys
from pathlib import Path

APP = "AppBase"            # identificador fijo: User-Agent, /api/version, nombre del .exe. No es el que se cambia en Opciones
NOMBRE = "App base"        # nombre de fábrica que muestra la página (se cambia en Opciones)
PREFIJO = "BASE"           # de las variables de entorno: BASE_DB, BASE_PUERTO, BASE_REPO, BASE_NAVEGADOR...
PUERTO = 8095              # el de fábrica (se cambia en Opciones)
VERSION = "0.0.0"
REPO = ""                  # "usuario/repositorio" de GitHub donde se publican los releases ("" = no busca)
SUBTITULO = ""             # la línea chica debajo del nombre en la pantalla de ingreso
LOGIN = "Usuario"          # cómo se llama el dato para entrar ("Legajo", "Usuario"...)
FRONTEND: Path | None = None   # app/frontend: se sirve en /static/app/; su icono.svg es el ícono de fábrica de la app
# compilada con PyInstaller: el código va en _internal/ y los datos al lado del .exe; desde el código, en la raíz
COMPILADA = bool(getattr(sys, "frozen", False))
RAIZ = Path(sys.executable).resolve().parent if COMPILADA else Path.cwd()


def env(nombre: str, defecto: str | None = None) -> str | None:
    """Una variable de entorno de esta app: env("DB") lee <PREFIJO>_DB."""
    return os.environ.get(f"{PREFIJO}_{nombre}", defecto)


def exe() -> str:
    return APP + ".exe"


def configurar(*, app: str, nombre: str, prefijo: str, puerto: int, version: str, repo: str = "", raiz: Path | None = None,
               base: str | None = None, subtitulo: str = "", login: str = "Usuario", frontend: Path | None = None) -> None:
    """raiz: la carpeta de la app (donde va data/) cuando corre desde el código; compilada se usa la del .exe.
    base: el nombre del archivo de la base sin extensión (por defecto, APP en minúsculas).
    frontend: la carpeta con los archivos propios de la app (icono.svg: su ícono de fábrica)."""
    global APP, NOMBRE, PREFIJO, PUERTO, VERSION, REPO, RAIZ, SUBTITULO, LOGIN, FRONTEND
    APP, NOMBRE, PREFIJO, PUERTO, VERSION, SUBTITULO, LOGIN = app, nombre, prefijo, int(puerto), version, subtitulo, login
    REPO = os.environ.get(f"{prefijo}_REPO", repo)   # vacío desactiva la búsqueda de actualizaciones (así corren los tests)
    if not COMPILADA and raiz:
        RAIZ = Path(raiz)
    FRONTEND = Path(frontend) if frontend else None
    from . import db
    db.DB_PATH = Path(os.environ.get(f"{prefijo}_DB") or RAIZ / "data" / f"{base or app.lower()}.db")
