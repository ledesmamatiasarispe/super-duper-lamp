"""Rutas de mantenimiento. Delgadas: leen el pedido, llaman a servicios y devuelven el resultado.

Los cuerpos llegan como dict y se pasan crudos a servicios: es ahí donde se valida, así un "7,5" o una fecha mal escrita
termina en un mensaje claro (400) y no en un error interno. Los errores de negocio los traduce el núcleo.
La sesión, los usuarios, la versión, el nombre y logo, el puerto y las actualizaciones son rutas del núcleo.
"""
from typing import Optional

from fastapi import APIRouter, Body, File, UploadFile
from fastapi.responses import FileResponse

from nucleo.auth import Admin, Usuario

from . import calendario as cal
from . import servicios as sv

router = APIRouter()


# ── mapa de planta ──
@router.get("/api/planos")
def mapa_planta(u: dict = Usuario):
    return sv.mapa_planta()


@router.post("/api/planos")
def crear_plano(body: dict = Body(...), u: dict = Admin):
    return sv.crear_plano(u, nombre=body.get("nombre"), ancho=body.get("ancho"), alto=body.get("alto"))


@router.put("/api/planos/{plano_id}")
def guardar_plano(plano_id: int, body: dict = Body(...), u: dict = Admin):
    return sv.guardar_plano(u, plano_id, **{k: body.get(k) for k in ("nombre", "ancho", "alto", "elementos", "equipos")})


@router.delete("/api/planos/{plano_id}")
def eliminar_plano(plano_id: int, u: dict = Admin):
    sv.eliminar_plano(u, plano_id)
    return {"ok": True}


# ── listas para los formularios ──
@router.get("/api/opciones")
def opciones(u: dict = Usuario):
    return {"frecuencias": cal.FRECUENCIAS, "intervalos": cal.INTERVALO_MESES, "resultados": cal.RESULTADOS, "personas": sv.listar_personas(),
            "equipos": sv.listar_equipos(), "secciones": sv.secciones_disponibles(), "areas": sv.listar_areas()}


# ── áreas ──
@router.get("/api/areas/seguimiento")
def seguimiento_areas(anio: int, u: dict = Usuario):
    return sv.seguimiento_areas(anio)


@router.post("/api/areas")
def crear_area(body: dict = Body(...), u: dict = Admin):
    return sv.crear_area(u, nombre=body.get("nombre"))


@router.put("/api/areas/{area_id}")
def renombrar_area(area_id: int, body: dict = Body(...), u: dict = Admin):
    return sv.renombrar_area(u, area_id, nombre=body.get("nombre"))


@router.post("/api/areas/{area_id}/baja")
def baja_area(area_id: int, u: dict = Admin):
    return sv.cambiar_alta_area(u, area_id, activo=False)


@router.post("/api/areas/{area_id}/alta")
def alta_area(area_id: int, u: dict = Admin):
    return sv.cambiar_alta_area(u, area_id, activo=True)


@router.delete("/api/areas/{area_id}")
def eliminar_area(area_id: int, u: dict = Admin):
    sv.eliminar_area(u, area_id)
    return {"ok": True}


@router.post("/api/personas")
def crear_persona(body: dict = Body(...), u: dict = Admin):
    return sv.crear_persona(u, nombre=body.get("nombre"), categoria=body.get("categoria"), contacto=body.get("contacto"))


@router.put("/api/personas/{persona_id}")
def actualizar_persona(persona_id: int, body: dict = Body(...), u: dict = Admin):
    return sv.actualizar_persona(u, persona_id, nombre=body.get("nombre"), contacto=body.get("contacto"))


@router.post("/api/personas/{persona_id}/baja")
def baja_persona(persona_id: int, u: dict = Admin):
    return sv.cambiar_alta_persona(u, persona_id, activo=False)


@router.post("/api/personas/{persona_id}/alta")
def alta_persona(persona_id: int, u: dict = Admin):
    return sv.cambiar_alta_persona(u, persona_id, activo=True)


@router.get("/api/personas/seguimiento")
def seguimiento_personas(anio: int, u: dict = Usuario):
    return sv.seguimiento_personas(anio)


@router.get("/api/personas/{persona_id}/trabajos")
def trabajos_de_persona(persona_id: int, anio: int, u: dict = Usuario):
    return sv.trabajos_de_persona(persona_id, anio)


# ── equipos ──
@router.get("/api/equipos")
def equipos(baja: bool = False, u: dict = Usuario):
    return sv.listar_equipos(incluir_baja=baja)


