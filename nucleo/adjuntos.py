"""Archivos subidos: validación y dónde se guardan. Mismo mecanismo que UltraMantenimiento y Gestión Automotor.

data/adjuntos/<carpeta>/<hex>.<ext>: el nombre original solo se muestra, nunca se usa como ruta. Se valida la FIRMA del
contenido, no solo la extensión, para que un ejecutable renombrado a .jpg no entre. subir() escribe el archivo antes del
INSERT y lo borra si la transacción falla. Cada módulo vincula los adjuntos por id desde sus tablas, y es el módulo el
que decide si uno se puede borrar (si una revisión vieja lo usa, no).
"""
import re
import secrets
from pathlib import Path

from . import db, validar
from .errores import ErrorDeNegocio, NoEncontrado

MAX_BYTES = 20 * 1024 * 1024
# extensión -> (MIME, es imagen, cómo empieza el archivo; None = texto)
TIPOS = {
    "jpg": ("image/jpeg", True, (b"\xff\xd8\xff",)), "jpeg": ("image/jpeg", True, (b"\xff\xd8\xff",)),
    "png": ("image/png", True, (b"\x89PNG\r\n\x1a\n",)), "gif": ("image/gif", True, (b"GIF87a", b"GIF89a")),
    "webp": ("image/webp", True, (b"RIFF",)),
    "pdf": ("application/pdf", False, (b"%PDF",)),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", False, (b"PK\x03\x04",)),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", False, (b"PK\x03\x04",)),
    "csv": ("text/csv", False, None), "txt": ("text/plain", False, None),
}
IMAGENES = ("jpg", "jpeg", "png", "gif", "webp")


def validar_archivo(nombre, datos: bytes, permitidos=tuple(TIPOS)) -> dict:
    """Controla extensión, tamaño y firma. Devuelve nombre (para mostrar), ext, tipo (MIME) y es_imagen."""
    nombre = validar.nombre_de_archivo(nombre)
    ext = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if ext not in permitidos or ext not in TIPOS:
        raise ErrorDeNegocio(f"Tipo de archivo no admitido. Se aceptan: {', '.join(sorted(permitidos))}.")
    if not datos:
        raise ErrorDeNegocio("El archivo está vacío.")
    if len(datos) > MAX_BYTES:
        raise ErrorDeNegocio(f"El archivo supera el máximo de {MAX_BYTES // (1024 * 1024)} MB.")
    mime, es_imagen, firmas = TIPOS[ext]
    if firmas and not datos.startswith(firmas) or ext == "webp" and datos[8:12] != b"WEBP":
        raise ErrorDeNegocio(f"El archivo no es un .{ext} válido (su contenido no coincide con la extensión).")
    if firmas is None and b"\x00" in datos[:4096]:
        raise ErrorDeNegocio(f"El archivo no es un .{ext} de texto válido.")
    return {"nombre": nombre, "ext": "jpg" if ext == "jpeg" else ext, "tipo": mime, "es_imagen": es_imagen}


def carpeta(sub: str) -> Path:
    """data/adjuntos/<sub>: sub lo elige el módulo, igual se limita a letras, números, - y _."""
    return db.DB_PATH.parent / "adjuntos" / re.sub(r"[^A-Za-z0-9_-]", "", sub)


def subir(usuario: dict, *, sub: str, nombre, datos: bytes, permitidos=tuple(TIPOS)) -> dict:
    """Valida, guarda y registra. Se puede llamar dentro de la transacción de un caso de uso (es reentrante)."""
    v = validar_archivo(nombre, datos, permitidos)
    destino_carpeta = carpeta(sub)
    destino_carpeta.mkdir(parents=True, exist_ok=True)
    archivo = f"{secrets.token_hex(16)}.{v['ext']}"
    (destino_carpeta / archivo).write_bytes(datos)
    try:
        with db.transaccion() as c:
            c.execute("INSERT INTO archivos (carpeta, archivo, nombre, tipo, tamanio, es_imagen, creado_por, creado_en) "
                      "VALUES (?,?,?,?,?,?,?,?)", (sub, archivo, v["nombre"], v["tipo"], len(datos), int(v["es_imagen"]),
                                                    usuario.get("nombre"), db.ahora()))
            return dict(c.execute("SELECT * FROM archivos WHERE id=last_insert_rowid()").fetchone())
    except Exception:
        (destino_carpeta / archivo).unlink(missing_ok=True)
        raise


def archivo(adjunto_id: int) -> dict:
    """Dónde está y cómo entregarlo. Quién lo puede bajar lo decide la ruta del módulo."""
    with db.transaccion() as c:
        a = validar.fila(c, "SELECT * FROM archivos WHERE id=?", (adjunto_id,), "ese archivo")
    ruta = carpeta(a["carpeta"]) / a["archivo"]
    if not ruta.is_file():
        raise NoEncontrado("El archivo no está en la carpeta de adjuntos.")
    return {**dict(a), "ruta": ruta}


def eliminar(adjunto_id: int) -> None:
    """Borra la fila y después el archivo. El módulo controla antes que nadie lo use."""
    with db.transaccion() as c:
        a = validar.fila(c, "SELECT carpeta, archivo FROM archivos WHERE id=?", (adjunto_id,), "ese archivo")
        c.execute("DELETE FROM archivos WHERE id=?", (adjunto_id,))
    (carpeta(a["carpeta"]) / a["archivo"]).unlink(missing_ok=True)
