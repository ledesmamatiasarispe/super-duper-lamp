"""Carga las fichas de mantenimiento originales (las planillas .xls en papel) como equipos e instructivos de la app.

De cada ficha se leen las secciones (A, B, C…) con su frecuencia y sus actividades, y los repuestos críticos. Lo que
la ficha no dice bien (nombre del equipo, sector, marca, responsable, qué instructivo es de qué equipo) sale de la
tabla de abajo, que se armó con el CronogramaMantenimiento-2027.xlsm: varias fichas tienen el encabezado copiado de
otra (la del Aparejo de la zona de amolado dice "aparejo del elevador de arena"; la de las mangas, "Molino de
tierra") y muchas traen hojas sueltas de plantilla (Hoja1/Hoja3, del Puente grúa Expedición) que no son de ese equipo.

Cada sección aparece dos veces en la hoja (dos rondas de firmas): vale la primera. En los equipos iguales que usaban
la misma ficha (Noyeras N° 1 y N° 2), el segundo recibe una copia: en la app los equipos no comparten instructivo.
La ficha 25 (Amoladoras) no tiene secciones: es un registro de altas y bajas, no un preventivo, y no se carga.

    .venv/Scripts/python.exe herramientas/cargar_fichas.py "<carpeta de las fichas>" --simular
    .venv/Scripts/python.exe herramientas/cargar_fichas.py "<carpeta de las fichas>" [--reemplazar-prueba]

--simular muestra lo leído sin tocar la base. --reemplazar-prueba borra antes los equipos, instructivos y tareas
de prueba (solo si no hay ningún registro, lectura ni correctivo cargado) y deja el instructivo de EJEMPLO, con
código EJ01: así los equipos y los instructivos quedan con los mismos códigos que el cronograma 2027.
Usa la base de MANT_DB o data/mantenimiento.db. COPIARLA ANTES."""
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import xlrd  # noqa: E402

import app.main  # noqa: E402,F401  (configura el núcleo: la base es la de MANT_DB o data/mantenimiento.db)
from modulos.mantenimiento import servicios as sv  # noqa: E402
from nucleo.db import transaccion  # noqa: E402


def inicializar(con_ejemplos: bool = True) -> None:
    from nucleo.db import inicializar as _inicializar
    _inicializar(app.main.MODULOS, con_ejemplos=con_ejemplos)

USUARIO = {"nombre": "Carga de fichas originales"}
TITULO_EJEMPLO = "EJEMPLO · Bomba centrífuga de agua de refrigeración"

# código, nombre, área, marca / modelo, horómetro (en este orden se crean: el código lo asigna la app)
EQUIPOS = [
    ("EQ-001", "Compresor ETR-50", "Servicios", "Cetec ETR-50", True),
    ("EQ-002", "Compresor ETR-80C", "Servicios", "Cetec ETR-80C", True),
    ("EQ-003", "Granalladora", "Terminación", "Americana AC-1200", False),
    ("EQ-004", "Transformadores", "Servicios", "Brenta 200 kVA y 1000 kVA", False),
    ("EQ-005", "Durómetro Brinell", "Laboratorio", "", False),
    ("EQ-006", "Zarandas", "Arenas", "", False),
    ("EQ-007", "Noyera N° 1", "Noyería", "", False),
    ("EQ-008", "Noyera N° 2", "Noyería", "", False),
    ("EQ-009", "Noyera N° 3", "Noyería", "", False),
    ("EQ-010", "Cascarera", "Noyería", "", False),
    ("EQ-011", "Pegadora de vacío", "Noyería", "", False),
    ("EQ-012", "Molino de tierra", "Arenas", "Tecno", False),
    ("EQ-013", "Mezclador continuo de arena", "Arenas", "IMF T36/3", False),
    ("EQ-014", "Montacargas molino de tierra", "Arenas", "", False),
    ("EQ-015", "Monorriel horno recuperador de arena", "Arenas", "", False),
    ("EQ-016", "Pluma moldeo", "Moldeo", "", False),
    ("EQ-017", "Puente grúa Noyería", "Noyería", "", False),
    ("EQ-018", "Puente grúa Sayos 500 kg", "Moldeo", "", False),
    ("EQ-019", "Puente grúa Sayos 1000 kg", "Moldeo", "", False),
    ("EQ-020", "Aparejo eléctrico mezcladora de arena", "Arenas", "", False),
    ("EQ-021", "Puente grúa Expedición", "Expedición", "Ferro", False),
    ("EQ-022", "Sistema de elevación de arena recuperada", "Arenas", "", False),
    ("EQ-023", "Aparejo eléctrico zona de amolado", "Terminación", "", False),
    ("EQ-024", "Lavador de humos", "Fusión", "", False),
    ("EQ-025", "Pluma horno", "Fusión", "", False),
    ("EQ-026", "Horno de inducción", "Fusión", "", False),
    ("EQ-027", "Radiador horno (PE 713.1)", "Fusión", "", False),
    ("EQ-028", "Elevador de bolsas de arena (silo)", "Arenas", "", False),
]

