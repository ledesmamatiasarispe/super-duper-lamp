"""Rutas de la base común: la página, la versión, el nombre y logo, y el puerto.

MISMO ARCHIVO en UltraMantenimiento, Gestión Automotor y Edificios de Mamá: main.py hace app.include_router(router) y
sirve "/" con pagina(). Lo propio de cada app sale de version.py."""
from html import escape
from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from . import auth, marca, puerto
from . import version as v

router = APIRouter()
Usuario = Depends(auth.usuario_actual)
Admin = Depends(auth.solo_admin)


def pagina(index: Path) -> HTMLResponse:
    """index.html con dos ajustes:
    - pide sus .js y .css con la versión (app.js?v=1.0.3): al actualizar cambia la dirección y el navegador baja los
      nuevos en vez de seguir con los de su caché; la página misma no se guarda, para que siempre traiga la versión;
    - el nombre y el logo elegidos en Opciones (van acá porque el login también los muestra, antes de la sesión)."""
    html = index.read_text(encoding="utf-8")
    for ext in (".js", ".css"):
        html = html.replace(f'{ext}"', f'{ext}?v={v.VERSION}"')
    m = marca.marca()
    html = html.replace(v.NOMBRE, escape(m["nombre"]))
    if m["logo"]:
        logo = f'/api/marca/logo?v={m["logo"]}'
        html = html.replace('type="image/svg+xml" href="/static/icono.svg"', f'type="{marca.archivo_logo()["tipo"]}" href="{logo}"')
        html = html.replace("/static/icono.svg", logo).replace("/static/logo.svg", logo)
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})


@router.get("/api/version")
def version():
    """Sin sesión: la pantalla la consulta mientras la app se reinicia después de actualizar, y al arrancar otra copia
    pregunta quién atiende un puerto (app es el identificador fijo, no el nombre de Opciones)."""
    return {"version": v.VERSION, "app": v.APP}


# ── nombre y logo ──
@router.get("/api/marca/logo", include_in_schema=False)
def ver_logo():
    """Sin sesión: lo muestra la pantalla de ingreso. Un SVG puede traer scripts: la política de seguridad no los deja
    correr aunque alguien abra la imagen sola en una pestaña."""
    a = marca.archivo_logo()
    return FileResponse(a["ruta"], media_type=a["tipo"], headers={
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:",
        "X-Content-Type-Options": "nosniff", "Cache-Control": "public, max-age=31536000, immutable"})


@router.get("/api/marca")
def ver_marca(u: dict = Usuario):
    return marca.marca()


@router.put("/api/marca/nombre")
def cambiar_nombre(body: dict = Body(...), u: dict = Admin):
    return marca.cambiar_nombre(u, body.get("nombre"))


@router.post("/api/marca/logo")
async def subir_logo(archivo: UploadFile = File(...), u: dict = Admin):
    return marca.subir_logo(u, nombre=archivo.filename, datos=await archivo.read(marca.MAX_LOGO + 1))


@router.delete("/api/marca/logo")
def quitar_logo(u: dict = Admin):
    return marca.quitar_logo(u)


# ── puerto ──
@router.get("/api/puerto")
def ver_puerto(u: dict = Admin):
    return puerto.estado()


@router.put("/api/puerto")
def cambiar_puerto(body: dict = Body(...), u: dict = Admin):
    return puerto.cambiar(u, body.get("puerto"))
