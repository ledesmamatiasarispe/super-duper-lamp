from datetime import date

import pytest

from app import calendario as cal


def meses(frecuencia, inicio=None, especificos=""):
    return [m for m in range(1, 13) if cal.veces_por_mes(frecuencia, inicio, especificos, m)]


def test_frecuencias_por_intervalo():
    assert meses("Trimestral", 1) == [1, 4, 7, 10]
    assert meses("Trimestral", 2) == [2, 5, 8, 11]
    assert meses("Semestral", 3) == [3, 9]
    assert meses("Anual", 11) == [11]
    assert meses("Mensual", 5) == list(range(1, 13))   # el ciclo sigue todo el año, también antes del mes de inicio
    assert cal.veces_por_mes("Quincenal", 1, "", 6) == 2


def test_meses_especificos_mandan_sobre_la_frecuencia():
    assert meses("Mensual", 1, "3, 9") == [3, 9]
    with pytest.raises(ValueError):
        cal.meses_especificos("3, 13")


def test_frecuencias_fuera_del_calendario_no_programan_meses():
    assert meses("Por horas", 1) == []
    assert meses("Según condición", 1) == []


HOY = date(2026, 11, 3)


@pytest.mark.parametrize("esperado, resultados, mes, estado", [
    (1, ["Realizado"], 4, "hecho"),
    (1, ["Con observaciones"], 4, "hecho"),
    (1, [], 4, "vencido"),
    (1, [], 11, "pendiente"),          # mes en curso
    (1, [], 12, "pendiente"),
    (1, ["Reprogramado"], 4, "reprogramado"),
    (1, ["No realizado"], 4, "no_realizado"),
    (1, ["No aplica"], 4, "no_aplica"),
    (2, ["Realizado"], 4, "vencido"),   # quincenal con una sola vez
    (0, ["Realizado"], 5, "extra"),
    (0, [], 5, "vacio"),
])
def test_estado_de_celda(esperado, resultados, mes, estado):
    assert cal.estado_celda(esperado, resultados, 2026, mes, HOY).estado == estado


def test_no_se_exige_nada_antes_del_alta_de_la_tarea():
    alta = date(2026, 6, 15)
    assert cal.estado_celda(1, [], 2026, 4, HOY, alta).estado == "antes_alta"
    assert cal.estado_celda(1, [], 2026, 7, HOY, alta).estado == "vencido"
    # lo que se registró se ve igual, aunque sea de antes del alta
    assert cal.estado_celda(1, ["Realizado"], 2026, 4, HOY, alta).estado == "hecho"
    assert cal.estado_celda(1, ["Reprogramado"], 2026, 4, HOY, alta).estado == "reprogramado"


def test_servicio_por_horas():
    # nunca se hizo: manda el próximo inicial del Plan
    assert cal.estado_por_horas(1000, 51000, None, None, 100).estado == "sin_lectura"
    e = cal.estado_por_horas(1000, 51000, 50850, None, 100)
    assert (e.proximo, e.faltan, e.estado) == (51000, 150, "al_dia")
    assert cal.estado_por_horas(1000, 51000, 50950, None, 100).estado == "proximo"
    assert cal.estado_por_horas(1000, 51000, 51020, None, 100).estado == "vencido"
    # ya se hizo a las 51020: el próximo es 52020, el inicial deja de importar
    e = cal.estado_por_horas(1000, 51000, 51100, 51020, 100)
    assert (e.proximo, e.faltan, e.estado) == (52020, 920, "al_dia")
    assert cal.estado_por_horas(1000, None, 500, None, 100).estado == "falta_dato"


def estados(celdas):
    return [c["estado"] for c in celdas]


def test_grilla_por_horas_proyecta_desde_el_ultimo_servicio():
    # cada 1000 h, primer servicio a 51000, bloques de 1000 desde 50000; hecho a 51020, lectura 51500
    g = cal.grilla_por_horas(1000, 51000, [(51020, "2026-10-28")], 51500, 100, 50000, 1000, columnas=6)
    assert estados(g) == ["vacio", "hecho", "programado", "programado", "programado", "programado"]
    assert "52.020" in g[2]["detalle"][0]


def test_grilla_por_horas_marca_vencido_y_hecho_tarde():
    # nunca se hizo y la lectura ya pasó el inicial: el próximo está vencido
    g = cal.grilla_por_horas(1000, 51000, [], 51200, 100, 50000, 1000, columnas=4)
    assert estados(g) == ["vacio", "vencido", "programado", "programado"]
    # tocaba a 51000 y se hizo recién a 52100: el bloque de 51000 queda "tarde"
    g = cal.grilla_por_horas(1000, 51000, [(52100, "2026-11-01")], 52150, 100, 50000, 1000, columnas=5)
    assert estados(g) == ["vacio", "tarde", "hecho", "programado", "programado"]


def test_grilla_por_horas_proximo_cerca():
    g = cal.grilla_por_horas(1000, 51000, [], 50950, 100, 50000, 1000, columnas=3)
    assert estados(g) == ["vacio", "proximo", "programado"]
    # servicio menos frecuente que el bloque: aparece cada 4 columnas
    g = cal.grilla_por_horas(4000, 53000, [], 50950, 100, 50000, 1000, columnas=8)
    assert estados(g) == ["vacio", "vacio", "vacio", "programado", "vacio", "vacio", "vacio", "programado"]