# código del instructivo, cómo empieza el nombre de la ficha, título, tipo de seguridad, responsable, equipos
# (el primero es el dueño del instructivo; los demás reciben una copia)
FICHAS = [
    ("IT01", "1 - ", "Compresor Cetec ETR-50", "compresor", "Chofer", ["EQ-001"]),
    ("IT02", "2 - ", "Compresor Cetec ETR-80C", "compresor", "Chofer", ["EQ-002"]),
    ("IT03", "3 - ", "Horno de inducción", "horno", "Mantenimiento y Fusión", ["EQ-026"]),
    ("IT04", "4 - ", "Granalladora", "general", "Expedición", ["EQ-003"]),
    ("IT05", "5 - ", "Molino de tierra", "general", "Moldeo", ["EQ-012"]),
    ("IT06", "6 - FichaMantenimiento-Noyera(automatizada)", "Noyera N° 1", "general", "Noyería", ["EQ-007", "EQ-008"]),
    ("IT07", "6 - FichaMantenimiento-Noyera (manual)", "Noyera manual (N° 3)", "general", "Noyería", ["EQ-009"]),
    ("IT08", "10 - ", "Cascarera", "general", "Noyería", ["EQ-010"]),
    ("IT09", "11 - ", "Pegadoras de vacío (1 y 2)", "general", "Noyería", ["EQ-011"]),
    ("IT10", "12 - ", "Zarandas (1 y 2)", "general", "Moldeo", ["EQ-006"]),
    ("IT11", "13 - ", "Montacargas del molino de tierra", "izaje", "Moldeo", ["EQ-014"]),
    ("IT12", "14 - ", "Monorriel del horno recuperador de arena", "izaje", "Mantenimiento", ["EQ-015"]),
    ("IT13", "15 - ", "Pluma de moldeo", "izaje", "Fusión", ["EQ-016"]),
    ("IT14", "16 - FichaMantenimiento-AparejoMescladora", "Aparejo eléctrico de la mezcladora de arena", "izaje",
     "A definir", ["EQ-020"]),
    ("IT15", "16 - FichaMantenimiento-AparejoZonaAmolado", "Aparejo eléctrico de la zona de amolado", "izaje",
     "A definir", ["EQ-023"]),
    ("IT16", "16 - FichaMantenimiento-PlumaHorno", "Pluma del horno", "izaje", "Fusión", ["EQ-025"]),
    ("IT17", "17 - ", "Puente grúa Noyería", "izaje", "Mantenimiento", ["EQ-017"]),
    ("IT18", "18 - ", "Puente grúa Sayos 500 kg", "izaje", "Mantenimiento", ["EQ-018"]),
    ("IT19", "19 - ", "Puente grúa Sayos 1000 kg", "izaje", "Mantenimiento", ["EQ-019"]),
    ("IT20", "20 - ", "Puente grúa Expedición", "izaje", "Mantenimiento", ["EQ-021"]),
    ("IT21", "21 - ", "Mezclador continuo de arena", "general", "Mantenimiento", ["EQ-013"]),
    ("IT22", "22 - ", "Transformadores", "transformador", "Fusión (ejecuta personal externo)", ["EQ-004"]),
    ("IT23", "23 - ", "Sistema de elevación de arena recuperada", "general", "Mantenimiento", ["EQ-022"]),
    ("IT24", "24 - ", "Lavador de humos", "general", "Mantenimiento", ["EQ-024"]),
    ("IT25", "26 - ", "Mangas filtrantes del sistema elevador de arena", "general", "A definir", ["EQ-022"]),
    ("IT26", "27 - ", "Elevador de bolsas de arena (silo)", "izaje", "A definir", ["EQ-028"]),
]
SIN_PREVENTIVO = {"25 - ": "Amoladoras: la ficha es un registro de altas y bajas, no tiene secciones de mantenimiento."}

