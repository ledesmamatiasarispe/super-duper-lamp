"""Lo que el asistente (la barra "Preguntá algo", modulos/asistente de appbase) sabe de mantenimiento.

Reparto, según la prueba con modelos locales chicos (Qwen 2.5 3B, Llama 3.2 3B, 17/11/2026):
  - SIN IA (responder): lo que es una lista o una cuenta (vencidos, pendientes, lo que le falta a una máquina). Ahí los
    modelos fallaban: a "¿hay algo vencido?" contestaban "No figura" en vez de "No, ninguna".
  - CON IA (contexto): lo que es texto libre (qué le pasó, qué se le cambió, cómo se hace un servicio). Los datos van
    ya resumidos y calculados ("último servicio C: 6/7/2026 a las 466 h"): sin ese resumen, un modelo leyó mal una lista
    de registros e inventó una fecha.
Todo se lee con los servicios del módulo (las mismas cuentas que Inicio y el Mapa): acá no se calcula nada nuevo."""
import re
import unicodedata
from datetime import date
from pathlib import Path

from . import servicios as s

_PALABRAS_VACIAS = set("""cuando donde como cual cuales cuanto cuantos cuanta cuantas tiene tienen tenia hace hacer hizo
hicieron ultimo ultima ultimos ultimas maquina maquinas equipo equipos para esta estan este estos esas esos alguna alguno
algun algo sobre desde fueron paso pasaron sabes decime dame quiero quien quienes porque tambien entre hasta segun
todas todos cada servicio servicios mantenimiento""".split())


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c)).replace("-", " ")


def _palabras(t: str) -> set[str]:
    return set(re.findall(r"[a-zñ0-9]+", _norm(t)))


# ── qué máquina nombra la pregunta ──
def _candidatos(pregunta: str) -> list[dict]:
    """Los equipos que mejor coinciden con la pregunta (más de uno si empatan: "el compresor" son dos).
    Cuenta el código (EQ-001), el modelo pegado a su número (ETR-50, "etr 50", "etr50") y las palabras del nombre."""
    q = _norm(pregunta)
    q_pegado = q.replace(" ", "")
    palabras_q = _palabras(pregunta)
    puntajes = []
    for e in s.listar_equipos():
        if re.search(rf"\b{re.escape(_norm(e['codigo']))}\b", q):
            return [e]
        nombre = _norm(e["nombre"] + " " + (e.get("marca_modelo") or ""))
        puntos = 0.0
        for m in set(re.findall(r"[a-z]+ ?\d+[a-z]?\b", nombre)):    # ETR-50, ETR-80C, PE 713
            if m.replace(" ", "") in q_pegado:
                puntos += 3
        propias = [p for p in re.findall(r"[a-zñ]+", _norm(e["nombre"])) if len(p) >= 4 and p not in _PALABRAS_VACIAS]
        for p in propias:
            if p in palabras_q or (p.endswith("s") and p[:-1] in palabras_q) or p + "s" in palabras_q:
                puntos += 1 + (0.5 if p == propias[0] else 0)       # "horno de inducción" antes que "pluma horno"
        if puntos:
            puntajes.append((puntos, e))
    if not puntajes:
        return []
    mejor = max(p for p, _ in puntajes)
    return [e for p, e in puntajes if p == mejor]


def _enlaces(e: dict) -> list[dict]:
    enlaces = [{"texto": "Ver instructivo", "ir": f"instructivos/{i}"} for i in (e.get("instructivo_ids") or [])[:1]]
    if e.get("plano_id"):
        enlaces.append({"texto": "Ver en el mapa", "ir": f"mapa/{e['plano_id']}"})
    return enlaces + [{"texto": "Especificaciones", "accion": "verEspecificaciones", "datos": {"equipo_id": e["id"]}},
                      {"texto": "Registros", "ir": "registros"}, {"texto": "Correctivos", "ir": "correctivos"}]


