"""UltraMantenimiento: el núcleo (nucleo/, el de appbase, sin cambios) + el módulo de mantenimiento.

Una fusión con otra app hecha sobre el núcleo sería sumar sus módulos a MODULOS."""
from pathlib import Path

import nucleo

from . import version as v

nucleo.configurar(app=v.APP, nombre=v.NOMBRE, prefijo=v.PREFIJO, puerto=v.PUERTO, version=v.VERSION, repo=v.REPO,
                  subtitulo=v.SUBTITULO, login=v.LOGIN, base=v.BASE, raiz=Path(__file__).resolve().parent.parent,
                  frontend=Path(__file__).resolve().parent / "frontend")

from modulos import mantenimiento  # noqa: E402  (después de configurar)
from nucleo.aplicacion import crear_app  # noqa: E402

MODULOS = [mantenimiento.MODULO]
app = crear_app(MODULOS)
