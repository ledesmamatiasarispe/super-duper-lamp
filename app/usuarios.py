"""Usuarios del sistema: alta, rol, baja y contraseñas.

Reglas que evitan quedarse afuera: siempre queda al menos un administrador activo, nadie se da de baja a sí mismo,
y la baja o el cambio de contraseña cierran las sesiones abiertas de esa persona. Una contraseña puesta por un
administrador (alta o restablecer) es provisoria: el usuario la tiene que cambiar al entrar.
"""
import sqlite3

from .auth import hash_password, verificar_password
from .db import transaccion
from .servicios import ErrorDeNegocio, NoEncontrado, _numero, _texto

MINIMO_PASSWORD = 6
_COLS = "legajo, nombre, es_admin, activo, debe_cambiar"


def _password_valida(password) -> str:
    p = str(password or "")
    if len(p) < MINIMO_PASSWORD:
        raise ErrorDeNegocio(f"La contraseña tiene que tener al menos {MINIMO_PASSWORD} caracteres.")
    return p


def _usuario(c, legajo: int) -> sqlite3.Row:
    u = c.execute(f"SELECT {_COLS} FROM usuarios WHERE legajo=?", (legajo,)).fetchone()
    if not u:
        raise NoEncontrado(f"No existe el usuario con legajo {legajo}.")
    return u


def _exigir_otro_admin(c, legajo: int, accion: str) -> None:
    otros = c.execute("SELECT count(*) FROM usuarios WHERE es_admin=1 AND activo=1 AND legajo<>?", (legajo,)).fetchone()[0]
    if not otros:
        raise ErrorDeNegocio(f"No se puede {accion}: es el único administrador activo y el sistema quedaría sin quien lo configure. "
                             "Primero hay que nombrar otro administrador.")


def _cerrar_sesiones(c, legajo: int, excepto_token: str | None = None) -> None:
    c.execute("UPDATE sesiones SET activa=0 WHERE legajo=? AND token IS NOT ?", (legajo, excepto_token))


def sincronizar_persona(c, legajo: int) -> None:
    """Deja la ficha de Personal igual al usuario: mismo nombre y misma alta, en Mantenimiento interno.

    Si todavía no tiene ficha y hay un operario interno suelto con ese nombre, es la misma persona: se vincula.
    El mismo nombre en un proveedor o en la fila "Otro" es otra cosa, y se avisa en vez de mezclarlos.
    """
    u = _usuario(c, legajo)
    ficha = c.execute("SELECT id FROM personas WHERE usuario_legajo=?", (legajo,)).fetchone()
    mismo_nombre = c.execute("SELECT id, categoria, pide_nombre, usuario_legajo FROM personas WHERE lower(nombre)=lower(?)",
                             (u["nombre"],)).fetchone()
    if mismo_nombre and (not ficha or mismo_nombre["id"] != ficha["id"]):
        if ficha or mismo_nombre["categoria"] != "interno" or mismo_nombre["pide_nombre"] or mismo_nombre["usuario_legajo"]:
            raise ErrorDeNegocio(f"En Personal ya hay otro '{u['nombre']}'. Usar un nombre que lo distinga (por ejemplo, con el apellido).")
        c.execute("UPDATE personas SET usuario_legajo=?, activo=? WHERE id=?", (legajo, u["activo"], mismo_nombre["id"]))
        return
    if ficha:
        c.execute("UPDATE personas SET nombre=?, activo=? WHERE id=?", (u["nombre"], u["activo"], ficha["id"]))
    else:
        c.execute("INSERT INTO personas (nombre, categoria, activo, usuario_legajo) VALUES (?, 'interno', ?, ?)",
                  (u["nombre"], u["activo"], legajo))


def listar() -> list[dict]:
    with transaccion() as c:
        return [dict(r) for r in c.execute(f"SELECT {_COLS} FROM usuarios ORDER BY activo DESC, es_admin DESC, nombre")]


