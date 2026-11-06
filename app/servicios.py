"""Casos de uso: la única puerta a los datos. Cada función es una transacción completa.

Las rutas de main.py solo parsean y llaman acá; ninguna valida ni escribe SQL por su cuenta.
"""
import json
import math
import re
import secrets
import shutil
import sqlite3
from datetime import date, datetime
from pathlib import Path

from . import calendario as cal
from . import db
from .db import transaccion


class ErrorDeNegocio(Exception):
    """Lo que el usuario cargó no se puede aceptar; el mensaje se le muestra tal cual."""


class NoEncontrado(Exception):
    pass


# ── validaciones de campo ───────────────────────────────────────────────────

def _texto(valor, campo: str, obligatorio: bool = True) -> str:
    t = str(valor or "").strip()
    if obligatorio and not t:
        raise ErrorDeNegocio(f"Falta {campo}.")
    return t


def _fecha(valor, campo: str, obligatorio: bool = True) -> str | None:
    if valor in (None, ""):
        if obligatorio:
            raise ErrorDeNegocio(f"Falta {campo}.")
        return None
    try:
        return date.fromisoformat(str(valor)[:10]).isoformat()
    except ValueError:
        raise ErrorDeNegocio(f"{campo.capitalize()}: '{valor}' no es una fecha.")


def _numero(valor, campo: str, entero: bool = False, minimo: float = 0, maximo: float = 1e9):
    if valor in (None, ""):
        return None
    try:
        n = float(str(valor).replace(",", "."))
    except ValueError:
        n = None
    if n is None or not math.isfinite(n):   # float() acepta "nan" e "inf": tampoco son números cargables
        raise ErrorDeNegocio(f"{campo.capitalize()}: '{valor}' no es un número.")
    if not minimo <= n <= maximo:
        raise ErrorDeNegocio(f"{campo.capitalize()} tiene que estar entre {minimo:g} y {maximo:g}.")
    if entero:
        if n != int(n):
            raise ErrorDeNegocio(f"{campo.capitalize()} tiene que ser un número entero.")
        return int(n)
    return round(n, 2)


def _opcion(valor, opciones: list[str], campo: str) -> str:
    if valor not in opciones:
        raise ErrorDeNegocio(f"{campo.capitalize()}: elegir una de {', '.join(opciones)}.")
    return valor


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _fila(c: sqlite3.Connection, sql: str, params: tuple, que: str) -> sqlite3.Row:
    r = c.execute(sql, params).fetchone()
    if not r:
        raise NoEncontrado(f"No existe {que}.")
    return r


def _persona(c, persona_id, campo: str, obligatorio: bool = False):
    if persona_id in (None, ""):
        if obligatorio:
            raise ErrorDeNegocio(f"Falta {campo}.")
        return None
    if not c.execute("SELECT 1 FROM personas WHERE id=?", (persona_id,)).fetchone():
        raise ErrorDeNegocio(f"{campo.capitalize()}: la persona elegida no existe.")
    return int(persona_id)


def _quien(c, persona_id, nombre, obligatorio: bool = False) -> tuple[int | None, str]:
    """Quién hizo el trabajo: la persona elegida y, si es genérica ("Mantenimiento interno"), el nombre de quién fue."""
    pid = _persona(c, persona_id, "quién lo hizo", obligatorio)
    if pid is None:
        return None, ""
    p = c.execute("SELECT nombre, pide_nombre FROM personas WHERE id=?", (pid,)).fetchone()
    if not p["pide_nombre"]:
        return pid, ""
    return pid, _texto(nombre, f"el nombre de quién lo hizo ({p['nombre']})")


# SQL de "quién lo hizo" para los listados: "Mantenimiento interno — Juan Pérez"
_REALIZADO_POR = "p.nombre || coalesce(' — ' || nullif({t}.realizado_por_nombre, ''), '') AS realizado_por"


# ── personas ────────────────────────────────────────────────────────────────

CATEGORIAS = {"interno": "Mantenimiento interno", "externo": "Proveedor externo"}
_COLS_PERSONA = "id, nombre, categoria, contacto, pide_nombre, activo, usuario_legajo"
_ORDEN_PERSONAS = "ORDER BY categoria DESC, pide_nombre, activo DESC, nombre"   # interno primero; la genérica al final


def listar_personas() -> list[dict]:
    with transaccion() as c:
        return [dict(r) for r in c.execute(f"SELECT {_COLS_PERSONA} FROM personas {_ORDEN_PERSONAS}")]


def _nombre_libre(c, nombre: str, excepto: int | None = None) -> None:
    if c.execute("SELECT 1 FROM personas WHERE lower(nombre)=lower(?) AND id IS NOT ?", (nombre, excepto)).fetchone():
        raise ErrorDeNegocio(f"Ya existe '{nombre}'.")


def crear_persona(usuario: dict, *, nombre, categoria, contacto="") -> dict:
    nombre = _texto(nombre, "el nombre")
    categoria = _opcion(categoria, list(CATEGORIAS), "la categoría")
    with transaccion() as c:
        _nombre_libre(c, nombre)
        c.execute("INSERT INTO personas (nombre, categoria, contacto) VALUES (?,?,?)",
                  (nombre, categoria, _texto(contacto, "", False)))
        return dict(c.execute(f"SELECT {_COLS_PERSONA} FROM personas WHERE id=last_insert_rowid()").fetchone())


def _persona_editable(c, persona_id: int) -> sqlite3.Row:
    p = _fila(c, f"SELECT {_COLS_PERSONA} FROM personas WHERE id=?", (persona_id,), "esa persona")
    if p["pide_nombre"]:
        raise ErrorDeNegocio(f"'{p['nombre']}' es la categoría en sí (la opción Otro): no se edita ni se da de baja.")
    return p


def actualizar_persona(usuario: dict, persona_id: int, *, nombre, contacto="") -> dict:
    """La categoría no se cambia: los trabajos ya registrados se cuentan en la que tenía."""
    nombre = _texto(nombre, "el nombre")
    with transaccion() as c:
        p = _persona_editable(c, persona_id)
        if p["usuario_legajo"] and nombre != p["nombre"]:
            raise ErrorDeNegocio("Es un usuario del sistema: el nombre se cambia en Usuarios.")
        _nombre_libre(c, nombre, excepto=persona_id)
        c.execute("UPDATE personas SET nombre=?, contacto=? WHERE id=?", (nombre, _texto(contacto, "", False), persona_id))
        return dict(c.execute(f"SELECT {_COLS_PERSONA} FROM personas WHERE id=?", (persona_id,)).fetchone())


def cambiar_alta_persona(usuario: dict, persona_id: int, *, activo: bool) -> dict:
    """Dar de baja solo la saca de las listas para elegir: sus trabajos siguen contando en el seguimiento."""
    with transaccion() as c:
        if _persona_editable(c, persona_id)["usuario_legajo"]:
            raise ErrorDeNegocio("Es un usuario del sistema: se da de baja o se reactiva en Usuarios.")
        c.execute("UPDATE personas SET activo=? WHERE id=?", (int(activo), persona_id))
        return dict(c.execute(f"SELECT {_COLS_PERSONA} FROM personas WHERE id=?", (persona_id,)).fetchone())


# Trabajos de cualquier tipo en una sola lista: preventivos (registros) y correctivos
_SQL_TRABAJOS = """
    SELECT 'Preventivo' AS tipo, r.fecha, r.realizado_por_id AS persona_id, r.realizado_por_nombre AS nombre_libre,
           e.codigo AS equipo_codigo, e.nombre AS equipo, i.codigo || '-' || s.letra || ' · ' || r.resultado AS detalle,
           r.horas_hombre, NULL AS horas_parada
    FROM registros r JOIN tareas t ON t.id = r.tarea_id JOIN equipos e ON e.id = t.equipo_id
    JOIN secciones s ON s.id = t.seccion_id JOIN instructivos i ON i.id = s.instructivo_id
    WHERE r.realizado_por_id IS NOT NULL AND substr(r.fecha, 1, 4) = :anio
    UNION ALL
    SELECT 'Correctivo', co.fecha, co.realizado_por_id, co.realizado_por_nombre, e.codigo, e.nombre, co.falla,
           co.horas_hombre, co.horas_parada
    FROM correctivos co JOIN equipos e ON e.id = co.equipo_id
    WHERE co.realizado_por_id IS NOT NULL AND substr(co.fecha, 1, 4) = :anio
"""


def seguimiento_personas(anio: int) -> list[dict]:
    """Por cada operario o proveedor: cuántos trabajos hizo en el año, sus horas-hombre y el último.
    Para la fila genérica ("Otro"), además, los nombres escritos a mano: candidatos a darse de alta."""
    with transaccion() as c:
        personas = c.execute(f"SELECT {_COLS_PERSONA} FROM personas {_ORDEN_PERSONAS}").fetchall()
        trabajos = c.execute(_SQL_TRABAJOS, {"anio": str(anio)}).fetchall()
    salida = []
    for p in personas:
        suyos = [t for t in trabajos if t["persona_id"] == p["id"]]
        salida.append({**dict(p),
                       "preventivos": sum(t["tipo"] == "Preventivo" for t in suyos),
                       "correctivos": sum(t["tipo"] == "Correctivo" for t in suyos),
                       "horas_hombre": round(sum(t["horas_hombre"] or 0 for t in suyos), 2),
                       "ultimo": max((t["fecha"] for t in suyos), default=None),
                       "nombres_libres": sorted({t["nombre_libre"] for t in suyos if t["nombre_libre"]})})
    return salida


def trabajos_de_persona(persona_id: int, anio: int) -> list[dict]:
    with transaccion() as c:
        _fila(c, "SELECT 1 FROM personas WHERE id=?", (persona_id,), "esa persona")
        filas = c.execute(f"SELECT * FROM ({_SQL_TRABAJOS}) WHERE persona_id = :id ORDER BY fecha DESC",
                          {"anio": str(anio), "id": persona_id})
        return [dict(r) for r in filas]


# ── equipos ─────────────────────────────────────────────────────────────────

def listar_equipos(incluir_baja: bool = False) -> list[dict]:
    """Con `vinculos`: cuántas cosas lo referencian (tareas del Plan, de alta o no, lecturas y correctivos).
    En 0 se puede eliminar; si no, solo marcarlo obsoleto."""
    with transaccion() as c:
        filas = c.execute("""
            SELECT e.*, coalesce(a.nombre, '') AS sector, (SELECT count(*) FROM tareas WHERE equipo_id = e.id)
                      + (SELECT count(*) FROM lecturas_horometro WHERE equipo_id = e.id)
                      + (SELECT count(*) FROM correctivos WHERE equipo_id = e.id) AS vinculos,
                   (SELECT group_concat(instructivo_id) FROM instructivo_equipos WHERE equipo_id = e.id) AS instructivos
            FROM equipos e LEFT JOIN areas a ON a.id = e.area_id """ + ("" if incluir_baja else "WHERE e.activo=1 ") + "ORDER BY e.codigo")
        salida = []
        for r in filas:
            d = dict(r)
            d["instructivo_ids"] = sorted(int(x) for x in (d.pop("instructivos") or "").split(",") if x)
            salida.append(d)
        return salida


