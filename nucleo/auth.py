"""Login con token Bearer y sesiones en la base. La contraseña se guarda con PBKDF2 (estándar de la librería), nunca
en texto ni con un SHA-256 simple, que se adivina demasiado rápido si alguien se lleva el archivo de la base.

Autorización binaria: administrador sí/no. Una contraseña provisoria (debe_cambiar) NO bloquea: la pantalla muestra un
aviso amarillo hasta que se cambie en Opciones.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, Header, HTTPException

from . import ajustes
from .db import ahora, transaccion

HORAS_SESION = 12
_ITERACIONES = 200_000


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITERACIONES).hex()
    return salt, h


def verificar_password(password: str, salt: str, guardado: str) -> bool:
    return hmac.compare_digest(hash_password(password, salt)[1], guardado)


def _publico(u) -> dict:
    return {"id": u["id"], "usuario": u["usuario"], "nombre": u["nombre"], "es_admin": bool(u["es_admin"]),
            "debe_cambiar": bool(u["debe_cambiar"])}


def login(usuario, password) -> dict:
    with transaccion() as c:
        u = c.execute("SELECT id, usuario, nombre, password_hash, salt, es_admin, debe_cambiar FROM usuarios "
                      "WHERE usuario=? AND activo=1", (str(usuario or "").strip(),)).fetchone()
        if not u or not verificar_password(str(password or ""), u["salt"], u["password_hash"]):
            raise HTTPException(401, f"{ajustes.LOGIN} o contraseña incorrectos")
        token = secrets.token_hex(32)
        c.execute("INSERT INTO sesiones (token, usuario_id, vence_en) VALUES (?,?,?)",
                  (token, u["id"], (datetime.now() + timedelta(hours=HORAS_SESION)).isoformat()))
    return {"token": token, "usuario": _publico(u)}


def logout(token: str) -> None:
    with transaccion() as c:
        c.execute("UPDATE sesiones SET activa=0 WHERE token=?", (token,))


def _token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Hay que iniciar sesión")
    return authorization.split(" ", 1)[1].strip()


def sesion(authorization: Optional[str] = Header(None)) -> dict:
    """La sesión vigente: quién es y si sigue con una contraseña provisoria (debe_cambiar)."""
    token = _token(authorization)
    with transaccion() as c:
        u = c.execute("SELECT u.id, u.usuario, u.nombre, u.es_admin, u.debe_cambiar FROM sesiones s "
                      "JOIN usuarios u ON u.id = s.usuario_id WHERE s.token=? AND s.activa=1 AND s.vence_en>? AND u.activo=1",
                      (token, ahora())).fetchone()
    if not u:
        raise HTTPException(401, "La sesión venció: iniciar sesión de nuevo")
    return {**_publico(u), "token": token}


def usuario_actual(usuario: dict = Depends(sesion)) -> dict:
    """Para todo lo que usa la app. La contraseña provisoria no bloquea (la pantalla avisa)."""
    return usuario


def solo_admin(usuario: dict = Depends(usuario_actual)) -> dict:
    """Configurar el sistema y manejar usuarios es de administrador; usar el día a día, de cualquiera."""
    if not usuario["es_admin"]:
        raise HTTPException(403, "Solo un administrador puede hacer esto")
    return usuario


Usuario = Depends(usuario_actual)
Admin = Depends(solo_admin)