# ── especificaciones: el dato técnico cargado, o la invitación a cargarlo (nunca uno inventado) ──
_VACIAS_ESPECIFICACION = _PALABRAS_VACIAS | set("""que el la los las de del es son se le lo un una al en mi hay usa usan lleva
llevan necesita necesitan va van tipo marca modelo medida valor cuál dato datos especificacion especificaciones sabe
saber necesito decir dice cuanto cuanta lleva y o a con por""".split())


def _linea_especificacion(x: dict) -> str:
    fuente = x.get("fuente_texto") or s.FUENTES_ESPECIFICACION.get(x["fuente"], x["fuente"])
    return (f"- {x['nombre']}: {x['valor']}{' ' + x['unidad'] if x.get('unidad') else ''} (según {fuente.lower()}"
            f"{', ' + x['fuente_detalle'] if x.get('fuente_detalle') else ''})" + (f". Nota: {x['notas']}" if x.get("notas") else ""))


def _nombre_sugerido(pregunta: str, e: dict | None = None) -> str:
    """De "¿qué aceite usa el compresor ETR-50?" sale "Aceite": las palabras de la pregunta que no son relleno ni el
    nombre de la máquina. Es solo una sugerencia para el formulario: quien carga la corrige."""
    de_la_maquina = _palabras(f"{e['nombre']} {e.get('marca_modelo') or ''} {e['codigo']}") if e else set()
    tokens = re.findall(r"[a-záéíóúñü0-9]+", (pregunta or "").lower())

    def sirve(p):
        return (len(p) >= 3 and _norm(p) not in _VACIAS_ESPECIFICACION and _norm(p) not in de_la_maquina
                and not re.fullmatch(r"\d+[a-z]?", p))
    # la primera palabra que sirve y las que la siguen, con sus "de"/"del" ("presión de trabajo", "correa del motor")
    inicio = next((i for i, p in enumerate(tokens) if sirve(p)), None)
    if inicio is None:
        return ""
    frase, i = [tokens[inicio]], inicio + 1
    while i < len(tokens) and len(frase) < 5:
        if sirve(tokens[i]):
            frase.append(tokens[i])
        elif tokens[i] in ("de", "del"):   # "de", "del", "de la", "de los"... seguido de una palabra que sirve
            j = i + 1 + (i + 1 < len(tokens) and tokens[i + 1] in ("la", "las", "los", "el"))
            if j >= len(tokens) or not sirve(tokens[j]):
                break
            frase += tokens[i:j + 1]
            i = j
        else:
            break
        i += 1
    return " ".join(frase).capitalize()


def _especificaciones_pedidas(pregunta: str, e: dict) -> list[dict]:
    """Las especificaciones del equipo cuyo nombre aparece en la pregunta ("aceite" -> "Aceite", "correas" -> "Correa")."""
    q = _palabras(pregunta)
    salida = []
    for x in s.listar_especificaciones(e["id"]):
        propias = [p for p in _palabras(x["nombre"]) if len(p) >= 3 and p not in _VACIAS_ESPECIFICACION]
        if propias and all(p in q or p + "s" in q or p.rstrip("s") in q or p + "es" in q for p in propias):
            salida.append(x)
    return salida


def _cargar(e: dict | None, nombre: str) -> dict:
    return {"texto": "Cargar especificación", "accion": "especificacion",
            "datos": {"equipo_id": e["id"] if e else None, "nombre": nombre}}


# ── sin IA: listas y cuentas ──
_PIDE_VENCIDOS = re.compile(r"\b(vencid\w*|atrasad\w*|venci\w*|retrasad\w*)\b")
_PIDE_PENDIENTES = re.compile(r"\b(pendiente\w*|toca\w*|falta hacer|faltan hacer|este mes|que hay para hacer)\b")
# "¿qué hay que hacer en el servicio A?" o "¿cómo se hace...?" piden el procedimiento (instructivo), no lo pendiente
_PIDE_PROCEDIMIENTO = re.compile(r"\b(como se hace|como hago|pasos|procedimiento|instructivo|servicio [a-h])\b")
_PIDE_LECTURA = re.compile(r"\b(horometro|lectura|cuantas horas tiene|horas de uso)\b")