# frases de seguridad del cronograma 2027, por tipo de equipo (la base va en todos, salvo donde no entra personal propio)
_BASE = ["Coordinar la parada con el responsable del sector antes de comenzar.",
         "Cortar la energía en el tablero, bloquear el seccionador y colocar la tarjeta «NO OPERAR – EN MANTENIMIENTO».",
         "Verificar la ausencia de tensión (y de presión, si hay neumática o hidráulica) antes de intervenir.",
         "Usar EPP: guantes, anteojos de seguridad y calzado de seguridad; protección auditiva donde corresponda."]
_FIN = ["Al terminar: retirar herramientas, reponer guardas y protecciones, probar el equipo y entregarlo al responsable."]
SEGURIDAD = {
    "general": _BASE + _FIN,
    "compresor": _BASE + ["Despresurizar el tanque y la línea de aire, y esperar a que el equipo se enfríe antes de abrir."] + _FIN,
    "horno": _BASE + ["Intervenir con el horno sin potencia y coordinado con Fusión.",
                      "Mantener el circuito de refrigeración en servicio mientras haya material caliente en el crisol."] + _FIN,
    "izaje": _BASE + ["Trabajar sin carga suspendida y señalizar el área bajo el recorrido del equipo.",
                      "Para trabajos en altura usar arnés con línea de vida o plataforma elevadora."] + _FIN,
    "transformador": ["Solo interviene personal externo habilitado, con la cabina sin tensión.",
                      "El personal de planta no ingresa a la cabina."] + _FIN,
}

# errores de tipeo evidentes de las fichas (el resto del texto queda como estaba)
CORRECCIONES = [("estadod e ", "estado de "), ("prestañas", "pestañas"), ("se sielten", "se suelten"),
                ("que indice mediante", "que indique mediante"), ("enciendal al llegare", "enciendan al llegar"),
                ("injectores", "inyectores"), ("¡importante !", "¡Importante! "), ("puesta  a tierra", "puesta a tierra"),
                ("controlar puesta tierra", "controlar puesta a tierra")]
GRUPOS = {"ESTRUCTURA": "Estructura", "TESTEOS": "Testeros", "TESTEROS": "Testeros", "CARRO": "Carro",
          "GANCHOS": "Ganchos", "INSTALACIÓN ELECTRICA": "Instalación eléctrica", "SEÑALIZACION": "Señalización"}

# la ficha 23 anota al lado de cada repuesto dónde va (en la columna de observaciones, corrida)
REPUESTOS_A_MANO = {
    "IT23": [{"nombre": "Correa (B-41) — motor del extractor", "cantidad": 1},
             {"nombre": "Cadena de 70 eslabones — reductor del extractor", "cantidad": None},
             {"nombre": "Corona de 50 dientes, eje Ø 45 mm — conjunto extractor de la tolva de arena", "cantidad": None}],
}

ENCABEZADO = re.compile(r"^([A-Za-z])\s*-\s*\(?\s*(.*?)\s*\)?\s*$")
NUMERO = r"(\d+(?:[.,]\d+)?)"


