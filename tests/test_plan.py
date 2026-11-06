"""Plan: una sección se programa una sola vez por equipo."""
from tests.test_api import api, error, tarea  # noqa: F401  (fixture con el admin ya logueado)


def ids(api):
    op = api.get("/api/opciones").json()
    eq = {e["codigo"]: e["id"] for e in op["equipos"]}
    sec = {s["codigo"]: s["id"] for s in op["secciones"]}
    return eq, sec


def test_no_se_programa_dos_veces_la_misma_seccion_al_mismo_equipo(api):
    eq, sec = ids(api)
    r = api.post("/api/tareas", json={"equipo_id": eq["EQ-002"], "seccion_id": sec["IT02-A"], "frecuencia": "Bimestral", "mes_inicio": 1})
    assert "ya está programada para EQ-002 (tarea EQ-002-1)" in error(r)
    # y a otro equipo tampoco: los equipos no comparten instructivo (uno parecido lleva una copia)
    it02 = next(x for x in api.get("/api/opciones").json()["secciones"] if x["codigo"] == "IT02-A")["instructivo_id"]
    it01 = next(x for x in api.get("/api/opciones").json()["secciones"] if x["codigo"] == "IT01-A")["instructivo_id"]
    assert "los equipos no comparten" in error(api.put(f"/api/equipos/{eq['EQ-001']}/instructivos",
                                                       json={"instructivo_ids": [it01, it02]}))


def test_editar_no_choca_consigo_misma_pero_si_con_otra(api):
    eq, sec = ids(api)
    t1 = tarea(api, "EQ-002-1")
    base = {"equipo_id": eq["EQ-002"], "frecuencia": "Mensual", "mes_inicio": 2}
    assert api.put(f"/api/tareas/{t1['id']}", json={**base, "seccion_id": sec["IT02-A"]}).status_code == 200
    # pasar EQ-002-2 (IT02-B, sin registros) a IT02-A la duplicaría
    t2 = tarea(api, "EQ-002-2")
    assert "ya está programada" in error(api.put(f"/api/tareas/{t2['id']}", json={**base, "seccion_id": sec["IT02-A"]}))


def test_dada_de_baja_libera_la_seccion_y_reactivarla_no_duplica(api):
    eq, sec = ids(api)
    t1 = tarea(api, "EQ-002-1")
    api.post(f"/api/tareas/{t1['id']}/baja")
    nueva = api.post("/api/tareas", json={"equipo_id": eq["EQ-002"], "seccion_id": sec["IT02-A"], "frecuencia": "Bimestral", "mes_inicio": 1})
    assert nueva.status_code == 200
    assert "ya está programada" in error(api.post(f"/api/tareas/{t1['id']}/alta"))


def test_solo_secciones_de_los_instructivos_del_equipo(api):
    eq, sec = ids(api)
    secciones = {x["codigo"]: x for x in api.get("/api/opciones").json()["secciones"]}
    # la relación nace del Plan de ejemplo
    assert secciones["IT01-A"]["equipo_ids"] == [eq["EQ-001"]] and secciones["IT02-A"]["equipo_ids"] == [eq["EQ-002"]]
    # al compresor no se le programa una sección de la granalladora
    r = api.post("/api/tareas", json={"equipo_id": eq["EQ-001"], "seccion_id": sec["IT02-B"], "frecuencia": "Mensual", "mes_inicio": 1})
    assert "no aplica a EQ-001" in error(r)
    # no se le quita a un equipo un instructivo del que tiene tareas activas
    assert "primero hay que dar de baja" in error(api.put(f"/api/equipos/{eq['EQ-002']}/instructivos", json={"instructivo_ids": []}))
    assert "lista" in error(api.put(f"/api/equipos/{eq['EQ-002']}/instructivos", json={"instructivo_ids": "x"}))
    equipo = next(e for e in api.get("/api/equipos").json() if e["codigo"] == "EQ-002")
    assert equipo["instructivo_ids"] == [secciones["IT02-A"]["instructivo_id"]]


def test_programar_todos_ofrece_lo_que_falta_y_guarda_todo_o_nada(api):
    eq, sec = ids(api)
    # los ejemplos ya tienen todo programado; al darle de baja una tarea, su sección vuelve a ofrecerse
    t = tarea(api, "EQ-002-2")
    assert api.get("/api/tareas/sin-programar").json() == []
    api.post(f"/api/tareas/{t['id']}/baja")
    falta = api.get("/api/tareas/sin-programar").json()
    assert [(x["equipo_codigo"], x["seccion"]) for x in falta] == [("EQ-002", "IT02-B")]
    # si una falla no se guarda ninguna, y el error dice cuál
    buena = {"equipo_id": eq["EQ-002"], "seccion_id": sec["IT02-B"], "frecuencia": "Semestral", "mes_inicio": 3}
    mala = {"equipo_id": eq["EQ-002"], "seccion_id": sec["IT02-A"], "frecuencia": "Mensual", "mes_inicio": 1}
    assert "EQ-002 IT02-A: IT02-A ya está programada" in error(api.post("/api/tareas/lote", json={"tareas": [buena, mala]}))
    assert len(api.get("/api/tareas/sin-programar").json()) == 1
    r = api.post("/api/tareas/lote", json={"tareas": [buena]})
    assert r.status_code == 200 and [x["codigo"] for x in r.json()] == ["EQ-002-3"]
    assert api.get("/api/tareas/sin-programar").json() == []
    assert "No hay tareas" in error(api.post("/api/tareas/lote", json={"tareas": []}))


def test_frecuencia_sugerida_por_la_ficha():
    from app.servicios import _frecuencia_sugerida as sug
    assert sug("Cada tres meses", False) == {"frecuencia": "Trimestral"}
    assert sug("Cada 4 meses", False) == {"frecuencia": "Cuatrimestral"}
    assert sug("Cada 12 meses", False) == {"frecuencia": "Anual"}
    assert sug("Mensual", False) == {"frecuencia": "Mensual"}
    assert sug("Cada 8 meses", False) == {}
    assert sug("Cada 1000 horas", True) == {"frecuencia": "Por horas", "cada_horas": 1000}
    assert sug("Cada 1000 horas", False) == {}
    assert sug("", True) == {}
