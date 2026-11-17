"""Lo que la IA lee para no tener que leer todo: la GUÍA de uso, los SINÓNIMOS y las FICHAS.

  GUÍA      un archivo Markdown por módulo (Fuente.guia) más el del asistente (ia/guia.md): cómo se usa la app y la
            dinámica de cada pestaña, escrito corto y para leer. Cada "## Título" es una sección; un renglón "ir: vista"
            debajo del título dice a qué pantalla lleva. A la IA le llegan solo las 2 o 3 secciones que vienen al caso.
  SINÓNIMOS un archivo de texto por módulo (Fuente.sinonimos) más el del asistente (ia/sinonimos.txt): un grupo por
            renglón, separado por comas ("correctivo, reparación, arreglo"). Cuando la pregunta dice una palabra del grupo,
            se buscan todas. Sirve para la guía, la Ayuda de las pantallas y las fichas.
  FICHAS    un texto corto y ya armado por cada cosa cargada en la base (Fuente.fichas: una máquina, un correctivo, una
            sección de un instructivo...). Se arman solas a partir de los datos y se rehacen cuando la base cambia (se
            mira la fecha del archivo de la base: no hay que acordarse de actualizarlas). Con ellas se contesta lo que
            no nombra una cosa en particular ("¿qué máquinas usan correa SPZ?").

La búsqueda es por raíces de palabras (sin acentos; "cargo" = "cargar", "correa" = "correas") y pesa más las palabras raras: "aceite" encuentra lo justo;
"máquina", que está en todas las fichas, casi no cuenta."""
import math
import re
import unicodedata
from pathlib import Path

from nucleo import db

CARPETA = Path(__file__).resolve().parent / "ia"
MAX_CARACTERES_GUIA = 2600      # lo que se le pasa a la IA de la guía y la Ayuda (unos 750 tokens)
MAX_CARACTERES_FICHAS = 2600    # lo mismo para las fichas encontradas
MAX_FICHA = 700                 # una ficha más larga se corta (mejor varias fichas chicas que una enorme)

VACIAS = set("""que como cual cuales cuando donde quien quienes cuanto cuanta cuantos cuantas para por con sin sobre entre
hasta desde este esta estos estas ese esa esos esas aquel aquella una uno unos unas los las del al el la lo le les se me te
nos hay tiene tienen tenia tenian esta estan son ser fue fueron era eran hace hacen hacer hizo hago puedo podes puede pueden
quiero queres necesito saber sabes decime dame mostrame algo alguna alguno algun todo toda todos todas cada otro otra otros
otras mas menos muy tambien pero porque pasa paso hoy app aplicacion barra favor gracias tengo tenes
usa usan usar uso lleva llevan llevar va van tuvo tuvieron tuve dice dicen""".split())


def norm(t) -> str:
    t = unicodedata.normalize("NFKD", str(t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c)).replace("-", " ")


def palabras(t) -> list[str]:
    return re.findall(r"[a-z0-9]+", norm(t))


_SUFIJOS = ("amientos", "amiento", "aciones", "acion", "iendo", "ando", "ados", "adas", "idos", "idas", "ado", "ada", "ido",
            "ida", "ar", "er", "ir", "as", "es", "os", "an", "en", "a", "o", "e", "s")


def raiz(p: str) -> str:
    """La raíz de una palabra, para que "cargo", "cargar" y "carga" (o "correctivo" y "correctivos") sean la misma.
    Es tosca a propósito: le saca una terminación común y deja al menos 4 letras."""
    if len(p) < 5 or p.isdigit():
        return p
    for s in _SUFIJOS:
        if p.endswith(s) and len(p) - len(s) >= 4:
            return p[:-len(s)]
    return p


def _rellenado(t) -> str:
    """Las raíces del texto entre espacios, para buscar palabras y frases enteras con " x " in texto."""
    return " " + " ".join(raiz(p) for p in palabras(t)) + " "


def _esta(variante: str, texto: str) -> bool:
    return f" {variante} " in texto