def _texto(valor) -> str:
    return re.sub(r"\s+", " ", str(valor)).strip() if valor not in ("", None) else ""


def _prolijo(t: str) -> str:
    for mal, bien in CORRECCIONES:
        t = t.replace(mal, bien)
    t = re.sub(r"\s+", " ", t).strip().rstrip(".").strip()
    return t[:1].upper() + t[1:]


def _frecuencia(t: str) -> str:
    t = t.strip()
    return (t.lower() if t.isupper() else t)[:1].upper() + (t.lower() if t.isupper() else t)[1:]


def _repuesto(t: str) -> dict:
    """'Correas: 2 (juego) (SPZ 1060 Lw)' -> Correas (juego) (SPZ 1060 Lw), 2. Si no hay cantidad clara, queda el texto."""
    t = t.strip().rstrip(".").strip()
    cantidad, nombre = None, t
    if m := re.match(rf"^(.*?):\s*{NUMERO}\s*(.*)$", t):            # Aceite: 5 litros / Correas: 2 (juego) (SPZ…)
        etiqueta, n, resto = m.groups()
        cantidad, nombre = n, etiqueta.strip()
        if resto:
            unidad, _, mas = resto.partition(" ") if not resto.startswith("(") else ("", "", resto)
            nombre += (f" ({unidad})" if unidad else "") + (f" {mas.strip()}" if mas.strip() else "")
    elif m := re.match(rf"^(.*?):\s*juego de {NUMERO}\s*(.*)$", t):   # Correa: juego de 2 (B43)
        nombre, cantidad = f"{m.group(1)} (juego) {m.group(3)}".strip(), m.group(2)
    elif m := re.match(rf"^{NUMERO}\s*(m|metros|l|litros)\s+de\s+(.+)$", t, re.I):   # 28 m de cable de acero…
        cantidad, nombre = m.group(1), f"{m.group(3)} ({m.group(2)})"
    elif m := re.match(rf"^{NUMERO}\s*-?\s*(\D.*)$", t):              # 1-Filtro de aceite… / 2 rodamiento ucp 208
        cantidad, nombre = m.groups()
    elif m := re.match(rf"^(.*\D)\s+{NUMERO}$", t):                   # Electro válvula 1
        nombre, cantidad = m.groups()
    nombre = _prolijo(nombre)
    return {"nombre": nombre, "cantidad": float(cantidad.replace(",", ".")) if cantidad else None}


def leer_ficha(ruta: Path) -> dict:
    secciones: dict[str, dict] = {}
    repuestos: list[str] = []
    for h in xlrd.open_workbook(str(ruta)).sheets():
        actual, en_repuestos, col_obs = None, False, None
        for r in range(h.nrows):
            celdas = [(c, _texto(h.cell_value(r, c))) for c in range(h.ncols)]
            celdas = [(c, t) for c, t in celdas if t]
            if not celdas:
                continue
            primera = celdas[0][1] if celdas[0][0] == 0 else ""
            if any(t.upper().startswith(("APROBÓ", "HOJA ", "HOLA ")) for _, t in celdas):
                en_repuestos = False
                continue
            if primera.lower().startswith("repuestos críticos"):
                en_repuestos, actual = True, None
                col_obs = next((c for c, t in celdas if t.upper().startswith("OBSERVACIONES")), None)
                continue
            if en_repuestos:
                for c, t in celdas:
                    if (col_obs is None or c < col_obs) and t.strip("- ") and t.lower() != "no posee":
                        if repuestos and (repuestos[-1].count("(") > repuestos[-1].count(")") or repuestos[-1].endswith(":")):
                            repuestos[-1] += " " + t   # la línea sigue en la fila de abajo
                        else:
                            repuestos.append(t)
                continue
            m = ENCABEZADO.match(primera) if len(primera) < 60 else None
            if m and re.search(r"mes|hora|anual|mensual|semana", m.group(2), re.I):
                letra = m.group(1).upper()
                # la misma sección por segunda vez (otra ronda de firmas, u otra hoja) no se vuelve a leer
                actual = None if letra in secciones else secciones.setdefault(
                    letra, {"letra": letra, "frecuencia": _frecuencia(m.group(2)), "actividades": []})
                continue
            if any(t.startswith("Firma") for _, t in celdas):
                actual = None
                continue
            if actual is not None and primera:
                texto = GRUPOS.get(primera, None)
                act = ({"texto": texto, "es_grupo": True, "detalle": ""} if texto else
                       {"texto": _prolijo(primera), "es_grupo": False, "detalle": ""})
                propias = [a["texto"] for a in actual["actividades"] if not a["es_grupo"]]
                if not texto and propias and act["texto"] == propias[0]:
                    actual = None   # la lista vuelve a empezar: es la copia para la segunda ronda de firmas
                elif texto or act["texto"] not in propias:   # una línea repetida suelta (pasa en las plumas) va una vez
                    actual["actividades"].append(act)
    vistos, unicos = set(), []
    for t in repuestos:   # las fichas por hoja (compresores) repiten la misma lista en cada hoja
        clave = re.sub(r"\W", "", t.lower())
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(_repuesto(t))
    return {"secciones": sorted(secciones.values(), key=lambda s: s["letra"]), "repuestos": unicos}