def asignar_instructivos_equipo(usuario: dict, equipo_id: int, *, instructivo_ids) -> dict:
    """Qué instructivos aplican a este equipo. No se le puede quitar uno del que tiene tareas activas en el Plan.
    Cada instructivo es de un solo equipo: solo se le puede sumar uno que no tenga equipo (para uno parecido, se copia)."""
    if not isinstance(instructivo_ids, list):
        raise ErrorDeNegocio("Instructivos: se esperaba una lista.")
    try:
        nuevos = {int(x) for x in instructivo_ids}
    except (TypeError, ValueError):
        raise ErrorDeNegocio("Instructivos: la lista tiene un valor que no es un instructivo.")
    with transaccion() as c:
        e = _fila(c, "SELECT codigo FROM equipos WHERE id=?", (equipo_id,), "ese equipo")
        actuales = {r[0] for r in c.execute("SELECT instructivo_id FROM instructivo_equipos WHERE equipo_id=?", (equipo_id,))}
        for it_id in nuevos - actuales:
            it = c.execute("SELECT codigo, vigente FROM instructivos WHERE id=?", (it_id,)).fetchone()
            if not it:
                raise ErrorDeNegocio("Uno de los instructivos elegidos no existe.")
            if not it["vigente"]:
                raise ErrorDeNegocio(f"{it['codigo']} está obsoleto: no se asigna a equipos.")
            dueno = c.execute("SELECT e.codigo FROM instructivo_equipos x JOIN equipos e ON e.id = x.equipo_id "
                              "WHERE x.instructivo_id=?", (it_id,)).fetchone()
            if dueno:
                raise ErrorDeNegocio(f"{it['codigo']} es el instructivo de {dueno[0]}: los equipos no comparten instructivo. "
                                     "Para un equipo parecido, se copia el suyo.")
        for it_id in actuales - nuevos:
            usadas = c.execute("""SELECT i.codigo || '-' || s.letra FROM tareas t JOIN secciones s ON s.id = t.seccion_id
                                  JOIN instructivos i ON i.id = s.instructivo_id
                                  WHERE t.equipo_id=? AND s.instructivo_id=? AND t.activa=1""", (equipo_id, it_id)).fetchall()
            if usadas:
                raise ErrorDeNegocio(f"{e['codigo']} tiene en el Plan {', '.join(u[0] for u in usadas)}: "
                                     "primero hay que dar de baja esas tareas.")
            c.execute("DELETE FROM instructivo_equipos WHERE equipo_id=? AND instructivo_id=?", (equipo_id, it_id))
        c.executemany("INSERT INTO instructivo_equipos (instructivo_id, equipo_id) VALUES (?,?)",
                      [(it_id, equipo_id) for it_id in nuevos - actuales])
    return next(x for x in listar_equipos(incluir_baja=True) if x["id"] == equipo_id)


def _area(c, area_id, actual: int | None = None) -> int | None:
    """El área del equipo: opcional, y de la lista. Una dada de baja no se elige, salvo que el equipo ya la tuviera."""
    if area_id in (None, ""):
        return None
    a = c.execute("SELECT id, nombre, activo FROM areas WHERE id=?", (area_id,)).fetchone()
    if not a:
        raise ErrorDeNegocio("El área elegida no existe.")
    if not a["activo"] and a["id"] != actual:
        raise ErrorDeNegocio(f"El área '{a['nombre']}' está dada de baja.")
    return a["id"]


def _datos_equipo(c, datos: dict, area_actual: int | None = None) -> tuple:
    return (_texto(datos.get("nombre"), "el nombre del equipo"), _area(c, datos.get("area_id"), area_actual),
            _texto(datos.get("marca_modelo"), "la marca", False), int(bool(datos.get("usa_horometro"))))


def _equipo(c, equipo_id: int) -> dict:
    return dict(c.execute("SELECT e.*, coalesce(a.nombre, '') AS sector FROM equipos e LEFT JOIN areas a ON a.id = e.area_id "
                          "WHERE e.id=?", (equipo_id,)).fetchone())


def crear_equipo(usuario: dict, *, copiar_de=None, **datos) -> dict:
    """Con `copiar_de` (otro equipo, parecido): el nuevo nace con una copia de su instructivo, en la misma transacción.
    Devuelve el equipo y los instructivos copiados (vacío si no se copió nada)."""
    copiados: list[Path] = []
    try:
        with transaccion() as c:
            campos = _datos_equipo(c, datos)
            ultimo = c.execute("SELECT max(CAST(substr(codigo, 4) AS INTEGER)) FROM equipos WHERE codigo LIKE 'EQ-%'").fetchone()[0]
            codigo = f"EQ-{(ultimo or 0) + 1:03d}"
            c.execute("INSERT INTO equipos (codigo, nombre, area_id, marca_modelo, usa_horometro, creado_por, creado_en, "
                      "modificado_por, modificado_en) VALUES (?,?,?,?,?,?,?,?,?)",
                      (codigo, *campos, usuario["nombre"], _ahora(), usuario["nombre"], _ahora()))
            e = _equipo(c, c.execute("SELECT last_insert_rowid()").fetchone()[0])
            e["instructivos_copiados"] = (_copiar_de_equipo(c, usuario, e, copiar_de, copiados)
                                          if copiar_de not in (None, "") else [])
            return e
    except Exception:
        for p in copiados:   # la base volvió atrás: los archivos copiados tampoco quedan
            p.unlink(missing_ok=True)
        raise


def copiar_instructivo_de_equipo(usuario: dict, equipo_id: int, *, desde) -> dict:
    """Para un equipo que todavía no tiene instructivo: le copia el de otro equipo parecido."""
    copiados: list[Path] = []
    try:
        with transaccion() as c:
            e = _equipo(c, _fila(c, "SELECT id, activo, codigo FROM equipos WHERE id=?", (equipo_id,), "ese equipo")["id"])
            if not e["activo"]:
                raise ErrorDeNegocio(f"{e['codigo']} está obsoleto: no se le copia instructivo.")
            e["instructivos_copiados"] = _copiar_de_equipo(c, usuario, e, desde, copiados)
            return e
    except Exception:
        for p in copiados:
            p.unlink(missing_ok=True)
        raise


def _copiar_de_equipo(c, usuario: dict, equipo: dict, desde, copiados: list[Path]) -> list[dict]:
    """Copia al `equipo` los instructivos vigentes del equipo `desde`."""
    origen = _fila(c, "SELECT id, codigo FROM equipos WHERE id=?", (desde,), "el equipo del que se copia")
    if origen["id"] == equipo["id"]:
        raise ErrorDeNegocio("No se copia el instructivo de un equipo a sí mismo.")
    its = [r[0] for r in c.execute("""SELECT x.instructivo_id FROM instructivo_equipos x JOIN instructivos i ON i.id = x.instructivo_id
                                      WHERE x.equipo_id=? AND i.vigente=1 ORDER BY i.codigo""", (origen["id"],))]
    if not its:
        raise ErrorDeNegocio(f"{origen['codigo']} no tiene un instructivo vigente para copiar.")
    salida = []
    for it_id in its:
        nuevo = _copiar_instructivo(c, usuario, it_id, equipo, copiados)
        salida.append({"id": nuevo, "codigo": c.execute("SELECT codigo FROM instructivos WHERE id=?", (nuevo,)).fetchone()[0],
                       "desde": c.execute("SELECT codigo FROM instructivos WHERE id=?", (it_id,)).fetchone()[0]})
    return salida


def _ficha_equipo(e: dict, ubicacion: str = "general") -> dict:
    """La tabla "Datos del equipo" con que arranca un instructivo (la misma que arma el frontend en instructivoPara)."""
    return {"tipo": "tabla", "ubicacion": ubicacion, "datos": {"titulo": "Datos del equipo", "encabezado": False, "filas": [
        ["Código", e["codigo"]], ["Equipo", e["nombre"]], ["Sector", e.get("sector") or "—"],
        ["Marca / modelo", e.get("marca_modelo") or "—"],
        ["Horómetro", "Sí: se anota la lectura en cada servicio" if e.get("usa_horometro") else "No"]]}}


def _copiar_instructivo(c, usuario: dict, origen_id: int, equipo: dict, copiados: list[Path]) -> int:
    """Copia la revisión vigente de un instructivo como instructivo nuevo de `equipo`: revisión 0, sin el historial del
    original, y a partir de ahí cada uno cambia por su lado. Las imágenes y archivos que usa se duplican en la carpeta
    del nuevo (anotados en `copiados`, para borrarlos si la transacción falla). El título y la ficha "Datos del equipo"
    pasan a ser los del equipo nuevo."""
    o = _contenido(c, origen_id)
    ultimo = c.execute("SELECT max(CAST(substr(codigo, 3) AS INTEGER)) FROM instructivos WHERE codigo LIKE 'IT%'").fetchone()[0]
    codigo = f"IT{(ultimo or 0) + 1:02d}"
    titulo = equipo["nombre"] + (" " + equipo["marca_modelo"] if equipo.get("marca_modelo") else "")
    descripcion = o["descripcion"].replace(o["titulo"], titulo) if o["titulo"] else o["descripcion"]
    c.execute("INSERT INTO instructivos (codigo, titulo, descripcion, seguridad, repuestos, fecha_revision, "
              "creado_por, creado_en, modificado_por, modificado_en) VALUES (?,?,?,?,?,?,?,?,?,?)",
              (codigo, titulo, descripcion, json.dumps(o["seguridad"], ensure_ascii=False),
               json.dumps(o["repuestos"], ensure_ascii=False), date.today().isoformat(),
               usuario["nombre"], _ahora(), usuario["nombre"], _ahora()))
    it_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    _escribir_secciones(c, it_id, codigo, [{"letra": s["letra"], "actividades": s["actividades"]} for s in o["secciones"]])
    # solo los adjuntos que usa la revisión vigente: lo subido de más o lo de revisiones viejas no hace falta
    usados = _ids_en_contenido({"bloques": o["bloques"], "archivos": o["archivos"]})
    mapa, carpeta_o, carpeta_n = {}, _carpeta_adjuntos(o["codigo"]), _carpeta_adjuntos(codigo)
    for a in c.execute(f"SELECT * FROM adjuntos WHERE id IN ({','.join('?' * len(usados))})", list(usados)).fetchall() if usados else []:
        fuente = carpeta_o / a["archivo"]
        if not fuente.is_file():   # el archivo se perdió: el nuevo sale sin él
            continue
        carpeta_n.mkdir(parents=True, exist_ok=True)
        archivo = f"{secrets.token_hex(16)}.{a['archivo'].rsplit('.', 1)[-1]}"
        shutil.copyfile(fuente, carpeta_n / archivo)
        copiados.append(carpeta_n / archivo)
        c.execute("INSERT INTO adjuntos (instructivo_id, archivo, nombre, tipo, tamanio, es_imagen, creado_por, creado_en) "
                  "VALUES (?,?,?,?,?,?,?,?)", (it_id, archivo, a["nombre"], a["tipo"], a["tamanio"], a["es_imagen"],
                                               usuario["nombre"], _ahora()))
        mapa[a["id"]] = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    # bloques con sus imágenes ya apuntando a las copias; el orden se renumera si alguno no pudo copiarse
    bloques, posicion = [], {}
    for i, b in enumerate(o["bloques"]):
        if b["tipo"] == "imagen":
            if b["datos"]["adjunto_id"] not in mapa:
                continue
            b = {**b, "datos": {**b["datos"], "adjunto_id": mapa[b["datos"]["adjunto_id"]]}}
        elif b["tipo"] == "tabla" and b["datos"].get("titulo") == "Datos del equipo":
            b = _ficha_equipo(equipo, b.get("ubicacion", "general"))
        posicion[i] = len(bloques)
        bloques.append(b)
    orden = [t if not t.startswith("bloque:") else f"bloque:{posicion[int(t[7:])]}"
             for t in o["orden"] if not t.startswith("bloque:") or int(t[7:]) in posicion]
    archivos = [mapa[a["id"]] for a in o["archivos"] if a["id"] in mapa]
    c.execute("UPDATE instructivos SET bloques=?, orden=?, archivos=? WHERE id=?",
              (json.dumps(bloques, ensure_ascii=False), json.dumps(orden), json.dumps(archivos), it_id))
    c.execute("INSERT INTO instructivo_equipos (instructivo_id, equipo_id) VALUES (?,?)", (it_id, equipo["id"]))
    return it_id


