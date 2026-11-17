"""El asistente: la barra "Preguntá algo" de arriba de todo. No sabe nada del negocio: cada módulo de la app le registra
una FUENTE que sabe contestar sobre lo suyo (ver modulos/mantenimiento/asistente.py en UltraMantenimiento).

Una pregunta se contesta así, en este orden:
  1. RESPUESTA DIRECTA: si una fuente la sabe contestar sin IA (listas, cuentas, vencimientos), contesta ella. Es
     instantáneo y exacto; justo donde un modelo chico se equivoca (confunde "no hay ninguna" con "no tengo el dato").
  2. CON IA: si no, cada fuente junta los DATOS que vienen al caso (ya resumidos y calculados) y la IA local solo los
     redacta. Nunca inventa de dónde sacar algo: lo que no está en los datos, "No figura en la app".
  3. SIN IA: si la IA no está instalada o no responde, se muestra el resumen que la fuente armó con esos mismos datos.
     La barra sirve igual, como buscador.

La IA es local (Ollama, en esta PC o en otra de la red): no sale nada a internet. Se configura en Opciones."""
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

from nucleo import validar
from nucleo.db import transaccion
from nucleo.errores import ErrorDeNegocio
from nucleo.marca import guardar_config, leer_config

URL_DEFECTO = "http://127.0.0.1:11434"
MODELO_DEFECTO = "qwen2.5:3b"
_CLAVE_URL, _CLAVE_MODELO = "asistente_url", "asistente_modelo"
MAX_PREGUNTA = 300

SISTEMA = """Sos el asistente de la app. Respondés en español rioplatense, claro y en pocas oraciones.
Reglas:
- Usá SOLO la información de DATOS. No inventes fechas, horas, nombres, cantidades ni repuestos.
- Los números ya están calculados en DATOS: copialos tal cual, no hagas cuentas.
- Si lo que se pregunta no figura en DATOS, decí "No figura en la app" y nada más.
- Cuando des una fecha o un dato, decí de dónde sale (registro, correctivo, instructivo, horómetro...).
- No repitas los DATOS enteros: contestá la pregunta."""


@dataclass
class Fuente:
    """Lo que un módulo le enseña al asistente. Las funciones reciben la pregunta tal como se escribió y devuelven
    None si no es de su tema.
      responder(pregunta) -> {"texto": str, "enlaces": [...]}                 contesta sin IA (exacto, instantáneo)
      contexto(pregunta)  -> {"titulo": str, "datos": str, "resumen": str, "enlaces": [...], "si_no_figura": {...}}
                             datos: lo que lee la IA (texto corto, ya calculado; mejor < 1500 palabras)
                             resumen: lo que se muestra si no hay IA
                             si_no_figura (opcional): {"texto", "enlace"} que la pantalla ofrece si la IA contesta
                             "No figura en la app" (por ejemplo: cargar ese dato que falta)
      sin_resultado(pregunta) -> {"texto", "enlaces"}    qué decir cuando nadie encontró nada (en vez de "No encontré")
      ejemplos: preguntas que funcionan bien, para la respuesta a "ayuda".
    Un enlace es {"texto": "Ver instructivo", "ir": "instructivos/5"} (la pantalla hace irA) o
    {"texto": "Cargar especificación", "accion": "especificacion", "datos": {...}}: la pantalla llama a la función que el
    módulo registró en window.asisAcciones.especificacion(datos). La acción "preguntar" ({"pregunta"}) es del asistente."""
    nombre: str
    responder: Callable[[str], dict | None] | None = None
    contexto: Callable[[str], dict | None] | None = None
    sin_resultado: Callable[[str], dict | None] | None = None
    ejemplos: list[str] = field(default_factory=list)


FUENTES: list[Fuente] = []


def registrar(fuente: Fuente) -> None:
    """Idempotente por nombre: registrar dos veces la misma fuente (tests, recargas) la reemplaza."""
    FUENTES[:] = [f for f in FUENTES if f.nombre != fuente.nombre] + [fuente]


