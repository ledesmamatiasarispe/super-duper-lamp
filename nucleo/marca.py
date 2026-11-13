"""El nombre y el logo que muestra la página (barra, pantalla de ingreso y pestaña del navegador). Se cambian en Opciones.

El nombre de fábrica es ajustes.NOMBRE. Se guardan en la tabla config (marca_nombre, marca_logo) y el logo en data/marca/, que
las actualizaciones no tocan. Un logo nuevo se guarda con otro nombre de archivo: así el navegador no muestra el viejo
de su caché."""
import re
import secrets
from pathlib import Path

from . import db
from . import ajustes as v

from .errores import ErrorDeNegocio, NoEncontrado

MAX_NOMBRE = 40
MAX_LOGO = 2 * 1024 * 1024
# extensión -> (MIME, cómo empieza el archivo). La firma evita que un ejecutable entre renombrado.
_TIPOS_LOGO = {"png": ("image/png", (b"\x89PNG\r\n\x1a\n",)), "jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
               "jpeg": ("image/jpeg", (b"\xff\xd8\xff",)), "gif": ("image/gif", (b"GIF87a", b"GIF89a")),
               "webp": ("image/webp", (b"RIFF",)), "svg": ("image/svg+xml", None)}


def carpeta() -> Path:
    return db.DB_PATH.parent / "marca"


def leer_config(c, clave: str) -> str | None:
    r = c.execute("SELECT valor FROM config WHERE clave=?", (clave,)).fetchone()
    return r[0] if r else None


def guardar_config(c, clave: str, valor: str | None) -> None:
    """None borra la clave (vuelve a lo de fábrica)."""
    if valor is None:
        c.execute("DELETE FROM config WHERE clave=?", (clave,))
    else:
        c.execute("INSERT INTO config (clave, valor) VALUES (?, ?) ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor",
                  (clave, valor))


def marca() -> dict:
    """logo es None con el de fábrica; si no, el nombre del archivo."""
    with db.transaccion() as c:
        nombre, logo = leer_config(c, "marca_nombre"), leer_config(c, "marca_logo")
    if logo and not (carpeta() / logo).is_file():
        logo = None   # si alguien borró el archivo, vuelve el de fábrica en vez de una imagen rota
    return {"nombre": nombre or v.NOMBRE, "propio": bool(nombre), "logo": logo, "defecto": v.NOMBRE}


def cambiar_nombre(usuario: dict, nombre) -> dict:
    """Vacío vuelve al nombre de fábrica."""
    nombre = " ".join(str(nombre or "").split())
    if len(nombre) > MAX_NOMBRE:
        raise ErrorDeNegocio(f"El nombre puede tener hasta {MAX_NOMBRE} caracteres.")
    with db.transaccion() as c:
        guardar_config(c, "marca_nombre", nombre if nombre and nombre != v.NOMBRE else None)
    return marca()


def _validar_logo(nombre, datos: bytes) -> str:
    nombre = re.split(r"[\\/]", str(nombre or ""))[-1]
    ext = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if ext not in _TIPOS_LOGO:
        raise ErrorDeNegocio(f"El logo tiene que ser una imagen: {', '.join(sorted(_TIPOS_LOGO))}.")
    if not datos:
        raise ErrorDeNegocio("El archivo está vacío.")
    if len(datos) > MAX_LOGO:
        raise ErrorDeNegocio(f"El logo supera el máximo de {MAX_LOGO // (1024 * 1024)} MB.")
    firmas = _TIPOS_LOGO[ext][1]
    if firmas and not datos.startswith(firmas) or ext == "webp" and datos[8:12] != b"WEBP":
        raise ErrorDeNegocio(f"El archivo no es un .{ext} válido (su contenido no coincide con la extensión).")
    if ext == "svg" and b"<svg" not in datos[:4096].lower():
        raise ErrorDeNegocio("El archivo no es un .svg válido.")
    return "jpg" if ext == "jpeg" else ext


def subir_logo(usuario: dict, *, nombre, datos: bytes) -> dict:
    ext = _validar_logo(nombre, datos)
    carpeta().mkdir(parents=True, exist_ok=True)
    archivo = f"logo-{secrets.token_hex(8)}.{ext}"
    (carpeta() / archivo).write_bytes(datos)
    try:
        with db.transaccion() as c:
            anterior = leer_config(c, "marca_logo")
            guardar_config(c, "marca_logo", archivo)
    except Exception:
        (carpeta() / archivo).unlink(missing_ok=True)
        raise
    if anterior:
        (carpeta() / anterior).unlink(missing_ok=True)
    return marca()


def quitar_logo(usuario: dict) -> dict:
    """Vuelve al logo de fábrica."""
    with db.transaccion() as c:
        anterior = leer_config(c, "marca_logo")
        guardar_config(c, "marca_logo", None)
    if anterior:
        (carpeta() / anterior).unlink(missing_ok=True)
    return marca()


def archivo_logo() -> dict:
    logo = marca()["logo"]
    if not logo:
        raise NoEncontrado("No hay un logo propio cargado.")
    return {"ruta": carpeta() / logo, "tipo": _TIPOS_LOGO[logo.rsplit(".", 1)[-1]][0]}