def _miles(n) -> str:
    return f"{n:,.0f}".replace(",", ".") if isinstance(n, (int, float)) else str(n)


def _fecha(iso) -> str:
    return "/".join(reversed(str(iso)[:10].split("-"))) if iso else "sin fecha"


def _linea_pendiente(p: dict, con_equipo: str = "") -> str:
    return f"- {con_equipo}{p['codigo']} (servicio {p['seccion']}): {p['detalle']}"


def responder(pregunta: str) -> dict | None:
    q = _norm(pregunta)
    pide_vencidos, pide_pendientes = bool(_PIDE_VENCIDOS.search(q)), bool(_PIDE_PENDIENTES.search(q))
    candidatos = _candidatos(pregunta)
    if len(candidatos) > 1:
        return {"titulo": "¿Cuál máquina?",
                "texto": "Encontré varias máquinas con ese nombre. ¿Por cuál preguntás?",
                "enlaces": [{"texto": f"{e['codigo']} · {e['nombre']}", "accion": "preguntar",
                             "datos": {"pregunta": f"{pregunta.rstrip(' ?¿')} ({e['codigo']})?"}} for e in candidatos[:8]]}
    if len(candidatos) == 1:
        e = candidatos[0]
        pedidas = _especificaciones_pedidas(pregunta, e)
        if pedidas:
            return {"titulo": f"{e['codigo']} · {e['nombre']}",
                    "texto": "Especificaciones cargadas:\n" + "\n".join(map(_linea_especificacion, pedidas)),
                    "enlaces": [{"texto": "Ver todas las especificaciones", "accion": "verEspecificaciones", "datos": {"equipo_id": e["id"]}}]}
    if len(candidatos) == 1 and _PIDE_LECTURA.search(q) and not re.search(r"\b(falta\w*|proximo|servicio)\b", q):
        e = candidatos[0]
        h = next((x for x in s.estado_horometros() if x["equipo_id"] == e["id"]), None)
        texto = (f"El {e['nombre']} no lleva horómetro." if not h
                 else f"El {e['nombre']} no tiene ninguna lectura de horómetro cargada." if h["ultima_lectura"] is None
                 else f"Última lectura del horómetro del {e['nombre']}: {_miles(h['ultima_lectura'])} h, anotada el "
                      f"{_fecha(h['fecha_lectura'])}.")
        return {"titulo": f"{e['codigo']} · {e['nombre']}", "texto": texto, "enlaces": [{"texto": "Horómetros", "ir": "horometros"}]}
    if not (pide_vencidos or pide_pendientes) or _PIDE_PROCEDIMIENTO.search(q):
        return None
    estados = s._estado_equipos()
    if candidatos:
        e = candidatos[0]
        lista = estados.get(e["codigo"], {"pendientes": []})["pendientes"]
        if pide_vencidos and not pide_pendientes:
            lista = [p for p in lista if p["estado"] == "vencido"]
            texto = (f"El {e['nombre']} tiene {len(lista)} vencida(s):\n" + "\n".join(map(_linea_pendiente, lista))) if lista \
                else f"No, el {e['nombre']} no tiene nada vencido ni atrasado."
        else:
            texto = (f"Lo que tiene pendiente el {e['nombre']}:\n" + "\n".join(map(_linea_pendiente, lista))) if lista \
                else f"El {e['nombre']} está al día: no tiene nada pendiente."
        return {"titulo": f"{e['codigo']} · {e['nombre']}", "texto": texto, "enlaces": _enlaces(e)}
    nombres = {x["codigo"]: x["nombre"] for x in s.listar_equipos()}
    todos = [(cod, p) for cod, x in sorted(estados.items()) for p in x["pendientes"]]
    if pide_vencidos and not pide_pendientes:
        lista = [(c, p) for c, p in todos if p["estado"] == "vencido"]
        texto = (f"Hay {len(lista)} tarea(s) vencida(s) o atrasada(s):\n"
                 + "\n".join(_linea_pendiente(p, nombres.get(c, c) + " · ") for c, p in lista)) if lista \
            else "No, no hay ninguna tarea vencida ni atrasada."
    else:
        lista = todos
        texto = (f"Hay {len(lista)} pendientes:\n" + "\n".join(_linea_pendiente(p, nombres.get(c, c) + " · ") for c, p in lista)) \
            if lista else "No hay nada pendiente: está todo al día."
    return {"titulo": "Pendientes", "texto": texto, "enlaces": [{"texto": "Ir a Inicio", "ir": "inicio"}, {"texto": "Cronograma", "ir": "cronograma"}]}


