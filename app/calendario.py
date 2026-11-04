"""Reglas del cronograma, sin base de datos: qué meses toca cada tarea y en qué estado está cada celda.

Es la lógica que en el Excel vivía en las fórmulas de la hoja Cronograma y de Horómetros.
"""
from dataclasses import dataclass
from datetime import date

# Frecuencias del calendario: meses entre un servicio y el siguiente. Las demás no van al cronograma mensual.
INTERVALO_MESES = {"Quincenal": 1, "Mensual": 1, "Bimestral": 2, "Trimestral": 3,
                   "Cuatrimestral": 4, "Semestral": 6, "Anual": 12}
POR_HORAS = "Por horas"
SEGUN_CONDICION = "Según condición"
FRECUENCIAS = [*INTERVALO_MESES, POR_HORAS, SEGUN_CONDICION]

RESULTADOS = ["Realizado", "Con observaciones", "No realizado", "Reprogramado", "No aplica"]
CUMPLE = {"Realizado", "Con observaciones"}   # cuentan como hecho


def meses_especificos(texto: str) -> list[int]:
    """'3, 9' -> [3, 9]. Lanza ValueError con un mensaje legible si algo no es un mes."""
    meses = []
    for parte in (texto or "").replace(";", ",").split(","):
        parte = parte.strip()
        if not parte:
            continue
        if not parte.isdigit() or not 1 <= int(parte) <= 12:
            raise ValueError(f"'{parte}' no es un mes (1 a 12).")
        meses.append(int(parte))
    return sorted(set(meses))


def veces_por_mes(frecuencia: str, mes_inicio: int | None, especificos: str, mes: int) -> int:
    """Cuántas veces toca la tarea en ese mes (0 si no toca). El ciclo se repite igual todos los años:
    todos los intervalos dividen a 12, así que el mes de inicio fija la fase para siempre."""
    lista = meses_especificos(especificos)
    if lista:
        return (2 if frecuencia == "Quincenal" else 1) if mes in lista else 0
    intervalo = INTERVALO_MESES.get(frecuencia)
    if not intervalo or not mes_inicio:
        return 0
    if (mes - mes_inicio) % intervalo:
        return 0
    return 2 if frecuencia == "Quincenal" else 1


@dataclass
class Celda:
    esperado: int        # veces que toca ese mes
    hechos: int          # registros que cumplen
    estado: str          # ver estado_celda
    detalle: str = ""    # para el tooltip


def estado_celda(esperado: int, resultados: list[str], anio: int, mes: int, hoy: date,
                 alta: date | None = None) -> Celda:
    """Estado de una tarea en un mes, a partir de lo que se registró.

    hecho        cumplió lo que tocaba (o más)
    extra        no tocaba y se hizo igual
    pendiente    toca este mes o uno futuro y todavía no se completó
    vencido      tocaba en un mes que ya pasó y no se completó
    reprogramado / no_realizado / no_aplica   tocaba, no se cumplió, y quedó registrado por qué
    antes_alta   el mes es anterior a que existiera la tarea: no se le exige nada
    vacio        no toca y no hay nada
    """
    hechos = sum(1 for r in resultados if r in CUMPLE)
    detalle = ", ".join(resultados)
    if esperado == 0:
        return Celda(0, hechos, "extra" if hechos else "vacio", detalle)
    if hechos >= esperado:
        return Celda(esperado, hechos, "hecho", detalle)
    # no se completó: si quedó asentado el motivo, ese motivo es el estado (lo registrado se ve siempre)
    for motivo, estado in (("No aplica", "no_aplica"), ("Reprogramado", "reprogramado"), ("No realizado", "no_realizado")):
        if motivo in resultados:
            return Celda(esperado, hechos, estado, detalle)
    if alta and (anio, mes) < (alta.year, alta.month):
        return Celda(esperado, hechos, "antes_alta", detalle)
    pasado = (anio, mes) < (hoy.year, hoy.month)
    return Celda(esperado, hechos, "vencido" if pasado else "pendiente", detalle)


@dataclass
class EstadoHoras:
    ultima_lectura: int | None
    hecho_a: int | None       # horómetro del último servicio registrado
    proximo: int | None
    faltan: int | None
    estado: str               # sin_lectura | falta_dato | al_dia | proximo | vencido


def estado_por_horas(cada_horas: int | None, proximo_inicial: int | None, ultima_lectura: int | None,
                     hecho_a: int | None, aviso: int) -> EstadoHoras:
    """Servicio por horas: el próximo es el último hecho + intervalo; si nunca se hizo, el inicial del Plan."""
    if hecho_a is not None and cada_horas:
        proximo = hecho_a + cada_horas
    else:
        proximo = proximo_inicial
    if proximo is None:
        return EstadoHoras(ultima_lectura, hecho_a, None, None, "falta_dato")
    if ultima_lectura is None:
        return EstadoHoras(None, hecho_a, proximo, None, "sin_lectura")
    faltan = proximo - ultima_lectura
    estado = "vencido" if faltan < 0 else "proximo" if faltan <= aviso else "al_dia"
    return EstadoHoras(ultima_lectura, hecho_a, proximo, faltan, estado)


# Para la grilla de horómetros: si dos cosas caen en el mismo bloque de horas, se ve la más urgente
_PRIORIDAD = {"vacio": 0, "programado": 1, "hecho": 2, "proximo": 3, "tarde": 4, "vencido": 5}


def grilla_por_horas(cada_horas: int, proximo_inicial: int | None, hechos: list[tuple[int, str]],
                     ultima_lectura: int | None, aviso: int, inicio: int, tamanio: int, columnas: int = 12) -> list[dict]:
    """El "cronograma" de un servicio por horas: en vez de meses, bloques de `tamanio` horas desde `inicio`.

    hechos: (horómetro, fecha) de cada servicio registrado. Cada servicio corre el siguiente a sus horas + cada_horas;
    antes del primero manda el próximo inicial del Plan. Marca:
      hecho       se hizo en ese bloque
      tarde       tocaba en ese bloque y se hizo en uno posterior
      vencido     el próximo ya quedó atrás de la última lectura
      proximo     el próximo, a `aviso` horas o menos
      programado  el próximo (lejos todavía) y los siguientes, proyectados
    """
    celdas = [{"estado": "vacio", "detalle": []} for _ in range(columnas)]

    def poner(horas: int, estado: str, texto: str) -> None:
        i = (horas - inicio) // tamanio
        if 0 <= i < columnas:
            c = celdas[i]
            c["detalle"].append(texto)
            if _PRIORIDAD[estado] > _PRIORIDAD[c["estado"]]:
                c["estado"] = estado

    toca = proximo_inicial
    for horas, fecha in sorted(hechos):
        if toca is not None and (horas - inicio) // tamanio > (toca - inicio) // tamanio:
            poner(toca, "tarde", f"Tocaba a {toca:,} h y se hizo a {horas:,} h".replace(",", "."))
        poner(horas, "hecho", f"Hecho a {horas:,} h el {fecha}".replace(",", "."))
        toca = horas + cada_horas
    if toca is None or not cada_horas:
        return celdas
    primero = True
    while (toca - inicio) // tamanio < columnas:
        if primero and ultima_lectura is not None and toca < ultima_lectura:
            estado = "vencido"
        elif primero and ultima_lectura is not None and toca - ultima_lectura <= aviso:
            estado = "proximo"
        else:
            estado = "programado"
        poner(toca, estado, f"{'Próximo' if primero else 'Después'}: a {toca:,} h".replace(",", "."))
        toca += cada_horas
        primero = False
    return celdas
