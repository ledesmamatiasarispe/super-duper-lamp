"""API y archivos de la pantalla. Rutas delgadas: leen el pedido, llaman a servicios y devuelven el resultado.

Los cuerpos llegan como dict y se pasan crudos a servicios: es ahí donde se valida, así un "7,5" o una
fecha mal escrita termina en un mensaje claro (400) y no en un error interno.
"""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Body, Depends, FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import actualizador, auth, rutas_base, servicios as sv, usuarios
from . import calendario as cal
from .db import inicializar

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def _inicio(_app):
    inicializar()
    for hecho in sv.separar_instructivos_compartidos():   # una sola vez: después el índice único impide compartir
        print("Instructivo compartido separado:", hecho)
    actualizador.buscar_en_segundo_plano()
    yield


app = FastAPI(title="UltraMantenimiento", lifespan=_inicio)
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
app.include_router(rutas_base.router)

Usuario = Depends(auth.usuario_actual)
Admin = Depends(auth.solo_admin)


@app.exception_handler(sv.ErrorDeNegocio)
async def _error_negocio(_req: Request, e: sv.ErrorDeNegocio):
    return JSONResponse({"detail": str(e)}, status_code=400)


@app.exception_handler(sv.NoEncontrado)
async def _no_encontrado(_req: Request, e: sv.NoEncontrado):
    return JSONResponse({"detail": str(e)}, status_code=404)


@app.get("/", include_in_schema=False)
def pantalla():
    return rutas_base.pagina(FRONTEND / "index.html")


# ── sesión ──
@app.post("/api/auth/login")
def login(body: dict = Body(...)):
    try:
        legajo = int(str(body.get("legajo", "")).strip())
    except ValueError:
        raise sv.ErrorDeNegocio("El legajo es un número.")
    return auth.login(legajo, str(body.get("password", "")))


Sesion = Depends(auth.sesion)


@app.post("/api/auth/logout")
def logout(u: dict = Sesion):
    auth.logout(u["token"])
    return {"ok": True}


@app.get("/api/auth/yo")
def yo(u: dict = Sesion):
    return {k: u[k] for k in ("legajo", "nombre", "es_admin", "debe_cambiar")}


@app.post("/api/auth/password")
def cambiar_mi_password(body: dict = Body(...), u: dict = Sesion):
    usuarios.cambiar_password(u, actual=body.get("actual"), nueva=body.get("nueva"))
    return {"ok": True}


# ── versión y actualizaciones ──
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


# ── usuarios (solo administradores) ──
@app.get("/api/usuarios")
def listar_usuarios(u: dict = Admin):
    return usuarios.listar()


@app.post("/api/usuarios")
def crear_usuario(body: dict = Body(...), u: dict = Admin):
    return usuarios.crear(u, **{k: body.get(k) for k in ("legajo", "nombre", "password", "es_admin")})


@app.put("/api/usuarios/{legajo}")
def actualizar_usuario(legajo: int, body: dict = Body(...), u: dict = Admin):
    return usuarios.actualizar(u, legajo, nombre=body.get("nombre"), es_admin=bool(body.get("es_admin")))


@app.post("/api/usuarios/{legajo}/baja")
def baja_usuario(legajo: int, u: dict = Admin):
    return usuarios.cambiar_alta(u, legajo, activo=False)


@app.post("/api/usuarios/{legajo}/alta")
def alta_usuario(legajo: int, u: dict = Admin):
    return usuarios.cambiar_alta(u, legajo, activo=True)


@app.post("/api/usuarios/{legajo}/password")
def restablecer_password(legajo: int, body: dict = Body(...), u: dict = Admin):
    return usuarios.restablecer_password(u, legajo, password=body.get("password"))


# ── mapa de planta ──
@app.get("/api/planos")
def mapa_planta(u: dict = Usuario):
    return sv.mapa_planta()


@app.post("/api/planos")
def crear_plano(body: dict = Body(...), u: dict = Admin):
    return sv.crear_plano(u, nombre=body.get("nombre"), ancho=body.get("ancho"), alto=body.get("alto"))