# ── con IA: los datos de una máquina, ya resumidos ──
def _datos_equipo(e: dict) -> tuple[str, str]:
    """(datos para la IA, resumen para mostrar sin IA)."""
    hoy = date.today().isoformat()
    lineas = [f"Hoy: {hoy}", f"EQUIPO: {e['codigo']} {e['nombre']} | marca/modelo: {e.get('marca_modelo') or '-'} | sector: {e.get('sector') or '-'}"]
    resumen = []
    tareas = [t for t in s.listar_tareas() if t["equipo_id"] == e["id"]]
    if tareas:
        lineas.append("PLAN (tareas):")
        for t in tareas:
            cada = f"cada {t['cada_horas']} horas" if t.get("cada_horas") else (t.get("frecuencia") or "-")
            lineas.append(f"- servicio {t['seccion'][-1]} ({t['seccion']}): {cada}")
    h = next((x for x in s.estado_horometros() if x["equipo_id"] == e["id"]), None)
    if h:
        lectura = h["ultima_lectura"] if h["ultima_lectura"] is not None else "NO HAY NINGUNA LECTURA CARGADA"
        lineas.append(f"HORÓMETRO: última lectura {lectura}" + (f" ({h['fecha_lectura']})" if h.get("fecha_lectura") else ""))
        resumen.append(f"Horómetro: {_miles(lectura)} h" + (f" (al {_fecha(h['fecha_lectura'])})" if h.get("fecha_lectura") else "")
                       if h["ultima_lectura"] is not None else "Horómetro: no tiene lecturas cargadas.")
        for sv in h["servicios"]:
            hecho = f"hecho a las {sv['hecho_a']} h" if sv.get("hecho_a") is not None else "sin registro de cuándo se hizo"
            faltan = f"faltan {sv['faltan']} h" if sv.get("faltan") is not None else "faltan: sin dato (no hay lectura)"
            lineas.append(f"- servicio {sv['seccion'][-1]} ({sv['seccion']}, cada {sv['cada_horas']} h): {hecho}; próximo a las "
                          f"{sv['proximo']} h; {faltan}")
            resumen.append(f"- Servicio {sv['seccion'][-1]}: próximo a las {sv['proximo']} h ({faltan})")
    registros = s.listar_registros(equipo_id=e["id"], limite=500)
    if registros:
        ultimo = registros[0]["fecha"]
        secciones = sorted({r["seccion"] for r in registros if r["fecha"] == ultimo})
        lineas.append(f"ÚLTIMO MANTENIMIENTO REGISTRADO: {ultimo} (servicios {', '.join(secciones)})")
        resumen.append(f"Último mantenimiento registrado: {_fecha(ultimo)} ({', '.join(secciones)})")
        lineas.append("ÚLTIMO REGISTRO DE CADA SERVICIO:")
        for sec in sorted({r["seccion"] for r in registros}):
            r = next(x for x in registros if x["seccion"] == sec)   # vienen del más nuevo al más viejo
            horas = f", a las {r['horometro']} h de horómetro" if r.get("horometro") is not None else ""
            lineas.append(f"- servicio {sec[-1]} ({sec}): {r['fecha']}{horas}; resultado {r['resultado']}; "
                          f"hizo: {r.get('realizado_por_nombre') or r.get('realizado_por') or 'sin dato'}")
        lineas.append("REGISTROS (los más nuevos):")
        for r in registros[:6]:
            lineas.append(f"- {r['fecha']} servicio {r['seccion'][-1]}: {r['resultado']}; novedades: {(r.get('novedades') or '-')[:160]}"
                          + (f"; repuestos: {r['repuestos']}" if r.get("repuestos") else ""))
    else:
        lineas.append("ÚLTIMO MANTENIMIENTO REGISTRADO: no hay ningún registro")
        resumen.append("No tiene mantenimientos registrados.")
    pend = s._estado_equipos().get(e["codigo"], {"pendientes": []})["pendientes"]
    lineas.append("PENDIENTES:" if pend else "PENDIENTES: NO HAY NINGUNO, está al día.")
    lineas += [_linea_pendiente(p) for p in pend]
    resumen.append("Pendiente:\n" + "\n".join(map(_linea_pendiente, pend)) if pend else "Al día: nada pendiente.")
    correctivos = s.listar_correctivos(equipo_id=e["id"])
    lineas.append("CORRECTIVOS (reparaciones, los más nuevos):" if correctivos else "CORRECTIVOS: ninguno")
    for c in correctivos[:8]:
        lineas.append(f"- {c['fecha']}: falla: {c['falla']}; acción: {(c.get('accion') or '-')[:220]}; repuestos: {c.get('repuestos') or '-'}")
    if correctivos:
        resumen.append("Últimas reparaciones:\n" + "\n".join(f"- {_fecha(c['fecha'])}: {c['falla']}" + (f" → {c['accion'][:120]}" if c.get("accion") else "")
                                                            for c in correctivos[:3]))
    especificaciones = s.listar_especificaciones(e["id"])
    lineas.append("ESPECIFICACIONES TÉCNICAS (cargadas, con su fuente):" if especificaciones else "ESPECIFICACIONES TÉCNICAS: ninguna cargada")
    lineas += [_linea_especificacion(x) for x in especificaciones]
    if especificaciones:
        resumen.append("Especificaciones:\n" + "\n".join(map(_linea_especificacion, especificaciones)))
    for it_id in (e.get("instructivo_ids") or [])[:1]:
        it = s.obtener_instructivo(it_id)
        lineas.append(f"INSTRUCTIVO {it['codigo']} ({it['titulo']}):")
        for sec in it.get("secciones") or []:
            lineas.append(f"- servicio {sec['letra']}: " + "; ".join(a["texto"] for a in sec.get("actividades") or []))
        if it.get("repuestos"):
            lineas.append("- repuestos del instructivo: " + "; ".join(
                r["nombre"] + (f" x{r['cantidad']:g}" if r.get("cantidad") is not None else "") for r in it["repuestos"]))
    return "\n".join(lineas), "\n".join(resumen)