# ── ajustes ──
def ajustes() -> dict:
    with transaccion() as c:
        return {"url": leer_config(c, _CLAVE_URL) or URL_DEFECTO, "modelo": leer_config(c, _CLAVE_MODELO) or MODELO_DEFECTO}


def guardar_ajustes(usuario: dict, *, url=None, modelo=None) -> dict:
    url = validar.texto(url, "la dirección de la IA", obligatorio=False, maximo=200).rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        raise ErrorDeNegocio("La dirección de la IA empieza con http:// (por ejemplo, http://127.0.0.1:11434).")
    modelo = validar.texto(modelo, "el modelo", obligatorio=False, maximo=100)
    with transaccion() as c:
        guardar_config(c, _CLAVE_URL, None if not url or url == URL_DEFECTO else url)
        guardar_config(c, _CLAVE_MODELO, None if not modelo or modelo == MODELO_DEFECTO else modelo)
    _ESTADO.clear()
    return estado(forzar=True)


# ── la IA (Ollama) ──
_ESTADO: dict = {}


def estado(forzar: bool = False) -> dict:
    """¿Hay IA? Pregunta a Ollama qué modelos tiene (con 2 s de espera como mucho) y lo recuerda 30 s, para que abrir
    la pantalla no espere a una IA apagada cada vez."""
    a = ajustes()
    if not forzar and _ESTADO.get("hasta", 0) > time.time() and _ESTADO.get("clave") == (a["url"], a["modelo"]):
        return _ESTADO["valor"]
    try:
        with urllib.request.urlopen(a["url"] + "/api/tags", timeout=2) as r:
            modelos = sorted(m["name"] for m in json.loads(r.read()).get("models", []))
        if a["modelo"] in modelos:
            valor = {"disponible": True, "motivo": "", "modelos": modelos, **a}
        else:
            valor = {"disponible": False, "modelos": modelos, **a,
                     "motivo": f"Ollama está instalado pero no tiene el modelo {a['modelo']}"
                               + (f" (tiene: {', '.join(modelos)})." if modelos else ". Hay que bajarlo: ollama pull " + a["modelo"])}
    except (OSError, ValueError):
        valor = {"disponible": False, "modelos": [], **a,
                 "motivo": "No se encontró la IA local (Ollama) en " + a["url"] + ". Sin ella, la barra busca y muestra un resumen. "
                           "Si estaba andando, un administrador la puede reiniciar desde Opciones."}
    _ESTADO.update(hasta=time.time() + 30, clave=(a["url"], a["modelo"]), valor=valor)
    return valor


# ── reiniciar la IA (si se colgó o se cerró) ──
_ES_LOCAL = ("http://127.0.0.1", "http://localhost", "https://127.0.0.1", "https://localhost")