def separar_instructivos_compartidos() -> list[str]:
    """Migración: antes los equipos iguales compartían instructivo; ahora cada uno tiene el suyo. Un instructivo
    compartido queda con el primer equipo (el de menor código) y a cada uno de los otros se le hace una copia, con
    sus tareas del Plan pasadas a las secciones de la copia (misma letra). Después, un índice único impide volver a
    compartir. Devuelve qué se copió, para el registro del arranque."""
    hechos, copiados = [], []
    try:
        with transaccion() as c:
            sistema = {"nombre": "Sistema"}
            for r in c.execute("""SELECT instructivo_id FROM instructivo_equipos GROUP BY instructivo_id
                                  HAVING count(*) > 1""").fetchall():
                it_id = r[0]
                equipos = [x[0] for x in c.execute("""SELECT e.id FROM instructivo_equipos x JOIN equipos e ON e.id = x.equipo_id
                                                      WHERE x.instructivo_id=? ORDER BY e.codigo""", (it_id,))]
                secciones_o = {s["letra"]: s["id"] for s in c.execute("SELECT id, letra FROM secciones WHERE instructivo_id=?", (it_id,))}
                for eq_id in equipos[1:]:
                    e = _equipo(c, eq_id)
                    nuevo = _copiar_instructivo(c, sistema, it_id, e, copiados)
                    secciones_n = {s["letra"]: s["id"] for s in c.execute("SELECT id, letra FROM secciones WHERE instructivo_id=?", (nuevo,))}
                    for letra, sid in secciones_o.items():
                        c.execute("UPDATE tareas SET seccion_id=? WHERE equipo_id=? AND seccion_id=?", (secciones_n[letra], eq_id, sid))
                    c.execute("DELETE FROM instructivo_equipos WHERE instructivo_id=? AND equipo_id=?", (it_id, eq_id))
                    codigos = c.execute("SELECT (SELECT codigo FROM instructivos WHERE id=?), (SELECT codigo FROM instructivos WHERE id=?)",
                                        (it_id, nuevo)).fetchone()
                    hechos.append(f"{e['codigo']}: {codigos[0]} -> copia {codigos[1]}")
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_instructivo_equipos_instructivo ON instructivo_equipos(instructivo_id)")
    except Exception:
        for p in copiados:
            p.unlink(missing_ok=True)
        raise
    return hechos


def actualizar_equipo(usuario: dict, equipo_id: int, **datos) -> dict:
    with transaccion() as c:
        actual = _fila(c, "SELECT area_id FROM equipos WHERE id=?", (equipo_id,), "ese equipo")
        nombre, area, marca, horometro = _datos_equipo(c, datos, actual["area_id"])
        if not horometro and c.execute("SELECT 1 FROM tareas WHERE equipo_id=? AND frecuencia=? AND activa=1",
                                       (equipo_id, cal.POR_HORAS)).fetchone():
            raise ErrorDeNegocio("El equipo tiene tareas 'Por horas' en el Plan: no puede quedar sin horómetro.")
        c.execute("UPDATE equipos SET nombre=?, area_id=?, marca_modelo=?, usa_horometro=?, modificado_por=?, modificado_en=? "
                  "WHERE id=?", (nombre, area, marca, horometro, usuario["nombre"], _ahora(), equipo_id))
        return _equipo(c, equipo_id)


def marcar_equipo_obsoleto(usuario: dict, equipo_id: int, *, motivo) -> dict:
    """Lo normal para un equipo que ya no está: sale de las listas y su historial queda completo y consultable.
    Sus tareas del Plan se dan de baja en el mismo paso: no se programa mantenimiento a una máquina que no está.
    Devuelve el equipo y los códigos de las tareas que se dieron de baja."""
    motivo = _texto(motivo, "el motivo")
    with transaccion() as c:
        e = _fila(c, "SELECT codigo, activo FROM equipos WHERE id=?", (equipo_id,), "ese equipo")
        if not e["activo"]:
            raise ErrorDeNegocio(f"{e['codigo']} ya está obsoleto.")
        tareas = [f"{e['codigo']}-{r['numero']}" for r in c.execute(
            "SELECT numero FROM tareas WHERE equipo_id=? AND activa=1 ORDER BY numero", (equipo_id,))]
        c.execute("UPDATE tareas SET activa=0, modificado_por=?, modificado_en=? WHERE equipo_id=? AND activa=1",
                  (usuario["nombre"], _ahora(), equipo_id))
        c.execute("UPDATE equipos SET activo=0, fecha_baja=?, motivo_baja=?, modificado_por=?, modificado_en=? WHERE id=?",
                  (date.today().isoformat(), motivo, usuario["nombre"], _ahora(), equipo_id))
        return {"equipo": dict(c.execute("SELECT * FROM equipos WHERE id=?", (equipo_id,)).fetchone()), "tareas_dadas_de_baja": tareas}


def reactivar_equipo(usuario: dict, equipo_id: int) -> dict:
    """Vuelve a las listas. Sus tareas no se reactivan solas: se decide en el Plan cuáles siguen."""
    with transaccion() as c:
        _fila(c, "SELECT 1 FROM equipos WHERE id=?", (equipo_id,), "ese equipo")
        c.execute("UPDATE equipos SET activo=1, fecha_baja=NULL, motivo_baja=NULL, modificado_por=?, modificado_en=? WHERE id=?",
                  (usuario["nombre"], _ahora(), equipo_id))
        return dict(c.execute("SELECT * FROM equipos WHERE id=?", (equipo_id,)).fetchone())


def eliminar_equipo(usuario: dict, equipo_id: int) -> None:
    """Solo para uno creado por error: si algo lo referencia (Plan, lecturas, correctivos), se marca obsoleto."""
    with transaccion() as c:
        e = _fila(c, "SELECT codigo FROM equipos WHERE id=?", (equipo_id,), "ese equipo")
        usos = [que for que, sql in (("tareas en el Plan", "SELECT 1 FROM tareas WHERE equipo_id=?"),
                                     ("lecturas de horómetro", "SELECT 1 FROM lecturas_horometro WHERE equipo_id=?"),
                                     ("correctivos", "SELECT 1 FROM correctivos WHERE equipo_id=?"))
                if c.execute(sql, (equipo_id,)).fetchone()]
        if usos:
            raise ErrorDeNegocio(f"{e['codigo']} tiene {', '.join(usos)}: no se elimina, se marca obsoleto.")
        # su instructivo se va con él si era solo suyo (nació con el equipo cargado por error)
        propios = [r[0] for r in c.execute("""SELECT instructivo_id FROM instructivo_equipos x WHERE equipo_id=?
                                              AND NOT EXISTS (SELECT 1 FROM instructivo_equipos y
                                                              WHERE y.instructivo_id = x.instructivo_id AND y.equipo_id <> ?)""",
                                           (equipo_id, equipo_id))]
        c.execute("DELETE FROM instructivo_equipos WHERE equipo_id=?", (equipo_id,))
        c.execute("DELETE FROM equipos WHERE id=?", (equipo_id,))
    for it_id in propios:   # el que se usó en algún Plan no se borra: queda sin equipo, a la vista en la pestaña
        try:
            eliminar_instructivo(usuario, it_id)
        except ErrorDeNegocio:
            pass


# ── áreas ───────────────────────────────────────────────────────────────────

def listar_areas() -> list[dict]:
    with transaccion() as c:
        return [dict(r) for r in c.execute("SELECT id, nombre, activo FROM areas ORDER BY activo DESC, nombre")]


def _nombre_area(c, nombre, excepto: int | None = None) -> str:
    nombre = _texto(nombre, "el nombre del área")
    if c.execute("SELECT 1 FROM areas WHERE nombre=? AND id IS NOT ?", (nombre, excepto)).fetchone():   # NOCASE
        raise ErrorDeNegocio(f"Ya existe el área '{nombre}'.")
    return nombre


def crear_area(usuario: dict, *, nombre) -> dict:
    with transaccion() as c:
        c.execute("INSERT INTO areas (nombre) VALUES (?)", (_nombre_area(c, nombre),))
        return dict(c.execute("SELECT id, nombre, activo FROM areas WHERE id=last_insert_rowid()").fetchone())


def renombrar_area(usuario: dict, area_id: int, *, nombre) -> dict:
    """Los equipos apuntan al área por id: renombrarla los corrige a todos de una vez."""
    with transaccion() as c:
        _fila(c, "SELECT 1 FROM areas WHERE id=?", (area_id,), "esa área")
        c.execute("UPDATE areas SET nombre=? WHERE id=?", (_nombre_area(c, nombre, excepto=area_id), area_id))
        return dict(c.execute("SELECT id, nombre, activo FROM areas WHERE id=?", (area_id,)).fetchone())


def cambiar_alta_area(usuario: dict, area_id: int, *, activo: bool) -> dict:
    """Dar de baja la saca de la lista para elegir; los equipos que ya la tienen la conservan."""
    with transaccion() as c:
        _fila(c, "SELECT 1 FROM areas WHERE id=?", (area_id,), "esa área")
        c.execute("UPDATE areas SET activo=? WHERE id=?", (int(activo), area_id))
        return dict(c.execute("SELECT id, nombre, activo FROM areas WHERE id=?", (area_id,)).fetchone())


def eliminar_area(usuario: dict, area_id: int) -> None:
    """Solo para una creada por error: si algún equipo la tiene (aunque sea obsoleto), se da de baja."""
    with transaccion() as c:
        a = _fila(c, "SELECT nombre FROM areas WHERE id=?", (area_id,), "esa área")
        if c.execute("SELECT 1 FROM equipos WHERE area_id=?", (area_id,)).fetchone():
            raise ErrorDeNegocio(f"'{a['nombre']}' tiene equipos: no se elimina, se da de baja.")
        c.execute("DELETE FROM areas WHERE id=?", (area_id,))


def seguimiento_areas(anio: int) -> list[dict]:
    """Por área, en el año: cuántos equipos tiene, preventivos hechos, correctivos y horas de parada."""
    with transaccion() as c:
        filas = c.execute("""
            SELECT a.id, a.nombre, a.activo,
                   (SELECT count(*) FROM equipos e WHERE e.area_id = a.id AND e.activo = 1) AS equipos,
                   (SELECT count(*) FROM registros r JOIN tareas t ON t.id = r.tarea_id JOIN equipos e ON e.id = t.equipo_id
                     WHERE e.area_id = a.id AND substr(r.fecha, 1, 4) = :anio
                       AND r.resultado IN ('Realizado', 'Con observaciones')) AS preventivos,
                   (SELECT count(*) FROM correctivos co JOIN equipos e ON e.id = co.equipo_id
                     WHERE e.area_id = a.id AND substr(co.fecha, 1, 4) = :anio) AS correctivos,
                   (SELECT coalesce(sum(co.horas_parada), 0) FROM correctivos co JOIN equipos e ON e.id = co.equipo_id
                     WHERE e.area_id = a.id AND substr(co.fecha, 1, 4) = :anio) AS horas_parada,
                   (SELECT count(*) FROM equipos e WHERE e.area_id = a.id) AS equipos_total
            FROM areas a ORDER BY a.activo DESC, a.nombre""", {"anio": str(anio)})
        return [dict(r) for r in filas]


# ── instructivos ────────────────────────────────────────────────────────────

def listar_instructivos() -> list[dict]:
    with transaccion() as c:
        filas = c.execute("""
            SELECT i.id, i.codigo, i.titulo, i.revision, i.fecha_revision, i.vigente,
                   (SELECT count(*) FROM secciones s JOIN tareas t ON t.seccion_id = s.id
                     WHERE s.instructivo_id = i.id AND t.activa = 1) AS tareas
            FROM instructivos i ORDER BY i.codigo""")
        return [dict(r) for r in filas]


def _contenido(c, it_id: int) -> dict:
    it = _fila(c, "SELECT * FROM instructivos WHERE id=?", (it_id,), "ese instructivo")
    secciones = []
    for s in c.execute("SELECT id, letra FROM secciones WHERE instructivo_id=? ORDER BY letra", (it_id,)):
        acts = [{"texto": a["texto"], "es_grupo": bool(a["es_grupo"]), "detalle": a["detalle"]}
                for a in c.execute("SELECT texto, es_grupo, detalle FROM actividades WHERE seccion_id=? ORDER BY orden", (s["id"],))]
        tareas = [dict(t) for t in c.execute("""
            SELECT t.id, e.codigo || '-' || t.numero AS codigo, e.nombre AS equipo, t.frecuencia, t.cada_horas
            FROM tareas t JOIN equipos e ON e.id = t.equipo_id WHERE t.seccion_id=? AND t.activa=1 ORDER BY e.codigo""",
                                                (s["id"],))]
        secciones.append({"letra": s["letra"], "codigo": f"{it['codigo']}-{s['letra']}", "actividades": acts, "tareas": tareas})
    d = dict(it)
    d["seguridad"] = json.loads(it["seguridad"])
    d["repuestos"] = _repuestos(json.loads(it["repuestos"]))
    d["secciones"] = secciones
    d["bloques"] = json.loads(it["bloques"])
    d["orden"] = _completar_orden(json.loads(it["orden"]), [s["letra"] for s in secciones], d["bloques"])
    d["archivos"] = _adjuntos_por_id(c, json.loads(it["archivos"]))
    return d


