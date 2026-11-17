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

from . import textos

URL_DEFECTO = "http://127.0.0.1:11434"
MODELO_DEFECTO = "qwen2.5:3b"
_CLAVE_URL, _CLAVE_MODELO = "asistente_url", "asistente_modelo"
MAX_PREGUNTA = 300
# La conversación que se recuerda (la manda la pantalla): las últimas preguntas y respuestas, hasta ~1800 caracteres
# (unos 500 tokens). Alcanza para entender "¿y eso cuándo fue?" sin comerse la memoria de un modelo chico (num_ctx 3072,
# donde los DATOS de una máquina ya ocupan bastante).
MAX_TURNOS, MAX_CARACTERES_HISTORIAL, MAX_RESPUESTA_RECORDADA = 6, 1800, 450

# La IA ELIGE, no redacta: recibe los datos en fragmentos numerados y contesta con los números de los que sirven (que
# la app muestra tal cual) y como mucho una oración corta. Escribir es lo caro en una PC sin placa de video (unos 7
# tokens por segundo; leer es 10 a 100 veces más rápido): una respuesta así son ~20 tokens en vez de 100-200, y lo que se
# muestra es copia fiel de la app, sin fechas ni números reescritos.
MAX_PARTES = 5
SISTEMA = """Sos el asistente de una app. Te paso FRAGMENTOS numerados con lo que dice la app y una PREGUNTA.
Tu trabajo es ELEGIR, no escribir. Contestás en JSON:
- "partes": los números de los fragmentos que contestan la pregunta, el más importante primero (como mucho 5).
  La app los muestra tal cual, así que no hace falta repetirlos.
- "respuesta": UNA oración corta (máximo 20 palabras, español rioplatense) que conteste directo, usando SOLO lo que
  dicen esos fragmentos. Puede quedar vacía si los fragmentos ya lo dicen todo.
- Si ningún fragmento contesta la pregunta: "partes": [] y "respuesta": "No figura en la app".
Nunca inventes fechas, horas, nombres, cantidades ni repuestos: los números ya están calculados en los fragmentos.
Las preguntas anteriores de la conversación sirven para entender a qué se refiere la pregunta nueva."""
_FORMATO = {"type": "object", "required": ["partes", "respuesta"],
            "properties": {"partes": {"type": "array", "items": {"type": "integer"}}, "respuesta": {"type": "string"}}}


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
      temas(pregunta) -> [str]   de qué cosa habla la pregunta (por ejemplo ["EQ-001"]; varias si el nombre es de varias;
                                 [] si no nombra ninguna). Es lo que permite seguir la conversación: si la pregunta no
                                 nombra nada ("¿y el aceite?"), se le agrega el tema de la anterior: "¿y el aceite? (EQ-001)".
                                 Por eso el tema tiene que ser algo que la misma fuente reconozca escrito entre paréntesis.
      ejemplos: preguntas que funcionan bien, para la respuesta a "ayuda".
      fichas() -> [{"tipo", "titulo", "texto", "ir"}]   un texto corto y ya armado por cada cosa cargada (una máquina, un
                                 correctivo...). Se buscan cuando nadie dio un contexto (ver textos.py).
      guia: ruta a un .md con cómo se usa lo del módulo, para la IA (secciones "## ...", ver textos.py).
      sinonimos: ruta a un .txt con palabras que en el módulo quieren decir lo mismo (un grupo por renglón).
    Un enlace es {"texto": "Ver instructivo", "ir": "instructivos/5"} (la pantalla hace irA) o
    {"texto": "Cargar especificación", "accion": "especificacion", "datos": {...}}: la pantalla llama a la función que el
    módulo registró en window.asisAcciones.especificacion(datos). La acción "preguntar" ({"pregunta"}) es del asistente."""
    nombre: str
    responder: Callable[[str], dict | None] | None = None
    contexto: Callable[[str], dict | None] | None = None
    sin_resultado: Callable[[str], dict | None] | None = None
    ejemplos: list[str] = field(default_factory=list)
    temas: Callable[[str], list[str]] | None = None
    fichas: Callable[[], list[dict]] | None = None
    guia: Path | str | None = None
    sinonimos: Path | str | None = None


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


def _ia(pregunta: str, fragmentos: list[dict], a: dict, historial: list | None = None) -> dict:
    """Le pide a la IA (Ollama, /api/chat) que elija: {"partes": [números], "respuesta": "..."}. El JSON lo fuerza
    Ollama con el esquema (_FORMATO). La conversación va antes, como preguntas y respuestas; los fragmentos solo en la
    pregunta de ahora (son los vigentes)."""
    anteriores = []
    for t in historial or []:
        anteriores += [{"role": "user", "content": t["pregunta"]}, {"role": "assistant", "content": t["respuesta"]}]
    lista = "\n".join(f"[{i}] {f['grupo'] + ' › ' if f['grupo'] else ''}{f['texto']}" for i, f in enumerate(fragmentos, 1))
    cuerpo = {"model": a["modelo"], "stream": True, "keep_alive": "30m", "format": _FORMATO,
              "options": {"temperature": 0.1, "num_ctx": 3072, "num_predict": 160},
              "messages": [{"role": "system", "content": SISTEMA}, *anteriores,
                           {"role": "user", "content": f"FRAGMENTOS:\n{lista}\n\nPREGUNTA: {pregunta}"}]}
    pedido = urllib.request.Request(a["url"] + "/api/chat", data=json.dumps(cuerpo).encode(),
                                    headers={"Content-Type": "application/json"})
    escrito = []
    with urllib.request.urlopen(pedido, timeout=300) as r:
        for linea in r:
            if not linea.strip():
                continue
            parte = json.loads(linea)
            if parte.get("error"):
                raise RuntimeError(parte["error"])
            escrito.append(parte.get("message", {}).get("content") or "")
            if parte.get("done"):
                break
    try:
        elegido = json.loads("".join(escrito))
    except ValueError:
        raise RuntimeError("la IA no contestó en el formato pedido") from None
    if not isinstance(elegido, dict):
        raise RuntimeError("la IA no contestó en el formato pedido")
    return elegido


def _fragmentos(contexto: dict) -> list[dict]:
    """Los pedazos que la IA puede elegir: los que trae el contexto ({grupo, texto}) o, si no, los renglones de sus
    `datos`. Un renglón que no empieza con "- " es un título ("PLAN (tareas):") y se lo pone como grupo de los "- "
    que lo siguen, para que cada pedazo se entienda solo."""
    if contexto.get("fragmentos"):
        return [{"grupo": str(f.get("grupo") or ""), "texto": str(f.get("texto") or "")} for f in contexto["fragmentos"]
                if f.get("texto")]
    salida, grupo = [], ""
    for renglon in str(contexto.get("datos") or "").splitlines():
        renglon = renglon.strip()
        if not renglon:
            continue
        if renglon.startswith("- "):
            salida.append({"grupo": grupo, "texto": renglon[2:]})
            continue
        titulo, dos_puntos, resto = renglon.partition(":")
        # "PLAN (tareas)" -> "Plan (tareas)", "INSTRUCTIVO IT01 (...)" -> "Instructivo IT01 (...)": los códigos quedan
        titulo = " ".join(p.lower() if p.isalpha() and p.isupper() else p for p in titulo.split())
        titulo = titulo[:1].upper() + titulo[1:]
        grupo = titulo if dos_puntos and len(titulo) <= 60 else ""
        if resto.strip() or not dos_puntos:
            salida.append({"grupo": "", "texto": renglon})
    return salida


def _fecha_legible(t: str) -> str:
    return re.sub(r"\b(\d{4})-(\d{2})-(\d{2})\b", r"\3/\2/\1", t)


def _componer(elegido: dict, fragmentos: list[dict]) -> str:
    """El texto que se muestra: la oración de la IA y, debajo, los fragmentos que eligió, tal cual (los del mismo grupo
    juntos). Si no eligió ninguno, "No figura en la app" (y la pantalla ofrece cargar el dato, si el módulo lo propone)."""
    numeros = []
    for n in elegido.get("partes") or []:
        if isinstance(n, int) and 1 <= n <= len(fragmentos) and n not in numeros:
            numeros.append(n)
    numeros = numeros[:MAX_PARTES]
    respuesta = _fecha_legible(" ".join(str(elegido.get("respuesta") or "").split())[:300])
    if not numeros:
        return respuesta if "no figura" in respuesta.lower() else "No figura en la app."
    grupos: dict[str, list[str]] = {}
    for n in numeros:
        f = fragmentos[n - 1]
        grupos.setdefault(f["grupo"], []).append(_fecha_legible(f["texto"]))
    lineas = [f"- **{g}:** {' '.join(t)}" if g else f"- {' '.join(t)}" for g, t in grupos.items()]
    return (respuesta + "\n" if respuesta else "") + "\n".join(lineas)


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
                     r"donde (veo|cargo|esta|estan|se ve|se carga|encuentro|anoto)|para que sirve|que significa|que quiere decir|"
                     r"como (funciona|se calcula|se cuenta|anda)|explicame|"
                     r"que pasa (si|cuando)|"
                     r"(como|donde) (lo |la |los |las |le )(cargo|registro|agrego|anoto|borro|elimino|edito|cambio|veo|imprimo)|"
                     r"(quiero|tengo que|necesito|como hago para|como puedo|donde puedo) (anotar|cargar|registrar|agregar|"
                     r"borrar|eliminar|editar|modificar|cambiar|imprimir|ver|dar de (alta|baja)|programar|reactivar))\b")
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


def _historial(historial) -> list[dict]:
    """La conversación que manda la pantalla, limpia y recortada: los últimos turnos que entran en el tope de caracteres
    (los más nuevos primero en entrar). Cada turno: {pregunta, respuesta, tema}."""
    turnos = []
    for t in (historial if isinstance(historial, list) else [])[-MAX_TURNOS:]:
        if isinstance(t, dict) and validar.corto(t.get("pregunta"), MAX_PREGUNTA):
            respuesta = validar.corto(t.get("respuesta"), 4000)
            if len(respuesta) > MAX_RESPUESTA_RECORDADA:
                respuesta = respuesta[:MAX_RESPUESTA_RECORDADA].rsplit(" ", 1)[0] + " […]"
            turnos.append({"pregunta": validar.corto(t.get("pregunta"), MAX_PREGUNTA),
                           "respuesta": respuesta or "(sin respuesta)", "tema": validar.corto(t.get("tema"), 60)})
    elegidos, total = [], 0
    for t in reversed(turnos):
        total += len(t["pregunta"]) + len(t["respuesta"])
        if total > MAX_CARACTERES_HISTORIAL and elegidos:
            break
        elegidos.insert(0, t)
    return elegidos


def _temas(pregunta: str) -> list[str]:
    return [t for f in FUENTES if f.temas for t in (f.temas(pregunta) or [])]


# preguntas que piden algo general aunque se venga hablando de una cosa: no se les pega el tema anterior
_GENERAL = re.compile(r"\b(todas|todos|en general|que (maquinas|equipos)|cuales (maquinas|equipos)|alguna (maquina|otra)|"
                      r"algun (equipo|otro)|otras? (maquinas?|equipos?))\b")


def preguntar(pregunta, ayuda: list | None = None, historial: list | None = None, sin_tema: bool = False) -> Iterator[dict]:
    """La respuesta como una serie de eventos (para mostrarla a medida que se escribe):
      {"tipo": "inicio", "modo": "directa"|"ia"|"resumen"|"nada", "titulo", "enlaces", "aviso", "si_no_figura",
       "tema", "sigue"}
      {"tipo": "texto", "texto": "..."}        (uno o muchos)
      {"tipo": "fin", "segundos": 3.2}
    Orden: "ayuda"/"hola" -> lo que un módulo contesta sin IA -> si es de USO de la app, la Ayuda de las pantallas
    (`ayuda`: [{pantalla, titulo, texto}], la manda la pantalla) -> los datos de los módulos con IA -> si nadie encontró
    nada, lo que proponga un módulo (sin_resultado). Si la IA falla a mitad de camino, se muestra el resumen.

    La conversación (`historial`: [{pregunta, respuesta, tema}], la manda la pantalla): si la pregunta no nombra nada y
    la anterior sí ("¿cuántas horas tiene?" después de preguntar por el EQ-001), se contesta sobre lo mismo; el evento
    inicio lo dice en `sigue` para que la pantalla lo muestre y ofrezca preguntar sin eso (`sin_tema`). `tema` es de qué
    habló esta respuesta, para la próxima pregunta. La IA además recibe las últimas preguntas y respuestas."""
    q = validar.texto(pregunta, "la pregunta", maximo=MAX_PREGUNTA)
    charla = _historial(historial)
    t0 = time.time()
    doble = "\n\n"
    de_uso = bool(_DE_USO.search(_norm(q)))
    sigue = None
    if charla and not sin_tema and not de_uso and not _SALUDO.match(_norm(q)) and not _GENERAL.search(_norm(q)):
        anterior = charla[-1]["tema"]
        if anterior and not _temas(q):
            sigue = anterior
            q = f"{q.rstrip(' ?¿')} ({anterior})?"
    propios = _temas(q)
    tema = propios[0] if len(propios) == 1 else ""

    def fin():
        return {"tipo": "fin", "segundos": round(time.time() - t0, 1)}

    def directa(r, modo="directa"):
        yield {"tipo": "inicio", "modo": modo, "titulo": r.get("titulo", ""), "enlaces": r.get("enlaces", []), "aviso": "",
               "tema": tema, "sigue": sigue}
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

    # de USO: la guía y la Ayuda, buscando por lo que importa ("¿cómo cargo una nota?" busca "una nota", no "cargo")
    manual = textos.manual(_DE_USO.sub(" ", _norm(q)), ayuda) if de_uso else None
    contextos = [manual] if manual else [x for x in (f.contexto(q) for f in FUENTES if f.contexto) if x]
    if not contextos:                     # no nombra nada en particular: las fichas de todo lo cargado
        contextos = [x for x in [textos.buscar_fichas(q)] if x]
        # si la IA no encuentra el dato en las fichas, se ofrece lo mismo que cuando no se encontró nada (cargarlo)
        propuesta = next((r for r in (f.sin_resultado(q) for f in FUENTES if f.sin_resultado and contextos) if r), None)
        if propuesta and propuesta.get("enlaces"):
            contextos[0]["si_no_figura"] = {"texto": propuesta["texto"], "enlace": propuesta["enlaces"][0]}
    if not contextos:                     # último recurso: quizás es de uso aunque no lo parezca ("quiero anotar una rotura")
        contextos = [x for x in [textos.manual(q, ayuda, minimo=2)] if x]
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
               "si_no_figura": si_no_figura, "tema": tema, "sigue": sigue}
        yield {"tipo": "texto", "texto": resumen}
        yield fin()
        return

    yield {"tipo": "inicio", "modo": "ia", "titulo": titulo, "enlaces": enlaces, "aviso": "", "si_no_figura": si_no_figura,
           "tema": tema, "sigue": sigue}
    fragmentos = [f for x in contextos for f in _fragmentos(x)]
    try:
        yield {"tipo": "texto", "texto": _componer(_ia(q, fragmentos, est, charla), fragmentos)}
    except (OSError, ValueError, RuntimeError) as e:
        _ESTADO.clear()
        yield {"tipo": "aviso", "aviso": f"La IA local no respondió ({e}). Esto es lo que dice la app:"}
        yield {"tipo": "texto", "texto": resumen}
    yield fin()
