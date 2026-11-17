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
    assert inicio["modo"] == "directa" and "¿Por cuál" in texto
    # cada máquina es un botón que vuelve a preguntar nombrándola por su código
    botones = {b["texto"]: b["datos"]["pregunta"] for b in inicio["enlaces"]}
    assert botones["EQ-003 · Compresor de pistón"] == "¿qué le pasó al compresor (EQ-003)?"
    assert preguntar(sin_ia, botones["EQ-003 · Compresor de pistón"])[0]["titulo"] == "EQ-003 · Compresor de pistón"
    assert preguntar(sin_ia, "¿qué le pasó al compresor de pistón?")[0]["titulo"] == "EQ-003 · Compresor de pistón"


def test_especificaciones(sin_ia):
    comp = equipo(sin_ia, "EQ-001")
    url = f"/api/equipos/{comp['id']}/especificaciones"
    r = sin_ia.post(url, json={"nombre": "Aceite", "valor": "ISO VG 46", "unidad": "", "fuente": "manual", "fuente_detalle": "Manual Cetec, pág. 12"})
    assert r.status_code == 200, r.text
    aceite = r.json()
    assert "ya tiene" in error(sin_ia.post(url, json={"nombre": "aceite", "valor": "otro"}))      # sin importar mayúsculas
    assert "valor" in error(sin_ia.post(url, json={"nombre": "Correa"}))
    assert "lista" in error(sin_ia.post(url, json={"nombre": "Correa", "valor": "SPZ", "fuente": "inventada"}))
    assert sin_ia.post(url, json={"nombre": "Presión de trabajo", "valor": "8", "unidad": "bar", "fuente": "placa"}).status_code == 200
    lista = sin_ia.get(f"/api/especificaciones?equipo_id={comp['id']}").json()
    assert [x["nombre"] for x in lista["especificaciones"]] == ["Aceite", "Presión de trabajo"]
    assert lista["especificaciones"][0]["fuente_texto"] == "Manual del fabricante"
    assert equipo(sin_ia, "EQ-001")["especificaciones"] == 2

    # la barra la contesta la app, con su fuente, sin IA
    inicio, texto = preguntar(sin_ia, "¿qué aceite usa el ETR-50?")
    assert inicio["modo"] == "directa" and "Aceite: ISO VG 46 (según manual del fabricante, Manual Cetec, pág. 12)" in texto
    assert "8 bar" in preguntar(sin_ia, "¿cuál es la presión de trabajo del EQ-001?")[1]
    # sin máquina en la pregunta: aparece en la búsqueda
    assert "ISO VG 46" in preguntar(sin_ia, "¿qué equipos usan aceite ISO VG 46?")[1]

    # lo que no está: no se inventa, se ofrece cargarlo (con la máquina y el nombre sugeridos)
    inicio, _ = preguntar(sin_ia, "¿qué correa lleva el ETR-50?")
    assert inicio["si_no_figura"]["enlace"] == {"texto": "Cargar especificación", "accion": "especificacion",
                                                "datos": {"equipo_id": comp["id"], "nombre": "Correa"}}
    inicio, texto = preguntar(sin_ia, "¿qué grasa se usa en los rodillos?")
    assert inicio["modo"] == "nada" and "No hay nada cargado" in texto
    assert inicio["enlaces"][0]["datos"] == {"equipo_id": None, "nombre": "Grasa"}
    # sin máquina pero con algo en las fichas: se busca ahí, y si la IA no lo encuentra, también se ofrece cargarlo
    inicio, texto = preguntar(sin_ia, "¿qué aceite usan los rodillos?")
    assert inicio["titulo"] == "Búsqueda en lo anotado" and "ISO VG 46" in texto
    assert inicio["si_no_figura"]["enlace"]["datos"] == {"equipo_id": None, "nombre": "Aceite"}

    # corregir y borrar (borrar es de administrador)
    r = sin_ia.put(f"/api/especificaciones/{aceite['id']}", json={"nombre": "Aceite", "valor": "ISO VG 68", "fuente": "proveedor"})
    assert r.json()["valor"] == "ISO VG 68"
    assert sin_ia.delete(f"/api/especificaciones/{aceite['id']}").status_code == 200
    assert len(sin_ia.get("/api/especificaciones").json()["especificaciones"]) == 1


