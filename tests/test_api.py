"""Flujos completos por la API, contra una base nueva con los dos equipos de ejemplo."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from nucleo import db

HOY = date.today().isoformat()


@pytest.fixture()
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "prueba.db")
    from app.main import app
    with TestClient(app) as cliente:
        r = cliente.post("/api/auth/login", json={"usuario": "admin", "password": "admin"})
        assert r.status_code == 200, r.text
        token = r.json()["token"]
        cliente.headers["Authorization"] = f"Bearer {token}"
        # la contraseña de fábrica es provisoria: no bloquea nada, pero /api/auth/yo lo informa (el banner)
        assert cliente.get("/api/equipos").status_code == 200
        assert cliente.get("/api/auth/yo").json()["debe_cambiar"] is True
        assert cliente.post("/api/auth/password", json={"actual": "admin", "nueva": "clave-admin"}).status_code == 200
        assert cliente.get("/api/auth/yo").json()["debe_cambiar"] is False
        yield cliente


def tarea(api, codigo):
    return next(t for t in api.get("/api/tareas").json() if t["codigo"] == codigo)


def error(r, status=400):
    assert r.status_code == status, r.text
    return r.json()["detail"]


def test_sin_sesion_no_se_entra(api):
    assert api.get("/api/equipos", headers={"Authorization": ""}).status_code == 401
    assert error(api.post("/api/auth/login", json={"usuario": "admin", "password": "mal"}), 401)


def test_ejemplos(api):
    equipos = {e["codigo"]: e for e in api.get("/api/equipos").json()}
    assert equipos["EQ-001"]["usa_horometro"] == 1 and equipos["EQ-002"]["usa_horometro"] == 0
    assert [t["codigo"] for t in api.get("/api/tareas").json()] == ["EQ-001-1", "EQ-001-2", "EQ-001-3", "EQ-002-1", "EQ-002-2"]


def test_registro_con_horometro(api):
    t = tarea(api, "EQ-001-2")   # cambio de aceite, por horas
    base = {"fecha": HOY, "resultado": "Realizado", "realizado_por_id": 1, "realizado_por_nombre": "Juan"}
    assert "horómetro" in error(api.post(f"/api/tareas/{t['id']}/registros", json=base))
    assert "número" in error(api.post(f"/api/tareas/{t['id']}/registros", json={**base, "horometro": "51.0x"}))
    assert api.post(f"/api/tareas/{t['id']}/registros", json={**base, "horometro": 51020}).status_code == 200
    # la lectura del servicio pasa a ser la última del equipo y corre el próximo servicio
    comp = next(e for e in api.get("/api/horometros").json() if e["codigo"] == "EQ-001")
    aceite = next(s for s in comp["servicios"] if s["codigo"] == "EQ-001-2")
    assert comp["ultima_lectura"] == 51020 and aceite["proximo"] == 52020 and aceite["estado"] == "al_dia"
    # el horómetro no retrocede
    assert "no puede bajar" in error(api.post(f"/api/equipos/{comp['equipo_id']}/lecturas", json={"fecha": HOY, "horas": 50000}))


def test_registro_sin_horometro_y_reglas_de_resultado(api):
    t = tarea(api, "EQ-002-1")
    url = f"/api/tareas/{t['id']}/registros"
    assert "no tiene horómetro" in error(api.post(url, json={"fecha": HOY, "resultado": "Realizado", "realizado_por_id": 1, "horometro": 10}))
    assert "Novedades" in error(api.post(url, json={"fecha": HOY, "resultado": "No realizado"}))
    assert "nueva fecha" in error(api.post(url, json={"fecha": HOY, "resultado": "Reprogramado"}))
    manana = (date.today() + timedelta(days=1)).isoformat()
    assert "futura" in error(api.post(url, json={"fecha": manana, "resultado": "Realizado", "realizado_por_id": 1, "realizado_por_nombre": "Juan"}))
    assert api.post(url, json={"fecha": HOY, "resultado": "Realizado", "realizado_por_id": 1, "realizado_por_nombre": "Juan"}).status_code == 200
    # se ve en el cronograma, en el mes de hoy
    fila = next(f for f in api.get(f"/api/cronograma?anio={date.today().year}").json()["filas"] if f["codigo"] == "EQ-002-1")
    assert fila["celdas"][date.today().month - 1]["estado"] == "hecho"


def test_plan_valida_frecuencias(api):
    opciones = api.get("/api/opciones").json()
    granalla = next(e for e in opciones["equipos"] if e["codigo"] == "EQ-002")
    seccion = next(s for s in opciones["secciones"] if s["codigo"] == "IT02-A")
    base = {"equipo_id": granalla["id"], "seccion_id": seccion["id"]}
    assert "horómetro" in error(api.post("/api/tareas", json={**base, "frecuencia": "Por horas", "cada_horas": 500}))
    assert "mes de inicio" in error(api.post("/api/tareas", json={**base, "frecuencia": "Bimestral"}))
    assert "no es un mes" in error(api.post("/api/tareas", json={**base, "frecuencia": "Bimestral", "meses_especificos": "2, 14"}))
    # una sección que la granalladora todavía no tiene en el Plan (IT02-A ya está: sería un duplicado):
    # la de un segundo instructivo suyo
    otro = api.post("/api/instructivos", json={"titulo": "Granalladora: turbina", "equipo_id": granalla["id"],
                                               "secciones": [{"letra": "A", "actividades": [{"texto": "Revisar paletas"}]}]}).json()
    libre = next(s for s in api.get("/api/opciones").json()["secciones"] if s["codigo"] == otro["codigo"] + "-A")
    nueva = api.post("/api/tareas", json={**base, "seccion_id": libre["id"], "frecuencia": "Bimestral", "mes_inicio": "2"}).json()
    assert nueva["codigo"] == "EQ-002-3"


def test_instructivo_revisiones_y_bajas(api):
    it = next(i for i in api.get("/api/instructivos").json() if i["codigo"] == "IT01")
    cont = api.get(f"/api/instructivos/{it['id']}").json()
    cambio = {k: cont[k] for k in ("titulo", "descripcion", "seguridad", "repuestos")}
    cambio["secciones"] = [{"letra": s["letra"], "actividades": s["actividades"]} for s in cont["secciones"]]
    cambio["secciones"][0]["actividades"].append({"texto": "Controlar puesta a tierra", "es_grupo": False})
    assert "motivo" in error(api.put(f"/api/instructivos/{it['id']}", json=cambio))
    nuevo = api.put(f"/api/instructivos/{it['id']}", json={**cambio, "motivo": "Se agrega control de puesta a tierra"}).json()
    assert nuevo["revision"] == 1
    assert "Controlar puesta a tierra" not in str(api.get(f"/api/instructivos/{it['id']}/revisiones/0").json())
    # una sección programada no se puede quitar
    sin_b = {**cambio, "motivo": "x", "secciones": [s for s in cambio["secciones"] if s["letra"] != "B"]}
    assert "está en el Plan" in error(api.put(f"/api/instructivos/{it['id']}", json=sin_b))
    # ni marcarlo obsoleto ni eliminarlo mientras esté en el Plan
    assert "en el Plan" in error(api.post(f"/api/instructivos/{it['id']}/obsoleto", json={"motivo": "Se vendió"}))
    assert "obsoleto" in error(api.delete(f"/api/instructivos/{it['id']}"))


def test_instructivo_creado_por_error_se_elimina(api):
    nuevo = api.post("/api/instructivos", json={"titulo": "Prueba", "secciones": [
        {"letra": "A", "actividades": [{"texto": "Algo"}]}]}).json()
    assert nuevo["codigo"] == "IT03"
    assert api.delete(f"/api/instructivos/{nuevo['id']}").status_code == 200
    assert error(api.get(f"/api/instructivos/{nuevo['id']}"), 404)
    assert "ninguna actividad" in error(api.post("/api/instructivos", json={"titulo": "Vacío", "secciones": [
        {"letra": "A", "actividades": [{"texto": "Solo título", "es_grupo": True}]}]}))


def test_correctivo(api):
    granalla = next(e for e in api.get("/api/equipos").json() if e["codigo"] == "EQ-002")
    url = f"/api/equipos/{granalla['id']}/correctivos"
    assert "falla" in error(api.post(url, json={"fecha": HOY}))
    assert "número" in error(api.post(url, json={"fecha": HOY, "falla": "Ruido", "horas_parada": "nan"}))
    assert api.post(url, json={"fecha": HOY, "falla": "Ruido en la turbina", "horas_parada": "1,5"}).json()["horas_parada"] == 1.5


def test_persona_generica_pide_el_nombre(api):
    personas = {p["nombre"]: p for p in api.get("/api/opciones").json()["personas"]}
    interno = personas["Mantenimiento interno"]
    assert interno["pide_nombre"] == 1
    url = f"/api/tareas/{tarea(api, 'EQ-002-1')['id']}/registros"
    base = {"fecha": HOY, "resultado": "Realizado", "realizado_por_id": interno["id"]}
    assert "nombre de quién lo hizo" in error(api.post(url, json=base))
    assert api.post(url, json={**base, "realizado_por_nombre": "Juan Pérez"}).status_code == 200
    assert api.get("/api/registros").json()[0]["realizado_por"] == "Mantenimiento interno — Juan Pérez"
    # una persona con nombre propio no lo pide, y si viene se ignora
    ana = api.post("/api/personas", json={"nombre": "Ana Gómez", "categoria": "interno"}).json()
    assert api.post(url, json={**base, "realizado_por_id": ana["id"], "realizado_por_nombre": "x"}).status_code == 200
    assert api.get("/api/registros").json()[0]["realizado_por"] == "Ana Gómez"
    # en los correctivos, igual
    granalla = next(e for e in api.get("/api/equipos").json() if e["codigo"] == "EQ-002")
    curl = f"/api/equipos/{granalla['id']}/correctivos"
    assert "nombre de quién lo hizo" in error(api.post(curl, json={"fecha": HOY, "falla": "Ruido", "realizado_por_id": interno["id"]}))


def test_horometro_es_un_numero_entero(api):
    t = tarea(api, "EQ-001-1")
    base = {"fecha": HOY, "resultado": "Realizado", "realizado_por_id": 1, "realizado_por_nombre": "Juan"}
    for malo in ("abc", "51000,5", "-10"):
        assert error(api.post(f"/api/tareas/{t['id']}/registros", json={**base, "horometro": malo}))


def test_grilla_de_horometros(api):
    comp = lambda: next(e for e in api.get("/api/horometros/grilla").json() if e["codigo"] == "EQ-001")
    g = comp()
    assert g["ultima_lectura"] is None and g["bloques"][0] == 48000   # sin lecturas: ancla en el primer servicio (51000)
    aceite = next(f for f in g["filas"] if f["codigo"] == "EQ-001-2")
    assert aceite["celdas"][3]["estado"] == "programado"
    t = tarea(api, "EQ-001-2")
    api.post(f"/api/tareas/{t['id']}/registros", json={"fecha": HOY, "resultado": "Realizado", "realizado_por_id": 1,
                                                       "realizado_por_nombre": "Juan", "horometro": 51020})
    g = comp()
    aceite = next(f for f in g["filas"] if f["codigo"] == "EQ-001-2")
    i = g["bloques"].index(51000)
    assert g["actual"] == i and aceite["celdas"][i]["estado"] == "hecho" and aceite["proximo"] == 52020
    assert api.get("/api/horometros/grilla?corrimiento=2").json()[0]["bloques"][0] == g["bloques"][0] + 2000


def test_lectura_de_un_servicio_dice_quien_fue(api):
    t = tarea(api, "EQ-001-2")
    api.post(f"/api/tareas/{t['id']}/registros", json={"fecha": HOY, "resultado": "Realizado", "realizado_por_id": 1,
                                                       "realizado_por_nombre": "Juan", "horometro": 51020})
    assert api.get("/api/lecturas").json()[0]["anoto"] == "Mantenimiento interno — Juan"


def test_operarios_y_proveedores_con_seguimiento(api):
    assert "categoría" in error(api.post("/api/personas", json={"nombre": "Sin categoría"}))
    ana = api.post("/api/personas", json={"nombre": "Ana Gómez", "categoria": "interno"}).json()
    frio = api.post("/api/personas", json={"nombre": "Frío Sur SRL", "categoria": "externo", "contacto": "Compresores · 351 555-0000"}).json()
    assert "Ya existe" in error(api.post("/api/personas", json={"nombre": "ana gómez", "categoria": "externo"}))
    genericas = [p for p in api.get("/api/opciones").json()["personas"] if p["pide_nombre"]]
    assert "no se edita" in error(api.post(f"/api/personas/{genericas[0]['id']}/baja"))
    # trabajos: un preventivo de Ana, un correctivo del proveedor y uno escrito a mano como "Otro operario"
    url = f"/api/tareas/{tarea(api, 'EQ-002-1')['id']}/registros"
    api.post(url, json={"fecha": HOY, "resultado": "Realizado", "realizado_por_id": ana["id"], "horas_hombre": "2,5"})
    otro = next(p for p in genericas if p["categoria"] == "interno")
    api.post(url, json={"fecha": HOY, "resultado": "Realizado", "realizado_por_id": otro["id"], "realizado_por_nombre": "Pedro"})
    granalla = next(e for e in api.get("/api/equipos").json() if e["codigo"] == "EQ-002")
    api.post(f"/api/equipos/{granalla['id']}/correctivos", json={"fecha": HOY, "falla": "Turbina", "realizado_por_id": frio["id"], "horas_hombre": 4})
    seg = {p["nombre"]: p for p in api.get(f"/api/personas/seguimiento?anio={date.today().year}").json()}
    assert (seg["Ana Gómez"]["preventivos"], seg["Ana Gómez"]["horas_hombre"]) == (1, 2.5)
    assert (seg["Frío Sur SRL"]["correctivos"], seg["Frío Sur SRL"]["contacto"]) == (1, "Compresores · 351 555-0000")
    assert seg["Mantenimiento interno"]["nombres_libres"] == ["Pedro"]
    trabajos = api.get(f"/api/personas/{frio['id']}/trabajos?anio={date.today().year}").json()
    assert [(t["tipo"], t["detalle"]) for t in trabajos] == [("Correctivo", "Turbina")]
    # dar de baja: sale de las listas para elegir, pero sus trabajos siguen contando
    api.post(f"/api/personas/{ana['id']}/baja")
    assert next(p for p in api.get(f"/api/personas/seguimiento?anio={date.today().year}").json() if p["id"] == ana["id"])["preventivos"] == 1


def test_equipo_obsoleto_da_de_baja_sus_tareas(api):
    comp = next(e for e in api.get("/api/equipos").json() if e["codigo"] == "EQ-001")
    assert "motivo" in error(api.post(f"/api/equipos/{comp['id']}/obsoleto", json={}))
    r = api.post(f"/api/equipos/{comp['id']}/obsoleto", json={"motivo": "Se vendió"}).json()
    assert r["tareas_dadas_de_baja"] == ["EQ-001-1", "EQ-001-2", "EQ-001-3"]
    assert (r["equipo"]["activo"], r["equipo"]["motivo_baja"]) == (0, "Se vendió")
    assert "EQ-001" not in [e["codigo"] for e in api.get("/api/equipos").json()]          # sale de las listas
    assert "EQ-001" in [e["codigo"] for e in api.get("/api/equipos?baja=true").json()]    # pero sigue guardado
    assert not [t for t in api.get("/api/tareas").json() if t["equipo_codigo"] == "EQ-001"]
    # obsoleto: no se le programan tareas ni se reactivan las suyas
    seccion = next(s for s in api.get("/api/opciones").json()["secciones"] if s["codigo"] == "IT01-A")
    assert "obsoleto" in error(api.post("/api/tareas", json={"equipo_id": comp["id"], "seccion_id": seccion["id"], "frecuencia": "Mensual", "mes_inicio": 1}))
    t1 = next(t for t in api.get("/api/tareas?baja=true").json() if t["codigo"] == "EQ-001-1")
    assert "reactivar el equipo" in error(api.post(f"/api/tareas/{t1['id']}/alta"))
    # reactivar el equipo no reactiva sus tareas: eso se decide en el Plan
    api.post(f"/api/equipos/{comp['id']}/alta")
    assert not [t for t in api.get("/api/tareas").json() if t["equipo_codigo"] == "EQ-001"]
    assert api.post(f"/api/tareas/{t1['id']}/alta").json()["activa"] == 1


def test_eliminar_equipo_solo_si_no_tiene_nada_vinculado(api):
    nuevo = api.post("/api/equipos", json={"nombre": "Cargado por error"}).json()
    assert next(e for e in api.get("/api/equipos").json() if e["id"] == nuevo["id"])["vinculos"] == 0
    assert api.delete(f"/api/equipos/{nuevo['id']}").status_code == 200
    assert nuevo["id"] not in [e["id"] for e in api.get("/api/equipos?baja=true").json()]
    # uno con un correctivo (aunque no tenga Plan) no se elimina
    otro = api.post("/api/equipos", json={"nombre": "Con historia"}).json()
    api.post(f"/api/equipos/{otro['id']}/correctivos", json={"fecha": HOY, "falla": "Ruido"})
    assert "correctivos" in error(api.delete(f"/api/equipos/{otro['id']}"))
    granalla = next(e for e in api.get("/api/equipos").json() if e["codigo"] == "EQ-002")
    assert "tareas en el Plan" in error(api.delete(f"/api/equipos/{granalla['id']}"))


def test_la_pagina_pide_los_archivos_con_la_version(api):
    from nucleo.ajustes import VERSION
    r = api.get("/")
    assert r.headers["cache-control"] == "no-cache"
    for archivo in ("nucleo/nucleo.js", "nucleo/nucleo.css", "mantenimiento/mantenimiento.js", "mantenimiento/mapa.js",
                    "mantenimiento/ayuda_mantenimiento.js", "mantenimiento/mantenimiento.css"):
        assert f'/static/{archivo}?v={VERSION}"' in r.text, archivo
    assert "/static/app/icono.svg" in r.text and api.get("/static/app/icono.svg").status_code == 200   # el ícono de la app
    assert "Legajo" in r.text and "Fundición Romero" in r.text


def test_lo_registrado_antes_del_alta_no_cuenta_en_el_cumplimiento(api):
    """Se cargó el historial de un año en que la tarea todavía no estaba en el Plan: se ve, pero no infla el porcentaje."""
    from modulos.mantenimiento import servicios as sv
    t = tarea(api, "EQ-002-1")
    with db.transaccion() as c:
        c.execute("UPDATE tareas SET frecuencia='Mensual', mes_inicio=1, meses_especificos='', creado_en='2030-06-01' WHERE id=?", (t["id"],))
        c.execute("INSERT INTO registros (tarea_id, fecha, resultado) VALUES (?, '2030-03-15', 'Realizado')", (t["id"],))
    cr = sv.cronograma(2030, date(2030, 12, 20))
    fila = next(f for f in cr["filas"] if f["codigo"] == "EQ-002-1")
    assert [c["estado"] for c in fila["celdas"][:6]] == ["antes_alta", "antes_alta", "hecho", "antes_alta", "antes_alta", "vencido"]
    otras = sum(1 for f in cr["filas"] if f["codigo"] != "EQ-002-1" for c in f["celdas"] if c["estado"] == "vencido")
    assert cr["cumplimiento"]["esperadas"] == 6 + otras and cr["cumplimiento"]["cumplidas"] == 0


def test_cambio_de_horometro(api):
    """El horómetro nuevo arranca de otro número: los servicios conservan lo que les faltaba y las lecturas no chocan."""
    comp = next(e for e in api.get("/api/horometros").json() if e["codigo"] == "EQ-001")
    url = f"/api/equipos/{comp['equipo_id']}"
    assert api.post(f"{url}/lecturas", json={"fecha": "2026-02-02", "horas": 50900}).status_code == 200
    faltaban = {s["codigo"]: s["faltan"] for s in next(e for e in api.get("/api/horometros").json() if e["codigo"] == "EQ-001")["servicios"]}
    assert "después de la última" in error(api.post(f"{url}/cambio-horometro", json={"fecha": "2026-01-10", "horas": 58}))
    r = api.post(f"{url}/cambio-horometro", json={"fecha": "2026-04-07", "horas": 58, "observaciones": "se rompió"})
    assert r.status_code == 200, r.text
    ahora = next(e for e in api.get("/api/horometros").json() if e["codigo"] == "EQ-001")
    assert ahora["ultima_lectura"] == 58
    assert {s["codigo"]: s["faltan"] for s in ahora["servicios"]} == faltaban
    # el nuevo tiene sus propias lecturas; el viejo sigue sin poder retroceder en su tramo
    assert api.post(f"{url}/lecturas", json={"fecha": "2026-07-06", "horas": 923}).status_code == 200
    assert "no puede bajar" in error(api.post(f"{url}/lecturas", json={"fecha": "2026-03-01", "horas": 49000}))
    assert "no puede bajar" in error(api.post(f"{url}/lecturas", json={"fecha": "2026-08-01", "horas": 500}))
    assert api.post(f"{url}/lecturas", json={"fecha": "2026-03-01", "horas": 51000}).status_code == 200
    assert next(e for e in api.get("/api/horometros").json() if e["codigo"] == "EQ-001")["ultima_lectura"] == 923
    lecturas = api.get(f"/api/lecturas?equipo_id={comp['equipo_id']}").json()
    assert [l["cambio"] for l in lecturas if l["fecha"] == "2026-04-07"] == [1]