# ── archivos (guía y sinónimos): se leen de nuevo solo si cambiaron ──
_ARCHIVOS: dict = {}


def _leer(ruta) -> str:
    ruta = Path(ruta)
    try:
        marca = ruta.stat().st_mtime_ns
    except OSError:
        return ""
    if _ARCHIVOS.get(ruta, (None,))[0] != marca:
        _ARCHIVOS[ruta] = (marca, ruta.read_text(encoding="utf-8"))
    return _ARCHIVOS[ruta][1]


def _fuentes():
    from .servicios import FUENTES      # acá adentro: servicios importa este archivo
    return FUENTES


# ── sinónimos ──
def grupos_de_sinonimos() -> list[set[str]]:
    """Los grupos del asistente y de cada módulo; dos grupos que comparten una palabra se juntan en uno."""
    rutas = [CARPETA / "sinonimos.txt"] + [f.sinonimos for f in _fuentes() if getattr(f, "sinonimos", None)]
    grupos: list[set[str]] = []
    for ruta in rutas:
        for renglon in _leer(ruta).splitlines():
            renglon = renglon.split("#", 1)[0]
            grupo = {" ".join(raiz(p) for p in palabras(x)) for x in renglon.split(",")} - {""}
            if len(grupo) < 2:
                continue
            for otro in [g for g in grupos if g & grupo]:
                grupo |= otro
                grupos.remove(otro)
            grupos.append(grupo)
    return grupos


def conceptos(pregunta: str) -> list[set[str]]:
    """Lo que hay que buscar: cada palabra que importa de la pregunta, con sus sinónimos ("arreglo" -> {arreglo,
    correctivo, reparacion...}). Las frases de los sinónimos ("dar de baja") cuentan como una sola cosa."""
    texto = _rellenado(pregunta)
    usadas, lista = set(), []
    for grupo in grupos_de_sinonimos():
        dichas = [v for v in grupo if _esta(v, texto)]
        if dichas:
            lista.append(grupo)
            usadas |= {p for v in dichas for p in v.split()}
    for p in palabras(pregunta):
        r = raiz(p)
        if r in usadas or p in VACIAS or (len(p) < 3 and not p.isdigit()):
            continue
        usadas.add(r)
        lista.append({r})
    return lista


def ordenar(pregunta: str, docs: list[dict], clave: str = "_n") -> list[tuple[float, int, dict, bool]]:
    """(puntaje, cuántas cosas de la pregunta encontró, doc, si alguna está en su título) de los docs que encuentran
    algo, el mejor primero. Cada doc trae su texto rellenado en doc[clave] (y su título en doc["_t"], si tiene).
    Una palabra que está en muchos docs pesa poco (idf)."""
    lista = conceptos(pregunta)
    if not lista or not docs:
        return []
    # cuántas veces aparece cada cosa en cada doc (0 = no está)
    veces = [[sum(d[clave].count(f" {v} ") for v in c) for c in lista] for d in docs]
    n = len(docs)
    pesos = [math.log((n + 1) / (sum(1 for x in veces if x[i]) + 0.5)) for i in range(len(lista))]
    puntuados = []
    for d, x in zip(docs, veces):
        # lo que importa es QUÉ encuentra (palabras raras pesan más); repetirse solo desempata
        puntos = sum(p * (1 + 0.15 * min(k - 1, 4)) for p, k in zip(pesos, x) if k)
        if puntos > 0:
            en_titulo = any(any(f" {v} " in d.get("_t", "") for v in c) for c in lista)
            puntuados.append((puntos + d.get("_extra", 0), sum(1 for k in x if k), d, en_titulo))
    return sorted(puntuados, key=lambda x: -x[0])


def _hasta(elegidos, maximo: int, linea) -> list:
    """Los primeros que entran en `maximo` caracteres (al menos uno)."""
    salida, total = [], 0
    for x in elegidos:
        largo = len(linea(x))
        if salida and total + largo > maximo:
            break
        salida.append(x)
        total += largo
    return salida


