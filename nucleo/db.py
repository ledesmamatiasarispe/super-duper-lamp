"""Base SQLite: conexión, transacciones y el esquema del núcleo. El esquema de cada módulo lo trae el módulo.

sqlite3 directo (sin ORM), claves foráneas activadas, una conexión por caso de uso. Las bases existentes no se
recrean: las tablas son CREATE ... IF NOT EXISTS y las columnas que se suman después van en Modulo.columnas (o en
COLUMNAS, las del núcleo), que se agregan al arrancar.

CONCURRENCIA: varios usuarios escriben a la vez contra el mismo archivo. Cada transacción arranca con BEGIN IMMEDIATE,
que toma el permiso de escritura AL EMPEZAR: dos casos de uso que escriben quedan en fila (el segundo espera hasta
busy_timeout), y lo que uno valida leyendo no lo puede invalidar otro entre la lectura y la escritura. Con el BEGIN
diferido de sqlite3 los dos leían, y el segundo en escribir recibía "database is locked" en vez del mensaje de la regla.
(Lo resolvió primero Gestión Automotor.)
"""
import itertools
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PATH = Path("data") / "app.db"   # lo fija ajustes.configurar(); los tests lo cambian con monkeypatch
ESPERA_MS = 30_000   # cuánto espera una escritura a que termine la de otro usuario antes de dar error

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario       TEXT    NOT NULL UNIQUE COLLATE NOCASE,   -- con lo que entra (un nombre o un número de legajo)
    nombre        TEXT    NOT NULL,
    password_hash TEXT    NOT NULL,
    salt          TEXT    NOT NULL,
    es_admin      INTEGER NOT NULL DEFAULT 0,
    activo        INTEGER NOT NULL DEFAULT 1,
    debe_cambiar  INTEGER NOT NULL DEFAULT 0,               -- contraseña provisoria: no bloquea, la pantalla avisa
    creado_en     TEXT
);
CREATE TABLE IF NOT EXISTS sesiones (
    token      TEXT PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    vence_en   TEXT    NOT NULL,
    activa     INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS config (
    clave  TEXT PRIMARY KEY,
    valor  TEXT NOT NULL
);
-- Archivos subidos (adjuntos.py). Cada módulo los vincula por id desde sus propias tablas. Se llama archivos y no
-- adjuntos para no chocar con la tabla propia de una app (UltraMantenimiento tiene adjuntos de sus instructivos).
CREATE TABLE IF NOT EXISTS archivos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    carpeta     TEXT    NOT NULL,                 -- subcarpeta de data/adjuntos/ (la elige el módulo)
    archivo     TEXT    NOT NULL UNIQUE,          -- <hex>.<ext>: nombre aleatorio, nunca el original
    nombre      TEXT    NOT NULL,                 -- el original, solo para mostrar
    tipo        TEXT    NOT NULL,                 -- MIME
    tamanio     INTEGER NOT NULL,
    es_imagen   INTEGER NOT NULL DEFAULT 0,
    creado_por  TEXT, creado_en TEXT
);
"""
COLUMNAS: list[tuple[str, str, str]] = []   # (tabla, columna, tipo) que el núcleo sume más adelante


def conectar() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # isolation_level=None: las transacciones las abre transaccion() a mano (BEGIN IMMEDIATE), no sqlite3 por su cuenta
    conn = sqlite3.connect(DB_PATH, timeout=ESPERA_MS / 1000, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA busy_timeout = {ESPERA_MS}")
    return conn


_en_curso = threading.local()   # la conexión de la transacción abierta en este hilo (si hay)
_savepoints = itertools.count(1)


@contextmanager
def transaccion():
    """Una transacción por caso de uso: commit si termina bien, rollback si algo lanza.

    REENTRANTE: si este hilo ya tiene una abierta, el bloque de adentro usa la MISMA conexión dentro de un SAVEPOINT
    (si falla deshace solo lo suyo y relanza; si termina bien no confirma nada: confirma el bloque de afuera). Sin esto,
    un caso de uso que llamara a otro abriría una segunda conexión y esperaría para siempre a la primera.
    Ojo: executescript confirma por su cuenta; dentro de una transacción usar ejecutar_script()."""
    externa = getattr(_en_curso, "conn", None)
    if externa is not None:
        nombre = f"sp{next(_savepoints)}"
        externa.execute(f"SAVEPOINT {nombre}")
        try:
            yield externa
        except BaseException:
            externa.execute(f"ROLLBACK TO {nombre}")
            externa.execute(f"RELEASE {nombre}")
            raise
        externa.execute(f"RELEASE {nombre}")
        return
    conn = conectar()
    _en_curso.conn = conn
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        _en_curso.conn = None
        conn.close()


def ejecutar_script(c: sqlite3.Connection, script: str) -> None:
    """Un script SQL sentencia por sentencia, DENTRO de la transacción de c (executescript haría COMMIT por su cuenta).
    Sirve para rehacer una tabla en una migración."""
    sentencia = ""
    for linea in script.splitlines(keepends=True):
        sentencia += linea
        if sqlite3.complete_statement(sentencia):
            c.execute(sentencia)
            sentencia = ""


def agregar_columnas(c: sqlite3.Connection, columnas) -> None:
    for tabla, columna, tipo in columnas:
        if columna not in {r[1] for r in c.execute(f"PRAGMA table_info({tabla})")}:
            c.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")


def ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def inicializar(modulos=(), con_ejemplos: bool = True) -> None:
    """El esquema del núcleo y el de cada módulo, sus columnas nuevas y migraciones, el administrador inicial y, la
    primera vez, los datos de ejemplo de cada módulo."""
    conn = conectar()
    try:   # executescript confirma por su cuenta: va fuera de transaccion() (son todos CREATE ... IF NOT EXISTS)
        conn.executescript(ESQUEMA)
        for m in modulos:
            if m.esquema:
                conn.executescript(m.esquema)
    finally:
        conn.close()
    with transaccion() as c:
        agregar_columnas(c, COLUMNAS)
        for m in modulos:
            agregar_columnas(c, m.columnas)
            if m.migrar:
                m.migrar(c)
        primera_vez = not c.execute("SELECT 1 FROM usuarios").fetchone()
        if primera_vez:
            from .auth import hash_password
            salt, h = hash_password("admin")
            c.execute("INSERT INTO usuarios (usuario, nombre, password_hash, salt, es_admin, debe_cambiar, creado_en) "
                      "VALUES ('admin', 'Administrador', ?, ?, 1, 1, ?)", (h, salt, ahora()))
        for m in modulos:
            clave = f"ejemplos_{m.nombre}"
            if con_ejemplos and m.datos_iniciales and not c.execute("SELECT 1 FROM config WHERE clave=?", (clave,)).fetchone():
                m.datos_iniciales(c)
                c.execute("INSERT INTO config (clave, valor) VALUES (?, '1')", (clave,))
