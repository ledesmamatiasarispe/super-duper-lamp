"""Varios usuarios a la vez: transaccion() serializa las escrituras (BEGIN IMMEDIATE), así lo que un caso de uso
valida leyendo no lo invalida otro entre la lectura y la escritura. Mismo test que Gestión Automotor."""
import threading
import time

from modulos.mantenimiento import servicios as sv
from nucleo import db
from tests.test_api import HOY, api  # noqa: F401  (fixture con el admin ya logueado)


def test_dos_lecturas_a_la_vez_no_hacen_bajar_el_horometro(api, monkeypatch):
    equipo = next(e for e in api.get("/api/equipos").json() if e["usa_horometro"])["id"]
    original = sv._exigir_lectura_coherente

    def lento(*a, **k):
        original(*a, **k)
        time.sleep(0.5)   # la ventana entre validar e insertar, donde estaría la carrera

    monkeypatch.setattr(sv, "_exigir_lectura_coherente", lento)
    resultados = []

    def cargar(horas):
        try:
            sv.registrar_lectura({"nombre": "Prueba"}, equipo, fecha=HOY, horas=horas)
            resultados.append("ok")
        except Exception as e:  # noqa: BLE001  (se mira qué error fue)
            resultados.append(e)

    hilos = [threading.Thread(target=cargar, args=(h,)) for h in (90000, 80000)]
    hilos[0].start()
    time.sleep(0.1)   # el segundo arranca mientras el primero está entre validar e insertar
    hilos[1].start()
    for h in hilos:
        h.join(20)
    assert resultados[0] == "ok", resultados
    # el segundo esperó su turno y vio la lectura del primero: el mensaje de la regla, no "database is locked"
    assert isinstance(resultados[1], sv.ErrorDeNegocio) and "no puede bajar" in str(resultados[1])


def test_transaccion_anidada_reusa_la_conexion_y_deshace_solo_lo_suyo(api):
    nombres = lambda: {a["nombre"] for a in sv.listar_areas()}  # noqa: E731
    with db.transaccion() as c:
        sv.crear_area({"nombre": "Prueba"}, nombre="Queda")
        try:
            with db.transaccion() as c2:
                assert c2 is c
                sv.crear_area({"nombre": "Prueba"}, nombre="Se deshace")
                raise sv.ErrorDeNegocio("falla el de adentro")
        except sv.ErrorDeNegocio:
            pass
    assert "Queda" in nombres() and "Se deshace" not in nombres()
    try:
        with db.transaccion():
            sv.crear_area({"nombre": "Prueba"}, nombre="Tampoco")
            raise RuntimeError("falla el de afuera")
    except RuntimeError:
        pass
    assert "Tampoco" not in nombres()