def _carpeta_ollama() -> Path | None:
    """Dónde está instalado Ollama: lo que dice Windows (Programas instalados), el PATH o las carpetas de fábrica."""
    candidatas = []
    try:
        import winreg
        for raiz in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(raiz, r"Software\Microsoft\Windows\CurrentVersion\Uninstall") as k:
                    for i in range(winreg.QueryInfoKey(k)[0]):
                        with winreg.OpenKey(k, winreg.EnumKey(k, i)) as sub:
                            try:
                                if "ollama" in str(winreg.QueryValueEx(sub, "DisplayName")[0]).lower():
                                    candidatas.append(Path(winreg.QueryValueEx(sub, "InstallLocation")[0]))
                            except OSError:
                                pass
            except OSError:
                pass
    except ImportError:   # no es Windows
        pass
    if shutil.which("ollama"):
        candidatas.append(Path(shutil.which("ollama")).parent)
    candidatas += [Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama", Path(r"C:\Program Files\Ollama")]
    return next((c for c in candidatas if (c / "ollama.exe").exists()), None)


def _entorno_del_usuario() -> dict:
    """Las variables de entorno como las ve Windows ahora (por ejemplo OLLAMA_MODELS, que dice en qué disco están los
    modelos), aunque esta app se haya abierto antes de que se configuraran."""
    entorno = dict(os.environ)
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            for i in range(winreg.QueryInfoKey(k)[1]):
                nombre, valor, _ = winreg.EnumValue(k, i)
                if nombre.upper().startswith("OLLAMA"):
                    entorno[nombre] = valor
    except (ImportError, OSError):
        pass
    return entorno


def _cerrar_ollama(carpeta: Path) -> None:
    """Cierra SOLO los procesos que salen de la carpeta de Ollama (el servidor, la app de la bandeja y el que corre el
    modelo): ningún otro programa de la PC."""
    filtro = (str(carpeta).rstrip("\\") + "\\*").replace("'", "''")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                    f"Get-CimInstance Win32_Process | Where-Object {{ $_.ExecutablePath -like '{filtro}' }} | "
                    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"],
                   capture_output=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _abrir_ollama(carpeta: Path) -> None:
    """Arranca el servidor de Ollama (ollama serve), sin ventana. NO se abre la app de la bandeja ("ollama app.exe"):
    abierta desde otro programa, en la prueba abría pero su servidor no arrancaba nunca. El servidor solo sí (responde
    en ~6 s). Hasta reiniciar la PC no se ve el ícono de Ollama en la bandeja; al reiniciar, Windows la abre como siempre."""
    orden = [str(carpeta / "ollama.exe"), "serve"]
    comun = dict(cwd=str(carpeta), env=_entorno_del_usuario(), close_fds=True,
                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sin_ventana = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:   # que siga vivo aunque se cierre esta app (si Windows lo permite)
        subprocess.Popen(orden, creationflags=sin_ventana | getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0), **comun)
    except OSError:
        subprocess.Popen(orden, creationflags=sin_ventana, **comun)


def reiniciar(usuario: dict, espera: float = 45) -> dict:
    """Cierra Ollama y lo vuelve a abrir, y espera (hasta `espera` segundos) a que responda. Solo si la IA corre en esta
    PC: si está en otra de la red, se reinicia allá."""
    a = ajustes()
    if not a["url"].startswith(_ES_LOCAL):
        raise ErrorDeNegocio(f"La IA está en otra PC ({a['url']}): hay que reiniciarla en esa PC.")
    carpeta = _carpeta_ollama()
    if not carpeta:
        raise ErrorDeNegocio("No se encontró Ollama instalado en esta PC. Se baja gratis de ollama.com.")
    _cerrar_ollama(carpeta)
    time.sleep(1.5)
    _abrir_ollama(carpeta)
    limite = time.time() + espera
    while time.time() < limite:
        time.sleep(1.5)
        e = estado(forzar=True)
        if e["disponible"] or e["modelos"]:   # ya responde (con o sin el modelo elegido)
            return e
    raise ErrorDeNegocio(f"Se volvió a abrir Ollama pero no respondió en {espera:.0f} segundos. Probá de nuevo en un rato "
                         "o reiniciá la PC.")


def _ia(pregunta: str, datos: str, a: dict) -> Iterator[str]:
    """Los pedazos de texto a medida que la IA los escribe (Ollama, /api/chat en modo stream)."""
    cuerpo = {"model": a["modelo"], "stream": True, "keep_alive": "30m",
              "options": {"temperature": 0.1, "num_ctx": 3072},
              "messages": [{"role": "system", "content": SISTEMA},
                           {"role": "user", "content": f"DATOS:\n{datos}\n\nPREGUNTA: {pregunta}"}]}
    pedido = urllib.request.Request(a["url"] + "/api/chat", data=json.dumps(cuerpo).encode(),
                                    headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(pedido, timeout=300) as r:
        for linea in r:
            if not linea.strip():
                continue
            parte = json.loads(linea)
            if parte.get("error"):
                raise RuntimeError(parte["error"])
            if parte.get("message", {}).get("content"):
                yield parte["message"]["content"]
            if parte.get("done"):
                return


# ── preguntar ──
def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


_SALUDO = re.compile(r"^\W*(hola|buenas|buen dia|buenos dias|buenas tardes|ayuda|ayudame|help|menu|"
                     r"que (podes|puedo|sabes)( hacer| preguntar| preguntarte)?|"
                     r"como (funciona|te uso|se usa) (esto|esta barra|la barra)|que (sos|es esto))\W*$")
# preguntas de USO de la app ("¿cómo cargo un correctivo?"): se contestan con los textos de la Ayuda de las pantallas.
# "¿cómo se hace el servicio B?" NO es de uso: es del instructivo de la máquina (lo contesta el módulo).
_DE_USO = re.compile(r"\b(como (cargo|registro|agrego|anoto|creo|borro|elimino|edito|modifico|imprimo|cambio|uso|veo|encuentro|"
                     r"marco|programo|doy de (alta|baja)|reactivo|subo|asigno|dibujo|ubico|busco|reinicio)|como se (carga|registra|"
                     r"agrega|anota|crea|borra|elimina|edita|modifica|imprime|cambia|usa|ve|programa|marca|sube|asigna|dibuja|ubica)|"
                     r"donde (veo|cargo|esta|estan|se ve|se carga|encuentro|anoto)|para que sirve|que significa|que quiere decir)\b")
_VACIAS = set("como cargo registro agrego creo donde esta estan para que sirve significa quiere decir hago hace hacer "
              "una uno unos unas los las del con por sobre esto este esta".split())


def _ayuda(pregunta: str) -> dict:
    ejemplos = [e for f in FUENTES for e in f.ejemplos][:6]
    texto = "\n".join([
        "Soy la barra de preguntas: contesto con lo que está cargado en la app.",
        "- Lo que se calcula (vencidos, pendientes, lecturas) lo contesta la app al instante.",
        "- Lo demás lo redacta una IA que corre en esta PC, solo con los datos cargados: si algo no está, te lo digo.",
        "- También explico cómo se usa cada pantalla («¿cómo cargo…?»).",
    ] + (["Probá con alguna de estas:"] if ejemplos else []))
    return {"titulo": "Ayuda", "texto": texto,
            "enlaces": [{"texto": e, "accion": "preguntar", "datos": {"pregunta": e}} for e in ejemplos]}


def _manual(pregunta: str, ayuda: list) -> dict | None:
    """Los pasos de la Ayuda (los manda la pantalla: Ayuda.pasos de cada módulo) que comparten palabras con la pregunta."""
    buscadas = {p for p in re.findall(r"[a-z0-9]+", _norm(pregunta)) if len(p) >= 4 and p not in _VACIAS}
    if not buscadas or not isinstance(ayuda, list):
        return None

    def puntos(paso):
        palabras = set(re.findall(r"[a-z0-9]+", _norm(f"{paso.get('pantalla', '')} {paso.get('titulo', '')} {paso.get('texto', '')}")))
        return sum(1 for b in buscadas if b in palabras or b.rstrip("s") in palabras or b + "s" in palabras)
    pasos = [p for p in ayuda[:400] if isinstance(p, dict)]
    elegidos = sorted((x for x in pasos if puntos(x)), key=puntos, reverse=True)[:6]
    if not elegidos:
        return None
    lineas = [f"- Pantalla {validar.corto(p.get('pantalla'), 40)} · {validar.corto(p.get('titulo'), 120)}: "
              f"{validar.corto(p.get('texto'), 700)}" for p in elegidos]
    vistas = []
    for p in elegidos:
        v = validar.corto(p.get("pantalla"), 40)
        if v and v not in vistas and re.fullmatch(r"[a-z_]+", v):
            vistas.append(v)
    salto = "\n"
    return {"titulo": "Cómo se usa la app", "datos": "AYUDA DE LA APP (cómo se usa cada pantalla):" + salto + salto.join(lineas),
            "resumen": "Lo que dice la Ayuda:" + salto + salto.join(lineas),
            "enlaces": [{"texto": f"Ir a {v}", "ir": v} for v in vistas[:3]]}


def preguntar(pregunta, ayuda: list | None = None) -> Iterator[dict]:
    """La respuesta como una serie de eventos (para mostrarla a medida que se escribe):
      {"tipo": "inicio", "modo": "directa"|"ia"|"resumen"|"nada", "titulo", "enlaces", "aviso", "si_no_figura"}
      {"tipo": "texto", "texto": "..."}        (uno o muchos)
      {"tipo": "fin", "segundos": 3.2}
    Orden: "ayuda"/"hola" -> lo que un módulo contesta sin IA -> si es de USO de la app, la Ayuda de las pantallas
    (`ayuda`: [{pantalla, titulo, texto}], la manda la pantalla) -> los datos de los módulos con IA -> si nadie encontró
    nada, lo que proponga un módulo (sin_resultado). Si la IA falla a mitad de camino, se muestra el resumen."""
    q = validar.texto(pregunta, "la pregunta", maximo=MAX_PREGUNTA)
    t0 = time.time()
    doble = "\n\n"

    def fin():
        return {"tipo": "fin", "segundos": round(time.time() - t0, 1)}

    def directa(r, modo="directa"):
        yield {"tipo": "inicio", "modo": modo, "titulo": r.get("titulo", ""), "enlaces": r.get("enlaces", []), "aviso": ""}
        yield {"tipo": "texto", "texto": r["texto"]}
        yield fin()

    if _SALUDO.match(_norm(q)):
        yield from directa(_ayuda(q))
        return
    for f in FUENTES:
        r = f.responder(q) if f.responder else None
        if r:
            yield from directa(r)
            return

    manual = _manual(q, ayuda or []) if _DE_USO.search(_norm(q)) else None
    contextos = [manual] if manual else [x for x in (f.contexto(q) for f in FUENTES if f.contexto) if x]
    if not contextos:
        for f in FUENTES:
            r = f.sin_resultado(q) if f.sin_resultado else None
            if r:
                yield from directa(r, "nada")
                return
        yield from directa({"texto": "No encontré nada sobre eso en la app. Escribí «ayuda» para ver qué se puede preguntar."}, "nada")
        return
    titulo = " · ".join(x["titulo"] for x in contextos if x.get("titulo"))
    enlaces = [e for x in contextos for e in x.get("enlaces", [])]
    resumen = doble.join(x["resumen"] for x in contextos if x.get("resumen"))
    si_no_figura = next((x["si_no_figura"] for x in contextos if x.get("si_no_figura")), None)
    est = estado()
    if not est["disponible"]:
        yield {"tipo": "inicio", "modo": "resumen", "titulo": titulo, "enlaces": enlaces, "aviso": est["motivo"],
               "si_no_figura": si_no_figura}
        yield {"tipo": "texto", "texto": resumen}
        yield fin()
        return

    yield {"tipo": "inicio", "modo": "ia", "titulo": titulo, "enlaces": enlaces, "aviso": "", "si_no_figura": si_no_figura}
    escrito = False
    try:
        for pedazo in _ia(q, doble.join(x["datos"] for x in contextos), est):
            escrito = True
            yield {"tipo": "texto", "texto": pedazo}
    except (OSError, ValueError, RuntimeError) as e:
        _ESTADO.clear()
        yield {"tipo": "aviso", "aviso": f"La IA local no respondió ({e}). Esto es lo que dice la app:"}
        yield {"tipo": "texto", "texto": (doble if escrito else "") + resumen}
    yield fin()
