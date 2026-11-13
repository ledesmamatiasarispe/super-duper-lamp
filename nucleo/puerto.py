"""El puerto donde atiende la app: se elige en Opciones y vale desde la próxima vez que se abre.

Lo propio de cada app sale de ajustes (PREFIJO de sus variables de entorno, PUERTO de fábrica y APP, su
identificador). Varias apps pueden convivir en una PC: si
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
from . import ajustes as v

from .errores import ErrorDeNegocio

MINIMO, MAXIMO = 1024, 65535


def __getattr__(nombre):
    """DEFECTO, VARIABLE y VARIABLE_ACTUAL dependen de la app: se calculan al pedirlos."""
    if nombre == "DEFECTO":
        return v.PUERTO
    if nombre == "VARIABLE":
        return f"{v.PREFIJO}_PUERTO"
    if nombre == "VARIABLE_ACTUAL":   # el que se usó al arrancar (otro, si el elegido estaba ocupado)
        return f"{v.PREFIJO}_PUERTO_ACTUAL"
    raise AttributeError(nombre)


def _var() -> str:
    return f"{v.PREFIJO}_PUERTO"


def _var_actual() -> str:
    return f"{v.PREFIJO}_PUERTO_ACTUAL"
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
    return bool(os.environ.get(_var()))


def configurado() -> int:
    return int(os.environ[_var()]) if fijo() else guardado() or v.PUERTO


def actual() -> int:
    """Donde está atendiendo ahora (el configurado si arrancó por otro camino, como los tests)."""
    return int(os.environ.get(_var_actual()) or configurado())


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
    raise SystemExit(f"No hay un puerto libre desde el {elegido}: cerrá el programa que lo usa o cambiá {_var()}.")


# ── Opciones ──
def estado() -> dict:
    return {"elegido": configurado(), "actual": actual(), "defecto": v.PUERTO, "fijo": fijo(), "variable": _var()}


def cambiar(usuario: dict, puerto) -> dict:
    if fijo():
        raise ErrorDeNegocio(f"El puerto lo fija la variable {_var()}: se cambia ahí, no desde la app.")
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
        guardar_config(c, CLAVE, None if puerto == v.PUERTO else str(puerto))
    return estado()
