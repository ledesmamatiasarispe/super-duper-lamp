"""Las tablas de mantenimiento y sus migraciones. usuarios, sesiones y config son del núcleo.

migrar(c) corre al arrancar, dentro de la transacción del núcleo y antes de que nadie use las tablas: es idempotente.
La primera vez que arranca sobre una base anterior al núcleo (UltraMantenimiento 1.0.x), pasa los usuarios al esquema
del núcleo SIN perder nada: el legajo pasa a ser el id y también el usuario con el que se entra (así cada uno sigue
entrando con su legajo y todo lo que apuntaba al legajo sigue apuntando a la misma persona). Antes copia la base.
"""
import json
import sqlite3
from datetime import datetime

from nucleo import db

ESQUEMA = """
-- Quién hace los trabajos (no tiene por qué tener usuario: un proveedor externo no entra al sistema).
-- Dos categorías: operarios de mantenimiento interno y proveedores externos. Cada categoría tiene además una fila
-- genérica (pide_nombre=1, la que lleva el nombre de la categoría): es "Otro (escribir nombre)" al registrar y
-- "la categoría en general" como responsable de una tarea del Plan.
CREATE TABLE IF NOT EXISTS personas (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre  TEXT    NOT NULL UNIQUE,
    categoria TEXT  NOT NULL DEFAULT 'interno' CHECK (categoria IN ('interno', 'externo')),
    contacto  TEXT  NOT NULL DEFAULT '',        -- teléfono, mail o rubro (sobre todo de proveedores)
    pide_nombre INTEGER NOT NULL DEFAULT 0,
    activo  INTEGER NOT NULL DEFAULT 1,
    usuario_legajo INTEGER REFERENCES usuarios(id)   -- la ficha de un usuario del sistema (nombre y alta los maneja Usuarios)
);
-- Áreas de la planta (Servicios, Terminación...): una lista, para que el mismo sector no aparezca escrito de tres formas
CREATE TABLE IF NOT EXISTS areas (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre  TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    activo  INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS equipos (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo         TEXT    NOT NULL UNIQUE,
    nombre         TEXT    NOT NULL,
    area_id        INTEGER REFERENCES areas(id),
    marca_modelo   TEXT    NOT NULL DEFAULT '',
    usa_horometro  INTEGER NOT NULL DEFAULT 0,
    activo         INTEGER NOT NULL DEFAULT 1,            -- 0 = obsoleto
    fecha_baja     TEXT, motivo_baja TEXT,
    creado_por     TEXT, creado_en TEXT, modificado_por TEXT, modificado_en TEXT
);
CREATE TABLE IF NOT EXISTS instructivos (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo         TEXT    NOT NULL UNIQUE,          -- IT01
    titulo         TEXT    NOT NULL,
    descripcion    TEXT    NOT NULL DEFAULT '',
    seguridad      TEXT    NOT NULL DEFAULT '[]',     -- JSON: lista de textos
    repuestos      TEXT    NOT NULL DEFAULT '[]',     -- JSON: lista de textos
    bloques        TEXT    NOT NULL DEFAULT '[]',     -- JSON: contenido adicional (texto, nota, tabla, imagen, gráfico)
    archivos       TEXT    NOT NULL DEFAULT '[]',     -- JSON: ids de adjuntos listados en el documento
    orden          TEXT    NOT NULL DEFAULT '[]',     -- JSON: orden del documento ("seccion:A", "bloque:0", "repuestos")
    revision      INTEGER NOT NULL DEFAULT 0,
    fecha_revision TEXT    NOT NULL,
    vigente        INTEGER NOT NULL DEFAULT 1,
    fecha_baja     TEXT, motivo_baja TEXT,
    creado_por     TEXT, creado_en TEXT, modificado_por TEXT, modificado_en TEXT
);
-- A qué equipos aplica cada instructivo (uno o varios: equipos iguales comparten instructivo).
-- El Plan solo deja programarle a un equipo secciones de sus instructivos.
CREATE TABLE IF NOT EXISTS instructivo_equipos (
    instructivo_id  INTEGER NOT NULL REFERENCES instructivos(id),
    equipo_id       INTEGER NOT NULL REFERENCES equipos(id),
    PRIMARY KEY (instructivo_id, equipo_id)
);
-- Cada sección (IT01-A, IT01-B...) es un grupo de actividades que se hacen juntas: lo que el Plan programa
CREATE TABLE IF NOT EXISTS secciones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    instructivo_id  INTEGER NOT NULL REFERENCES instructivos(id),
    letra           TEXT    NOT NULL,
    UNIQUE (instructivo_id, letra)
);
CREATE TABLE IF NOT EXISTS actividades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    seccion_id  INTEGER NOT NULL REFERENCES secciones(id) ON DELETE CASCADE,
    orden       INTEGER NOT NULL,
    texto       TEXT    NOT NULL,
    es_grupo    INTEGER NOT NULL DEFAULT 0,
    detalle     TEXT    NOT NULL DEFAULT ''          -- sub-pasos de la actividad, uno por renglón
);
-- Imágenes y archivos de un instructivo. Solo se agregan: sacarlos del contenido no los borra, así una revisión
-- vieja sigue mostrando los suyos. El archivo se guarda con un nombre propio (nunca el que trae el usuario).
CREATE TABLE IF NOT EXISTS adjuntos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    instructivo_id  INTEGER NOT NULL REFERENCES instructivos(id),
    archivo         TEXT    NOT NULL UNIQUE,         -- <hex>.<ext> dentro de data/adjuntos/<código>/
    nombre          TEXT    NOT NULL,                -- nombre original, solo para mostrar
    tipo            TEXT    NOT NULL,                -- MIME
    tamanio         INTEGER NOT NULL,
    es_imagen       INTEGER NOT NULL,
    creado_por TEXT, creado_en TEXT
);
-- Historial de revisiones: el contenido anterior completo, como quedó antes de cada cambio
CREATE TABLE IF NOT EXISTS instructivo_versiones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    instructivo_id  INTEGER NOT NULL REFERENCES instructivos(id),
    revision        INTEGER NOT NULL,
    contenido       TEXT    NOT NULL,
    motivo          TEXT    NOT NULL,                -- qué cambió para pasar a la revisión siguiente
    creado_por      TEXT, creado_en TEXT
);
-- Plan: qué sección se le hace a qué equipo y cada cuánto
CREATE TABLE IF NOT EXISTS tareas (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    equipo_id          INTEGER NOT NULL REFERENCES equipos(id),
    numero             INTEGER NOT NULL,             -- EQ-001-<numero>
    seccion_id         INTEGER NOT NULL REFERENCES secciones(id),
    frecuencia         TEXT    NOT NULL,
    mes_inicio         INTEGER,
    meses_especificos  TEXT    NOT NULL DEFAULT '',  -- "3,9": manda sobre frecuencia + mes de inicio
    cada_horas         INTEGER,                      -- solo "Por horas"
    proximo_inicial    INTEGER,                      -- horómetro del primer servicio, si nunca se registró uno
    responsable_id     INTEGER REFERENCES personas(id),
    observaciones      TEXT    NOT NULL DEFAULT '',
    activa             INTEGER NOT NULL DEFAULT 1,
    creado_por TEXT, creado_en TEXT, modificado_por TEXT, modificado_en TEXT,
    UNIQUE (equipo_id, numero)
);
CREATE TABLE IF NOT EXISTS registros (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    tarea_id           INTEGER NOT NULL REFERENCES tareas(id),
    fecha              TEXT    NOT NULL,
    resultado          TEXT    NOT NULL,
    realizado_por_id   INTEGER REFERENCES personas(id),
    realizado_por_nombre TEXT  NOT NULL DEFAULT '',  -- quién fue, si la persona elegida es genérica
    horas_hombre       REAL,
    horometro          INTEGER,
    novedades          TEXT    NOT NULL DEFAULT '',
    repuestos          TEXT    NOT NULL DEFAULT '',
    reprogramado_para  TEXT,
    creado_por TEXT, creado_en TEXT
);
CREATE TABLE IF NOT EXISTS lecturas_horometro (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    equipo_id    INTEGER NOT NULL REFERENCES equipos(id),
    fecha        TEXT    NOT NULL,
    horas        INTEGER NOT NULL,
    anoto_id     INTEGER REFERENCES personas(id),
    observaciones TEXT   NOT NULL DEFAULT '',
    registro_id  INTEGER REFERENCES registros(id),   -- si vino de un registro de mantenimiento
    cambio       INTEGER NOT NULL DEFAULT 0,  -- 1 = primera lectura de un horómetro nuevo (el anterior se rompió o se reemplazó)
    horas_anterior INTEGER,                   -- en un cambio: lo último que marcó el horómetro reemplazado, si se sabe
    creado_por TEXT, creado_en TEXT
);
CREATE TABLE IF NOT EXISTS correctivos (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    equipo_id         INTEGER NOT NULL REFERENCES equipos(id),
    fecha             TEXT    NOT NULL,
    falla             TEXT    NOT NULL,
    causa             TEXT    NOT NULL DEFAULT '',
    accion            TEXT    NOT NULL DEFAULT '',
    horas_parada      REAL,
    horas_hombre      REAL,
    repuestos         TEXT    NOT NULL DEFAULT '',
    realizado_por_id  INTEGER REFERENCES personas(id),
    realizado_por_nombre TEXT NOT NULL DEFAULT '',
    accion_sgc        INTEGER NOT NULL DEFAULT 0,
    observaciones     TEXT    NOT NULL DEFAULT '',
    creado_por TEXT, creado_en TEXT
);
-- Mapa de planta: cada plano es un dibujo (rectángulos, líneas, textos) en metros. Las máquinas se ubican como puntos
-- con equipos.plano_id/plano_x/plano_y: una máquina está en un solo plano.
CREATE TABLE IF NOT EXISTS planos (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre     TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    ancho      REAL    NOT NULL,
    alto       REAL    NOT NULL,
    elementos  TEXT    NOT NULL DEFAULT '[]',          -- JSON: lo dibujado (ver servicios._validar_elementos)
    creado_por TEXT, creado_en TEXT, modificado_por TEXT, modificado_en TEXT
);
"""