@app.put("/api/planos/{plano_id}")
def guardar_plano(plano_id: int, body: dict = Body(...), u: dict = Admin):
    return sv.guardar_plano(u, plano_id, **{k: body.get(k) for k in ("nombre", "ancho", "alto", "elementos", "equipos")})


@app.delete("/api/planos/{plano_id}")
def eliminar_plano(plano_id: int, u: dict = Admin):
    sv.eliminar_plano(u, plano_id)
    return {"ok": True}


# ── listas para los formularios ──
@app.get("/api/opciones")
def opciones(u: dict = Usuario):
    return {"frecuencias": cal.FRECUENCIAS, "intervalos": cal.INTERVALO_MESES, "resultados": cal.RESULTADOS, "personas": sv.listar_personas(),
            "equipos": sv.listar_equipos(), "secciones": sv.secciones_disponibles(), "areas": sv.listar_areas()}


# ── áreas ──
@app.get("/api/areas/seguimiento")
def seguimiento_areas(anio: int, u: dict = Usuario):
    return sv.seguimiento_areas(anio)


@app.post("/api/areas")
def crear_area(body: dict = Body(...), u: dict = Admin):
    return sv.crear_area(u, nombre=body.get("nombre"))


@app.put("/api/areas/{area_id}")
def renombrar_area(area_id: int, body: dict = Body(...), u: dict = Admin):
    return sv.renombrar_area(u, area_id, nombre=body.get("nombre"))


@app.post("/api/areas/{area_id}/baja")
def baja_area(area_id: int, u: dict = Admin):
    return sv.cambiar_alta_area(u, area_id, activo=False)


@app.post("/api/areas/{area_id}/alta")
def alta_area(area_id: int, u: dict = Admin):
    return sv.cambiar_alta_area(u, area_id, activo=True)


@app.delete("/api/areas/{area_id}")
def eliminar_area(area_id: int, u: dict = Admin):
    sv.eliminar_area(u, area_id)
    return {"ok": True}


@app.post("/api/personas")
def crear_persona(body: dict = Body(...), u: dict = Admin):
    return sv.crear_persona(u, nombre=body.get("nombre"), categoria=body.get("categoria"), contacto=body.get("contacto"))


@app.put("/api/personas/{persona_id}")
def actualizar_persona(persona_id: int, body: dict = Body(...), u: dict = Admin):
    return sv.actualizar_persona(u, persona_id, nombre=body.get("nombre"), contacto=body.get("contacto"))


@app.post("/api/personas/{persona_id}/baja")
def baja_persona(persona_id: int, u: dict = Admin):
    return sv.cambiar_alta_persona(u, persona_id, activo=False)


@app.post("/api/personas/{persona_id}/alta")
def alta_persona(persona_id: int, u: dict = Admin):
    return sv.cambiar_alta_persona(u, persona_id, activo=True)


@app.get("/api/personas/seguimiento")
def seguimiento_personas(anio: int, u: dict = Usuario):
    return sv.seguimiento_personas(anio)


@app.get("/api/personas/{persona_id}/trabajos")
def trabajos_de_persona(persona_id: int, anio: int, u: dict = Usuario):
    return sv.trabajos_de_persona(persona_id, anio)


# ── equipos ──
@app.get("/api/equipos")
def equipos(baja: bool = False, u: dict = Usuario):
    return sv.listar_equipos(incluir_baja=baja)


@app.post("/api/equipos")
def crear_equipo(body: dict = Body(...), u: dict = Admin):
    return sv.crear_equipo(u, copiar_de=body.get("copiar_de"),
                           **{k: body.get(k) for k in ("nombre", "area_id", "marca_modelo", "usa_horometro")})


@app.put("/api/equipos/{equipo_id}")
def actualizar_equipo(equipo_id: int, body: dict = Body(...), u: dict = Admin):
    return sv.actualizar_equipo(u, equipo_id, **{k: body.get(k) for k in ("nombre", "area_id", "marca_modelo", "usa_horometro")})


@app.post("/api/equipos/{equipo_id}/obsoleto")
def equipo_obsoleto(equipo_id: int, body: dict = Body(...), u: dict = Admin):
    return sv.marcar_equipo_obsoleto(u, equipo_id, motivo=body.get("motivo"))