def obtener_instructivo(it_id: int) -> dict:
    with transaccion() as c:
        d = _contenido(c, it_id)
        usados = _adjuntos_referenciados(c, it_id)
        d["adjuntos"] = [{**a, "en_uso": a["id"] in usados} for a in _adjuntos_por_id(c, None, it_id)]
        d["versiones"] = [dict(v) for v in c.execute(
            "SELECT revision, motivo, creado_por, creado_en FROM instructivo_versiones WHERE instructivo_id=? ORDER BY revision DESC",
            (it_id,))]
        return d


def _lineas(valor, campo: str) -> list[str]:
    if not isinstance(valor, list):
        raise ErrorDeNegocio(f"{campo.capitalize()}: se esperaba una lista.")
    return [t for t in (str(x).strip() for x in valor) if t]


def _repuestos(valor) -> list[dict]:
    """Cada repuesto o insumo: nombre y cantidad mínima (opcional). Acepta el formato viejo, una lista de textos."""
    if not isinstance(valor, list):
        raise ErrorDeNegocio("Repuestos: se esperaba una lista.")
    limpios = []
    for r in valor:
        nombre = _corto(r.get("nombre") if isinstance(r, dict) else r, 300)
        if nombre:
            cantidad = _numero(r.get("cantidad") if isinstance(r, dict) else None,
                               f"la cantidad mínima de '{nombre[:40]}'", minimo=0, maximo=1e6)
            limpios.append({"nombre": nombre, "cantidad": cantidad})
    return limpios

def _validar_contenido(datos: dict) -> dict:
    secciones, letras = [], set()
    for s in datos.get("secciones") or []:
        letra = str(s.get("letra", "")).strip().upper()
        if len(letra) != 1 or not "A" <= letra <= "Z":
            raise ErrorDeNegocio(f"Sección '{letra}': la letra tiene que ser de la A a la Z.")
        if letra in letras:
            raise ErrorDeNegocio(f"La sección {letra} está repetida.")
        letras.add(letra)
        acts = [{"texto": str(a.get("texto", "")).strip()[:500], "es_grupo": bool(a.get("es_grupo")),
                 "detalle": "" if a.get("es_grupo") else str(a.get("detalle") or "").strip()[:2000]}
                for a in s.get("actividades") or [] if str(a.get("texto", "")).strip()]
        if not any(not a["es_grupo"] for a in acts):
            raise ErrorDeNegocio(f"La sección {letra} no tiene ninguna actividad.")
        secciones.append({"letra": letra, "actividades": acts})
    if not secciones:
        raise ErrorDeNegocio("El instructivo necesita al menos una sección con actividades.")
    secciones.sort(key=lambda s: s["letra"])
    bloques = _validar_bloques(datos.get("bloques") or [], letras)
    return {"titulo": _texto(datos.get("titulo"), "el título"),
            "descripcion": _texto(datos.get("descripcion"), "la descripción", False),
            "seguridad": _lineas(datos.get("seguridad") or [], "seguridad"),
            "repuestos": _repuestos(datos.get("repuestos") or []),
            "secciones": secciones,
            "bloques": bloques,
            "orden": _completar_orden(datos.get("orden"), [s["letra"] for s in secciones], bloques),
            "archivos": _ids_adjuntos(datos.get("archivos") or [], "archivos adjuntos")}


def _completar_orden(orden, letras: list[str], bloques: list[dict]) -> list[str]:
    """Orden del documento debajo de título, descripción y seguridad (que van siempre arriba): cada sección
    ("seccion:A"), cada bloque por su posición en la lista ("bloque:0") y los repuestos, una vez cada uno.
    Se descarta lo que no existe o se repite, y lo que falta va donde iba antes de que el orden fuera libre
    (bloques generales, cada sección seguida de los suyos, repuestos): así se leen igual los instructivos viejos."""
    validos = {f"seccion:{l}" for l in letras} | {f"bloque:{i}" for i in range(len(bloques))} | {"repuestos"}
    resultado = []
    for t in orden if isinstance(orden, list) else []:
        if isinstance(t, str) and t in validos and t not in resultado:
            resultado.append(t)
    previo = [f"bloque:{i}" for i, b in enumerate(bloques) if b.get("ubicacion", "general") not in letras]
    for letra in letras:
        previo += [f"seccion:{letra}"] + [f"bloque:{i}" for i, b in enumerate(bloques) if b.get("ubicacion") == letra]
    return resultado + [t for t in previo + ["repuestos"] if t not in resultado]


# ── bloques de contenido (traídos de Procedimientos de GNC API) ──
# texto      título opcional + párrafo
# nota       aviso destacado: info | precaucion | peligro
# tabla      filas de celdas; la primera puede ser encabezado (sirve también de ficha técnica: Campo | Valor)
# imagen     un adjunto de imagen, con epígrafe y ancho
# grafico    barras | linea | torta a partir de pares etiqueta/valor (se dibuja como SVG: se imprime nítido)
# Cada bloque va en "general" (debajo de la descripción) o en una sección (debajo de sus actividades).
TIPOS_BLOQUE = ("texto", "nota", "tabla", "imagen", "grafico")
_MAX_BLOQUES = 80
_MAX_BYTES_BLOQUES = 300_000


def _corto(valor, maximo: int) -> str:
    return str(valor or "").strip()[:maximo]


def _ids_adjuntos(valor, campo: str) -> list[int]:
    if not isinstance(valor, list):
        raise ErrorDeNegocio(f"{campo.capitalize()}: se esperaba una lista.")
    ids = []
    for x in valor:
        n = _numero(x, campo, entero=True, minimo=1, maximo=10**9)
        if n is not None and n not in ids:
            ids.append(n)
    return ids


def _validar_bloques(bloques, letras: set[str]) -> list[dict]:
    """Forma de cada bloque, sin mirar la base (que los adjuntos existan lo valida _exigir_adjuntos)."""
    if not isinstance(bloques, list) or len(bloques) > _MAX_BLOQUES:
        raise ErrorDeNegocio(f"Contenido adicional: hasta {_MAX_BLOQUES} bloques.")
    limpios = []
    for n, b in enumerate(bloques, 1):
        if not isinstance(b, dict) or b.get("tipo") not in TIPOS_BLOQUE:
            raise ErrorDeNegocio(f"Bloque {n}: tipo desconocido.")
        tipo, d = b["tipo"], b.get("datos") or {}
        ubicacion = str(b.get("ubicacion") or "general").strip().upper()
        if ubicacion != "GENERAL" and ubicacion not in letras:
            raise ErrorDeNegocio(f"Bloque {n}: la sección {ubicacion} no existe en el instructivo.")
        ubicacion = "general" if ubicacion == "GENERAL" else ubicacion
        if tipo == "texto":
            datos = {"titulo": _corto(d.get("titulo"), 200), "texto": _corto(d.get("texto"), 8000)}
            if not datos["texto"] and not datos["titulo"]:
                raise ErrorDeNegocio(f"Bloque {n} (texto): está vacío.")
        elif tipo == "nota":
            datos = {"nivel": d.get("nivel") if d.get("nivel") in ("info", "precaucion", "peligro") else "info",
                     "texto": _corto(d.get("texto"), 2000)}
            if not datos["texto"]:
                raise ErrorDeNegocio(f"Bloque {n} (nota): falta el texto.")
        elif tipo == "tabla":
            filas = d.get("filas") or []
            if not isinstance(filas, list) or not filas or len(filas) > 40:
                raise ErrorDeNegocio(f"Bloque {n} (tabla): entre 1 y 40 filas.")
            filas = [[_corto(celda, 300) for celda in (f if isinstance(f, list) else [f])][:8] for f in filas]
            ancho = max(len(f) for f in filas)
            datos = {"titulo": _corto(d.get("titulo"), 200), "encabezado": bool(d.get("encabezado")),
                     "filas": [f + [""] * (ancho - len(f)) for f in filas]}
        elif tipo == "imagen":
            adj = _numero(d.get("adjunto_id"), "la imagen", entero=True, minimo=1, maximo=10**9)
            if adj is None:
                raise ErrorDeNegocio(f"Bloque {n} (imagen): falta elegir la imagen.")
            datos = {"adjunto_id": adj, "epigrafe": _corto(d.get("epigrafe"), 300),
                     "ancho": d.get("ancho") if d.get("ancho") in ("chico", "mediano", "completo") else "mediano"}
        else:  # grafico
            filas = d.get("filas") or []
            if not isinstance(filas, list) or not 1 <= len(filas) <= 30:
                raise ErrorDeNegocio(f"Bloque {n} (gráfico): entre 1 y 30 valores.")
            pares = []
            for f in filas:
                if not isinstance(f, (list, tuple)) or len(f) != 2:
                    raise ErrorDeNegocio(f"Bloque {n} (gráfico): cada valor es un par etiqueta y número.")
                valor = _numero(f[1], f"el valor de '{_corto(f[0], 40)}' del gráfico", minimo=-1e9, maximo=1e9)
                if valor is None:
                    raise ErrorDeNegocio(f"Bloque {n} (gráfico): falta el valor de '{_corto(f[0], 40)}'.")
                pares.append([_corto(f[0], 60), valor])
            if d.get("forma", "barras") == "torta" and any(v < 0 for _, v in pares):
                raise ErrorDeNegocio(f"Bloque {n} (gráfico de torta): los valores no pueden ser negativos.")
            datos = {"forma": d.get("forma") if d.get("forma") in ("barras", "linea", "torta") else "barras",
                     "titulo": _corto(d.get("titulo"), 200), "unidad": _corto(d.get("unidad"), 20), "filas": pares}
        limpios.append({"tipo": tipo, "ubicacion": ubicacion, "datos": datos})
    if len(json.dumps(limpios, ensure_ascii=False).encode()) > _MAX_BYTES_BLOQUES:
        raise ErrorDeNegocio("El contenido adicional es demasiado largo.")
    return limpios


def _exigir_adjuntos(c, it_id: int | None, cont: dict) -> None:
    """Las imágenes y archivos que nombra el contenido tienen que ser adjuntos de ESTE instructivo."""
    imagenes = {b["datos"]["adjunto_id"] for b in cont["bloques"] if b["tipo"] == "imagen"}
    pedidos = imagenes | set(cont["archivos"])
    if not pedidos:
        return
    if it_id is None:
        raise ErrorDeNegocio("Primero hay que crear el instructivo; después, con Modificar, se le agregan imágenes y archivos.")
    propios = {r["id"]: r["es_imagen"] for r in c.execute("SELECT id, es_imagen FROM adjuntos WHERE instructivo_id=?", (it_id,))}
    if pedidos - set(propios):
        raise ErrorDeNegocio("Alguna imagen o archivo no es de este instructivo.")
    if any(not propios[i] for i in imagenes):
        raise ErrorDeNegocio("Un bloque de imagen tiene que usar una imagen (jpg, png, gif o webp), no otro tipo de archivo.")


def _adjuntos_por_id(c, ids: list[int] | None, it_id: int | None = None) -> list[dict]:
    """Datos para mostrar de una lista de adjuntos, en ese orden (o todos los de un instructivo)."""
    cols = "id, nombre, tipo, tamanio, es_imagen, creado_por, creado_en"
    if ids is None:
        return [dict(r) for r in c.execute(f"SELECT {cols} FROM adjuntos WHERE instructivo_id=? ORDER BY id", (it_id,))]
    filas = {r["id"]: dict(r) for r in c.execute(
        f"SELECT {cols} FROM adjuntos WHERE id IN ({','.join('?' * len(ids))})", ids)} if ids else {}
    return [filas[i] for i in ids if i in filas]


