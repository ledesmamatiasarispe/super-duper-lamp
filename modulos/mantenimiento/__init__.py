"""Módulo MANTENIMIENTO: equipos e instructivos, Plan, Cronograma, Registros, Horómetros, Correctivos, Personal, Áreas
y Mapa de planta. Todo lo de UltraMantenimiento que no es del núcleo (sesión, usuarios, Opciones, actualizaciones...).

Archivos: esquema.py (tablas y migraciones), servicios.py y calendario.py (reglas), rutas.py (API),
personal_usuarios.py (la ficha de Personal de cada usuario), frontend/ (pantallas, ayuda, estilos).
Más adelante se puede partir en módulos más chicos (por ejemplo, el mapa de planta) si otra app los necesita.
"""
from pathlib import Path

from nucleo.modulo import Menu, Modulo

from . import esquema, personal_usuarios, servicios
from .rutas import router


def _al_iniciar() -> None:
    personal_usuarios.sincronizar_todos()   # el administrador de fábrica de una base nueva también tiene su ficha
    for hecho in servicios.separar_instructivos_compartidos():   # una sola vez: después el índice único impide compartir
        print("Instructivo compartido separado:", hecho)


MODULO = Modulo(
    nombre="mantenimiento",
    carpeta=Path(__file__).resolve().parent,
    esquema=esquema.ESQUEMA,
    migrar=esquema.migrar,
    datos_iniciales=esquema.datos_iniciales,
    router=router,
    scripts=["mantenimiento.js", "mapa.js", "ayuda_mantenimiento.js"],
    estilos=["mantenimiento.css", "mapa.css"],
    menu=[Menu("cronograma", "Cronograma", orden=1), Menu("registros", "Registros", orden=2),
          Menu("horometros", "Horómetros", orden=3), Menu("correctivos", "Correctivos", orden=4),
          Menu("plan", "Plan", orden=5), Menu("equipos", "Equipos e instructivos", orden=6),
          Menu("mapa", "Mapa", orden=7), Menu("personal", "Personal", orden=8), Menu("areas", "Áreas", orden=9)],
    al_iniciar=_al_iniciar,
)