def _migrar_usuarios_al_nucleo(c: sqlite3.Connection) -> None:
    """usuarios(legajo, ...) -> usuarios(id, usuario, ...) del núcleo, y sesiones(legajo) -> sesiones(usuario_id).
    RENAME COLUMN actualiza solo las claves foráneas que apuntaban a usuarios(legajo) (personas, sesiones): no hace falta
    rehacer ninguna tabla. Las sesiones abiertas siguen valiendo."""
    if "legajo" not in {r[1] for r in c.execute("PRAGMA table_info(usuarios)")}:
        return
    copia = db.DB_PATH.with_name(f"{db.DB_PATH.stem}_antes_del_nucleo.db")
    if not copia.exists():   # la base tal como estaba (la transacción todavía no escribió nada)
        origen, destino = sqlite3.connect(db.DB_PATH), sqlite3.connect(copia)
        try:
            origen.backup(destino)
        finally:
            destino.close()
            origen.close()
    c.execute("ALTER TABLE usuarios RENAME COLUMN legajo TO id")
    c.execute("ALTER TABLE usuarios ADD COLUMN usuario TEXT")
    c.execute("ALTER TABLE usuarios ADD COLUMN creado_en TEXT")
    c.execute("UPDATE usuarios SET usuario = CAST(id AS TEXT)")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_usuarios_usuario ON usuarios(usuario COLLATE NOCASE)")
    c.execute("ALTER TABLE sesiones RENAME COLUMN legajo TO usuario_id")