def _ids_en_contenido(cont: dict) -> set[int]:
    return ({b["datos"]["adjunto_id"] for b in cont.get("bloques", []) if b.get("tipo") == "imagen"}
            | {a if isinstance(a, int) else a["id"] for a in cont.get("archivos", [])})


def _adjuntos_referenciados(c, it_id: int) -> set[int]:
    """Lo que usa la revisión actual o cualquiera de las viejas."""
    it = c.execute("SELECT bloques, archivos FROM instructivos WHERE id=?", (it_id,)).fetchone()
    usados = _ids_en_contenido({"bloques": json.loads(it["bloques"]), "archivos": json.loads(it["archivos"])})
    for v in c.execute("SELECT contenido FROM instructivo_versiones WHERE instructivo_id=?", (it_id,)):
        usados |= _ids_en_contenido(json.loads(v["contenido"]))
    return usados


def _escribir_secciones(c, it_id: int, codigo: str, secciones: list[dict]) -> None:
    """Sincroniza por letra: la sección que sigue conserva su id (y con él las tareas del Plan que la usan)."""
    existentes = {r["letra"]: r["id"] for r in c.execute("SELECT id, letra FROM secciones WHERE instructivo_id=?", (it_id,))}
    nuevas = {s["letra"] for s in secciones}
    for letra, sid in existentes.items():
        if letra not in nuevas:
            if c.execute("SELECT 1 FROM tareas WHERE seccion_id=?", (sid,)).fetchone():
                raise ErrorDeNegocio(f"La sección {codigo}-{letra} está en el Plan: no se puede quitar. "
                                     "Primero hay que sacar sus tareas del Plan.")
            c.execute("DELETE FROM secciones WHERE id=?", (sid,))
    for s in secciones:
        sid = existentes.get(s["letra"])
        if sid is None:
            c.execute("INSERT INTO secciones (instructivo_id, letra) VALUES (?,?)", (it_id, s["letra"]))
            sid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        c.execute("DELETE FROM actividades WHERE seccion_id=?", (sid,))
        c.executemany("INSERT INTO actividades (seccion_id, orden, texto, es_grupo, detalle) VALUES (?,?,?,?,?)",
                      [(sid, i, a["texto"], int(a["es_grupo"]), a["detalle"]) for i, a in enumerate(s["actividades"], 1)])


def crear_instructivo(usuario: dict, *, equipo_id=None, **datos) -> dict:
    """Un instructivo nace con su equipo (equipo_id): queda vinculado en la misma transacción."""
    cont = _validar_contenido(datos)
    with transaccion() as c:
        if equipo_id not in (None, ""):
            eq = _fila(c, "SELECT id, codigo, activo FROM equipos WHERE id=?", (equipo_id,), "ese equipo")
            if not eq["activo"]:
                raise ErrorDeNegocio(f"{eq['codigo']} está obsoleto: no se le crea instructivo.")
        _exigir_adjuntos(c, None, cont)
        ultimo = c.execute("SELECT max(CAST(substr(codigo, 3) AS INTEGER)) FROM instructivos WHERE codigo LIKE 'IT%'").fetchone()[0]
        codigo = f"IT{(ultimo or 0) + 1:02d}"
        c.execute("INSERT INTO instructivos (codigo, titulo, descripcion, seguridad, repuestos, bloques, orden, fecha_revision, "
                  "creado_por, creado_en, modificado_por, modificado_en) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (codigo, cont["titulo"], cont["descripcion"], json.dumps(cont["seguridad"], ensure_ascii=False),
                   json.dumps(cont["repuestos"], ensure_ascii=False), json.dumps(cont["bloques"], ensure_ascii=False),
                   json.dumps(cont["orden"]), date.today().isoformat(),
                   usuario["nombre"], _ahora(), usuario["nombre"], _ahora()))
        it_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        _escribir_secciones(c, it_id, codigo, cont["secciones"])
        if equipo_id not in (None, ""):
            c.execute("INSERT INTO instructivo_equipos (instructivo_id, equipo_id) VALUES (?,?)", (it_id, int(equipo_id)))
        return _contenido(c, it_id)


def revisar_instructivo(usuario: dict, it_id: int, *, motivo, **datos) -> dict:
    """Todo cambio de contenido es una revisión nueva: se archiva lo anterior y la revisión sube 1."""
    motivo = _texto(motivo, "el motivo del cambio (qué se modificó)")
    cont = _validar_contenido(datos)
    with transaccion() as c:
        anterior = _contenido(c, it_id)
        if not anterior["vigente"]:
            raise ErrorDeNegocio("El instructivo está obsoleto: no se modifica.")
        _exigir_adjuntos(c, it_id, cont)
        foto = {k: anterior[k] for k in ("titulo", "descripcion", "seguridad", "repuestos", "fecha_revision", "bloques", "orden")}
        foto["archivos"] = [a["id"] for a in anterior["archivos"]]
        foto["secciones"] = [{"letra": s["letra"], "actividades": s["actividades"]} for s in anterior["secciones"]]
        c.execute("INSERT INTO instructivo_versiones (instructivo_id, revision, contenido, motivo, creado_por, creado_en) "
                  "VALUES (?,?,?,?,?,?)", (it_id, anterior["revision"], json.dumps(foto, ensure_ascii=False),
                                           motivo, usuario["nombre"], _ahora()))
        c.execute("UPDATE instructivos SET titulo=?, descripcion=?, seguridad=?, repuestos=?, bloques=?, archivos=?, orden=?, "
                  "revision=revision+1, fecha_revision=?, modificado_por=?, modificado_en=? WHERE id=?",
                  (cont["titulo"], cont["descripcion"], json.dumps(cont["seguridad"], ensure_ascii=False),
                   json.dumps(cont["repuestos"], ensure_ascii=False), json.dumps(cont["bloques"], ensure_ascii=False),
                   json.dumps(cont["archivos"]), json.dumps(cont["orden"]), date.today().isoformat(), usuario["nombre"], _ahora(), it_id))
        _escribir_secciones(c, it_id, anterior["codigo"], cont["secciones"])
        return _contenido(c, it_id)


def version_instructivo(it_id: int, revision: int) -> dict:
    with transaccion() as c:
        v = _fila(c, "SELECT contenido, motivo, creado_por, creado_en FROM instructivo_versiones "
                     "WHERE instructivo_id=? AND revision=?", (it_id, revision), "esa revisión")
        foto = {"bloques": [], "archivos": [], **json.loads(v["contenido"])}   # las revisiones viejas no tenían bloques
        foto["archivos"] = _adjuntos_por_id(c, foto["archivos"])
        foto["repuestos"] = _repuestos(foto.get("repuestos") or [])
        foto["orden"] = _completar_orden(foto.get("orden"), [s["letra"] for s in foto["secciones"]], foto["bloques"])
        return {**foto, "revision": revision, "motivo": v["motivo"],
                "reemplazada_por": v["creado_por"], "reemplazada_en": v["creado_en"]}


def marcar_obsoleto(usuario: dict, it_id: int, *, motivo) -> dict:
    """Lo normal para un instructivo que ya no se usa: queda guardado y consultable, pero sale del Plan."""
    motivo = _texto(motivo, "el motivo")
    with transaccion() as c:
        it = _fila(c, "SELECT codigo, vigente FROM instructivos WHERE id=?", (it_id,), "ese instructivo")
        if not it["vigente"]:
            raise ErrorDeNegocio(f"{it['codigo']} ya está obsoleto.")
        tareas = c.execute("""SELECT e.codigo || '-' || t.numero FROM tareas t JOIN secciones s ON s.id = t.seccion_id
                              JOIN equipos e ON e.id = t.equipo_id WHERE s.instructivo_id=? AND t.activa=1""", (it_id,)).fetchall()
        if tareas:
            raise ErrorDeNegocio(f"{it['codigo']} todavía está en el Plan ({', '.join(t[0] for t in tareas)}). "
                                 "Primero hay que dar de baja esas tareas.")
        c.execute("UPDATE instructivos SET vigente=0, fecha_baja=?, motivo_baja=?, modificado_por=?, modificado_en=? WHERE id=?",
                  (date.today().isoformat(), motivo, usuario["nombre"], _ahora(), it_id))
        return _contenido(c, it_id)


def eliminar_instructivo(usuario: dict, it_id: int) -> None:
    """Solo para uno creado por error: si alguna vez se programó, se marca obsoleto en vez de borrarlo."""
    with transaccion() as c:
        it = _fila(c, "SELECT codigo FROM instructivos WHERE id=?", (it_id,), "ese instructivo")
        if c.execute("SELECT 1 FROM tareas t JOIN secciones s ON s.id = t.seccion_id WHERE s.instructivo_id=?", (it_id,)).fetchone():
            raise ErrorDeNegocio(f"{it['codigo']} se usó en el Plan: no se elimina, se marca obsoleto.")
        archivos = [r["archivo"] for r in c.execute("SELECT archivo FROM adjuntos WHERE instructivo_id=?", (it_id,))]
        c.execute("DELETE FROM adjuntos WHERE instructivo_id=?", (it_id,))
        c.execute("DELETE FROM instructivo_versiones WHERE instructivo_id=?", (it_id,))
        c.execute("DELETE FROM instructivo_equipos WHERE instructivo_id=?", (it_id,))
        c.execute("DELETE FROM secciones WHERE instructivo_id=?", (it_id,))
        c.execute("DELETE FROM instructivos WHERE id=?", (it_id,))
    carpeta = _carpeta_adjuntos(it["codigo"])
    for a in archivos:   # después del commit: si la base falló, los archivos siguen
        (carpeta / a).unlink(missing_ok=True)
    try:
        carpeta.rmdir()
    except OSError:
        pass


# ── adjuntos (imágenes y archivos de un instructivo) ──
MAX_ADJUNTO = 20 * 1024 * 1024
# extensión -> (MIME, es imagen, cómo empieza el archivo). La firma evita que un ejecutable entre renombrado.
_TIPOS_ADJUNTO = {
    "jpg": ("image/jpeg", True, (b"\xff\xd8\xff",)), "jpeg": ("image/jpeg", True, (b"\xff\xd8\xff",)),
    "png": ("image/png", True, (b"\x89PNG\r\n\x1a\n",)), "gif": ("image/gif", True, (b"GIF87a", b"GIF89a")),
    "webp": ("image/webp", True, (b"RIFF",)),
    "pdf": ("application/pdf", False, (b"%PDF",)),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", False, (b"PK\x03\x04",)),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", False, (b"PK\x03\x04",)),
    "zip": ("application/zip", False, (b"PK\x03\x04",)),
    "doc": ("application/msword", False, (b"\xd0\xcf\x11\xe0",)), "xls": ("application/vnd.ms-excel", False, (b"\xd0\xcf\x11\xe0",)),
    "dwg": ("application/acad", False, (b"AC10",)),
    "dxf": ("application/dxf", False, None), "txt": ("text/plain", False, None), "csv": ("text/csv", False, None),
}
TIPOS_PERMITIDOS = ", ".join(sorted(_TIPOS_ADJUNTO))


def _carpeta_adjuntos(codigo: str) -> Path:
    # el código lo genera el sistema (IT01...), pero igual se limita a letras y números
    return db.DB_PATH.parent / "adjuntos" / re.sub(r"[^A-Za-z0-9]", "", codigo)


def _nombre_para_mostrar(nombre: str) -> str:
    """Solo el nombre (sin carpetas), sin caracteres de control. Nunca se usa como ruta."""
    base = re.split(r"[\\/]", str(nombre or ""))[-1]
    base = "".join(ch for ch in base if ch.isprintable()).strip().strip(".")
    return base[:150] or "archivo"


