"""Actualización automática desde los releases de GitHub.

Al arrancar, la app consulta el último release de REPO (app/version.py). Si es más nuevo que la versión instalada, a
los administradores se les pregunta al entrar si quieren actualizar. "Ahora no" no vuelve a preguntar por una semana
(la fecha se guarda en la base, en config: vale para todos los administradores, porque la app es una sola).

Instalar: baja el .zip del release, controla su SHA-256 contra el .sha256 publicado al lado (sin ese archivo no se
instala), lo descomprime en data/actualizacion/ y deja corriendo un .bat que espera a que la app se cierre, copia los
archivos nuevos sobre la instalación (sin tocar data/, donde están la base y los adjuntos) y la vuelve a abrir.

Solo la versión compilada se instala sola; en desarrollo se informa la versión nueva pero se actualiza con git."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile
from datetime import date, timedelta
from pathlib import Path

from . import db
from . import version as v
from .servicios import ErrorDeNegocio

# MANT_API_ACTUALIZACION la reemplaza solo para probar la actualización completa contra un servidor local
API = os.environ.get("MANT_API_ACTUALIZACION", "https://api.github.com/repos/{repo}/releases/latest")
EXE = "MantenimientoRomero.exe"
POSPONER_DIAS = 7
_CACHE_SEGUNDOS = 6 * 3600   # la consulta a GitHub se repite cada tanto, no en cada pantalla

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


def _pedir(url: str, timeout: float = 10) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "MantenimientoRomero/" + v.VERSION,
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310 (siempre https de GitHub)
        return r.read()


def _config(clave: str) -> str | None:
    with db.transaccion() as c:
        fila = c.execute("SELECT valor FROM config WHERE clave=?", (clave,)).fetchone()
        return fila[0] if fila else None


def buscar(forzar: bool = False) -> dict:
    """El último release: versión, notas y el .zip a instalar. Guarda el resultado un rato para no consultar de más."""
    with _lock:
        if not forzar and _estado and time.time() - _estado["buscado"] < _CACHE_SEGUNDOS:
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
    """Baja el .zip, controla el SHA-256 y lo descomprime. Devuelve la carpeta con la versión nueva."""
    if carpeta.exists():
        shutil.rmtree(carpeta, ignore_errors=True)
    carpeta.mkdir(parents=True)
    datos = _pedir(info["zip"]["url"], timeout=300)
    esperado = _pedir(info["sha256"]).decode("ascii", "replace").split()[0].strip().lower()
    if hashlib.sha256(datos).hexdigest() != esperado:
        raise ErrorDeNegocio("La descarga no coincide con su SHA-256 (archivo dañado o alterado): no se instala.")
    zip_path = carpeta / info["zip"]["nombre"]
    zip_path.write_bytes(datos)
    return _extraer(zip_path, carpeta / "nueva")


def instalar() -> dict:
    """Prepara la versión nueva y deja un .bat que la copia cuando la app se cierra; la app se cierra sola enseguida."""
    if not v.COMPILADA:
        raise ErrorDeNegocio("La actualización automática es para la versión compilada. En desarrollo, se actualiza con git.")
    info = buscar(forzar=True)
    if not (info["nueva"] and es_mas_nueva(info["nueva"])):
        raise ErrorDeNegocio("No hay una versión más nueva para instalar.")
    if not (info["zip"] and info["sha256"]):
        raise ErrorDeNegocio("El release no trae el .zip y su .sha256: no se puede instalar automáticamente.")
    instalacion = Path(sys.executable).resolve().parent
    trabajo = db.DB_PATH.parent / "actualizacion"
    nueva = preparar(info, trabajo)
    log = trabajo.parent / "actualizacion.log"
    bat = Path(tempfile.gettempdir()) / f"actualizar_mantenimiento_{os.getpid()}.bat"
    datos = db.DB_PATH.parent.resolve()
    # robocopy sin /MIR: agrega y pisa, nunca borra (así data/ y cualquier archivo propio de la instalación quedan)
    bat.write_text(f"""@echo off
chcp 65001 >nul
echo Actualizando Mantenimiento a {info['nueva']}...
:esperar
tasklist /FI "PID eq {os.getpid()}" 2>nul | find "{os.getpid()}" >nul && (timeout /t 1 /nobreak >nul & goto esperar)
robocopy "{nueva}" "{instalacion}" /E /XD "{datos}" /R:10 /W:2 /NP /LOG:"{log}"
start "" "{instalacion / EXE}"
rmdir /S /Q "{trabajo}"
del "%~f0"
""", encoding="utf-8")
    subprocess.Popen(["cmd", "/c", str(bat)], close_fds=True,
                     creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP)
    threading.Timer(1.5, os._exit, [0]).start()   # deja salir la respuesta antes de cerrarse
    return {"ok": True, "nueva": info["nueva"]}


def buscar_en_segundo_plano() -> None:
    """Al arrancar: consulta GitHub sin demorar el inicio (la respuesta queda guardada para cuando entre alguien)."""
    if v.REPO:
        threading.Thread(target=buscar, daemon=True).start()