# ── la guía ──
def secciones_de_guia() -> list[dict]:
    """Las secciones de todas las guías: {titulo, texto, ir}. Lo que va antes del primer "##" es la sección general."""
    rutas = [CARPETA / "guia.md"] + [f.guia for f in _fuentes() if getattr(f, "guia", None)]
    secciones = []
    for ruta in rutas:
        actual = None
        for renglon in _leer(ruta).splitlines():
            if renglon.startswith("## "):
                actual = {"titulo": renglon[3:].strip(), "texto": [], "ir": ""}
                secciones.append(actual)
            elif renglon.startswith("# "):
                actual = {"titulo": renglon[2:].strip(), "texto": [], "ir": ""}
                secciones.append(actual)
            elif actual is not None and re.fullmatch(r"ir:\s*[a-z_/0-9]+\s*", renglon.strip()) and not actual["texto"]:
                actual["ir"] = renglon.split(":", 1)[1].strip()
            elif actual is not None:
                actual["texto"].append(renglon)
    for s in secciones:
        s["texto"] = re.sub(r"\n{3,}", "\n\n", "\n".join(s["texto"]).strip())
    return [s for s in secciones if s["texto"]]


def manual(pregunta: str, ayuda: list | None, minimo: int = 1) -> dict | None:
    """Cómo se usa la app, para la pregunta: las secciones de la guía y los pasos de la Ayuda de las pantallas
    (`ayuda`: [{pantalla, titulo, texto}], los manda el navegador) que mejor coinciden. La guía va primero a igual
    puntaje: está escrita para esto. `minimo`: cuántas cosas de la pregunta tiene que encontrar el mejor (con 2, para
    usarla como último recurso cuando la pregunta no parecía de uso)."""
    docs = [{"tipo": "guia", "titulo": s["titulo"], "texto": s["texto"], "ir": s["ir"], "_extra": 0.5,
             "_n": _rellenado(s["titulo"] + " " + s["texto"]), "_t": _rellenado(s["titulo"])} for s in secciones_de_guia()]
    for p in (ayuda if isinstance(ayuda, list) else [])[:400]:
        if isinstance(p, dict) and p.get("texto"):
            pantalla = str(p.get("pantalla") or "")[:40]
            docs.append({"tipo": "ayuda", "titulo": str(p.get("titulo") or "")[:120], "texto": str(p["texto"])[:700],
                         "ir": pantalla if re.fullmatch(r"[a-z_]+", pantalla) else "", "pantalla": pantalla,
                         "_n": _rellenado(f"{pantalla} {p.get('titulo', '')} {p['texto']}")})
    puntuados = ordenar(pregunta, docs)
    # alcanza con que encuentre `minimo` cosas, o que lo buscado sea el tema de una sección de la guía ("cumplimiento")
    if not puntuados or (puntuados[0][1] < minimo and not (puntuados[0][2]["tipo"] == "guia" and puntuados[0][3])):
        return None

    def linea(d):
        if d["tipo"] == "guia":
            return f"[Guía] {d['titulo']}:\n{d['texto']}"
        return f"- Ayuda de la pantalla {d['pantalla']} · {d['titulo']}: {d['texto']}"
    elegidos = _hasta([x[2] for x in puntuados[:8]], MAX_CARACTERES_GUIA, linea)
    vistas = list(dict.fromkeys(d["ir"] for d in elegidos if d["ir"]))[:3]
    cuerpo = "\n\n".join(map(linea, elegidos))
    # para que la IA elija: cada oración de la guía es un fragmento (con su sección), cada paso de la Ayuda otro
    fragmentos = []
    for d in elegidos:
        if d["tipo"] == "guia":
            fragmentos += [{"grupo": d["titulo"], "texto": o} for o in oraciones(d["texto"])]
        else:
            fragmentos.append({"grupo": f"Ayuda de {d['pantalla']} · {d['titulo']}", "texto": d["texto"]})
    return {"titulo": "Cómo se usa la app", "datos": "CÓMO SE USA LA APP (guía y ayuda de las pantallas):\n" + cuerpo,
            "resumen": cuerpo, "fragmentos": fragmentos,
            "enlaces": [{"texto": f"Ir a {v.split('/')[0]}", "ir": v} for v in vistas]}