@router.post("/api/equipos")
def crear_equipo(body: dict = Body(...), u: dict = Admin):
    return sv.crear_equipo(u, copiar_de=body.get("copiar_de"),
                           **{k: body.get(k) for k in ("nombre", "area_id", "marca_modelo", "usa_horometro")})


@router.put("/api/equipos/{equipo_id}")
def actualizar_equipo(equipo_id: int, body: dict = Body(...), u: dict = Admin):
    return sv.actualizar_equipo(u, equipo_id, **{k: body.get(k) for k in ("nombre", "area_id", "marca_modelo", "usa_horometro")})


@router.post("/api/equipos/{equipo_id}/obsoleto")
def equipo_obsoleto(equipo_id: int, body: dict = Body(...), u: dict = Admin):
    return sv.marcar_equipo_obsoleto(u, equipo_id, motivo=body.get("motivo"))


@router.post("/api/equipos/{equipo_id}/alta")
def reactivar_equipo(equipo_id: int, u: dict = Admin):
    return sv.reactivar_equipo(u, equipo_id)


@router.put("/api/equipos/{equipo_id}/instructivos")
def asignar_instructivos(equipo_id: int, body: dict = Body(...), u: dict = Admin):
    return sv.asignar_instructivos_equipo(u, equipo_id, instructivo_ids=body.get("instructivo_ids"))


@router.post("/api/equipos/{equipo_id}/copiar-instructivo")
def copiar_instructivo(equipo_id: int, body: dict = Body(...), u: dict = Admin):
    return sv.copiar_instructivo_de_equipo(u, equipo_id, desde=body.get("desde"))


@router.delete("/api/equipos/{equipo_id}")
def eliminar_equipo(equipo_id: int, u: dict = Admin):
    sv.eliminar_equipo(u, equipo_id)
    return {"ok": True}


# ── instructivos ──
_CONTENIDO = ("titulo", "descripcion", "seguridad", "repuestos", "secciones", "bloques", "archivos", "orden")


@router.get("/api/instructivos")
def instructivos(u: dict = Usuario):
    return sv.listar_instructivos()


@router.get("/api/instructivos/{it_id}")
def instructivo(it_id: int, u: dict = Usuario):
    return sv.obtener_instructivo(it_id)


@router.post("/api/instructivos")
def crear_instructivo(body: dict = Body(...), u: dict = Admin):
    return sv.crear_instructivo(u, equipo_id=body.get("equipo_id"), **{k: body.get(k) for k in _CONTENIDO})


@router.put("/api/instructivos/{it_id}")
def revisar_instructivo(it_id: int, body: dict = Body(...), u: dict = Admin):
    return sv.revisar_instructivo(u, it_id, motivo=body.get("motivo"), **{k: body.get(k) for k in _CONTENIDO})


@router.get("/api/instructivos/{it_id}/revisiones/{revision}")
def revision_anterior(it_id: int, revision: int, u: dict = Usuario):
    return sv.version_instructivo(it_id, revision)


@router.post("/api/instructivos/{it_id}/obsoleto")
def obsoleto(it_id: int, body: dict = Body(...), u: dict = Admin):
    return sv.marcar_obsoleto(u, it_id, motivo=body.get("motivo"))


@router.delete("/api/instructivos/{it_id}")
def eliminar_instructivo(it_id: int, u: dict = Admin):
    sv.eliminar_instructivo(u, it_id)
    return {"ok": True}


@router.post("/api/instructivos/{it_id}/adjuntos")
async def subir_adjunto(it_id: int, archivo: UploadFile = File(...), u: dict = Admin):
    datos = await archivo.read(sv.MAX_ADJUNTO + 1)   # uno de más alcanza para saber que se pasó
    return sv.subir_adjunto(u, it_id, nombre=archivo.filename, datos=datos)