def subir_adjunto(usuario: dict, it_id: int, *, nombre, datos: bytes) -> dict:
    nombre = _nombre_para_mostrar(nombre)
    ext = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if ext not in _TIPOS_ADJUNTO:
        raise ErrorDeNegocio(f"Tipo de archivo no admitido. Se aceptan: {TIPOS_PERMITIDOS}.")
    if not datos:
        raise ErrorDeNegocio("El archivo está vacío.")
    if len(datos) > MAX_ADJUNTO:
        raise ErrorDeNegocio(f"El archivo supera el máximo de {MAX_ADJUNTO // (1024 * 1024)} MB.")
    mime, es_imagen, firmas = _TIPOS_ADJUNTO[ext]
    if firmas and not datos.startswith(firmas):
        raise ErrorDeNegocio(f"El archivo no es un .{ext} válido (su contenido no coincide con la extensión).")
    if ext == "webp" and datos[8:12] != b"WEBP":
        raise ErrorDeNegocio("El archivo no es un .webp válido.")
    if firmas is None and b"\x00" in datos[:4096]:
        raise ErrorDeNegocio(f"El archivo no es un .{ext} de texto válido.")
    with transaccion() as c:
        it = _fila(c, "SELECT codigo, vigente FROM instructivos WHERE id=?", (it_id,), "ese instructivo")
        if not it["vigente"]:
            raise ErrorDeNegocio("El instructivo está obsoleto: no se le agregan archivos.")
        carpeta = _carpeta_adjuntos(it["codigo"])
        carpeta.mkdir(parents=True, exist_ok=True)
        archivo = f"{secrets.token_hex(16)}.{ext}"
        destino = carpeta / archivo
        destino.write_bytes(datos)
        try:
            c.execute("INSERT INTO adjuntos (instructivo_id, archivo, nombre, tipo, tamanio, es_imagen, creado_por, creado_en) "
                      "VALUES (?,?,?,?,?,?,?,?)", (it_id, archivo, nombre, mime, len(datos), int(es_imagen), usuario["nombre"], _ahora()))
            aid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        except Exception:
            destino.unlink(missing_ok=True)
            raise
        return _adjuntos_por_id(c, [aid])[0]


def archivo_adjunto(adjunto_id: int) -> dict:
    """Dónde está el archivo y cómo entregarlo. Para quien tenga sesión (lo controla la ruta)."""
    with transaccion() as c:
        a = _fila(c, "SELECT a.*, i.codigo FROM adjuntos a JOIN instructivos i ON i.id = a.instructivo_id WHERE a.id=?",
                  (adjunto_id,), "ese archivo")
    ruta = _carpeta_adjuntos(a["codigo"]) / a["archivo"]
    if not ruta.is_file():
        raise NoEncontrado("El archivo no está en la carpeta de adjuntos.")
    return {"ruta": ruta, "nombre": a["nombre"], "tipo": a["tipo"], "es_imagen": bool(a["es_imagen"])}


def eliminar_adjunto(usuario: dict, adjunto_id: int) -> None:
    """Solo uno subido de más: si lo usa la revisión actual o una vieja, se queda (la revisión vieja lo muestra)."""
    with transaccion() as c:
        a = _fila(c, "SELECT a.*, i.codigo FROM adjuntos a JOIN instructivos i ON i.id = a.instructivo_id WHERE a.id=?",
                  (adjunto_id,), "ese archivo")
        if adjunto_id in _adjuntos_referenciados(c, a["instructivo_id"]):
            raise ErrorDeNegocio(f"'{a['nombre']}' está en el instructivo o en una revisión anterior: no se borra "
                                 "(las revisiones viejas tienen que seguir mostrándolo).")
        c.execute("DELETE FROM adjuntos WHERE id=?", (adjunto_id,))
    (_carpeta_adjuntos(a["codigo"]) / a["archivo"]).unlink(missing_ok=True)


# ── Plan (tareas) ───────────────────────────────────────────────────────────

_SQL_TAREAS = """
    SELECT t.*, e.codigo || '-' || t.numero AS codigo, e.codigo AS equipo_codigo, e.nombre AS equipo,
           e.usa_horometro, i.codigo || '-' || s.letra AS seccion, i.id AS instructivo_id, i.titulo AS instructivo,
           p.nombre AS responsable
    FROM tareas t JOIN equipos e ON e.id = t.equipo_id JOIN secciones s ON s.id = t.seccion_id
    JOIN instructivos i ON i.id = s.instructivo_id LEFT JOIN personas p ON p.id = t.responsable_id
"""


def listar_tareas(incluir_baja: bool = False) -> list[dict]:
    with transaccion() as c:
        filas = c.execute(_SQL_TAREAS + ("" if incluir_baja else "WHERE t.activa=1 ") + "ORDER BY e.codigo, t.numero")
        return [dict(r) for r in filas]


def secciones_disponibles() -> list[dict]:
    """Para elegir en el Plan: solo las de instructivos vigentes, con los equipos a los que aplica cada una."""
    with transaccion() as c:
        filas = c.execute("""
            SELECT s.id, i.id AS instructivo_id, i.codigo || '-' || s.letra AS codigo, i.titulo,
                   (SELECT group_concat(texto, ' · ') FROM (SELECT texto FROM actividades WHERE seccion_id = s.id
                     AND es_grupo = 0 ORDER BY orden LIMIT 3)) AS resumen,
                   (SELECT group_concat(equipo_id) FROM instructivo_equipos WHERE instructivo_id = i.id) AS equipos
            FROM secciones s JOIN instructivos i ON i.id = s.instructivo_id WHERE i.vigente=1 ORDER BY i.codigo, s.letra""")
        salida = []
        for r in filas:
            d = dict(r)
            d["equipo_ids"] = sorted(int(x) for x in (d.pop("equipos") or "").split(",") if x)
            salida.append(d)
        return salida


def _datos_tarea(c, datos: dict) -> dict:
    equipo = _fila(c, "SELECT id, codigo, usa_horometro, activo FROM equipos WHERE id=?", (datos.get("equipo_id"),), "ese equipo")
    if not equipo["activo"]:
        raise ErrorDeNegocio(f"{equipo['codigo']} está obsoleto: no se le programan tareas (reactivarlo primero si volvió a usarse).")
    seccion = c.execute("SELECT s.id, s.instructivo_id, i.vigente, i.codigo AS it_codigo, i.codigo || '-' || s.letra AS codigo "
                        "FROM secciones s JOIN instructivos i ON i.id = s.instructivo_id WHERE s.id=?",
                        (datos.get("seccion_id"),)).fetchone()
    if not seccion:
        raise ErrorDeNegocio("Falta el mantenimiento (sección del instructivo).")
    if not c.execute("SELECT 1 FROM instructivo_equipos WHERE instructivo_id=? AND equipo_id=?",
                     (seccion["instructivo_id"], equipo["id"])).fetchone():
        raise ErrorDeNegocio(f"{seccion['codigo']} es del instructivo {seccion['it_codigo']}, que no aplica a {equipo['codigo']}. "
                             f"Si corresponde, asignarle {seccion['it_codigo']} al equipo en Equipos.")
    frecuencia = _opcion(datos.get("frecuencia"), cal.FRECUENCIAS, "la frecuencia")
    mes_inicio = _numero(datos.get("mes_inicio"), "el mes de inicio", entero=True, minimo=1, maximo=12)
    try:
        especificos = ",".join(map(str, cal.meses_especificos(datos.get("meses_especificos") or "")))
    except ValueError as e:
        raise ErrorDeNegocio(f"Meses específicos: {e}")
    cada_horas = _numero(datos.get("cada_horas"), "cada cuántas horas", entero=True, minimo=1, maximo=1_000_000)
    proximo = _numero(datos.get("proximo_inicial"), "el próximo servicio (h)", entero=True, maximo=10_000_000)
    if frecuencia in cal.INTERVALO_MESES and not (mes_inicio or especificos):
        raise ErrorDeNegocio(f"Con frecuencia {frecuencia} hay que indicar el mes de inicio (o los meses específicos).")
    if frecuencia == cal.POR_HORAS:
        if not equipo["usa_horometro"]:
            raise ErrorDeNegocio(f"{equipo['codigo']} no tiene horómetro: no se le puede programar un servicio por horas.")
        if not cada_horas:
            raise ErrorDeNegocio("Con frecuencia 'Por horas' hay que indicar cada cuántas horas.")
    else:
        cada_horas = proximo = None
    if frecuencia not in cal.INTERVALO_MESES:
        mes_inicio, especificos = None, ""
    return {"equipo_id": equipo["id"], "seccion": seccion, "frecuencia": frecuencia, "mes_inicio": mes_inicio,
            "meses_especificos": especificos, "cada_horas": cada_horas, "proximo_inicial": proximo,
            "responsable_id": _persona(c, datos.get("responsable_id"), "el responsable"),
            "observaciones": _texto(datos.get("observaciones"), "", False)}


def _exigir_no_programada(c, equipo_id: int, seccion_id: int, excepto: int | None = None) -> None:
    """Una sección se programa una sola vez por equipo: para cambiarle la frecuencia se edita la tarea que ya está."""
    otra = c.execute("""SELECT e.codigo || '-' || t.numero AS tarea, i.codigo || '-' || s.letra AS seccion, e.codigo AS equipo
                        FROM tareas t JOIN equipos e ON e.id = t.equipo_id JOIN secciones s ON s.id = t.seccion_id
                        JOIN instructivos i ON i.id = s.instructivo_id
                        WHERE t.equipo_id=? AND t.seccion_id=? AND t.activa=1 AND t.id IS NOT ?""",
                     (equipo_id, seccion_id, excepto)).fetchone()
    if otra:
        raise ErrorDeNegocio(f"{otra['seccion']} ya está programada para {otra['equipo']} (tarea {otra['tarea']}). "
                             "Para cambiarle la frecuencia, editar esa tarea.")


def _insertar_tarea(c, usuario: dict, datos: dict) -> int:
    d = _datos_tarea(c, datos)
    if not d["seccion"]["vigente"]:
        raise ErrorDeNegocio(f"{d['seccion']['codigo']} es de un instructivo obsoleto.")
    _exigir_no_programada(c, d["equipo_id"], d["seccion"]["id"])
    numero = c.execute("SELECT coalesce(max(numero), 0) + 1 FROM tareas WHERE equipo_id=?", (d["equipo_id"],)).fetchone()[0]
    c.execute("INSERT INTO tareas (equipo_id, numero, seccion_id, frecuencia, mes_inicio, meses_especificos, cada_horas, "
              "proximo_inicial, responsable_id, observaciones, creado_por, creado_en, modificado_por, modificado_en) "
              "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (d["equipo_id"], numero, d["seccion"]["id"], d["frecuencia"], d["mes_inicio"], d["meses_especificos"],
               d["cada_horas"], d["proximo_inicial"], d["responsable_id"], d["observaciones"],
               usuario["nombre"], _ahora(), usuario["nombre"], _ahora()))
    return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def crear_tarea(usuario: dict, **datos) -> dict:
    with transaccion() as c:
        tid = _insertar_tarea(c, usuario, datos)
        return dict(c.execute(_SQL_TAREAS + "WHERE t.id=?", (tid,)).fetchone())


_FRECUENCIA_POR_MESES = {1: "Mensual", 2: "Bimestral", 3: "Trimestral", 4: "Cuatrimestral", 6: "Semestral", 12: "Anual"}
_NUMEROS = {"un": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "seis": 6, "ocho": 8, "doce": 12}


def _frecuencia_sugerida(texto: str, usa_horometro: bool) -> dict:
    """'Cada tres meses' -> Trimestral; 'Cada 1000 horas' -> Por horas cada 1000 (si el equipo tiene horómetro).
    Lo que no encaja en una frecuencia de la app (ej. 'Cada 8 meses') queda sin sugerir, para elegirlo a mano."""
    t = (texto or "").lower().replace(".", "")
    for palabra, n in _NUMEROS.items():
        t = re.sub(rf"\b{palabra}\b", str(n), t)
    if m := re.search(r"(\d+)\s*(h|hs|horas?)\b", t):
        return {"frecuencia": cal.POR_HORAS, "cada_horas": int(m.group(1))} if usa_horometro else {}
    if m := re.search(r"(\d+)\s*mes", t):
        return {"frecuencia": _FRECUENCIA_POR_MESES[int(m.group(1))]} if int(m.group(1)) in _FRECUENCIA_POR_MESES else {}
    if re.search(r"\bcada mes\b", t):
        return {"frecuencia": "Mensual"}
    return next(({"frecuencia": f} for f in cal.FRECUENCIAS if f.lower() in t), {})