def migrar(c: sqlite3.Connection) -> None:
    _migrar_usuarios_al_nucleo(c)
    _agregar_columnas(c)
    _migrar_areas(c)
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_personas_usuario ON personas(usuario_legajo)")
    c.execute("INSERT OR IGNORE INTO config VALUES ('aviso_horas', '100')")
    # una sola vez: la relación instructivo-equipo nace de lo que ya estaba en el Plan
    if not c.execute("SELECT 1 FROM config WHERE clave='instructivo_equipos_armado'").fetchone():
        c.execute("INSERT OR IGNORE INTO instructivo_equipos SELECT DISTINCT s.instructivo_id, t.equipo_id "
                  "FROM tareas t JOIN secciones s ON s.id = t.seccion_id")
        c.execute("INSERT INTO config VALUES ('instructivo_equipos_armado', '1')")


def _migrar_areas(c: sqlite3.Connection) -> None:
    """Antes el sector del equipo era texto libre: cada texto distinto pasa a ser un área y el equipo apunta a ella."""
    if "sector" not in {r[1] for r in c.execute("PRAGMA table_info(equipos)")}:
        return
    for (texto,) in c.execute("SELECT DISTINCT trim(sector) FROM equipos WHERE trim(sector) <> ''").fetchall():
        c.execute("INSERT OR IGNORE INTO areas (nombre) VALUES (?)", (texto,))   # NOCASE: 'terminación' = 'Terminación'
    c.execute("UPDATE equipos SET area_id = (SELECT id FROM areas WHERE nombre = trim(equipos.sector)) WHERE trim(sector) <> ''")
    c.execute("ALTER TABLE equipos DROP COLUMN sector")


