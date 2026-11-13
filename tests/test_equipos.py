"""Equipo e instructivo: el instructivo nace con su equipo, y se va con él si el equipo se cargó por error."""
from tests.test_api import api, error  # noqa: F401  (fixture con el admin ya logueado)

CONTENIDO = {"secciones": [{"letra": "A", "actividades": [{"texto": "Limpieza general"}]}]}


def equipo(api, eid):
    return next(e for e in api.get("/api/equipos?baja=true").json() if e["id"] == eid)


def test_el_instructivo_nace_vinculado_a_su_equipo(api):
    eq = api.post("/api/equipos", json={"nombre": "Torno"}).json()
    it = api.post("/api/instructivos", json={"titulo": "Torno", "equipo_id": eq["id"], **CONTENIDO}).json()
    assert equipo(api, eq["id"])["instructivo_ids"] == [it["id"]]
    seccion = next(s for s in api.get("/api/opciones").json()["secciones"] if s["codigo"] == f"{it['codigo']}-A")
    assert seccion["equipo_ids"] == [eq["id"]]
    # y ya se le puede programar
    assert api.post("/api/tareas", json={"equipo_id": eq["id"], "seccion_id": seccion["id"], "frecuencia": "Mensual",
                                         "mes_inicio": 1}).status_code == 200


def test_no_se_crea_instructivo_para_un_equipo_obsoleto(api):
    eq = api.post("/api/equipos", json={"nombre": "Viejo"}).json()
    api.post(f"/api/equipos/{eq['id']}/obsoleto", json={"motivo": "Se vendió"})
    assert "obsoleto" in error(api.post("/api/instructivos", json={"titulo": "Viejo", "equipo_id": eq["id"], **CONTENIDO}))


def test_eliminar_equipo_cargado_por_error_se_lleva_su_instructivo(api):
    eq = api.post("/api/equipos", json={"nombre": "Por error"}).json()
    it = api.post("/api/instructivos", json={"titulo": "Por error", "equipo_id": eq["id"], **CONTENIDO}).json()
    assert api.delete(f"/api/equipos/{eq['id']}").status_code == 200
    assert api.get(f"/api/instructivos/{it['id']}").status_code == 404


def test_un_instructivo_no_se_comparte(api):
    a = api.post("/api/equipos", json={"nombre": "Bomba 1"}).json()
    it = api.post("/api/instructivos", json={"titulo": "Bomba", "equipo_id": a["id"], **CONTENIDO}).json()
    b = api.post("/api/equipos", json={"nombre": "Bomba 2"}).json()
    assert "es el instructivo de " + a["codigo"] in error(api.put(f"/api/equipos/{b['id']}/instructivos", json={"instructivo_ids": [it["id"]]}))
    # uno sin equipo sí se puede asignar
    api.put(f"/api/equipos/{a['id']}/instructivos", json={"instructivo_ids": []})
    assert api.put(f"/api/equipos/{b['id']}/instructivos", json={"instructivo_ids": [it["id"]]}).status_code == 200