def crear(admin: dict, *, legajo, nombre, password, es_admin=False) -> dict:
    legajo = _numero(legajo, "el legajo", entero=True, minimo=1, maximo=9_999_999)
    if legajo is None:
        raise ErrorDeNegocio("Falta el legajo.")
    nombre = _texto(nombre, "el nombre")
    salt, h = hash_password(_password_valida(password))
    with transaccion() as c:
        if c.execute("SELECT 1 FROM usuarios WHERE legajo=?", (legajo,)).fetchone():
            raise ErrorDeNegocio(f"Ya existe un usuario con legajo {legajo}.")
        c.execute("INSERT INTO usuarios (legajo, nombre, password_hash, salt, es_admin, debe_cambiar) VALUES (?,?,?,?,?,1)",
                  (legajo, nombre, h, salt, int(bool(es_admin))))
        sincronizar_persona(c, legajo)
        return dict(_usuario(c, legajo))


def actualizar(admin: dict, legajo: int, *, nombre, es_admin) -> dict:
    nombre = _texto(nombre, "el nombre")
    with transaccion() as c:
        u = _usuario(c, legajo)
        if u["es_admin"] and not es_admin:
            _exigir_otro_admin(c, legajo, "quitarle el rol de administrador")
        c.execute("UPDATE usuarios SET nombre=?, es_admin=? WHERE legajo=?", (nombre, int(bool(es_admin)), legajo))
        sincronizar_persona(c, legajo)
        return dict(_usuario(c, legajo))


def cambiar_alta(admin: dict, legajo: int, *, activo: bool) -> dict:
    """Dar de baja no borra al usuario (lo que registró sigue diciendo quién fue): solo le impide entrar."""
    with transaccion() as c:
        u = _usuario(c, legajo)
        if not activo:
            if legajo == admin["legajo"]:
                raise ErrorDeNegocio("No podés darte de baja a vos mismo: lo tiene que hacer otro administrador.")
            if u["es_admin"]:
                _exigir_otro_admin(c, legajo, "darlo de baja")
            _cerrar_sesiones(c, legajo)
        c.execute("UPDATE usuarios SET activo=? WHERE legajo=?", (int(activo), legajo))
        sincronizar_persona(c, legajo)
        return dict(_usuario(c, legajo))


def restablecer_password(admin: dict, legajo: int, *, password) -> dict:
    """Para quien se olvidó la contraseña: queda una provisoria que tiene que cambiar al entrar."""
    if legajo == admin["legajo"]:
        raise ErrorDeNegocio("Para tu propia contraseña usá \"Cambiar contraseña\".")
    salt, h = hash_password(_password_valida(password))
    with transaccion() as c:
        _usuario(c, legajo)
        c.execute("UPDATE usuarios SET password_hash=?, salt=?, debe_cambiar=1 WHERE legajo=?", (h, salt, legajo))
        _cerrar_sesiones(c, legajo)
        return dict(_usuario(c, legajo))


def cambiar_password(usuario: dict, *, actual, nueva) -> None:
    """Cada uno cambia la suya; las otras sesiones abiertas se cierran, la actual sigue."""
    nueva = _password_valida(nueva)
    with transaccion() as c:
        u = c.execute("SELECT password_hash, salt FROM usuarios WHERE legajo=?", (usuario["legajo"],)).fetchone()
        if not verificar_password(str(actual or ""), u["salt"], u["password_hash"]):
            raise ErrorDeNegocio("La contraseña actual no es correcta.")
        if verificar_password(nueva, u["salt"], u["password_hash"]):
            raise ErrorDeNegocio("La contraseña nueva tiene que ser distinta de la actual.")
        salt, h = hash_password(nueva)
        c.execute("UPDATE usuarios SET password_hash=?, salt=?, debe_cambiar=0 WHERE legajo=?", (h, salt, usuario["legajo"]))
        _cerrar_sesiones(c, usuario["legajo"], excepto_token=usuario["token"])