def _agregar_columnas(c: sqlite3.Connection) -> None:
    """Columnas que se sumaron después de crear la base: CREATE TABLE IF NOT EXISTS no las agrega solo."""
    for tabla, columna, tipo in (("equipos", "area_id", "INTEGER REFERENCES areas(id)"),
                                 ("instructivos", "bloques", "TEXT NOT NULL DEFAULT '[]'"),
                                 ("instructivos", "archivos", "TEXT NOT NULL DEFAULT '[]'"),
                                 ("instructivos", "orden", "TEXT NOT NULL DEFAULT '[]'"),
                                 ("actividades", "detalle", "TEXT NOT NULL DEFAULT ''"),
                                 ("equipos", "fecha_baja", "TEXT"),
                                 ("equipos", "motivo_baja", "TEXT"),
                                 ("personas", "usuario_legajo", "INTEGER REFERENCES usuarios(id)"),
                                 ("personas", "pide_nombre", "INTEGER NOT NULL DEFAULT 0"),
                                 ("personas", "categoria", "TEXT NOT NULL DEFAULT 'interno'"),
                                 ("personas", "contacto", "TEXT NOT NULL DEFAULT ''"),
                                 ("registros", "realizado_por_nombre", "TEXT NOT NULL DEFAULT ''"),
                                 ("correctivos", "realizado_por_nombre", "TEXT NOT NULL DEFAULT ''"),
                                 ("lecturas_horometro", "cambio", "INTEGER NOT NULL DEFAULT 0"),
                                 ("lecturas_horometro", "horas_anterior", "INTEGER"),
                                 ("equipos", "plano_id", "INTEGER REFERENCES planos(id)"),
                                 ("equipos", "plano_x", "REAL"),
                                 ("equipos", "plano_y", "REAL")):
        if columna not in {r[1] for r in c.execute(f"PRAGMA table_info({tabla})")}:
            c.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
            if (tabla, columna) == ("personas", "pide_nombre"):   # las dos genéricas de los ejemplos
                c.execute("UPDATE personas SET pide_nombre=1 WHERE nombre IN ('Mantenimiento interno', 'Proveedor externo')")
            if (tabla, columna) == ("personas", "categoria"):
                c.execute("UPDATE personas SET categoria='externo' WHERE nombre='Proveedor externo'")


