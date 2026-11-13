"""El contrato de un módulo: todo lo que una parte del negocio trae para enchufarse al núcleo.

Un módulo es AUTOCONTENIDO: sus tablas, sus rutas, sus pantallas, su menú y su ayuda. Por eso dos apps hechas sobre el
núcleo se pueden fusionar activando los módulos de las dos en crear_app([...]). Para eso, cada módulo:
  - nombra sus tablas con un prefijo propio o un nombre que no choque (no "items" ni "datos");
  - registra sus rutas bajo /api/<nombre>/... (o rutas que no choquen con las del núcleo ni de otros módulos);
  - en el frontend, registra sus pantallas en VISTAS con nombres propios y su ayuda en Ayuda.pasos.

Estructura sugerida de una carpeta de módulo (ver modulos/notas, el ejemplo mínimo):
    modulos/<nombre>/__init__.py     MODULO = Modulo(...)
    modulos/<nombre>/servicios.py    casos de uso (cada uno una transacción); las reglas viven acá, no en las rutas
    modulos/<nombre>/rutas.py        APIRouter delgado: lee el pedido, llama al servicio, devuelve el resultado
    modulos/<nombre>/frontend/       <nombre>.js (pantallas, ayuda) y <nombre>.css
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class Menu:
    vista: str            # la pantalla (VISTAS.<vista> en el frontend del módulo)
    titulo: str           # lo que dice la pestaña
    solo_admin: bool = False
    orden: int = 50       # Inicio es 0, Usuarios 900: las pestañas se ordenan por este número


@dataclass
class Modulo:
    nombre: str                                   # identificador: /static/<nombre>/, ejemplos_<nombre> en config
    carpeta: Path | None = None                   # la carpeta del módulo (su frontend/ se sirve en /static/<nombre>/)
    esquema: str = ""                             # CREATE TABLE IF NOT EXISTS ... (se aplica al arrancar)
    columnas: list = field(default_factory=list)  # (tabla, columna, tipo) que se sumaron después de crear la base
    migrar: Callable | None = None                # migrar(c): ajustes de datos al arrancar, idempotentes
    datos_iniciales: Callable | None = None       # datos_iniciales(c): ejemplos inventados, UNA vez por base
    router: object | None = None                  # fastapi.APIRouter
    scripts: list[str] = field(default_factory=list)   # archivos de frontend/ que carga la página (en orden)
    estilos: list[str] = field(default_factory=list)
    menu: list[Menu] = field(default_factory=list)
    al_iniciar: Callable | None = None            # al_iniciar(): después de preparar la base (hilos de fondo, etc.)
    al_terminar: Callable | None = None