def oraciones(texto: str) -> list[str]:
    """Un texto de la guía en oraciones (los renglones cortados del archivo se juntan antes)."""
    plano = " ".join(texto.split())
    return [o for o in re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ0-9\"«(¿¡])", plano) if o.strip()]


# ── las fichas ──
_FICHAS: dict = {}


def _marca_de_la_base():
    """Cambia cada vez que alguien guarda algo: la fecha y el tamaño del archivo de la base (y de su -wal)."""
    marca = []
    for sufijo in ("", "-wal"):
        try:
            st = Path(str(db.DB_PATH) + sufijo).stat()
            marca.append((st.st_mtime_ns, st.st_size))
        except OSError:
            marca.append(None)
    return tuple(marca)


def fichas() -> list[dict]:
    """Todas las fichas de todos los módulos: {tipo, titulo, texto, ir}. Se rehacen solo si la base cambió."""
    marca = (_marca_de_la_base(), tuple(f.nombre for f in _fuentes() if getattr(f, "fichas", None)))
    if _FICHAS.get("marca") != marca:
        lista = []
        for f in _fuentes():
            if getattr(f, "fichas", None):
                for x in f.fichas() or []:
                    texto = str(x.get("texto") or "")
                    if len(texto) > MAX_FICHA:
                        texto = texto[:MAX_FICHA].rsplit(" ", 1)[0] + " […]"
                    ficha = {"tipo": str(x.get("tipo") or ""), "titulo": str(x.get("titulo") or ""), "texto": texto,
                             "ir": str(x.get("ir") or "")}
                    ficha["_n"] = _rellenado(f"{ficha['tipo']} {ficha['titulo']} {texto}")
                    lista.append(ficha)
        _FICHAS.update(marca=marca, lista=lista)
    return _FICHAS["lista"]


def linea_de_ficha(f: dict) -> str:
    return f"- [{f['tipo']}] {f['titulo']}: {f['texto']}"


def buscar_fichas(pregunta: str) -> dict | None:
    """Las fichas que mejor coinciden con la pregunta, como contexto para la IA (y resumen sin IA)."""
    puntuados = ordenar(pregunta, fichas())
    if not puntuados:
        return None
    mejor = puntuados[0][0]
    candidatas = [d for p, _, d, _ in puntuados[:15] if p >= mejor * 0.34]   # lo que encuentra de verdad, no de rebote
    elegidas = _hasta(candidatas, MAX_CARACTERES_FICHAS, linea_de_ficha)
    cuerpo = "\n".join(map(linea_de_ficha, elegidas))
    vistas = list(dict.fromkeys(f["ir"] for f in elegidas if f["ir"]))[:3]
    return {"titulo": "Búsqueda en lo anotado", "datos": "FICHAS DE LA APP QUE COINCIDEN CON LA PREGUNTA:\n" + cuerpo,
            "resumen": "Lo anotado que coincide:\n" + cuerpo,
            "fragmentos": [{"grupo": f"[{f['tipo']}] {f['titulo']}", "texto": f["texto"]} for f in elegidas],
            "enlaces": [{"texto": f"Ir a {v.split('/')[0]}", "ir": v} for v in vistas]}


def todo() -> dict:
    """Lo que lee la IA, para verlo desde Opciones: la guía, los sinónimos y las fichas."""
    lista = fichas()
    por_tipo: dict = {}
    for f in lista:
        por_tipo[f["tipo"]] = por_tipo.get(f["tipo"], 0) + 1
    return {"guia": [{k: s[k] for k in ("titulo", "texto", "ir")} for s in secciones_de_guia()],
            "sinonimos": [sorted(g) for g in grupos_de_sinonimos()],
            "fichas": [{k: f[k] for k in ("tipo", "titulo", "texto", "ir")} for f in lista], "por_tipo": por_tipo}