@app.post("/api/equipos/{equipo_id}/alta")
def reactivar_equipo(equipo_id: int, u: dict = Admin):
    return sv.reactivar_equipo(u, equipo_id)


@app.put("/api/equipos/{equipo_id}/instructivos")
def asignar_instructivos(equipo_id: int, body: dict = Body(...), u: dict = Admin):
    return sv.asignar_instructivos_equipo(u, equipo_id, instructivo_ids=body.get("instructivo_ids"))


@app.post("/api/equipos/{equipo_id}/copiar-instructivo")
def copiar_instructivo(equipo_id: int, body: dict = Body(...), u: dict = Admin):
    return sv.copiar_instructivo_de_equipo(u, equipo_id, desde=body.get("desde"))


@app.delete("/api/equipos/{equipo_id}")
def eliminar_equipo(equipo_id: int, u: dict = Admin):
    sv.eliminar_equipo(u, equipo_id)
    return {"ok": True}


# ── instructivos ──
_CONTENIDO = ("titulo", "descripcion", "seguridad", "repuestos", "secciones", "bloques", "archivos", "orden")


@app.get("/api/instructivos")
def instructivos(u: dict = Usuario):
    return sv.listar_instructivos()


@app.get("/api/instructivos/{it_id}")
def instructivo(it_id: int, u: dict = Usuario):
    return sv.obtener_instructivo(it_id)


@app.post("/api/instructivos")
def crear_instructivo(body: dict = Body(...), u: dict = Admin):
    return sv.crear_instructivo(u, equipo_id=body.get("equipo_id"), **{k: body.get(k) for k in _CONTENIDO})


@app.put("/api/instructivos/{it_id}")
def revisar_instructivo(it_id: int, body: dict = Body(...), u: dict = Admin):
    return sv.revisar_instructivo(u, it_id, motivo=body.get("motivo"), **{k: body.get(k) for k in _CONTENIDO})


@app.get("/api/instructivos/{it_id}/revisiones/{revision}")
def revision_anterior(it_id: int, revision: int, u: dict = Usuario):
    return sv.version_instructivo(it_id, revision)


@app.post("/api/instructivos/{it_id}/obsoleto")
def obsoleto(it_id: int, body: dict = Body(...), u: dict = Admin):
    return sv.marcar_obsoleto(u, it_id, motivo=body.get("motivo"))


@app.delete("/api/instructivos/{it_id}")
def eliminar_instructivo(it_id: int, u: dict = Admin):
    sv.eliminar_instructivo(u, it_id)
    return {"ok": True}


@app.post("/api/instructivos/{it_id}/adjuntos")
async def subir_adjunto(it_id: int, archivo: UploadFile = File(...), u: dict = Admin):
    datos = await archivo.read(sv.MAX_ADJUNTO + 1)   # uno de más alcanza para saber que se pasó
    return sv.subir_adjunto(u, it_id, nombre=archivo.filename, datos=datos)


