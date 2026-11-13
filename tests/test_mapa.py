"""Mapa de planta: planos dibujados y las máquinas ubicadas como puntos, con el estado de su mantenimiento."""
from tests.test_api import api, error  # noqa: F401  (fixture con el admin ya logueado)


def equipos(api):
    return {e["codigo"]: e for e in api.get("/api/planos").json()["equipos"]}


def guardar(api, plano, **cambios):
    datos = {"nombre": plano["nombre"], "ancho": plano["ancho"], "alto": plano["alto"], "elementos": [], "equipos": [], **cambios}
    return api.put(f"/api/planos/{plano['id']}", json=datos)


def test_planos_y_maquinas(api):
    assert api.get("/api/planos").json()["planos"] == []
    eq = equipos(api)
    assert eq["EQ-001"]["plano_id"] is None and eq["EQ-001"]["estado"] in ("al_dia", "sin_dato", "pendiente", "vencido")

    nave = api.post("/api/planos", json={"nombre": "Nave 1", "ancho": "50", "alto": 30}).json()
    assert "Ya hay" in error(api.post("/api/planos", json={"nombre": "nave 1", "ancho": 10, "alto": 10}))
    assert "Falta el ancho" in error(api.post("/api/planos", json={"nombre": "Nave 2", "alto": 10}))
    assert "entre" in error(api.post("/api/planos", json={"nombre": "Nave 2", "ancho": 0, "alto": 10}))

    dibujo = [{"tipo": "rect", "x": 0, "y": 0, "w": 20, "h": 10, "etiqueta": "Moldeo", "color": "azul"},
              {"tipo": "linea", "x1": 0, "y1": 15, "x2": 50, "y2": 15},
              {"tipo": "texto", "x": 25, "y": 25, "texto": "Portón", "tamanio": 2, "color": "rojo"}]
    r = guardar(api, nave, elementos=dibujo, equipos=[{"equipo_id": eq["EQ-001"]["id"], "x": 10, "y": 5}])
    assert r.status_code == 200, r.text
    plano = api.get("/api/planos").json()["planos"][0]
    assert plano["elementos"][0]["etiqueta"] == "Moldeo" and plano["elementos"][1]["color"] == "gris"
    assert (equipos(api)["EQ-001"]["plano_id"], equipos(api)["EQ-001"]["plano_x"]) == (nave["id"], 10)

    # lo dibujado tiene que quedar dentro del plano y ser de los tipos y colores conocidos
    assert "entre" in error(guardar(api, nave, elementos=[{"tipo": "rect", "x": 40, "y": 0, "w": 20, "h": 5}]))
    assert "Color" in error(guardar(api, nave, elementos=[{"tipo": "linea", "x1": 0, "y1": 0, "x2": 1, "y2": 1, "color": "url(#x)"}]))
    assert "desconocido" in error(guardar(api, nave, elementos=[{"tipo": "circulo"}]))
    assert "vacío" in error(guardar(api, nave, elementos=[{"tipo": "texto", "x": 1, "y": 1, "texto": "  "}]))
    assert "entre" in error(guardar(api, nave, equipos=[{"equipo_id": eq["EQ-001"]["id"], "x": 51, "y": 1}]))
    assert error(guardar(api, nave, equipos=[{"equipo_id": 999, "x": 1, "y": 1}]), 404)

    # una máquina está en un solo plano: ubicarla en otro la muda
    taller = api.post("/api/planos", json={"nombre": "Taller", "ancho": 20, "alto": 20}).json()
    assert guardar(api, taller, equipos=[{"equipo_id": eq["EQ-001"]["id"], "x": 3, "y": 4}]).status_code == 200
    assert equipos(api)["EQ-001"]["plano_id"] == taller["id"]
    # y sacarla del plano (no mandarla) la deja sin ubicar
    assert guardar(api, taller, equipos=[{"equipo_id": eq["EQ-002"]["id"], "x": 1, "y": 1}]).status_code == 200
    assert equipos(api)["EQ-001"]["plano_id"] is None and equipos(api)["EQ-002"]["plano_id"] == taller["id"]

    # eliminar un plano es borrar un dibujo: sus máquinas quedan sin ubicar
    assert api.delete(f"/api/planos/{taller['id']}").status_code == 200
    assert equipos(api)["EQ-002"]["plano_id"] is None
    assert [p["nombre"] for p in api.get("/api/planos").json()["planos"]] == ["Nave 1"]


def test_el_punto_muestra_lo_pendiente(api):
    """Lo que el mapa muestra de cada máquina es lo mismo que Inicio: si Inicio lo da por pendiente, el punto también."""
    inicio = api.get("/api/pendientes").json()
    eq = equipos(api)
    for t in inicio["atrasados"] + inicio["este_mes"] + inicio["por_horas"]:
        e = eq[t["equipo_codigo"]]
        assert t["tarea_id"] in {p["tarea_id"] for p in e["pendientes"]}
        assert e["estado"] != "al_dia"