def test_equipo_parecido_nace_con_una_copia_del_instructivo(api):
    from tests.test_adjuntos import PDF, PNG, subir
    eqs = {e["codigo"]: e for e in api.get("/api/equipos").json()}
    it01 = eqs["EQ-001"]["instructivo_ids"][0]
    original = api.get(f"/api/instructivos/{it01}").json()
    # el original con una imagen, un archivo, una ficha del equipo y un orden propio
    img, pdf = subir(api, it01, "foto.png", PNG).json(), subir(api, it01, "manual.pdf", PDF).json()
    ficha = {"tipo": "tabla", "ubicacion": "general", "datos": {"titulo": "Datos del equipo", "encabezado": False, "filas": [["Código", "EQ-001"]]}}
    foto = {"tipo": "imagen", "ubicacion": "A", "datos": {"adjunto_id": img["id"]}}
    cambio = {k: original[k] for k in ("titulo", "descripcion", "seguridad")}
    cambio.update(motivo="fotos", repuestos=[{"nombre": "Filtro", "cantidad": 2}], bloques=[ficha, foto], archivos=[pdf["id"]],
                  secciones=[{"letra": s["letra"], "actividades": s["actividades"]} for s in original["secciones"]],
                  orden=["repuestos", "bloque:1", "seccion:A", "seccion:B", "seccion:C", "bloque:0"])
    assert api.put(f"/api/instructivos/{it01}", json=cambio).status_code == 200

    nuevo = api.post("/api/equipos", json={"nombre": "Compresor 2", "marca_modelo": "Cetec ETR-50", "copiar_de": eqs["EQ-001"]["id"]}).json()
    assert [x["desde"] for x in nuevo["instructivos_copiados"]] == ["IT01"]
    copia = api.get(f"/api/instructivos/{nuevo['instructivos_copiados'][0]['id']}").json()
    assert copia["codigo"] != "IT01" and copia["revision"] == 0 and copia["versiones"] == []
    assert copia["titulo"] == "Compresor 2 Cetec ETR-50"
    assert [s["actividades"] for s in copia["secciones"]] == [s["actividades"] for s in original["secciones"]]
    assert copia["repuestos"] == [{"nombre": "Filtro", "cantidad": 2}] and copia["orden"] == cambio["orden"]
    # la ficha es la del equipo nuevo, y las imágenes y archivos son copias propias
    assert copia["bloques"][0]["datos"]["filas"][0] == ["Código", nuevo["codigo"]]
    assert copia["bloques"][1]["datos"]["adjunto_id"] not in (img["id"], pdf["id"])
    assert {a["nombre"] for a in copia["adjuntos"]} == {"foto.png", "manual.pdf"}
    assert api.get(f"/api/adjuntos/{copia['archivos'][0]['id']}").content == PDF
    assert equipo(api, nuevo["id"])["instructivo_ids"] == [copia["id"]]
    # cambiar la copia no toca el original
    api.put(f"/api/instructivos/{copia['id']}", json={**cambio, "titulo": "Otro", "bloques": [], "archivos": [], "orden": []})
    assert api.get(f"/api/instructivos/{it01}").json()["titulo"] == original["titulo"]


def test_copiar_a_un_equipo_sin_instructivo_y_errores(api):
    eqs = {e["codigo"]: e for e in api.get("/api/equipos").json()}
    sin = api.post("/api/equipos", json={"nombre": "Sin instructivo"}).json()
    r = api.post(f"/api/equipos/{sin['id']}/copiar-instructivo", json={"desde": eqs["EQ-002"]["id"]}).json()
    assert len(r["instructivos_copiados"]) == 1 and equipo(api, sin["id"])["instructivo_ids"] == [r["instructivos_copiados"][0]["id"]]
    vacio = api.post("/api/equipos", json={"nombre": "Otro sin"}).json()
    assert "no tiene un instructivo vigente" in error(api.post("/api/equipos", json={"nombre": "X", "copiar_de": vacio["id"]}))
    assert "a sí mismo" in error(api.post(f"/api/equipos/{sin['id']}/copiar-instructivo", json={"desde": sin["id"]}))
    # si falla la copia, tampoco queda el equipo a medias
    assert not any(e["nombre"] == "X" for e in api.get("/api/equipos").json())


def test_migracion_separa_los_instructivos_compartidos(api):
    from modulos.mantenimiento import servicios as sv
    from nucleo.db import transaccion
    eqs = {e["codigo"]: e for e in api.get("/api/equipos").json()}
    it02 = eqs["EQ-002"]["instructivo_ids"][0]
    otro = api.post("/api/equipos", json={"nombre": "Granalladora 2"}).json()
    with transaccion() as c:   # como estaba antes: compartido, y con una tarea de la sección B en el equipo nuevo
        c.execute("DROP INDEX ux_instructivo_equipos_instructivo")
        c.execute("INSERT INTO instructivo_equipos (instructivo_id, equipo_id) VALUES (?,?)", (it02, otro["id"]))
        sec_b = c.execute("SELECT id FROM secciones WHERE instructivo_id=? AND letra='B'", (it02,)).fetchone()[0]
        c.execute("INSERT INTO tareas (equipo_id, numero, seccion_id, frecuencia, mes_inicio, activa) VALUES (?,?,?,?,?,1)",
                  (otro["id"], 1, sec_b, "Semestral", 1))
    assert sv.separar_instructivos_compartidos() == [f"{otro['codigo']}: IT02 -> copia IT03"]
    nuevo = equipo(api, otro["id"])["instructivo_ids"]
    assert nuevo != [it02] and equipo(api, eqs["EQ-002"]["id"])["instructivo_ids"] == [it02]
    t = next(t for t in api.get("/api/tareas").json() if t["equipo_id"] == otro["id"])
    assert t["seccion"] == "IT03-B"
    assert sv.separar_instructivos_compartidos() == []   # la segunda vez no hay nada que hacer
