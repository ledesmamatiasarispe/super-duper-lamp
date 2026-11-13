"""Actualización automática desde los releases de GitHub.

Al arrancar, la app consulta el último release de REPO (app/version.py). Si es más nuevo que la versión instalada, a
los administradores se les pregunta al entrar si quieren actualizar. "Ahora no" no vuelve a preguntar por una semana
(la fecha se guarda en la base, en config: vale para todos los administradores, porque la app es una sola).

MISMO ARCHIVO en UltraMantenimiento y Gestión Automotor (lo propio sale de version.py: APP, PREFIJO, REPO). Edificios
de Mamá tiene su propia versión (se instala también desde el código fuente y en Linux/Mac), con los mismos pasos.

Instalar:
1. Baja el .zip del release y controla su SHA-256 contra el .sha256 publicado al lado (sin ese archivo no se instala).
2. Lo descomprime en data/actualizacion/nueva controlando que ningún archivo se escriba fuera de esa carpeta.
3. Copia la base: data/<base>_antes_de_v<versión>.db (con la API de backup de SQLite; quedan las últimas
   COPIAS_A_GUARDAR).
4. Deja corriendo un .bat que espera a que la app se cierre, guarda el programa actual en data/actualizacion/anterior,
   copia el nuevo encima (sin tocar data/, donde están la base y los adjuntos) y, si la copia falla, vuelve a poner el
   anterior. Después abre la app.
La conexión a GitHub usa los certificados de Windows más los de certifi (ver _contexto_ssl).

Solo la versión compilada se instala sola; en desarrollo se informa la versión nueva pero se actualiza con git."""
import hashlib
import json
import os
import shutil
import sqlite3
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from . import db
from . import version as v
from .servicios import ErrorDeNegocio

# <PREFIJO>_API_ACTUALIZACION la reemplaza solo para probar la actualización completa contra un servidor local
API = os.environ.get(f"{v.PREFIJO}_API_ACTUALIZACION", "https://api.github.com/repos/{repo}/releases/latest")
EXE = v.APP + ".exe"
POSPONER_DIAS = 7
COPIAS_A_GUARDAR = 3   # copias de la base de antes de cada actualización
_CACHE_SEGUNDOS = 6 * 3600   # la consulta a GitHub se repite cada tanto, no en cada pantalla
_REINTENTO_SEGUNDOS = 10 * 60   # si falló, se vuelve a probar a los 10 minutos

_estado: dict = {}
_lock = threading.Lock()


def _numeros(etiqueta: str) -> tuple:
    """'v1.10.2' -> (1, 10, 2). Lo que no es número (un sufijo '-beta') se ignora."""
    partes = []
    for p in str(etiqueta).strip().lstrip("vV").split("."):
        num = "".join(ch for ch in p if ch.isdigit())
        partes.append(int(num) if num else 0)
    return tuple(partes)


def es_mas_nueva(etiqueta: str, actual: str = v.VERSION) -> bool:
    return _numeros(etiqueta) > _numeros(actual)


@lru_cache(maxsize=1)
def _contexto_ssl() -> ssl.SSLContext:
    """Los certificados raíz de Windows MÁS los de certifi (la lista de Mozilla, viaja dentro del programa).
    Windows no trae todas las raíces instaladas: las baja a medida que su propio navegador las pide, y Python no
    dispara esa descarga. En una PC que nunca abrió GitHub con Edge faltaba la raíz y la búsqueda fallaba con
    "unable to get local issuer certificate". Las de Windows siguen: ahí están las de un antivirus o proxy que revisa
    el HTTPS de la empresa, que certifi no conoce. (Lo resolvió primero Gestión Automotor.)"""
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except (ImportError, OSError):   # sin certifi queda el de Windows solo
        pass
    return ctx


SIN_CERTIFICADO = ("No se pudo verificar el certificado de GitHub desde esta PC. Suele ser un antivirus o un proxy que "
                   "revisa las conexiones HTTPS. Probá abrir https://github.com en el navegador de esta PC y volver a "
                   "buscar; si sigue, bajá el .zip desde la página del release y descomprimilo sobre la instalación "
                   "(la carpeta data no se toca).")


def _pedir(url: str, timeout: float = 10) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": v.APP + "/" + v.VERSION,
                                               "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_contexto_ssl()) as r:   # noqa: S310 (https de GitHub)
            return r.read()
    except urllib.error.URLError as e:
        if isinstance(e.reason, ssl.SSLCertVerificationError):
            raise ErrorDeNegocio(SIN_CERTIFICADO) from e
        raise


def _config(clave: str) -> str | None:
    with db.transaccion() as c:
        fila = c.execute("SELECT valor FROM config WHERE clave=?", (clave,)).fetchone()
        return fila[0] if fila else None


