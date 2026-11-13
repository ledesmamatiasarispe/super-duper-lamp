"""crear_app(modulos): la aplicación FastAPI con el núcleo completo y los módulos enchufados.

Rutas del núcleo: la página, sesión (/api/auth/*), usuarios, /api/version, nombre y logo (/api/marca*), puerto
(/api/puerto) y actualizaciones (/api/actualizacion*). Los errores de negocio se traducen acá a HTTP: las rutas de los
módulos no llevan try/except.

La página se ARMA con los módulos: index.html del núcleo tiene marcadores ({{menu}}, {{estilos}}, {{scripts}}...) que
se llenan con las pestañas, estilos y scripts de cada módulo, con ?v=VERSION para que después de actualizar el navegador
no use los archivos viejos de su caché (sin Ctrl+F5). El nombre y el logo elegidos en Opciones también van acá, porque
la pantalla de ingreso los muestra antes de la sesión.
"""
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path

from fastapi import Body, Depends, FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import actualizador, ajustes, auth, db, marca, puerto, usuarios
from .auth import Admin, Usuario
from .errores import ErrorDeNegocio, NoEncontrado
from .modulo import Menu, Modulo

FRONTEND = Path(__file__).resolve().parent / "frontend"
_SOLO_ADMIN = ' class="solo-admin"'
MENU_NUCLEO = [Menu("inicio", "Inicio", orden=0), Menu("usuarios", "Usuarios", solo_admin=True, orden=900)]


def _pagina(modulos: list[Modulo]) -> str:
    v = ajustes.VERSION
    menu = sorted([*MENU_NUCLEO, *(m for mod in modulos for m in mod.menu)], key=lambda m: m.orden)
    vistos, items = set(), []
    for m in menu:   # un módulo puede reemplazar una pestaña del núcleo (su propio Inicio): queda la última
        if m.vista in vistos:
            items = [i for i in items if i.vista != m.vista]
        vistos.add(m.vista)
        items.append(m)
    items.sort(key=lambda m: m.orden)
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    reemplazos = {
        "{{menu}}": "\n        ".join(f'<a data-vista="{escape(m.vista)}" href="#{escape(m.vista)}"'
                                       f'{_SOLO_ADMIN if m.solo_admin else ""}>{escape(m.titulo)}</a>' for m in items),
        "{{estilos}}": "\n  ".join(f'<link rel="stylesheet" href="/static/{mod.nombre}/{e}?v={v}">' for mod in modulos for e in mod.estilos),
        "{{scripts}}": "\n  ".join(f'<script src="/static/{mod.nombre}/{s}?v={v}"></script>' for mod in modulos for s in mod.scripts),
        "{{v}}": v, "{{subtitulo}}": escape(ajustes.SUBTITULO), "{{login}}": escape(ajustes.LOGIN),
        "{{prefijo}}": ajustes.PREFIJO.lower(),
    }
    icono = "/static/app/icono.svg" if ajustes.FRONTEND and (ajustes.FRONTEND / "icono.svg").is_file() else "/static/nucleo/icono.svg"
    for k, val in reemplazos.items():
        html = html.replace(k, val)
    m = marca.marca()
    html = html.replace("{{nombre}}", escape(m["nombre"]))
    if m["logo"]:
        logo = f'/api/marca/logo?v={m["logo"]}'
        html = html.replace('type="image/svg+xml" href="{{icono}}"', f'type="{marca.archivo_logo()["tipo"]}" href="{logo}"')
        html = html.replace("{{icono}}", logo)
    return html.replace("{{icono}}", icono)