# ── fichas: un texto corto por cada cosa cargada, para la búsqueda del asistente (modulos/asistente/textos.py) ──
# Se arman con los mismos servicios que las pantallas y el asistente las rehace solo cuando la base cambia. Una pregunta
# que no nombra una máquina ("¿qué máquinas usan correa SPZ?", "¿quién arregló rodamientos?") se contesta con ellas.
def _horas(n) -> str:
    return f"{n:g} h" if isinstance(n, (int, float)) else f"{n} h"


def fichas() -> list[dict]:
    equipos = s.listar_equipos(incluir_baja=True)
    instructivos = {i["id"]: i for i in s.listar_instructivos()}
    tareas = s.listar_tareas()
    lista = []
    for e in equipos:
        plan = [f"servicio {t['seccion'][-1]} ({t['seccion']}): "
                + (f"cada {t['cada_horas']} horas" if t.get("cada_horas") else (t.get("frecuencia") or "-"))
                + (f", responsable {t['responsable']}" if t.get("responsable") else "")
                for t in tareas if t["equipo_id"] == e["id"]]
        its = [instructivos[i]["codigo"] for i in e.get("instructivo_ids") or [] if i in instructivos]
        lista.append({"tipo": "Equipo", "titulo": f"{e['codigo']} {e['nombre']}" + ("" if e["activo"] else " (obsoleto)"),
                      "ir": "equipos",
                      "texto": f"área {e.get('sector') or '-'}; marca/modelo {e.get('marca_modelo') or '-'}; "
                               f"{'con' if e.get('usa_horometro') else 'sin'} horómetro; "
                               f"instructivo {', '.join(its) or 'ninguno'}; plan: {'; '.join(plan) or 'nada programado'}"
                               + (f"; dado de baja: {e['motivo_baja']}" if not e["activo"] and e.get("motivo_baja") else "")})
    usado_por = {}
    for e in equipos:
        for i in e.get("instructivo_ids") or []:
            usado_por.setdefault(i, []).append(f"{e['codigo']} {e['nombre']}")
    for it_id, resumen in instructivos.items():
        it = s.obtener_instructivo(it_id)
        de = f"{it['codigo']} · {it['titulo']}" + ("" if it.get("vigente", 1) else " (obsoleto)")
        equipos_it = ", ".join(usado_por.get(it_id, [])) or "(no está asignado a ningún equipo)"
        if it.get("seguridad"):
            lista.append({"tipo": "Seguridad del instructivo", "titulo": de, "ir": f"instructivos/{it_id}",
                          "texto": f"equipo {equipos_it}. " + " ".join(str(it["seguridad"]).split())})
        for sec in it.get("secciones") or []:
            pasos = [(a["texto"].rstrip(":") + ":") if a.get("es_grupo") else a["texto"] + (f" ({a['detalle']})" if a.get("detalle") else "")
                     for a in sec.get("actividades") or []]
            lista.append({"tipo": "Sección de instructivo", "titulo": f"{de} · servicio {sec['letra']} ({sec['codigo']})",
                          "ir": f"instructivos/{it_id}", "texto": f"equipo {equipos_it}. Actividades: " + "; ".join(pasos)})
        if it.get("repuestos"):
            lista.append({"tipo": "Repuestos del instructivo", "titulo": de, "ir": f"instructivos/{it_id}",
                          "texto": f"equipo {equipos_it}. " + "; ".join(
                              r["nombre"] + (f" x{r['cantidad']:g}" if r.get("cantidad") is not None else "") for r in it["repuestos"])})
    for c in s.listar_correctivos():
        lista.append({"tipo": "Correctivo", "titulo": f"{_fecha(c['fecha'])} {c['equipo_codigo']} {c['equipo']}", "ir": "correctivos",
                      "texto": f"falla: {c['falla']}" + (f"; causa: {c['causa']}" if c.get("causa") else "")
                               + f"; acción: {c.get('accion') or '-'}"
                               + (f"; repuestos: {c['repuestos']}" if c.get("repuestos") else "")
                               + (f"; parada: {_horas(c['horas_parada'])}" if c.get("horas_parada") is not None else "")
                               + f"; hizo: {c.get('realizado_por_nombre') or c.get('realizado_por') or 'sin dato'}"
                               + ("; requiere acción del SGC" if c.get("accion_sgc") else "")
                               + (f"; observaciones: {c['observaciones']}" if c.get("observaciones") else "")})
    for r in s.listar_registros(limite=5000):
        novedades = r.get("novedades") or ""
        if novedades.startswith("Cargado del"):      # las cargas masivas del cronograma no dicen nada del trabajo
            novedades = ""
        if not (novedades or r.get("repuestos") or r["resultado"] not in ("Realizado",)):
            continue
        lista.append({"tipo": "Registro de mantenimiento", "ir": "registros",
                      "titulo": f"{_fecha(r['fecha'])} {r['equipo_codigo']} {r['equipo']} servicio {r['seccion'][-1]}",
                      "texto": f"resultado {r['resultado']}"
                               + (f" (para el {_fecha(r['reprogramado_para'])})" if r.get("reprogramado_para") else "")
                               + (f"; novedades: {novedades}" if novedades else "")
                               + (f"; repuestos: {r['repuestos']}" if r.get("repuestos") else "")
                               + f"; hizo: {r.get('realizado_por_nombre') or r.get('realizado_por') or 'sin dato'}"})
    for x in s.listar_especificaciones():
        lista.append({"tipo": "Especificación", "titulo": f"{x['equipo_codigo']} {x['equipo']} · {x['nombre']}", "ir": "equipos",
                      "texto": _linea_especificacion(x)[2:]})
    for a in s.listar_areas():
        de_area = [f"{e['codigo']} {e['nombre']}" for e in equipos if e.get("area_id") == a["id"] and e["activo"]]
        lista.append({"tipo": "Área", "titulo": a["nombre"] + ("" if a.get("activo", 1) else " (dada de baja)"), "ir": "areas",
                      "texto": f"{len(de_area)} equipos: " + (", ".join(de_area) or "ninguno")})
    for p in s.listar_personas():
        lista.append({"tipo": "Persona", "titulo": p["nombre"], "ir": "personal",
                      "texto": ("mantenimiento interno" if p.get("categoria") == "interno" else "proveedor externo")
                               + (f"; contacto: {p['contacto']}" if p.get("contacto") else "")
                               + ("" if p.get("activo", 1) else "; dado de baja")})
    return lista


