"""Áreas: lista como la de Personal; el equipo apunta al área por id."""
import sqlite3
from datetime import date

from modulos.mantenimiento.esquema import _migrar_areas
from tests.test_api import HOY, api, error  # noqa: F401  (fixture con el admin ya logueado)


def areas(api):
    return {a["nombre"]: a for a in api.get("/api/opciones").json()["areas"]}


def test_equipo_con_area_de_la_lista(api):
    a = areas(api)
    assert set(a) == {"Servicios", "Terminación"}
    eq = api.post("/api/equipos", json={"nombre": "Pulidora", "area_id": a["Terminación"]["id"]}).json()
    assert eq["sector"] == "Terminación"
    assert "no existe" in error(api.post("/api/equipos", json={"nombre": "X", "area_id": 999}))
    assert "Ya existe" in error(api.post("/api/areas", json={"nombre": "terminación"}))   # sin distinguir mayúsculas


def test_renombrar_corrige_todos_sus_equipos(api):
    a = areas(api)
    api.put(f"/api/areas/{a['Terminación']['id']}", json={"nombre": "Terminación y granallado"})
    granalla = next(e for e in api.get("/api/equipos").json() if e["codigo"] == "EQ-002")
    assert granalla["sector"] == "Terminación y granallado"


def test_baja_y_eliminar(api):
    a = areas(api)
    nueva = api.post("/api/areas", json={"nombre": "Moldeo"}).json()
    # de baja: no se elige para un equipo nuevo, pero el que ya la tiene la conserva al editarse
    eq = api.post("/api/equipos", json={"nombre": "Moldeadora", "area_id": nueva["id"]}).json()
    api.post(f"/api/areas/{nueva['id']}/baja")
    assert "dada de baja" in error(api.post("/api/equipos", json={"nombre": "Otra", "area_id": nueva["id"]}))
    assert api.put(f"/api/equipos/{eq['id']}", json={"nombre": "Moldeadora 1", "area_id": nueva["id"]}).json()["sector"] == "Moldeo"
    # eliminar solo si no tiene equipos
    assert "tiene equipos" in error(api.delete(f"/api/areas/{a['Servicios']['id']}"))
    error_carga = api.post("/api/areas", json={"nombre": "Por error"}).json()
    assert api.delete(f"/api/areas/{error_carga['id']}").status_code == 200


def test_seguimiento_por_area(api):
    a = areas(api)
    granalla = next(e for e in api.get("/api/equipos").json() if e["codigo"] == "EQ-002")
    api.post(f"/api/equipos/{granalla['id']}/correctivos", json={"fecha": HOY, "falla": "Ruido", "horas_parada": 3})
    t = next(t for t in api.get("/api/tareas").json() if t["codigo"] == "EQ-002-1")
    api.post(f"/api/tareas/{t['id']}/registros", json={"fecha": HOY, "resultado": "Realizado", "realizado_por_id": 1,
                                                       "realizado_por_nombre": "Juan"})
    seg = {x["nombre"]: x for x in api.get(f"/api/areas/seguimiento?anio={date.today().year}").json()}
    assert (seg["Terminación"]["equipos"], seg["Terminación"]["preventivos"], seg["Terminación"]["correctivos"],
            seg["Terminación"]["horas_parada"]) == (1, 1, 1, 3)
    assert seg["Servicios"]["correctivos"] == 0


def test_migracion_del_sector_escrito_a_mano():
    c = sqlite3.connect(":memory:")
    c.executescript("""
        CREATE TABLE areas (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL UNIQUE COLLATE NOCASE, activo INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE equipos (id INTEGER PRIMARY KEY, nombre TEXT, sector TEXT NOT NULL DEFAULT '', area_id INTEGER);
        INSERT INTO equipos (nombre, sector) VALUES ('A', 'Terminación'), ('B', 'terminación '), ('C', 'Servicios'), ('D', '');""")
    _migrar_areas(c)
    assert [r[0] for r in c.execute("SELECT nombre FROM areas ORDER BY nombre")] == ["Servicios", "Terminación"]
    assert c.execute("SELECT nombre, area_id FROM equipos ORDER BY nombre").fetchall() == [("A", 2), ("B", 2), ("C", 1), ("D", None)] \
        or len({r[0] for r in c.execute("SELECT area_id FROM equipos WHERE nombre IN ('A','B')")}) == 1
    assert "sector" not in {r[1] for r in c.execute("PRAGMA table_info(equipos)")}
