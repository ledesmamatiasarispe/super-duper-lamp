"""Validaciones de campo compartidas. Reciben el valor CRUDO del formulario (texto) y devuelven el valor limpio o lanzan
ErrorDeNegocio con un mensaje que nombra el campo. Así "7,5" o "nan" o una fecha mal escrita terminan en un 400 claro y
no en un error interno. Nunca reimplementar "obligatorio" o "número entre" en cada módulo."""
import math
import re
from datetime import date

from .errores import ErrorDeNegocio, NoEncontrado


def texto(valor, campo: str, obligatorio: bool = True, maximo: int | None = None) -> str:
    t = " ".join(str(valor or "").split()) if maximo else str(valor or "").strip()
    if obligatorio and not t:
        raise ErrorDeNegocio(f"Falta {campo}.")
    if maximo and len(t) > maximo:
        raise ErrorDeNegocio(f"{campo.capitalize()} puede tener hasta {maximo} caracteres.")
    return t


def corto(valor, maximo: int) -> str:
    return str(valor or "").strip()[:maximo]


def numero(valor, campo: str, entero: bool = False, minimo: float = 0, maximo: float = 1e9, obligatorio: bool = False):
    """Acepta coma decimal. Vacío devuelve None (o falla si es obligatorio)."""
    if valor in (None, ""):
        if obligatorio:
            raise ErrorDeNegocio(f"Falta {campo}.")
        return None
    try:
        n = float(str(valor).replace(",", "."))
    except ValueError:
        n = None
    if n is None or not math.isfinite(n):   # float() acepta "nan" e "inf": tampoco son números cargables
        raise ErrorDeNegocio(f"{campo.capitalize()}: '{valor}' no es un número.")
    if not minimo <= n <= maximo:
        raise ErrorDeNegocio(f"{campo.capitalize()} tiene que estar entre {minimo:g} y {maximo:g}.")
    if entero:
        if n != int(n):
            raise ErrorDeNegocio(f"{campo.capitalize()} tiene que ser un número entero.")
        return int(n)
    return round(n, 2)


def fecha(valor, campo: str, obligatorio: bool = True) -> str | None:
    """ISO (2026-11-13). Devuelve el texto ISO o None."""
    v = str(valor or "").strip()
    if not v:
        if obligatorio:
            raise ErrorDeNegocio(f"Falta {campo}.")
        return None
    try:
        return date.fromisoformat(v[:10]).isoformat()
    except ValueError:
        raise ErrorDeNegocio(f"{campo.capitalize()}: '{v}' no es una fecha válida.") from None


def opcion(valor, opciones, campo: str) -> str:
    if valor not in opciones:
        raise ErrorDeNegocio(f"{campo.capitalize()}: elegir una de {', '.join(map(str, opciones))}.")
    return valor


def fila(c, sql: str, params: tuple, que: str):
    """Una fila que tiene que existir; si no, NoEncontrado con "No existe <que>"."""
    r = c.execute(sql, params).fetchone()
    if not r:
        raise NoEncontrado(f"No existe {que}.")
    return r


def nombre_de_archivo(nombre) -> str:
    """Solo el nombre (sin carpetas), sin caracteres de control. Se muestra; nunca se usa como ruta."""
    base = re.split(r"[\\/]", str(nombre or ""))[-1]
    base = "".join(ch for ch in base if ch.isprintable()).strip().strip(".")
    return base[:150] or "archivo"
