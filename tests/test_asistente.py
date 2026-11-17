"""Lo que la barra de preguntas sabe de mantenimiento (modulos/mantenimiento/asistente.py), con la IA apagada: lo exacto
lo contesta la app, y lo demás se muestra como resumen. El camino con IA lo prueba appbase con un Ollama falso."""
import json

import pytest

from tests.test_api import HOY, api, error  # noqa: F401  (fixture con el admin ya logueado)


@pytest.fixture()
def sin_ia(api):
    assert api.put("/api/asistente/ajustes", json={"url": "http://127.0.0.1:9", "modelo": "x"}).status_code == 200
    return api


def preguntar(api, pregunta):
    r = api.post("/api/asistente/preguntar", json={"pregunta": pregunta})
    assert r.status_code == 200, r.text
    evs = [json.loads(x) for x in r.text.splitlines() if x.strip()]
    return evs[0], "".join(e["texto"] for e in evs if e["tipo"] == "texto")


def equipo(api, codigo):
    return next(e for e in api.get("/api/equipos").json() if e["codigo"] == codigo)


def test_lo_exacto_lo_contesta_la_app(sin_ia):
    inicio, texto = preguntar(sin_ia, "¿Hay alguna tarea vencida o atrasada?")
    atrasadas = sin_ia.get("/api/pendientes").json()["atrasados"]
    assert inicio["modo"] == "directa"
    assert texto.startswith("No, no hay ninguna") if not atrasadas else str(len(atrasadas)) in texto

    inicio, texto = preguntar(sin_ia, "¿cuántas horas tiene el ETR-50?")   # por el modelo de la marca
    assert inicio["modo"] == "directa" and inicio["titulo"].startswith("EQ-001") and "horómetro" in texto
    comp = equipo(sin_ia, "EQ-001")
    assert sin_ia.post(f"/api/equipos/{comp['id']}/lecturas", json={"fecha": HOY, "horas": 61234}).status_code == 200
    assert "61.234 h" in preguntar(sin_ia, "¿cuál es la lectura del horómetro del EQ-001?")[1]
    assert "no lleva horómetro" in preguntar(sin_ia, "lectura del horómetro de la granalladora")[1]


def test_lo_demas_va_con_los_datos_de_la_maquina(sin_ia):
    granalla = equipo(sin_ia, "EQ-002")
    sin_ia.post(f"/api/equipos/{granalla['id']}/correctivos", json={"fecha": HOY, "falla": "Rodamiento de la turbina roto",
                                                                   "accion": "Se cambió el rodamiento"})
    inicio, texto = preguntar(sin_ia, "¿Qué le pasó a la granalladora?")
    assert inicio["modo"] == "resumen" and inicio["titulo"] == "EQ-002 · Granalladora"   # sin IA: el resumen, con aviso
    assert "Rodamiento de la turbina roto" in texto and "No se encontró la IA" in inicio["aviso"]
    assert {"texto": "Correctivos", "ir": "correctivos"} in inicio["enlaces"]
    # el procedimiento de un servicio no es "lo pendiente", aunque diga "hay que hacer"
    assert preguntar(sin_ia, "¿qué hay que hacer en el servicio A de la granalladora?")[0]["modo"] == "resumen"
    # sin máquina: se busca en lo anotado
    inicio, texto = preguntar(sin_ia, "¿qué máquinas tuvieron problemas de rodamientos?")
    assert inicio["titulo"] == "Búsqueda en lo anotado" and "EQ-002 Granalladora" in texto


def test_si_el_nombre_es_de_varias_maquinas_pregunta_cual(sin_ia):
    sin_ia.post("/api/equipos", json={"codigo": "EQ-003", "nombre": "Compresor de pistón", "area_id": 1})
    inicio, texto = preguntar(sin_ia, "¿qué le pasó al compresor?")
    assert inicio["modo"] == "directa" and "EQ-001" in texto and "EQ-003" in texto
    assert preguntar(sin_ia, "¿qué le pasó al compresor de pistón?")[0]["titulo"] == "EQ-003 · Compresor de pistón"


def test_la_pregunta_se_valida(api):
    assert "pregunta" in error(api.post("/api/asistente/preguntar", json={"pregunta": ""}))
