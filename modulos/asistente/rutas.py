"""Rutas delgadas del asistente, bajo /api/asistente. La respuesta de una pregunta va de a pedazos (una línea JSON por
evento, ver servicios.preguntar) para que la pantalla la muestre a medida que la IA la escribe."""
import json

from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse

from nucleo.auth import Admin, Usuario

from . import servicios

router = APIRouter(prefix="/api/asistente")


@router.post("/preguntar")
def preguntar(body: dict = Body(...), u: dict = Usuario):
    eventos = servicios.preguntar(body.get("pregunta"), ayuda=body.get("ayuda"), historial=body.get("historial"),
                                  sin_tema=bool(body.get("sin_tema")))
    primero = next(eventos)   # valida la pregunta acá: un error de negocio sale como 400, no a mitad de la respuesta

    def lineas():
        yield json.dumps(primero, ensure_ascii=False) + "\n"
        for e in eventos:
            yield json.dumps(e, ensure_ascii=False) + "\n"
    return StreamingResponse(lineas(), media_type="application/x-ndjson", headers={"Cache-Control": "no-store"})


@router.get("/estado")
def estado(u: dict = Usuario):
    return servicios.estado()


@router.get("/textos")
def textos(u: dict = Usuario):
    """Lo que lee la IA (guía, sinónimos y fichas), para verlo desde Opciones. Las fichas son datos que cualquier
    usuario ya ve en las pantallas."""
    return servicios.textos.todo()


@router.post("/reiniciar")
def reiniciar(u: dict = Admin):
    return servicios.reiniciar(u)


@router.put("/ajustes")
def guardar_ajustes(body: dict = Body(...), u: dict = Admin):
    return servicios.guardar_ajustes(u, url=body.get("url"), modelo=body.get("modelo"))