@router.get("/api/adjuntos/{adjunto_id}")
def descargar_adjunto(adjunto_id: int, u: dict = Usuario):
    """Con sesión (header Bearer): la pantalla lo pide con fetch y lo muestra como blob, también las <img>."""
    a = sv.archivo_adjunto(adjunto_id)
    return FileResponse(a["ruta"], media_type=a["tipo"], filename=a["nombre"],
                        content_disposition_type="inline" if a["es_imagen"] or a["tipo"] == "application/pdf" else "attachment",
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"})


@router.delete("/api/adjuntos/{adjunto_id}")
def eliminar_adjunto(adjunto_id: int, u: dict = Admin):
    sv.eliminar_adjunto(u, adjunto_id)
    return {"ok": True}


# ── Plan ──
_TAREA = ("equipo_id", "seccion_id", "frecuencia", "mes_inicio", "meses_especificos", "cada_horas",
          "proximo_inicial", "responsable_id", "observaciones")


@router.get("/api/tareas")
def tareas(baja: bool = False, u: dict = Usuario):
    return sv.listar_tareas(incluir_baja=baja)


@router.post("/api/tareas")
def crear_tarea(body: dict = Body(...), u: dict = Admin):
    return sv.crear_tarea(u, **{k: body.get(k) for k in _TAREA})


@router.get("/api/tareas/sin-programar")
def tareas_sin_programar(u: dict = Admin):
    return sv.tareas_sin_programar()


@router.post("/api/tareas/lote")
def programar_tareas(body: dict = Body(...), u: dict = Admin):
    return sv.programar_tareas(u, [{k: t.get(k) for k in _TAREA} for t in body.get("tareas") or [] if isinstance(t, dict)])


@router.put("/api/tareas/{tarea_id}")
def actualizar_tarea(tarea_id: int, body: dict = Body(...), u: dict = Admin):
    return sv.actualizar_tarea(u, tarea_id, **{k: body.get(k) for k in _TAREA})


@router.post("/api/tareas/{tarea_id}/baja")
def baja_tarea(tarea_id: int, u: dict = Admin):
    return sv.cambiar_alta_tarea(u, tarea_id, activa=False)


@router.post("/api/tareas/{tarea_id}/alta")
def alta_tarea(tarea_id: int, u: dict = Admin):
    return sv.cambiar_alta_tarea(u, tarea_id, activa=True)


# ── cronograma y registros ──
@router.get("/api/cronograma")
def cronograma(anio: int, u: dict = Usuario):
    return sv.cronograma(anio)


@router.get("/api/pendientes")
def pendientes(u: dict = Usuario):
    return sv.pendientes()


@router.post("/api/tareas/{tarea_id}/registros")
def registrar(tarea_id: int, body: dict = Body(...), u: dict = Usuario):
    campos = ("fecha", "resultado", "realizado_por_id", "realizado_por_nombre", "horas_hombre", "horometro", "novedades", "repuestos", "reprogramado_para")
    return sv.registrar_mantenimiento(u, tarea_id, **{k: body.get(k) for k in campos})


@router.get("/api/registros")
def registros(anio: Optional[int] = None, equipo_id: Optional[int] = None, u: dict = Usuario):
    return sv.listar_registros(anio, equipo_id)


@router.delete("/api/registros/{registro_id}")
def anular_registro(registro_id: int, u: dict = Admin):
    sv.anular_registro(u, registro_id)
    return {"ok": True}


# ── horómetros ──
@router.get("/api/horometros")
def horometros(u: dict = Usuario):
    return sv.estado_horometros()


@router.get("/api/horometros/grilla")
def grilla_horometros(corrimiento: int = 0, u: dict = Usuario):
    return sv.grilla_horometros(corrimiento)


@router.get("/api/lecturas")
def lecturas(equipo_id: Optional[int] = None, u: dict = Usuario):
    return sv.listar_lecturas(equipo_id)


@router.post("/api/equipos/{equipo_id}/lecturas")
def registrar_lectura(equipo_id: int, body: dict = Body(...), u: dict = Usuario):
    return sv.registrar_lectura(u, equipo_id, **{k: body.get(k) for k in ("fecha", "horas", "anoto_id", "observaciones")})


@router.post("/api/equipos/{equipo_id}/cambio-horometro")
def cambiar_horometro(equipo_id: int, body: dict = Body(...), u: dict = Admin):
    return sv.cambiar_horometro(u, equipo_id, **{k: body.get(k) for k in ("fecha", "horas", "horas_anterior", "anoto_id", "observaciones")})


# ── correctivos ──
@router.get("/api/correctivos")
def correctivos(anio: Optional[int] = None, equipo_id: Optional[int] = None, u: dict = Usuario):
    return sv.listar_correctivos(anio, equipo_id)


@router.post("/api/equipos/{equipo_id}/correctivos")
def registrar_correctivo(equipo_id: int, body: dict = Body(...), u: dict = Usuario):
    campos = ("fecha", "falla", "causa", "accion", "horas_parada", "horas_hombre", "repuestos",
              "realizado_por_id", "realizado_por_nombre", "accion_sgc", "observaciones")
    return sv.registrar_correctivo(u, equipo_id, **{k: body.get(k) for k in campos})