@app.get("/api/adjuntos/{adjunto_id}")
def descargar_adjunto(adjunto_id: int, u: dict = Usuario):
    """Con sesión (header Bearer): la pantalla lo pide con fetch y lo muestra como blob, también las <img>."""
    a = sv.archivo_adjunto(adjunto_id)
    return FileResponse(a["ruta"], media_type=a["tipo"], filename=a["nombre"],
                        content_disposition_type="inline" if a["es_imagen"] or a["tipo"] == "application/pdf" else "attachment",
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"})


@app.delete("/api/adjuntos/{adjunto_id}")
def eliminar_adjunto(adjunto_id: int, u: dict = Admin):
    sv.eliminar_adjunto(u, adjunto_id)
    return {"ok": True}


# ── Plan ──
_TAREA = ("equipo_id", "seccion_id", "frecuencia", "mes_inicio", "meses_especificos", "cada_horas",
          "proximo_inicial", "responsable_id", "observaciones")


@app.get("/api/tareas")
def tareas(baja: bool = False, u: dict = Usuario):
    return sv.listar_tareas(incluir_baja=baja)


@app.post("/api/tareas")
def crear_tarea(body: dict = Body(...), u: dict = Admin):
    return sv.crear_tarea(u, **{k: body.get(k) for k in _TAREA})


@app.get("/api/tareas/sin-programar")
def tareas_sin_programar(u: dict = Admin):
    return sv.tareas_sin_programar()


@app.post("/api/tareas/lote")
def programar_tareas(body: dict = Body(...), u: dict = Admin):
    return sv.programar_tareas(u, [{k: t.get(k) for k in _TAREA} for t in body.get("tareas") or [] if isinstance(t, dict)])


@app.put("/api/tareas/{tarea_id}")
def actualizar_tarea(tarea_id: int, body: dict = Body(...), u: dict = Admin):
    return sv.actualizar_tarea(u, tarea_id, **{k: body.get(k) for k in _TAREA})


@app.post("/api/tareas/{tarea_id}/baja")
def baja_tarea(tarea_id: int, u: dict = Admin):
    return sv.cambiar_alta_tarea(u, tarea_id, activa=False)


@app.post("/api/tareas/{tarea_id}/alta")
def alta_tarea(tarea_id: int, u: dict = Admin):
    return sv.cambiar_alta_tarea(u, tarea_id, activa=True)


# ── cronograma y registros ──
@app.get("/api/cronograma")
def cronograma(anio: int, u: dict = Usuario):
    return sv.cronograma(anio)


@app.get("/api/pendientes")
def pendientes(u: dict = Usuario):
    return sv.pendientes()


@app.post("/api/tareas/{tarea_id}/registros")
def registrar(tarea_id: int, body: dict = Body(...), u: dict = Usuario):
    campos = ("fecha", "resultado", "realizado_por_id", "realizado_por_nombre", "horas_hombre", "horometro", "novedades", "repuestos", "reprogramado_para")
    return sv.registrar_mantenimiento(u, tarea_id, **{k: body.get(k) for k in campos})


@app.get("/api/registros")
def registros(anio: Optional[int] = None, equipo_id: Optional[int] = None, u: dict = Usuario):
    return sv.listar_registros(anio, equipo_id)


@app.delete("/api/registros/{registro_id}")
def anular_registro(registro_id: int, u: dict = Admin):
    sv.anular_registro(u, registro_id)
    return {"ok": True}


# ── horómetros ──
@app.get("/api/horometros")
def horometros(u: dict = Usuario):
    return sv.estado_horometros()


@app.get("/api/horometros/grilla")
def grilla_horometros(corrimiento: int = 0, u: dict = Usuario):
    return sv.grilla_horometros(corrimiento)


@app.get("/api/lecturas")
def lecturas(equipo_id: Optional[int] = None, u: dict = Usuario):
    return sv.listar_lecturas(equipo_id)


@app.post("/api/equipos/{equipo_id}/lecturas")
def registrar_lectura(equipo_id: int, body: dict = Body(...), u: dict = Usuario):
    return sv.registrar_lectura(u, equipo_id, **{k: body.get(k) for k in ("fecha", "horas", "anoto_id", "observaciones")})


@app.post("/api/equipos/{equipo_id}/cambio-horometro")
def cambiar_horometro(equipo_id: int, body: dict = Body(...), u: dict = Admin):
    return sv.cambiar_horometro(u, equipo_id, **{k: body.get(k) for k in ("fecha", "horas", "horas_anterior", "anoto_id", "observaciones")})


# ── correctivos ──
@app.get("/api/correctivos")
def correctivos(anio: Optional[int] = None, equipo_id: Optional[int] = None, u: dict = Usuario):
    return sv.listar_correctivos(anio, equipo_id)


@app.post("/api/equipos/{equipo_id}/correctivos")
def registrar_correctivo(equipo_id: int, body: dict = Body(...), u: dict = Usuario):
    campos = ("fecha", "falla", "causa", "accion", "horas_parada", "horas_hombre", "repuestos",
              "realizado_por_id", "realizado_por_nombre", "accion_sgc", "observaciones")
    return sv.registrar_correctivo(u, equipo_id, **{k: body.get(k) for k in campos})