def _explicar_http(e: urllib.error.HTTPError) -> str:
    """El 403/429 por límite de consultas (60 por hora por IP sin usuario, compartido por toda la red) se explica
    con la hora en que se libera: no es una falla de la app ni del repositorio."""
    cabeceras = e.headers or {}
    if e.code in (403, 429) and cabeceras.get("X-RateLimit-Remaining") == "0":
        try:
            hora = time.strftime("%H:%M", time.localtime(int(cabeceras.get("X-RateLimit-Reset"))))
            cuando = f"Se libera a las {hora}"
        except (TypeError, ValueError):
            cuando = "Se libera en menos de una hora"
        return (f"GitHub limitó por un rato las consultas desde esta red (hasta 60 por hora). {cuando}; "
                "la app vuelve a intentar sola.")
    return f"No se pudo consultar GitHub (HTTP {e.code})."


def buscar(forzar: bool = False) -> dict:
    """El último release: versión, notas y el .zip a instalar. Guarda el resultado un rato para no consultar de más."""
    with _lock:
        # una consulta que salió bien vale unas horas; una que falló se reintenta pronto (corte de internet, límite)
        vigencia = _CACHE_SEGUNDOS if _estado and not _estado["error"] else _REINTENTO_SEGUNDOS
        if not forzar and _estado and time.time() - _estado["buscado"] < vigencia:
            return dict(_estado)
        info = {"buscado": time.time(), "buscado_en": time.strftime("%Y-%m-%d %H:%M"), "error": None,
                "nueva": None, "notas": "", "url_release": None, "zip": None, "sha256": None}
        if not v.REPO:
            info["error"] = "Todavía no hay un repositorio de actualizaciones configurado."
        else:
            try:
                rel = json.loads(_pedir(API.format(repo=v.REPO)))
                assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
                zips = [n for n in assets if n.lower().endswith(".zip")]
                info.update(nueva=rel.get("tag_name"), notas=(rel.get("body") or "")[:4000], url_release=rel.get("html_url"))
                if zips:
                    info["zip"] = {"nombre": zips[0], "url": assets[zips[0]]}
                    if zips[0] + ".sha256" in assets:
                        info["sha256"] = assets[zips[0] + ".sha256"]
            except ErrorDeNegocio as e:   # el certificado: el mensaje ya dice qué hacer
                info["error"] = str(e)
            except urllib.error.HTTPError as e:
                # 404 en releases/latest: el repositorio existe pero todavía no publicó ninguna versión (no es una falla)
                info["error"] = None if e.code == 404 else _explicar_http(e)
            except Exception as e:   # sin internet, repositorio mal escrito, límite de GitHub: no es un error de la app
                info["error"] = f"No se pudo consultar GitHub ({type(e).__name__}: {e})."
        _estado.clear()
        _estado.update(info)
        return dict(info)


def estado(es_admin: bool) -> dict:
    """Lo que necesita la pantalla: si hay versión nueva, y si corresponde preguntarle a este usuario ahora."""
    info = buscar()
    disponible = bool(info["nueva"] and es_mas_nueva(info["nueva"]))
    hasta = _config("actualizacion_pospuesta_hasta")
    pospuesta = bool(hasta and hasta > date.today().isoformat())
    return {"version": v.VERSION, "repo": v.REPO, "compilada": v.COMPILADA, "disponible": disponible,
            "nueva": info["nueva"], "notas": info["notas"], "url_release": info["url_release"],
            "instalable": disponible and bool(info["zip"] and info["sha256"]), "error": info["error"],
            "buscado_en": info["buscado_en"], "pospuesta_hasta": hasta if pospuesta else None,
            # solo se pregunta a un administrador, en la versión compilada (la única que se instala sola)
            "preguntar": es_admin and v.COMPILADA and disponible and not pospuesta}


