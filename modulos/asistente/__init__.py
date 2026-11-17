"""Módulo ASISTENTE: la barra "Preguntá algo" arriba de todo, con micrófono donde el navegador lo permite, que contesta
con los datos de la app y una IA local (Ollama). Sin tablas propias: lo que configura va en la tabla config del núcleo.

Para que conteste sobre algo, cada módulo le registra una fuente (servicios.Fuente) al importarse:

    try:
        from modulos.asistente import Fuente, registrar
    except ImportError:          # la app no usa el asistente: el módulo funciona igual sin él
        registrar = None
    if registrar:
        registrar(Fuente("mantenimiento", responder=..., contexto=...))

y la app lo suma a MODULOS (en cualquier lugar de la lista: no tiene menú)."""
from pathlib import Path

from nucleo.modulo import Modulo

from .rutas import router
from .servicios import Fuente, registrar  # noqa: F401  (lo que usan los otros módulos)

MODULO = Modulo(
    nombre="asistente",
    carpeta=Path(__file__).resolve().parent,
    router=router,
    scripts=["asistente.js"],
    estilos=["asistente.css"],
)