def contenido(ficha: tuple, leido: dict, equipo: dict, archivo: str) -> dict:
    codigo, _, titulo, tipo, responsable, _ = ficha
    frecuencias = [["Sección", "Frecuencia según la ficha"]] + [[s["letra"], s["frecuencia"]] for s in leido["secciones"]]
    return {
        "titulo": titulo,
        "descripcion": (f"Mantenimiento preventivo: {titulo}. Responsable: {responsable}.\n"
                        f"Cargado de la ficha de mantenimiento original «{archivo}»."),
        "seguridad": SEGURIDAD[tipo],
        "repuestos": REPUESTOS_A_MANO.get(codigo, leido["repuestos"]),
        "secciones": [{"letra": s["letra"], "actividades": s["actividades"]} for s in leido["secciones"]],
        "bloques": [sv._ficha_equipo(equipo),
                    {"tipo": "tabla", "ubicacion": "general",
                     "datos": {"titulo": "Frecuencias", "encabezado": True, "filas": frecuencias}}],
    }


def buscar_archivos(carpeta: Path) -> dict[str, Path]:
    archivos = sorted(carpeta.glob("*.xls"))
    salida = {}
    for ficha in FICHAS:
        candidatos = [a for a in archivos if a.name.startswith(ficha[1])]
        if len(candidatos) != 1:
            raise SystemExit(f"{ficha[0]}: se esperaba UNA ficha que empiece con «{ficha[1]}» y hay {len(candidatos)}.")
        salida[ficha[0]] = candidatos[0]
    return salida


def borrar_datos_de_prueba() -> None:
    """Equipos, instructivos y tareas de prueba. Si ya hay algo registrado de verdad, no se borra nada."""
    with transaccion() as c:
        for tabla, que in (("registros", "registros de mantenimiento"), ("lecturas_horometro", "lecturas de horómetro"),
                           ("correctivos", "correctivos")):
            if c.execute(f"SELECT 1 FROM {tabla}").fetchone():
                raise SystemExit(f"La base ya tiene {que}: no son datos de prueba, no se borra nada.")
        # sin registros, las tareas del Plan no tienen historia: se pueden borrar (la app solo les da de baja)
        c.execute("DELETE FROM tareas")
    for e in sv.listar_equipos(incluir_baja=True):
        sv.eliminar_equipo(USUARIO, e["id"])   # se lleva su instructivo y los archivos adjuntos
    for it in sv.listar_instructivos():
        if it["titulo"] != TITULO_EJEMPLO:
            sv.eliminar_instructivo(USUARIO, it["id"])
    for a in sv.listar_areas():
        sv.eliminar_area(USUARIO, a["id"])
    # el ejemplo deja libres los códigos IT: así las fichas quedan IT01…IT26, como en el cronograma
    with transaccion() as c:
        ej = c.execute("SELECT codigo FROM instructivos WHERE titulo=?", (TITULO_EJEMPLO,)).fetchone()
        if ej and ej["codigo"] != "EJ01":
            c.execute("UPDATE instructivos SET codigo='EJ01' WHERE titulo=?", (TITULO_EJEMPLO,))
            viejo, nuevo = sv._carpeta_adjuntos(ej["codigo"]), sv._carpeta_adjuntos("EJ01")
            if viejo.is_dir():
                shutil.move(str(viejo), str(nuevo))