def _frecuencias_de_la_ficha(bloques: str | None) -> dict[str, str]:
    """La tabla 'Frecuencias' del instructivo (letra de la sección -> texto), si la tiene."""
    for b in json.loads(bloques or "[]"):
        datos = b.get("datos") or {}
        if str(datos.get("titulo", "")).strip().lower() == "frecuencias":
            filas = (datos.get("filas") or [])[1 if datos.get("encabezado") else 0:]
            return {str(f[0]).strip().upper(): str(f[1]) for f in filas if len(f) >= 2}
    return {}


def tareas_sin_programar() -> list[dict]:
    """Cada sección de un instructivo vigente que un equipo activo todavía no tiene en el Plan, con la frecuencia
    sugerida por la tabla 'Frecuencias' del instructivo. Es lo que ofrece "Programar todos" (en Opciones)."""
    with transaccion() as c:
        filas = c.execute("""
            SELECT e.id AS equipo_id, e.codigo AS equipo_codigo, e.nombre AS equipo, e.usa_horometro,
                   s.id AS seccion_id, s.letra, i.codigo || '-' || s.letra AS seccion, i.id AS instructivo_id, i.bloques
            FROM equipos e JOIN instructivo_equipos ie ON ie.equipo_id = e.id
            JOIN instructivos i ON i.id = ie.instructivo_id AND i.vigente = 1 JOIN secciones s ON s.instructivo_id = i.id
            WHERE e.activo = 1 AND NOT EXISTS (SELECT 1 FROM tareas t WHERE t.equipo_id = e.id AND t.seccion_id = s.id AND t.activa = 1)
            ORDER BY e.codigo, i.codigo, s.letra""").fetchall()
    salida = []
    for r in filas:
        d = dict(r)
        texto = _frecuencias_de_la_ficha(d.pop("bloques")).get(d["letra"].upper(), "")
        sugerida = _frecuencia_sugerida(texto, bool(d["usa_horometro"]))
        salida.append({**d, "segun_ficha": texto, "frecuencia": sugerida.get("frecuencia"),
                       "cada_horas": sugerida.get("cada_horas"),
                       "mes_inicio": 1 if sugerida.get("frecuencia") in cal.INTERVALO_MESES else None})
    return salida


def programar_tareas(usuario: dict, tareas: list[dict]) -> list[dict]:
    """Varias tareas de una vez ("Programar todos"): se programan todas o ninguna, y cada una pasa por las mismas
    reglas que una suelta. El error dice cuál falló, para corregirla en la lista."""
    if not tareas:
        raise ErrorDeNegocio("No hay tareas para programar.")
    with transaccion() as c:
        ids = []
        for datos in tareas:
            try:
                ids.append(_insertar_tarea(c, usuario, datos))
            except ErrorDeNegocio as e:
                eq = c.execute("SELECT codigo FROM equipos WHERE id=?", (datos.get("equipo_id"),)).fetchone()
                sec = c.execute("SELECT i.codigo || '-' || s.letra FROM secciones s JOIN instructivos i ON i.id = s.instructivo_id "
                                "WHERE s.id=?", (datos.get("seccion_id"),)).fetchone()
                donde = " ".join(x[0] for x in (eq, sec) if x)
                raise ErrorDeNegocio(f"{donde + ': ' if donde else ''}{e} No se programó ninguna.") from None
        marcas = ",".join("?" * len(ids))
        return [dict(r) for r in c.execute(_SQL_TAREAS + f"WHERE t.id IN ({marcas}) ORDER BY e.codigo, t.numero", ids)]


def actualizar_tarea(usuario: dict, tarea_id: int, **datos) -> dict:
    with transaccion() as c:
        actual = _fila(c, "SELECT equipo_id, seccion_id FROM tareas WHERE id=?", (tarea_id,), "esa tarea")
        d = _datos_tarea(c, datos)
        if (d["equipo_id"], d["seccion"]["id"]) != (actual["equipo_id"], actual["seccion_id"]) and \
                c.execute("SELECT 1 FROM registros WHERE tarea_id=?", (tarea_id,)).fetchone():
            raise ErrorDeNegocio("La tarea ya tiene registros: no se le cambia el equipo ni el mantenimiento "
                                 "(los registros dejarían de decir qué se hizo). Darla de baja y crear otra.")
        if c.execute("SELECT activa FROM tareas WHERE id=?", (tarea_id,)).fetchone()["activa"]:
            _exigir_no_programada(c, d["equipo_id"], d["seccion"]["id"], excepto=tarea_id)
        c.execute("UPDATE tareas SET equipo_id=?, seccion_id=?, frecuencia=?, mes_inicio=?, meses_especificos=?, cada_horas=?, "
                  "proximo_inicial=?, responsable_id=?, observaciones=?, modificado_por=?, modificado_en=? WHERE id=?",
                  (d["equipo_id"], d["seccion"]["id"], d["frecuencia"], d["mes_inicio"], d["meses_especificos"],
                   d["cada_horas"], d["proximo_inicial"], d["responsable_id"], d["observaciones"],
                   usuario["nombre"], _ahora(), tarea_id))
        return dict(c.execute(_SQL_TAREAS + "WHERE t.id=?", (tarea_id,)).fetchone())


def cambiar_alta_tarea(usuario: dict, tarea_id: int, *, activa: bool) -> dict:
    with transaccion() as c:
        t = _fila(c, "SELECT e.codigo, e.activo, t.equipo_id, t.seccion_id FROM tareas t JOIN equipos e ON e.id = t.equipo_id "
                     "WHERE t.id=?", (tarea_id,), "esa tarea")
        if activa and not t["activo"]:
            raise ErrorDeNegocio(f"{t['codigo']} está obsoleto: primero hay que reactivar el equipo.")
        if activa:   # reactivarla no puede dejar la misma sección dos veces en el Plan
            _exigir_no_programada(c, t["equipo_id"], t["seccion_id"], excepto=tarea_id)
        c.execute("UPDATE tareas SET activa=?, modificado_por=?, modificado_en=? WHERE id=?",
                  (int(activa), usuario["nombre"], _ahora(), tarea_id))
        return dict(c.execute(_SQL_TAREAS + "WHERE t.id=?", (tarea_id,)).fetchone())


# ── horómetro ───────────────────────────────────────────────────────────────

def _exigir_lectura_coherente(c, equipo_id: int, fecha: str, horas: int) -> None:
    """Un horómetro no retrocede: la lectura no puede ser menor que una anterior ni mayor que una posterior."""
    antes = c.execute("SELECT max(horas) FROM lecturas_horometro WHERE equipo_id=? AND fecha<=?", (equipo_id, fecha)).fetchone()[0]
    despues = c.execute("SELECT min(horas) FROM lecturas_horometro WHERE equipo_id=? AND fecha>?", (equipo_id, fecha)).fetchone()[0]
    if antes is not None and horas < antes:
        raise ErrorDeNegocio(f"El horómetro no puede bajar: ya hay una lectura de {antes:,} h en esa fecha o antes.".replace(",", "."))
    if despues is not None and horas > despues:
        raise ErrorDeNegocio(f"Hay una lectura posterior de {despues:,} h: esta no puede ser mayor.".replace(",", "."))


def registrar_lectura(usuario: dict, equipo_id: int, *, fecha, horas, anoto_id=None, observaciones="") -> dict:
    with transaccion() as c:
        eq = _fila(c, "SELECT codigo, usa_horometro FROM equipos WHERE id=?", (equipo_id,), "ese equipo")
        if not eq["usa_horometro"]:
            raise ErrorDeNegocio(f"{eq['codigo']} no tiene horómetro.")
        fecha = _fecha(fecha, "la fecha")
        if fecha > date.today().isoformat():
            raise ErrorDeNegocio("La fecha no puede ser futura.")
        horas = _numero(horas, "el horómetro", entero=True, maximo=10_000_000)
        if horas is None:
            raise ErrorDeNegocio("Falta la lectura del horómetro.")
        _exigir_lectura_coherente(c, equipo_id, fecha, horas)
        c.execute("INSERT INTO lecturas_horometro (equipo_id, fecha, horas, anoto_id, observaciones, creado_por, creado_en) "
                  "VALUES (?,?,?,?,?,?,?)", (equipo_id, fecha, horas, _persona(c, anoto_id, "quién anotó"),
                                             _texto(observaciones, "", False), usuario["nombre"], _ahora()))
        return {"id": c.execute("SELECT last_insert_rowid()").fetchone()[0], "fecha": fecha, "horas": horas}


def listar_lecturas(equipo_id: int | None = None, limite: int = 200) -> list[dict]:
    with transaccion() as c:
        filas = c.execute("""SELECT l.*, e.codigo AS equipo_codigo, e.nombre AS equipo,
                                    p.nombre || coalesce(' — ' || nullif(r.realizado_por_nombre, ''), '') AS anoto
                             FROM lecturas_horometro l JOIN equipos e ON e.id = l.equipo_id LEFT JOIN personas p ON p.id = l.anoto_id
                             LEFT JOIN registros r ON r.id = l.registro_id
                             WHERE ? IS NULL OR l.equipo_id = ? ORDER BY l.fecha DESC, l.id DESC LIMIT ?""",
                          (equipo_id, equipo_id, limite))
        return [dict(r) for r in filas]


def estado_horometros() -> list[dict]:
    """Por cada equipo con horómetro: última lectura y cuánto falta para cada servicio por horas."""
    with transaccion() as c:
        aviso = int(c.execute("SELECT valor FROM config WHERE clave='aviso_horas'").fetchone()[0])
        salida = []
        for e in c.execute("SELECT id, codigo, nombre FROM equipos WHERE usa_horometro=1 AND activo=1 ORDER BY codigo").fetchall():
            ultima = c.execute("SELECT horas, fecha FROM lecturas_horometro WHERE equipo_id=? ORDER BY horas DESC LIMIT 1",
                               (e["id"],)).fetchone()
            servicios = []
            for t in c.execute(_SQL_TAREAS + "WHERE t.equipo_id=? AND t.activa=1 AND t.frecuencia=? ORDER BY t.numero",
                               (e["id"], cal.POR_HORAS)).fetchall():
                hecho = c.execute("SELECT max(horometro) FROM registros WHERE tarea_id=? AND resultado IN ('Realizado','Con observaciones')",
                                  (t["id"],)).fetchone()[0]
                est = cal.estado_por_horas(t["cada_horas"], t["proximo_inicial"], ultima["horas"] if ultima else None, hecho, aviso)
                servicios.append({"tarea_id": t["id"], "codigo": t["codigo"], "seccion": t["seccion"],
                                  "cada_horas": t["cada_horas"], **est.__dict__})
            salida.append({"equipo_id": e["id"], "codigo": e["codigo"], "nombre": e["nombre"],
                           "ultima_lectura": ultima["horas"] if ultima else None,
                           "fecha_lectura": ultima["fecha"] if ultima else None, "servicios": servicios})
        return salida