def contexto(pregunta: str) -> dict | None:
    candidatos = _candidatos(pregunta)
    if len(candidatos) == 1:
        e = candidatos[0]
        datos, resumen = _datos_equipo(e)
        sugerido = _nombre_sugerido(pregunta, e)
        return {"titulo": f"{e['codigo']} · {e['nombre']}", "datos": datos, "resumen": resumen,
                "enlaces": _enlaces(e),
                "si_no_figura": {"texto": f"¿Lo sabés? Cargalo como especificación del {e['nombre']} y la próxima vez va a estar.",
                                 "enlace": _cargar(e, sugerido)}}
    return None     # sin una máquina: el asistente busca en las fichas (ver fichas())


def sin_resultado(pregunta: str) -> dict | None:
    """Nadie encontró nada: en vez de suponer, se ofrece cargar el dato como especificación de la máquina que corresponda."""
    sugerido = _nombre_sugerido(pregunta)
    if not sugerido:
        return None
    return {"titulo": "No está cargado",
            "texto": f"No hay nada cargado en la app sobre «{sugerido}». Si nombrás la máquina, busco en sus datos "
                     "(por ejemplo «… del ETR-50»). Si conocés el dato, cargalo como especificación de la máquina "
                     "y la próxima vez lo contesto.",
            "enlaces": [_cargar(None, sugerido)]}


def temas(pregunta: str) -> list[str]:
    """Las máquinas que nombra la pregunta, por su código: así "¿y cuántas horas tiene?" después de preguntar por el
    ETR-50 se contesta como "¿y cuántas horas tiene? (EQ-001)". Si nombra varias (el "compresor"), no se sigue ninguna."""
    return [e["codigo"] for e in _candidatos(pregunta)]


EJEMPLOS = ["¿Hay algo vencido?", "¿Qué le pasó al lavador de humos?", "¿Cuántas horas tiene el ETR-50?",
            "¿Qué hay que hacer en el servicio A del ETR-50?", "¿Qué máquinas tuvieron problemas de rodamientos?",
            "¿Cómo cargo un correctivo?"]

try:
    from modulos.asistente import Fuente, registrar
except ImportError:          # la app no trae el asistente: mantenimiento funciona igual
    registrar = None
if registrar:
    _IA = Path(__file__).resolve().parent / "ia"     # la guía de uso y los sinónimos, para la IA
    registrar(Fuente("mantenimiento", responder=responder, contexto=contexto, sin_resultado=sin_resultado, temas=temas,
                     fichas=fichas, guia=_IA / "guia.md", sinonimos=_IA / "sinonimos.txt", ejemplos=EJEMPLOS))