def cargar(carpeta: Path, simular: bool, reemplazar: bool) -> None:
    archivos = buscar_archivos(carpeta)
    leidas = {codigo: leer_ficha(ruta) for codigo, ruta in archivos.items()}
    for ficha in FICHAS:
        leido = leidas[ficha[0]]
        print(f"\n{ficha[0]} {ficha[2]}  <- {archivos[ficha[0]].name}  (equipos: {', '.join(ficha[5])})")
        for s in leido["secciones"]:
            print(f"  {s['letra']} · {s['frecuencia']}")
            for a in s["actividades"]:
                print(f"      {'# ' if a['es_grupo'] else '- '}{a['texto']}")
        for r in REPUESTOS_A_MANO.get(ficha[0], leido["repuestos"]):
            print(f"  repuesto: {r['nombre']}" + (f"  x {r['cantidad']:g}" if r["cantidad"] is not None else ""))
        if not leido["secciones"]:
            raise SystemExit(f"{ficha[0]}: la ficha no tiene ninguna sección legible.")
    for prefijo, motivo in SIN_PREVENTIVO.items():
        print(f"\nNo se carga «{prefijo}…»: {motivo}")
    if simular:
        return

    inicializar(con_ejemplos=False)
    if reemplazar:
        borrar_datos_de_prueba()
    if sv.listar_equipos(incluir_baja=True):
        raise SystemExit("La base ya tiene equipos: los códigos no coincidirían con el cronograma. "
                         "Usar --reemplazar-prueba (si son de prueba) o cargar a mano.")
    areas = {a["nombre"]: a["id"] for a in sv.listar_areas()}
    equipos = {}
    for codigo, nombre, area, marca, horometro in EQUIPOS:
        if area not in areas:
            areas[area] = sv.crear_area(USUARIO, nombre=area)["id"]
        e = sv.crear_equipo(USUARIO, nombre=nombre, area_id=areas[area], marca_modelo=marca, usa_horometro=horometro)
        assert e["codigo"] == codigo, f"se esperaba {codigo} y la app asignó {e['codigo']}"
        equipos[codigo] = e
    for ficha in FICHAS:
        dueno = equipos[ficha[5][0]]
        it = sv.crear_instructivo(USUARIO, equipo_id=dueno["id"],
                                  **contenido(ficha, leidas[ficha[0]], dueno, archivos[ficha[0]].name))
        assert it["codigo"] == ficha[0], f"se esperaba {ficha[0]} y la app asignó {it['codigo']}"
    for ficha in FICHAS:   # las copias al final, para no correr la numeración IT01…IT26
        for otro in ficha[5][1:]:
            copia = sv.copiar_instructivo_de_equipo(USUARIO, equipos[otro]["id"], desde=equipos[ficha[5][0]]["id"])
            print(f"{otro}: copia {copia['instructivos_copiados'][0]['codigo']} de {ficha[0]}")
    print(f"\nListo: {len(EQUIPOS)} equipos y {len(sv.listar_instructivos())} instructivos en la base.")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        raise SystemExit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8")
    cargar(Path(args[0]), simular="--simular" in sys.argv, reemplazar="--reemplazar-prueba" in sys.argv)