def posponer() -> str:
    """'Ahora no': no se vuelve a preguntar hasta dentro de una semana."""
    hasta = (date.today() + timedelta(days=POSPONER_DIAS)).isoformat()
    with db.transaccion() as c:
        c.execute("INSERT INTO config (clave, valor) VALUES ('actualizacion_pospuesta_hasta', ?) "
                  "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (hasta,))
    return hasta


def _extraer(zip_path: Path, destino: Path) -> Path:
    """Descomprime controlando que nada se escriba fuera de `destino`. Devuelve la carpeta que tiene el .exe."""
    with zipfile.ZipFile(zip_path) as z:
        base = destino.resolve()
        for nombre in z.namelist():
            if not (base / nombre).resolve().is_relative_to(base):
                raise ErrorDeNegocio("El archivo de la actualización tiene rutas inválidas: no se instala.")
        z.extractall(destino)
    for exe in [destino / EXE, *destino.glob("*/" + EXE)]:
        if exe.is_file():
            return exe.parent
    raise ErrorDeNegocio(f"La actualización no trae {EXE}: no se instala.")


def preparar(info: dict, carpeta: Path) -> Path:
    """Baja el .zip, controla el SHA-256 y lo descomprime. Devuelve la carpeta con la versión nueva.
    Lo de la actualización anterior se borra, salvo anterior/ (el programa de antes, por si hay que volver a mano)."""
    carpeta.mkdir(parents=True, exist_ok=True)
    for viejo in carpeta.iterdir():
        if viejo.name != "anterior":
            shutil.rmtree(viejo, ignore_errors=True) if viejo.is_dir() else viejo.unlink(missing_ok=True)
    datos = _pedir(info["zip"]["url"], timeout=300)
    esperado = _pedir(info["sha256"]).decode("ascii", "replace").split()[0].strip().lower()
    if hashlib.sha256(datos).hexdigest() != esperado:
        raise ErrorDeNegocio("La descarga no coincide con su SHA-256 (archivo dañado o alterado): no se instala.")
    zip_path = carpeta / info["zip"]["nombre"]
    zip_path.write_bytes(datos)
    return _extraer(zip_path, carpeta / "nueva")


def respaldar_base(version_nueva: str) -> Path | None:
    """Copia la base antes de cambiar el programa: si la versión nueva la migra y algo sale mal, está la de antes.
    Con la API de backup de SQLite (consistente aunque haya otros usuarios conectados). Quedan las últimas
    COPIAS_A_GUARDAR."""
    if not db.DB_PATH.exists():
        return None
    copia = db.DB_PATH.with_name(f"{db.DB_PATH.stem}_antes_de_{version_nueva}.db")
    copia.unlink(missing_ok=True)
    origen, destino = db.conectar(), sqlite3.connect(copia)
    try:
        origen.backup(destino)
    finally:
        destino.close()
        origen.close()
    viejas = sorted(db.DB_PATH.parent.glob(f"{db.DB_PATH.stem}_antes_de_v*.db"), key=lambda f: f.stat().st_mtime)
    for vieja in viejas[:-COPIAS_A_GUARDAR]:
        vieja.unlink(missing_ok=True)
    return copia


def script_windows(*, nueva: Path, instalacion: Path, trabajo: Path, version_nueva: str, pid: int) -> str:
    """El .bat que instala con la app cerrada (Windows no deja pisar un programa abierto). robocopy sin /MIR: agrega y
    pisa, nunca borra, y /XD deja data/ como está. robocopy devuelve 8 o más cuando falla: ahí vuelve el anterior."""
    datos = db.DB_PATH.parent.resolve()
    anterior = trabajo / "anterior"
    log = trabajo.parent / "actualizacion.log"
    return f"""@echo off
chcp 65001 >nul
echo Actualizando {v.APP} a {version_nueva}...
:esperar
tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul && (timeout /t 1 /nobreak >nul & goto esperar)
if exist "{anterior}" rmdir /S /Q "{anterior}"
robocopy "{instalacion}" "{anterior}" /E /XD "{datos}" /R:2 /W:1 /NP /LOG:"{log}"
robocopy "{nueva}" "{instalacion}" /E /XD "{datos}" /R:10 /W:2 /NP /LOG+:"{log}"
if errorlevel 8 (
  echo No se pudo copiar la version nueva: se vuelve a poner la anterior.
  robocopy "{anterior}" "{instalacion}" /E /XD "{datos}" /R:10 /W:2 /NP /LOG+:"{log}"
)
start "" "{instalacion / EXE}"
rmdir /S /Q "{nueva}"
del "%~f0"
"""


def instalar() -> dict:
    """Prepara la versión nueva, copia la base y deja un .bat que instala cuando la app se cierra (se cierra sola)."""
    if not v.COMPILADA:
        raise ErrorDeNegocio("La actualización automática es para la versión compilada. En desarrollo, se actualiza con git.")
    info = buscar(forzar=True)
    if not (info["nueva"] and es_mas_nueva(info["nueva"])):
        raise ErrorDeNegocio("No hay una versión más nueva para instalar.")
    if not (info["zip"] and info["sha256"]):
        raise ErrorDeNegocio("El release no trae el .zip y su .sha256: no se puede instalar automáticamente.")
    trabajo = db.DB_PATH.parent / "actualizacion"
    nueva = preparar(info, trabajo)
    respaldar_base(info["nueva"])
    bat = Path(tempfile.gettempdir()) / f"actualizar_{v.APP.lower()}_{os.getpid()}.bat"
    bat.write_text(script_windows(nueva=nueva, instalacion=Path(sys.executable).resolve().parent, trabajo=trabajo,
                                  version_nueva=info["nueva"], pid=os.getpid()), encoding="utf-8")
    subprocess.Popen(["cmd", "/c", str(bat)], close_fds=True,
                     creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP)
    threading.Timer(1.5, os._exit, [0]).start()   # deja salir la respuesta antes de cerrarse
    return {"ok": True, "nueva": info["nueva"]}


def buscar_en_segundo_plano() -> None:
    """Al arrancar: consulta GitHub sin demorar el inicio (la respuesta queda guardada para cuando entre alguien)."""
    if v.REPO:
        threading.Thread(target=buscar, daemon=True).start()
