"""Usuarios del sistema: alta, rol, baja y contraseñas.

Reglas que evitan quedarse afuera: siempre queda al menos un administrador activo, nadie se da de baja a sí mismo, y la
baja o el cambio de contraseña cierran las sesiones abiertas de esa persona. Una contraseña puesta por un administrador
(alta o restablecer) es provisoria: no bloquea, pero la pantalla avisa hasta que se cambie.

AL_GUARDAR: funciones (c, usuario_id) que un módulo agrega para enterarse de un alta o un cambio, dentro de la misma
transacción (por ejemplo, UltraMantenimiento mantiene la ficha de Personal igual al usuario). Si lanzan, no se guarda.
"""
import sqlite3

from . import validar
from .auth import hash_password, verificar_password
from .db import ahora, transaccion
from .errores import ErrorDeNegocio, NoEncontrado

MINIMO_PASSWORD = 6
_COLS = "id, usuario, nombre, es_admin, activo, debe_cambiar"
AL_GUARDAR: list = []


def _password_valida(password) -> str:
    p = str(password or "")
    if len(p) < MINIMO_PASSWORD:
        raise ErrorDeNegocio(f"La contraseña tiene que tener al menos {MINIMO_PASSWORD} caracteres.")
    return p


def _usuario(c, uid: int) -> sqlite3.Row:
    u = c.execute(f"SELECT {_COLS} FROM usuarios WHERE id=?", (uid,)).fetchone()
    if not u:
        raise NoEncontrado("No existe ese usuario.")
    return u


def _avisar(c, uid: int) -> dict:
    for f in AL_GUARDAR:
        f(c, uid)
    return dict(_usuario(c, uid))


def _exigir_otro_admin(c, uid: int, accion: str) -> None:
    if not c.execute("SELECT count(*) FROM usuarios WHERE es_admin=1 AND activo=1 AND id<>?", (uid,)).fetchone()[0]:
        raise ErrorDeNegocio(f"No se puede {accion}: es el único administrador activo y el sistema quedaría sin quien lo "
                             "configure. Primero hay que nombrar otro administrador.")


def _cerrar_sesiones(c, uid: int, excepto_token: str | None = None) -> None:
    c.execute("UPDATE sesiones SET activa=0 WHERE usuario_id=? AND token IS NOT ?", (uid, excepto_token))


def listar() -> list[dict]:
    with transaccion() as c:
        return [dict(r) for r in c.execute(f"SELECT {_COLS} FROM usuarios ORDER BY activo DESC, es_admin DESC, nombre")]


def crear(admin: dict, *, usuario, nombre, password, es_admin=False) -> dict:
    usuario = validar.texto(usuario, "el usuario", maximo=40)
    nombre = validar.texto(nombre, "el nombre", maximo=80)
    salt, h = hash_password(_password_valida(password))
    with transaccion() as c:
        if c.execute("SELECT 1 FROM usuarios WHERE usuario=?", (usuario,)).fetchone():
            raise ErrorDeNegocio(f"Ya existe el usuario '{usuario}'.")
        c.execute("INSERT INTO usuarios (usuario, nombre, password_hash, salt, es_admin, debe_cambiar, creado_en) "
                  "VALUES (?,?,?,?,?,1,?)", (usuario, nombre, h, salt, int(bool(es_admin)), ahora()))
        return _avisar(c, c.execute("SELECT last_insert_rowid()").fetchone()[0])


def actualizar(admin: dict, uid: int, *, nombre, es_admin) -> dict:
    nombre = validar.texto(nombre, "el nombre", maximo=80)
    with transaccion() as c:
        u = _usuario(c, uid)
        if u["es_admin"] and not es_admin:
            _exigir_otro_admin(c, uid, "quitarle el rol de administrador")
        c.execute("UPDATE usuarios SET nombre=?, es_admin=? WHERE id=?", (nombre, int(bool(es_admin)), uid))
        return _avisar(c, uid)


def cambiar_alta(admin: dict, uid: int, *, activo: bool) -> dict:
    """Dar de baja no borra al usuario (lo que registró sigue diciendo quién fue): solo le impide entrar."""
    with transaccion() as c:
        u = _usuario(c, uid)
        if not activo:
            if uid == admin["id"]:
                raise ErrorDeNegocio("No podés darte de baja a vos mismo: lo tiene que hacer otro administrador.")
            if u["es_admin"]:
                _exigir_otro_admin(c, uid, "darlo de baja")
            _cerrar_sesiones(c, uid)
        c.execute("UPDATE usuarios SET activo=? WHERE id=?", (int(activo), uid))
        return _avisar(c, uid)


def restablecer_password(admin: dict, uid: int, *, password) -> dict:
    """Para quien se olvidó la contraseña: queda una provisoria (con aviso hasta que la cambie)."""
    if uid == admin["id"]:
        raise ErrorDeNegocio("Para tu propia contraseña usá \"Cambiar contraseña\".")
    salt, h = hash_password(_password_valida(password))
    with transaccion() as c:
        _usuario(c, uid)
        c.execute("UPDATE usuarios SET password_hash=?, salt=?, debe_cambiar=1 WHERE id=?", (h, salt, uid))
        _cerrar_sesiones(c, uid)
        return dict(_usuario(c, uid))


def cambiar_password(usuario: dict, *, actual, nueva) -> None:
    """Cada uno cambia la suya; las otras sesiones abiertas se cierran, la actual sigue."""
    nueva = _password_valida(nueva)
    with transaccion() as c:
        u = c.execute("SELECT password_hash, salt FROM usuarios WHERE id=?", (usuario["id"],)).fetchone()
        if not verificar_password(str(actual or ""), u["salt"], u["password_hash"]):
            raise ErrorDeNegocio("La contraseña actual no es correcta.")
        if verificar_password(nueva, u["salt"], u["password_hash"]):
            raise ErrorDeNegocio("La contraseña nueva tiene que ser distinta de la actual.")
        salt, h = hash_password(nueva)
        c.execute("UPDATE usuarios SET password_hash=?, salt=?, debe_cambiar=0 WHERE id=?", (h, salt, usuario["id"]))
        _cerrar_sesiones(c, usuario["id"], excepto_token=usuario["token"])