def test_ayuda_y_uso_de_la_app(sin_ia):
    inicio, texto = preguntar(sin_ia, "ayuda")
    assert inicio["titulo"] == "Ayuda" and any(b["datos"]["pregunta"] == "¿Hay algo vencido?" for b in inicio["enlaces"])
    # la guía de mantenimiento (ia/guia.md) ...
    inicio, texto = preguntar(sin_ia, "¿Cómo cargo un correctivo?")
    assert inicio["titulo"] == "Cómo se usa la app" and "Correctivos" in texto and {"texto": "Ir a correctivos", "ir": "correctivos"} in inicio["enlaces"]
    # ... y la Ayuda de las pantallas, que manda el navegador
    ayuda = [{"pantalla": "correctivos", "titulo": "Botón violeta", "texto": "El botón violeta exporta los correctivos a Excel."}]
    r = sin_ia.post("/api/asistente/preguntar", json={"pregunta": "¿Dónde veo el botón violeta?", "ayuda": ayuda})
    evs = [json.loads(x) for x in r.text.splitlines() if x.strip()]
    assert evs[0]["titulo"] == "Cómo se usa la app" and "exporta" in "".join(e.get("texto", "") for e in evs if e["tipo"] == "texto")


def test_borrar_un_equipo_cargado_por_error_se_lleva_sus_especificaciones(sin_ia):
    r = sin_ia.post("/api/equipos", json={"nombre": "Equivocado", "area_id": 1}).json()
    sin_ia.post(f"/api/equipos/{r['id']}/especificaciones", json={"nombre": "Aceite", "valor": "x"})
    assert sin_ia.delete(f"/api/equipos/{r['id']}").status_code == 200
    assert sin_ia.get(f"/api/especificaciones?equipo_id={r['id']}").json()["especificaciones"] == []


def test_la_conversacion_sigue_con_la_misma_maquina(sin_ia):
    def con(pregunta, charla, **extra):
        r = sin_ia.post("/api/asistente/preguntar", json={"pregunta": pregunta, "historial": charla, **extra})
        evs = [json.loads(x) for x in r.text.splitlines() if x.strip()]
        return evs[0], "".join(e["texto"] for e in evs if e["tipo"] == "texto")

    inicio, texto = preguntar(sin_ia, "¿qué le pasó al ETR-50?")
    assert inicio["tema"] == "EQ-001"
    charla = [{"pregunta": "¿qué le pasó al ETR-50?", "respuesta": texto, "tema": inicio["tema"]}]
    inicio, texto = con("¿y cuántas horas tiene?", charla)
    assert inicio["sigue"] == "EQ-001" and inicio["modo"] == "directa" and "horómetro" in texto
    # nombrar otra máquina cambia de tema; pedir algo general, también
    assert con("¿y la granalladora?", charla)[0]["titulo"] == "EQ-002 · Granalladora"
    assert con("¿qué máquinas tuvieron problemas de rodamientos?", charla)[0]["sigue"] is None
    # un nombre de varias máquinas no sigue el tema anterior: pregunta cuál
    sin_ia.post("/api/equipos", json={"codigo": "EQ-003", "nombre": "Compresor de pistón", "area_id": 1})
    assert "¿Por cuál" in con("¿y el compresor?", charla)[1]
    # "Preguntar en general"
    assert con("¿y cuántas horas tiene?", charla, sin_tema=True)[0]["sigue"] is None


def test_guia_sinonimos_y_fichas_de_mantenimiento(sin_ia):
    t = sin_ia.get("/api/asistente/textos").json()
    titulos = [s["titulo"] for s in t["guia"]]
    assert "Cronograma anual" in titulos and "Correctivos" in titulos and "Opciones" in titulos   # la de mantenimiento y la común
    assert any("rulem" in " ".join(g) and "rodamient" in " ".join(g) for g in t["sinonimos"])
    assert {"Equipo", "Sección de instructivo", "Área", "Persona"} <= set(t["por_tipo"])

    # de uso: la guía, aunque no diga "cómo cargo"
    for q, pantalla in [("¿qué significa la cruz roja en el cronograma?", "cronograma"),
                        ("se rompió una correa, ¿dónde lo anoto?", "correctivos"),
                        ("¿qué es el cumplimiento?", "cronograma")]:
        inicio = preguntar(sin_ia, q)[0]
        assert inicio["titulo"] == "Cómo se usa la app" and {"texto": f"Ir a {pantalla}", "ir": pantalla} in inicio["enlaces"], q

    # las fichas se rehacen solas: un correctivo recién cargado ya se encuentra, y por un sinónimo
    granalla = equipo(sin_ia, "EQ-002")
    sin_ia.post(f"/api/equipos/{granalla['id']}/correctivos", json={"fecha": HOY, "falla": "Rulemán del rodillo trabado",
                                                                   "accion": "Se cambió"})
    inicio, texto = preguntar(sin_ia, "¿qué máquinas tuvieron problemas con cojinetes?")
    assert inicio["titulo"] == "Búsqueda en lo anotado" and "Rulemán del rodillo trabado" in texto


def test_la_pregunta_se_valida(api):
    assert "pregunta" in error(api.post("/api/asistente/preguntar", json={"pregunta": ""}))