def crear_app(modulos: list[Modulo] = (), con_ejemplos: bool = True) -> FastAPI:
    modulos = list(modulos)
    nombres = [m.nombre for m in modulos]
    if len(set(nombres)) != len(nombres) or {"nucleo", "app"} & set(nombres):
        raise ValueError(f"Nombres de módulo repetidos o reservados: {nombres}")

    @asynccontextmanager
    async def ciclo(_app):
        db.inicializar(modulos, con_ejemplos=con_ejemplos)
        for m in modulos:
            if m.al_iniciar:
                m.al_iniciar()
        actualizador.buscar_en_segundo_plano()
        yield
        for m in modulos:
            if m.al_terminar:
                m.al_terminar()

    app = FastAPI(title=ajustes.NOMBRE, lifespan=ciclo)
    app.state.modulos = modulos
    app.mount("/static/nucleo", StaticFiles(directory=FRONTEND), name="nucleo")
    if ajustes.FRONTEND and ajustes.FRONTEND.is_dir():
        app.mount("/static/app", StaticFiles(directory=ajustes.FRONTEND), name="app")
    for m in modulos:
        if m.carpeta and (m.carpeta / "frontend").is_dir():
            app.mount(f"/static/{m.nombre}", StaticFiles(directory=m.carpeta / "frontend"), name=m.nombre)

    @app.exception_handler(ErrorDeNegocio)
    async def _negocio(_req: Request, e: ErrorDeNegocio):
        return JSONResponse({"detail": str(e)}, status_code=400)

    @app.exception_handler(NoEncontrado)
    async def _no_encontrado(_req: Request, e: NoEncontrado):
        return JSONResponse({"detail": str(e)}, status_code=404)

    @app.get("/", include_in_schema=False)
    def pagina():
        return HTMLResponse(_pagina(modulos), headers={"Cache-Control": "no-cache"})

    @app.get("/api/version")
    def version():
        """Sin sesión: la pantalla la consulta mientras la app se reinicia después de actualizar, y al arrancar otra
        copia pregunta quién atiende un puerto (app es el identificador fijo, no el nombre de Opciones)."""
        return {"version": ajustes.VERSION, "app": ajustes.APP}

    # ── sesión ──
    @app.post("/api/auth/login")
    def login(body: dict = Body(...)):
        return auth.login(body.get("usuario"), body.get("password"))

    @app.post("/api/auth/logout")
    def logout(u: dict = Depends(auth.sesion)):
        auth.logout(u["token"])
        return {"ok": True}

    @app.get("/api/auth/yo")
    def yo(u: dict = Usuario):
        return {k: u[k] for k in ("id", "usuario", "nombre", "es_admin", "debe_cambiar")}

    @app.post("/api/auth/password")
    def cambiar_mi_password(body: dict = Body(...), u: dict = Usuario):
        usuarios.cambiar_password(u, actual=body.get("actual"), nueva=body.get("nueva"))
        return {"ok": True}

    # ── usuarios ──
    @app.get("/api/usuarios")
    def listar_usuarios(u: dict = Admin):
        return usuarios.listar()

    @app.post("/api/usuarios")
    def crear_usuario(body: dict = Body(...), u: dict = Admin):
        return usuarios.crear(u, **{k: body.get(k) for k in ("usuario", "nombre", "password", "es_admin")})

    @app.put("/api/usuarios/{uid}")
    def actualizar_usuario(uid: int, body: dict = Body(...), u: dict = Admin):
        return usuarios.actualizar(u, uid, nombre=body.get("nombre"), es_admin=body.get("es_admin"))

    @app.post("/api/usuarios/{uid}/baja")
    def baja_usuario(uid: int, u: dict = Admin):
        return usuarios.cambiar_alta(u, uid, activo=False)

    @app.post("/api/usuarios/{uid}/alta")
    def alta_usuario(uid: int, u: dict = Admin):
        return usuarios.cambiar_alta(u, uid, activo=True)

    @app.post("/api/usuarios/{uid}/password")
    def restablecer_password(uid: int, body: dict = Body(...), u: dict = Admin):
        return usuarios.restablecer_password(u, uid, password=body.get("password"))

    # ── nombre y logo ──
    @app.get("/api/marca/logo", include_in_schema=False)
    def ver_logo():
        """Sin sesión: lo muestra la pantalla de ingreso. Un SVG puede traer scripts: la política de seguridad no los
        deja correr aunque alguien abra la imagen sola en una pestaña."""
        a = marca.archivo_logo()
        return FileResponse(a["ruta"], media_type=a["tipo"], headers={
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:",
            "X-Content-Type-Options": "nosniff", "Cache-Control": "public, max-age=31536000, immutable"})

    @app.get("/api/marca")
    def ver_marca(u: dict = Usuario):
        return marca.marca()

    @app.put("/api/marca/nombre")
    def cambiar_nombre(body: dict = Body(...), u: dict = Admin):
        return marca.cambiar_nombre(u, body.get("nombre"))

    @app.post("/api/marca/logo")
    async def subir_logo(archivo: UploadFile = File(...), u: dict = Admin):
        return marca.subir_logo(u, nombre=archivo.filename, datos=await archivo.read(marca.MAX_LOGO + 1))

    @app.delete("/api/marca/logo")
    def quitar_logo(u: dict = Admin):
        return marca.quitar_logo(u)

    # ── puerto ──
    @app.get("/api/puerto")
    def ver_puerto(u: dict = Admin):
        return puerto.estado()

    @app.put("/api/puerto")
    def cambiar_puerto(body: dict = Body(...), u: dict = Admin):
        return puerto.cambiar(u, body.get("puerto"))

    # ── actualizaciones ──
    @app.get("/api/actualizacion")
    def estado_actualizacion(u: dict = Usuario):
        return actualizador.estado(es_admin=bool(u["es_admin"]))

    @app.post("/api/actualizacion/buscar")
    def buscar_actualizacion(u: dict = Admin):
        actualizador.buscar(forzar=True)
        return actualizador.estado(es_admin=True)

    @app.post("/api/actualizacion/posponer")
    def posponer_actualizacion(u: dict = Admin):
        return {"pospuesta_hasta": actualizador.posponer()}

    @app.post("/api/actualizacion/instalar")
    def instalar_actualizacion(u: dict = Admin):
        return actualizador.instalar()

    for m in modulos:
        if m.router is not None:
            app.include_router(m.router)
    return app
