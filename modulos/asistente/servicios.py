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
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
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
    """Lo que un módulo le enseña al asistente. Las dos funciones reciben la pregunta tal como se escribió y devuelven
    None si no es de su tema.
      responder(pregunta) -> {"texto": str, "enlaces": [...]}                 contesta sin IA (exacto, instantáneo)
      contexto(pregunta)  -> {"titulo": str, "datos": str, "resumen": str, "enlaces": [...]}
                             datos: lo que lee la IA (texto corto, ya calculado; mejor < 1500 palabras)
                             resumen: lo que se muestra si no hay IA
    Un enlace es {"texto": "Ver instructivo", "ir": "instructivos/5"}: la pantalla hace irA(ir)."""
    nombre: str
    responder: Callable[[str], dict | None] | None = None
    contexto: Callable[[str], dict | None] | None = None


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
                 "motivo": "No se encontró la IA local (Ollama) en " + a["url"] + ". Sin ella, la barra busca y muestra un resumen."}
    _ESTADO.update(hasta=time.time() + 30, clave=(a["url"], a["modelo"]), valor=valor)
    return valor


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
def preguntar(pregunta) -> Iterator[dict]:
    """La respuesta como una serie de eventos (para mostrarla a medida que se escribe):
      {"tipo": "inicio", "modo": "directa"|"ia"|"resumen"|"nada", "titulo", "enlaces", "aviso"}
      {"tipo": "texto", "texto": "..."}        (uno o muchos)
      {"tipo": "fin", "segundos": 3.2}
    Si la IA falla a mitad de camino, se muestra el resumen (con un aviso) en vez de dejar la respuesta cortada."""
    q = validar.texto(pregunta, "la pregunta", maximo=MAX_PREGUNTA)
    t0 = time.time()
    fin = lambda: {"tipo": "fin", "segundos": round(time.time() - t0, 1)}  # noqa: E731

    for f in FUENTES:
        r = f.responder(q) if f.responder else None
        if r:
            yield {"tipo": "inicio", "modo": "directa", "titulo": r.get("titulo", ""), "enlaces": r.get("enlaces", []), "aviso": ""}
            yield {"tipo": "texto", "texto": r["texto"]}
            yield fin()
            return

    contextos = [x for x in (f.contexto(q) for f in FUENTES if f.contexto) if x]
    if not contextos:
        yield {"tipo": "inicio", "modo": "nada", "titulo": "", "enlaces": [], "aviso": ""}
        yield {"tipo": "texto", "texto": "No encontré nada sobre eso. Probá nombrando la máquina (por ejemplo «ETR-50» o "
                                          "«horno de inducción») o algo que se haya anotado (por ejemplo «rodamientos»)."}
        yield fin()
        return
    titulo = " · ".join(x["titulo"] for x in contextos if x.get("titulo"))
    enlaces = [e for x in contextos for e in x.get("enlaces", [])]
    resumen = "\n\n".join(x["resumen"] for x in contextos if x.get("resumen"))
    est = estado()
    if not est["disponible"]:
        yield {"tipo": "inicio", "modo": "resumen", "titulo": titulo, "enlaces": enlaces, "aviso": est["motivo"]}
        yield {"tipo": "texto", "texto": resumen}
        yield fin()
        return

    yield {"tipo": "inicio", "modo": "ia", "titulo": titulo, "enlaces": enlaces, "aviso": ""}
    escrito = False
    try:
        for pedazo in _ia(q, "\n\n".join(x["datos"] for x in contextos), est):
            escrito = True
            yield {"tipo": "texto", "texto": pedazo}
    except (OSError, ValueError, RuntimeError) as e:
        _ESTADO.clear()
        yield {"tipo": "aviso", "aviso": f"La IA local no respondió ({e}). Esto es lo que dice la app:"}
        yield {"tipo": "texto", "texto": ("\n\n" if escrito else "") + resumen}
    yield fin()
