"""Orden libre del documento: secciones, bloques y repuestos en el orden que se elija (título, descripción y seguridad, siempre arriba)."""
from tests.test_adjuntos import contenido, it01
from tests.test_api import api, error  # noqa: F401  (fixture con el admin ya logueado)

TABLA = {"tipo": "tabla", "ubicacion": "general", "datos": {"encabezado": False, "filas": [["Presión", "8 bar"]]}}
NOTA = {"tipo": "nota", "ubicacion": "B", "datos": {"nivel": "peligro", "texto": "Aceite caliente"}}


def test_sin_orden_queda_como_antes(api):
    """Instructivos de antes del orden libre: bloques generales, cada sección con los suyos, repuestos."""
    it = it01(api)
    assert api.get(f"/api/instructivos/{it}").json()["orden"] == ["seccion:A", "seccion:B", "seccion:C", "repuestos"]
    nuevo = api.put(f"/api/instructivos/{it}", json=contenido(api, it, bloques=[NOTA, TABLA])).json()
    assert nuevo["orden"] == ["bloque:1", "seccion:A", "seccion:B", "bloque:0", "seccion:C", "repuestos"]


def test_orden_elegido_se_guarda_y_pasa_a_la_revision(api):
    it = it01(api)
    orden = ["repuestos", "seccion:C", "bloque:0", "seccion:A", "bloque:1", "seccion:B"]
    nuevo = api.put(f"/api/instructivos/{it}", json=contenido(api, it, bloques=[TABLA, NOTA], orden=orden)).json()
    assert nuevo["orden"] == orden
    assert api.get(f"/api/instructivos/{it}").json()["orden"] == orden
    # la revisión siguiente archiva la anterior con su orden
    api.put(f"/api/instructivos/{it}", json=contenido(api, it, orden=list(reversed(orden))))
    rev = nuevo["revision"]
    assert api.get(f"/api/instructivos/{it}/revisiones/{rev}").json()["orden"] == orden


def test_orden_se_corrige_solo(api):
    """Lo que no existe o se repite se descarta; lo que falta se agrega donde iba."""
    it = it01(api)
    orden = ["bloque:0", "bloque:0", "seccion:Z", "bloque:7", "repuestos", 5, "seccion:B"]
    nuevo = api.put(f"/api/instructivos/{it}", json=contenido(api, it, bloques=[TABLA], orden=orden)).json()
    assert nuevo["orden"] == ["bloque:0", "repuestos", "seccion:B", "seccion:A", "seccion:C"]
    assert api.put(f"/api/instructivos/{it}", json=contenido(api, it, orden="cualquier cosa")).status_code == 200


def test_repuestos_con_cantidad_minima(api):
    it = it01(api)
    # los instructivos viejos guardaban solo textos: se leen sin cantidad
    assert all(r["cantidad"] is None for r in api.get(f"/api/instructivos/{it}").json()["repuestos"])
    nuevo = api.put(f"/api/instructivos/{it}", json=contenido(api, it, repuestos=[
        {"nombre": "Filtro de aire", "cantidad": "2"}, {"nombre": "Aceite", "cantidad": "10,5"},
        {"nombre": "Correa", "cantidad": None}, {"nombre": "  ", "cantidad": 3}, "Grasa"])).json()
    assert nuevo["repuestos"] == [{"nombre": "Filtro de aire", "cantidad": 2}, {"nombre": "Aceite", "cantidad": 10.5},
                                  {"nombre": "Correa", "cantidad": None}, {"nombre": "Grasa", "cantidad": None}]
    assert "no es un número" in error(api.put(f"/api/instructivos/{it}", json=contenido(api, it, repuestos=[{"nombre": "X", "cantidad": "dos"}])))
    assert "entre" in error(api.put(f"/api/instructivos/{it}", json=contenido(api, it, repuestos=[{"nombre": "X", "cantidad": "-1"}])))


def test_alta_con_orden(api):
    eq = next(e for e in api.get("/api/equipos").json() if e["codigo"] == "EQ-002")
    r = api.post("/api/instructivos", json={
        "titulo": "Prueba de orden", "equipo_id": eq["id"], "repuestos": ["Correa"], "bloques": [TABLA],
        "secciones": [{"letra": "A", "actividades": [{"texto": "Revisar"}]}],
        "orden": ["seccion:A", "repuestos", "bloque:0"]})
    assert r.status_code == 200, r.text
    assert r.json()["orden"] == ["seccion:A", "repuestos", "bloque:0"]