def grilla_horometros(corrimiento: int = 0, columnas: int = 12) -> list[dict]:
    """El cronograma de los servicios por horas: por equipo, 12 bloques de horas en vez de 12 meses.

    El bloque es el intervalo más corto entre los servicios del equipo (el "mes" de ese equipo). La ventana arranca
    3 bloques antes de la última lectura, como el cronograma muestra los meses pasados; `corrimiento` la mueve.
    """
    with transaccion() as c:
        aviso = int(c.execute("SELECT valor FROM config WHERE clave='aviso_horas'").fetchone()[0])
        salida = []
        for e in c.execute("SELECT id, codigo, nombre FROM equipos WHERE usa_horometro=1 AND activo=1 ORDER BY codigo").fetchall():
            ultima = c.execute("SELECT horas, fecha FROM lecturas_horometro WHERE equipo_id=? ORDER BY horas DESC LIMIT 1",
                               (e["id"],)).fetchone()
            tareas = c.execute(_SQL_TAREAS + "WHERE t.equipo_id=? AND t.activa=1 AND t.frecuencia=? ORDER BY t.numero",
                               (e["id"], cal.POR_HORAS)).fetchall()
            equipo = {"equipo_id": e["id"], "codigo": e["codigo"], "nombre": e["nombre"],
                      "ultima_lectura": ultima["horas"] if ultima else None, "fecha_lectura": ultima["fecha"] if ultima else None,
                      "bloques": [], "actual": None, "filas": []}
            salida.append(equipo)
            if not tareas:
                continue
            tamanio = min(t["cada_horas"] for t in tareas)
            ancla = ultima["horas"] if ultima else min((t["proximo_inicial"] for t in tareas if t["proximo_inicial"]), default=0)
            inicio = max(0, ancla // tamanio - 3 + corrimiento) * tamanio
            equipo["bloques"] = [inicio + i * tamanio for i in range(columnas)]
            if ultima and 0 <= (ultima["horas"] - inicio) // tamanio < columnas:
                equipo["actual"] = (ultima["horas"] - inicio) // tamanio
            for t in tareas:
                hechos = [(r["horometro"], r["fecha"]) for r in c.execute(
                    "SELECT horometro, fecha FROM registros WHERE tarea_id=? AND horometro IS NOT NULL "
                    "AND resultado IN ('Realizado','Con observaciones')", (t["id"],))]
                est = cal.estado_por_horas(t["cada_horas"], t["proximo_inicial"], equipo["ultima_lectura"],
                                           max((h for h, _ in hechos), default=None), aviso)
                equipo["filas"].append({
                    "tarea_id": t["id"], "codigo": t["codigo"], "seccion": t["seccion"], "instructivo_id": t["instructivo_id"],
                    "cada_horas": t["cada_horas"], "responsable": t["responsable"], **est.__dict__,
                    "celdas": cal.grilla_por_horas(t["cada_horas"], t["proximo_inicial"], hechos, equipo["ultima_lectura"],
                                                   aviso, inicio, tamanio, columnas)})
        return salida


# ── registros de mantenimiento preventivo ───────────────────────────────────

def registrar_mantenimiento(usuario: dict, tarea_id: int, *, fecha, resultado, realizado_por_id=None, realizado_por_nombre="",
                            horas_hombre=None, horometro=None, novedades="", repuestos="", reprogramado_para=None) -> dict:
    with transaccion() as c:
        t = _fila(c, _SQL_TAREAS + "WHERE t.id=?", (tarea_id,), "esa tarea")
        if not t["activa"]:
            raise ErrorDeNegocio(f"La tarea {t['codigo']} está dada de baja.")
        fecha = _fecha(fecha, "la fecha")
        if fecha > date.today().isoformat():
            raise ErrorDeNegocio("La fecha no puede ser futura: se registra lo que ya se hizo.")
        resultado = _opcion(resultado, cal.RESULTADOS, "el resultado")
        horometro = _numero(horometro, "el horómetro", entero=True, maximo=10_000_000)
        if t["usa_horometro"] and resultado in cal.CUMPLE and horometro is None:
            raise ErrorDeNegocio(f"{t['equipo_codigo']} tiene horómetro: anotar la lectura al momento del servicio.")
        if horometro is not None and not t["usa_horometro"]:
            raise ErrorDeNegocio(f"{t['equipo_codigo']} no tiene horómetro.")
        reprogramado_para = _fecha(reprogramado_para, "la nueva fecha", obligatorio=resultado == "Reprogramado")
        if resultado != "Reprogramado":
            reprogramado_para = None
        elif reprogramado_para <= fecha:
            raise ErrorDeNegocio("La nueva fecha tiene que ser posterior a la del registro.")
        novedades = _texto(novedades, "", False)
        if resultado in ("Con observaciones", "No realizado") and not novedades:
            raise ErrorDeNegocio(f"Con resultado '{resultado}' hay que contar qué pasó en Novedades.")
        if horometro is not None:
            _exigir_lectura_coherente(c, t["equipo_id"], fecha, horometro)
        persona, nombre = _quien(c, realizado_por_id, realizado_por_nombre, obligatorio=resultado in cal.CUMPLE)
        c.execute("INSERT INTO registros (tarea_id, fecha, resultado, realizado_por_id, realizado_por_nombre, horas_hombre, horometro, "
                  "novedades, repuestos, reprogramado_para, creado_por, creado_en) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (tarea_id, fecha, resultado, persona, nombre, _numero(horas_hombre, "las horas-hombre", maximo=1000),
                   horometro, novedades, _texto(repuestos, "", False), reprogramado_para, usuario["nombre"], _ahora()))
        rid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        if horometro is not None:   # la lectura del servicio también es la última lectura del equipo
            c.execute("INSERT INTO lecturas_horometro (equipo_id, fecha, horas, anoto_id, observaciones, registro_id, "
                      "creado_por, creado_en) VALUES (?,?,?,?,?,?,?,?)",
                      (t["equipo_id"], fecha, horometro, persona, f"Servicio {t['seccion']}", rid, usuario["nombre"], _ahora()))
        return dict(c.execute("SELECT * FROM registros WHERE id=?", (rid,)).fetchone())


def listar_registros(anio: int | None = None, equipo_id: int | None = None, limite: int = 500) -> list[dict]:
    with transaccion() as c:
        filas = c.execute("""
            SELECT r.*, e.codigo || '-' || t.numero AS tarea, e.codigo AS equipo_codigo, e.nombre AS equipo,
                   i.codigo || '-' || s.letra AS seccion, """ + _REALIZADO_POR.format(t="r") + """
            FROM registros r JOIN tareas t ON t.id = r.tarea_id JOIN equipos e ON e.id = t.equipo_id
            JOIN secciones s ON s.id = t.seccion_id JOIN instructivos i ON i.id = s.instructivo_id
            LEFT JOIN personas p ON p.id = r.realizado_por_id
            WHERE (? IS NULL OR substr(r.fecha, 1, 4) = ?) AND (? IS NULL OR t.equipo_id = ?)
            ORDER BY r.fecha DESC, r.id DESC LIMIT ?""",
                          (anio, str(anio) if anio else None, equipo_id, equipo_id, limite))
        return [dict(r) for r in filas]


def anular_registro(usuario: dict, registro_id: int) -> None:
    """Para corregir un registro cargado por error (con su lectura de horómetro, si la generó)."""
    with transaccion() as c:
        _fila(c, "SELECT 1 FROM registros WHERE id=?", (registro_id,), "ese registro")
        c.execute("DELETE FROM lecturas_horometro WHERE registro_id=?", (registro_id,))
        c.execute("DELETE FROM registros WHERE id=?", (registro_id,))


# ── correctivos ─────────────────────────────────────────────────────────────

def registrar_correctivo(usuario: dict, equipo_id: int, *, fecha, falla, causa="", accion="", horas_parada=None,
                         horas_hombre=None, repuestos="", realizado_por_id=None, realizado_por_nombre="", accion_sgc=False,
                         observaciones="") -> dict:
    with transaccion() as c:
        _fila(c, "SELECT 1 FROM equipos WHERE id=?", (equipo_id,), "ese equipo")
        fecha = _fecha(fecha, "la fecha")
        if fecha > date.today().isoformat():
            raise ErrorDeNegocio("La fecha no puede ser futura.")
        persona, nombre = _quien(c, realizado_por_id, realizado_por_nombre)
        c.execute("INSERT INTO correctivos (equipo_id, fecha, falla, causa, accion, horas_parada, horas_hombre, repuestos, "
                  "realizado_por_id, realizado_por_nombre, accion_sgc, observaciones, creado_por, creado_en) "
                  "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (equipo_id, fecha, _texto(falla, "la falla o síntoma"), _texto(causa, "", False), _texto(accion, "", False),
                   _numero(horas_parada, "las horas de parada", maximo=10_000), _numero(horas_hombre, "las horas-hombre", maximo=1000),
                   _texto(repuestos, "", False), persona, nombre, int(bool(accion_sgc)),
                   _texto(observaciones, "", False), usuario["nombre"], _ahora()))
        return dict(c.execute("SELECT * FROM correctivos WHERE id=last_insert_rowid()").fetchone())


def listar_correctivos(anio: int | None = None, equipo_id: int | None = None) -> list[dict]:
    with transaccion() as c:
        filas = c.execute("""
            SELECT co.*, e.codigo AS equipo_codigo, e.nombre AS equipo, coalesce(a.nombre, '') AS sector, """ + _REALIZADO_POR.format(t="co") + """
            FROM correctivos co JOIN equipos e ON e.id = co.equipo_id LEFT JOIN areas a ON a.id = e.area_id LEFT JOIN personas p ON p.id = co.realizado_por_id
            WHERE (? IS NULL OR substr(co.fecha, 1, 4) = ?) AND (? IS NULL OR co.equipo_id = ?)
            ORDER BY co.fecha DESC, co.id DESC""", (anio, str(anio) if anio else None, equipo_id, equipo_id))
        return [dict(r) for r in filas]


# ── cronograma ──────────────────────────────────────────────────────────────

def cronograma(anio: int, hoy: date | None = None) -> dict:
    """La grilla del año: cada tarea del Plan x 12 meses, con lo que tocaba y lo que se registró."""
    hoy = hoy or date.today()
    with transaccion() as c:
        tareas = c.execute(_SQL_TAREAS + "WHERE t.activa=1 ORDER BY e.codigo, t.numero").fetchall()
        regs: dict[tuple[int, int], list[str]] = {}
        for r in c.execute("SELECT tarea_id, CAST(substr(fecha, 6, 2) AS INTEGER) AS mes, resultado FROM registros "
                           "WHERE substr(fecha, 1, 4) = ?", (str(anio),)):
            regs.setdefault((r["tarea_id"], r["mes"]), []).append(r["resultado"])
    filas, esperadas, cumplidas, pendientes_mes = [], 0, 0, 0
    for t in tareas:
        alta = date.fromisoformat(t["creado_en"][:10]) if t["creado_en"] else None
        celdas = []
        for mes in range(1, 13):
            esperado = cal.veces_por_mes(t["frecuencia"], t["mes_inicio"], t["meses_especificos"], mes)
            celda = cal.estado_celda(esperado, regs.get((t["id"], mes), []), anio, mes, hoy, alta)
            celdas.append(celda.__dict__)
            if celda.estado in ("hecho", "vencido", "reprogramado", "no_realizado") and (anio, mes) < (hoy.year, hoy.month):
                esperadas += 1
                cumplidas += celda.estado == "hecho"
            if (anio, mes) == (hoy.year, hoy.month) and celda.estado == "pendiente":
                pendientes_mes += 1
        filas.append({"tarea_id": t["id"], "codigo": t["codigo"], "equipo": t["equipo"], "equipo_codigo": t["equipo_codigo"],
                      "seccion": t["seccion"], "instructivo_id": t["instructivo_id"], "frecuencia": t["frecuencia"],
                      "cada_horas": t["cada_horas"], "responsable": t["responsable"], "celdas": celdas})
    return {"anio": anio, "hoy": hoy.isoformat(), "filas": filas,
            "cumplimiento": {"esperadas": esperadas, "cumplidas": cumplidas,
                             "porcentaje": round(100 * cumplidas / esperadas) if esperadas else None,
                             "pendientes_este_mes": pendientes_mes}}


def pendientes(hoy: date | None = None) -> dict:
    """La pantalla de inicio: lo que hay que hacer este mes, lo atrasado y los servicios por horas que se acercan."""
    hoy = hoy or date.today()
    crono = cronograma(hoy.year, hoy)
    este_mes, atrasados = [], []
    for f in crono["filas"]:
        for mes, celda in enumerate(f["celdas"], 1):
            item = {k: f[k] for k in ("tarea_id", "codigo", "equipo", "seccion", "instructivo_id", "responsable", "frecuencia")}
            if mes == hoy.month and celda["estado"] == "pendiente":
                este_mes.append({**item, "mes": mes, "faltan": celda["esperado"] - celda["hechos"]})
            elif mes < hoy.month and celda["estado"] == "vencido":
                atrasados.append({**item, "mes": mes})
    horas = [{**s, "equipo": e["nombre"], "equipo_codigo": e["codigo"]}
             for e in estado_horometros() for s in e["servicios"] if s["estado"] in ("proximo", "vencido", "sin_lectura", "falta_dato")]
    return {"hoy": hoy.isoformat(), "este_mes": este_mes, "atrasados": atrasados, "por_horas": horas,
            "cumplimiento": crono["cumplimiento"]}
