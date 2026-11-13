"""El puerto donde atiende la app: se elige en Opciones y vale desde la próxima vez que se abre.

MISMO ARCHIVO en UltraMantenimiento, Gestión Automotor y Edificios de Mamá (lo propio de cada una sale de version.py:
PREFIJO de sus variables de entorno, PUERTO de fábrica y APP, su identificador). Las tres pueden convivir en una PC: si
el puerto elegido lo usa otro programa, la app arranca en el siguiente libre y lo avisa en Opciones; si lo usa ESTA
misma app (ya estaba abierta), solo se abre el navegador. Para saber quién atiende se pregunta /api/version, que
contesta el identificador fijo de la app (version.APP), no el nombre que se cambia en Opciones.

Orden: la variable <PREFIJO>_PUERTO (fija el puerto, para pruebas o un servidor) > lo elegido en Opciones > el de fábrica."""
import json
import os
import socket
import sqlite3
import urllib.request

from . import db
from . import version as v

try:   # UltraMantenimiento y Gestión Automotor lo tienen en servicios; Edificios de Mamá, en validar
    from .servicios import ErrorDeNegocio
except ImportError:
    from .validar import ErrorDeNegocio

DEFECTO = v.PUERTO
MINIMO, MAXIMO = 1024, 65535
VARIABLE = f"{v.PREFIJO}_PUERTO"
VARIABLE_ACTUAL = f"{v.PREFIJO}_PUERTO_ACTUAL"   # el que se usó al arrancar (otro, si el elegido estaba ocupado)
CLAVE = "puerto"
_BUSCAR_HASTA = 50   # cuántos puertos siguientes se prueban si el elegido está ocupado


def guardado() -> int | None:
    """Lo elegido en Opciones. Se lee en solo lectura y sin transacción: corre antes de que arranque la app."""
    if not db.DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{db.DB_PATH.as_posix()}?mode=ro", uri=True)
        try:
            fila = conn.execute("SELECT valor FROM config WHERE clave=?", (CLAVE,)).fetchone()
        finally:
            conn.close()
        return int(fila[0]) if fila else None
    except (sqlite3.Error, ValueError):
        return None


def fijo() -> bool:
    return bool(os.environ.get(VARIABLE))


def configurado() -> int:
    return int(os.environ[VARIABLE]) if fijo() else guardado() or DEFECTO


def actual() -> int:
    """Donde está atendiendo ahora (el configurado si arrancó por otro camino, como los tests)."""
    return int(os.environ.get(VARIABLE_ACTUAL) or configurado())


def libre(puerto: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", puerto))
            return True
        except OSError:
            return False


def quien_atiende(puerto: int) -> str | None:
    """El identificador de la app que contesta en ese puerto, o None si no es ninguna de las nuestras (o nadie)."""
    try:
        with urllib.request.urlopen(f"http://localhost:{puerto}/api/version", timeout=2) as r:   # noqa: S310 (local)
            return json.loads(r.read()).get("app")
    except Exception:  # noqa: BLE001  (cualquier cosa que no sea nuestra respuesta)
        return None


def al_arrancar() -> tuple[int, bool]:
    """(puerto, ya_estaba_abierta). Si el elegido lo usa otro programa, el siguiente libre; si lo usa esta app, ese."""
    elegido = configurado()
    for puerto in range(elegido, min(elegido + _BUSCAR_HASTA, MAXIMO) + 1):
        if libre(puerto):
            return puerto, False
        if quien_atiende(puerto) == v.APP:
            return puerto, True
        if fijo():   # fijado a mano: no se busca otro
            break
    raise SystemExit(f"No hay un puerto libre desde el {elegido}: cerrá el programa que lo usa o cambiá {VARIABLE}.")


# ── Opciones ──
def estado() -> dict:
    return {"elegido": configurado(), "actual": actual(), "defecto": DEFECTO, "fijo": fijo(), "variable": VARIABLE}


def cambiar(usuario: dict, puerto) -> dict:
    if fijo():
        raise ErrorDeNegocio(f"El puerto lo fija la variable {VARIABLE}: se cambia ahí, no desde la app.")
    try:
        puerto = int(str(puerto).strip())
    except ValueError:
        raise ErrorDeNegocio("El puerto es un número.") from None
    if not MINIMO <= puerto <= MAXIMO:
        raise ErrorDeNegocio(f"El puerto tiene que estar entre {MINIMO} y {MAXIMO}.")
    if puerto != actual() and not libre(puerto):
        raise ErrorDeNegocio(f"El puerto {puerto} lo está usando otro programa en esta PC: elegí otro.")
    from .marca import guardar_config
    with db.transaccion() as c:
        guardar_config(c, CLAVE, None if puerto == DEFECTO else str(puerto))
    return estado()