def datos_iniciales(c: sqlite3.Connection) -> None:
    """Las dos personas genéricas y dos equipos de ejemplo (uno con horómetro y otro sin). Solo en una base sin equipos:
    el núcleo la llama una vez por base, y una base que ya venía de antes del núcleo ya tiene los suyos."""
    if c.execute("SELECT 1 FROM equipos").fetchone() or c.execute("SELECT 1 FROM personas").fetchone():
        return
    ahora, quien = datetime.now().isoformat(timespec="seconds"), "Sistema"
    aud = (quien, ahora, quien, ahora)
    for nombre, categoria in (("Mantenimiento interno", "interno"), ("Proveedor externo", "externo")):
        c.execute("INSERT INTO personas (nombre, categoria, pide_nombre) VALUES (?, ?, 1)", (nombre, categoria))

    for area in ("Servicios", "Terminación"):
        c.execute("INSERT INTO areas (nombre) VALUES (?)", (area,))
    c.execute("INSERT INTO equipos (codigo, nombre, area_id, marca_modelo, usa_horometro, creado_por, creado_en, modificado_por, modificado_en) "
              "VALUES ('EQ-001', 'Compresor de tornillo', 1, 'Cetec ETR-50', 1, ?,?,?,?)", aud)
    c.execute("INSERT INTO equipos (codigo, nombre, area_id, marca_modelo, usa_horometro, creado_por, creado_en, modificado_por, modificado_en) "
              "VALUES ('EQ-002', 'Granalladora', 2, 'Americana AC-1200', 0, ?,?,?,?)", aud)

    def instructivo(codigo, titulo, descripcion, seguridad, repuestos, secciones):
        c.execute("INSERT INTO instructivos (codigo, titulo, descripcion, seguridad, repuestos, fecha_revision, "
                  "creado_por, creado_en, modificado_por, modificado_en) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (codigo, titulo, descripcion, json.dumps(seguridad, ensure_ascii=False),
                   json.dumps(repuestos, ensure_ascii=False), ahora[:10], *aud))
        it = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        ids = {}
        for letra, actividades in secciones.items():
            c.execute("INSERT INTO secciones (instructivo_id, letra) VALUES (?,?)", (it, letra))
            ids[letra] = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            for i, texto in enumerate(actividades, 1):
                grupo = texto.startswith("#")
                c.execute("INSERT INTO actividades (seccion_id, orden, texto, es_grupo) VALUES (?,?,?,?)",
                          (ids[letra], i, texto.lstrip("# "), int(grupo)))
        return ids

    s1 = instructivo("IT01", "Compresor de tornillo",
                     "Mantenimiento preventivo del compresor de aire de la planta.",
                     ["Cortar la energía y bloquear el tablero antes de intervenir.",
                      "Descargar la presión del tanque y de las líneas.",
                      "Usar guantes y anteojos de seguridad."],
                     ["Filtro de aire", "Aceite para compresor de tornillo", "Filtro de aceite", "Filtro separador"],
                     {"A": ["Limpieza general", "Limpieza de filtro de aire", "Control de correas", "Control de nivel de aceite"],
                      "B": ["Cambio de aceite", "Cambio de filtro de aceite"],
                      "C": ["Cambio de filtro separador"]})
    s2 = instructivo("IT02", "Granalladora",
                     "Mantenimiento preventivo de la granalladora de terminación.",
                     ["Cortar la energía y bloquear el tablero antes de intervenir.",
                      "Esperar a que la turbina se detenga por completo.",
                      "Usar protección respiratoria."],
                     ["Paletas de turbina", "Mangas del colector de polvo"],
                     {"A": ["# Turbina", "Controlar desgaste de paletas", "Controlar ajuste de la turbina",
                            "# Cabina", "Controlar chapas de protección", "Limpiar el colector de polvo"],
                      "B": ["Cambiar mangas del colector de polvo", "Revisar rodamientos del elevador"]})

    def tarea(equipo, numero, seccion, frecuencia, mes_inicio=None, cada_horas=None, proximo_inicial=None):
        c.execute("INSERT INTO tareas (equipo_id, numero, seccion_id, frecuencia, mes_inicio, cada_horas, proximo_inicial, "
                  "responsable_id, creado_por, creado_en, modificado_por, modificado_en) VALUES (?,?,?,?,?,?,?,1,?,?,?,?)",
                  (equipo, numero, seccion, frecuencia, mes_inicio, cada_horas, proximo_inicial, *aud))

    tarea(1, 1, s1["A"], "Trimestral", mes_inicio=1)
    tarea(1, 2, s1["B"], "Por horas", cada_horas=1000, proximo_inicial=51000)
    tarea(1, 3, s1["C"], "Por horas", cada_horas=4000, proximo_inicial=53000)
    tarea(2, 1, s2["A"], "Mensual", mes_inicio=1)
    tarea(2, 2, s2["B"], "Semestral", mes_inicio=3)
    # la relación instructivo-equipo de los ejemplos (migrar() la arma para bases viejas, pero corre antes que esto)
    c.execute("INSERT OR IGNORE INTO instructivo_equipos SELECT DISTINCT s.instructivo_id, t.equipo_id "
              "FROM tareas t JOIN secciones s ON s.id = t.seccion_id")
