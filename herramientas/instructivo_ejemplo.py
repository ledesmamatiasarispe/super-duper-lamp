"""Crea el instructivo de EJEMPLO: una bomba centrífuga que usa todas las herramientas del editor, para mostrarles a
los usuarios qué se puede armar (secciones con grupos y detalles, notas de los tres niveles, tablas, imágenes,
gráficos de barras, línea y torta, repuestos con cantidad mínima, archivos adjuntos y el orden libre del contenido).

Queda sin equipo asignado (así no entra al Plan ni al Cronograma) y se ve en "Equipos e instructivos", en la línea
de instructivos sin equipo. Se crea en dos pasos, como lo haría un usuario: el alta (revisión 0) y una modificación
que le suma las imágenes y los archivos (revisión 1), así también muestra el historial de revisiones.

    .venv/Scripts/python.exe herramientas/instructivo_ejemplo.py      (usa la base de MANT_DB o data/mantenimiento.db)

Si ya existe un instructivo con este título, no hace nada."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app import servicios as sv  # noqa: E402
from app.db import inicializar, transaccion  # noqa: E402

TITULO = "EJEMPLO · Bomba centrífuga de agua de refrigeración"
ARCHIVOS = RAIZ / "herramientas" / "ejemplo"
USUARIO = {"nombre": "Sistema (ejemplo)"}


def act(texto, *detalle):
    return {"texto": texto, "es_grupo": False, "detalle": "\n".join(detalle)}


def grupo(texto):
    return {"texto": texto, "es_grupo": True}


SECCIONES = [
    {"letra": "A", "actividades": [   # mensual: inspección con la bomba en marcha
        grupo("Con la bomba en marcha"),
        act("Escuchar ruidos anormales en motor, acople y rodamientos (punto 2 y 3 del esquema)"),
        act("Medir la temperatura de los rodamientos con termómetro infrarrojo",
            "Lado acople y lado bomba", "Anotar el valor en Novedades al registrar"),
        act("Medir la vibración en el soporte de rodamientos", "Comparar con la tabla de valores de referencia"),
        act("Controlar el goteo del sello mecánico (punto 5)"),
        act("Verificar presión de descarga en el manómetro"),
        grupo("Con la bomba detenida y bloqueada"),
        act("Revisar el ajuste de los bulones de anclaje a la base"),
        act("Revisar el estado de la protección del acople"),
        act("Limpiar la carcasa del motor y las aletas de ventilación"),
    ]},
    {"letra": "B", "actividades": [   # por horas: lubricación
        act("Engrasar los rodamientos por el engrasador (punto 4)",
            "Grasa de litio EP2", "15 g por engrasador", "Limpiar el pico antes de inyectar"),
        act("Hacer girar la bomba 10 minutos y volver a medir la temperatura de los rodamientos"),
    ]},
    {"letra": "C", "actividades": [   # anual: con la bomba desarmada
        grupo("Revisión mayor"),
        act("Controlar la alineación motor-bomba con comparador", "Ver el esquema de alineación y sus tolerancias"),
        act("Cambiar el sello mecánico si tiene goteo o más de 8000 h"),
        act("Revisar el impulsor por desgaste o cavitación"),
        act("Medir la aislación del motor con megóhmetro (mínimo 1 MΩ)"),
        grupo("Al terminar"),
        act("Probar en marcha 30 minutos y registrar temperatura, vibración y presión"),
    ]},
]

SEGURIDAD = [
    "Bloquear y etiquetar el tablero del motor antes de intervenir (procedimiento LOTO).",
    "Cerrar las válvulas de succión y descarga y descargar la presión de la línea.",
    "Usar guantes, anteojos de seguridad y protección auditiva.",
    "No trabajar sobre la protección del acople con el motor en marcha.",
]

REPUESTOS = [
    {"nombre": "Grasa de litio EP2 (kg)", "cantidad": 1},
    {"nombre": "Rodamiento 6309-2Z (lado acople)", "cantidad": 1},
    {"nombre": "Rodamiento 6308-2Z (lado bomba)", "cantidad": 1},
    {"nombre": "Sello mecánico Ø 35 mm SiC/carbón", "cantidad": 1},
    {"nombre": "Elemento elástico del acople", "cantidad": 2},
    {"nombre": "Trapo industrial (kg)", "cantidad": 0.5},
]

# los bloques, en el orden de la lista; el orden del documento lo da ORDEN (más abajo)
NOTA_EJEMPLO = {"tipo": "nota", "datos": {"nivel": "info", "texto":
    "Este instructivo es un EJEMPLO: muestra todo lo que se puede poner en un instructivo (secciones con grupos y "
    "detalles, notas, tablas, imágenes, gráficos, repuestos y archivos). Tocá Modificar para ver cómo está armado; "
    "no está asignado a ningún equipo, así que no aparece en el Plan."}}
FICHA = {"tipo": "tabla", "datos": {"titulo": "Datos del equipo", "encabezado": False, "filas": [
    ["Equipo", "Bomba centrífuga de agua de refrigeración"], ["Marca / modelo", "Ejemplo BC-60/32"],
    ["Caudal / altura", "60 m³/h · 32 m"], ["Motor", "11 kW · 2900 rpm"], ["Horómetro", "Sí: se anota la lectura en cada servicio"]]}}
TEXTO_FUNCIONAMIENTO = {"tipo": "texto", "datos": {"titulo": "Cómo funciona", "texto":
    "El motor mueve el impulsor a través del acople elástico. El agua entra por la succión, el impulsor la acelera y "
    "sale por la descarga. Los puntos que más se desgastan son los rodamientos, el sello mecánico y el elemento "
    "elástico del acople: por eso son los que más se controlan."}}
NOTA_PRECAUCION = {"tipo": "nota", "datos": {"nivel": "precaucion", "texto":
    "Si un rodamiento supera los 80 °C o la vibración pasa de 4,5 mm/s, avisar al supervisor y registrar el servicio "
    "como «Con observaciones»."}}
NOTA_PELIGRO = {"tipo": "nota", "datos": {"nivel": "peligro", "texto":
    "Nunca hacer funcionar la bomba en seco ni con la válvula de descarga cerrada: el sello se destruye en segundos "
    "y la carcasa puede recalentarse."}}
TABLA_REFERENCIA = {"tipo": "tabla", "datos": {"titulo": "Valores de referencia", "encabezado": True, "filas": [
    ["Control", "Normal", "Alerta", "Qué hacer en alerta"],
    ["Temperatura de rodamiento", "hasta 70 °C", "más de 80 °C", "Engrasar y volver a medir; si sigue, cambiar rodamiento"],
    ["Vibración (soporte)", "hasta 2,8 mm/s", "más de 4,5 mm/s", "Revisar alineación y anclajes"],
    ["Goteo del sello", "sin goteo", "goteo continuo", "Programar cambio de sello"],
    ["Presión de descarga", "2,8 a 3,2 bar", "menos de 2,5 bar", "Revisar succión e impulsor"]]}}
GRAFICO_TEMPERATURA = {"tipo": "grafico", "datos": {"forma": "linea", "unidad": "°C",
    "titulo": "Temperatura del rodamiento lado acople (mediciones mensuales)",
    "filas": [["Jun", 52], ["Jul", 54], ["Ago", 55], ["Sep", 58], ["Oct", 61]]}}
GRAFICO_PARADAS = {"tipo": "grafico", "datos": {"forma": "barras", "unidad": "h",
    "titulo": "Horas de parada por causa (último año)",
    "filas": [["Sello", 14], ["Rodamientos", 9], ["Acople", 4], ["Eléctrica", 3]]}}
GRAFICO_TIEMPO = {"tipo": "grafico", "datos": {"forma": "torta", "unidad": "min",
    "titulo": "En qué se va el tiempo del servicio anual",
    "filas": [["Desarme y armado", 120], ["Alineación", 60], ["Cambio de sello", 45], ["Prueba en marcha", 30]]}}
TEXTO_CIERRE = {"tipo": "texto", "datos": {"titulo": "Criterio de aceptación", "texto":
    "El servicio se da por bueno cuando, después de 30 minutos en marcha, la temperatura, la vibración y la presión "
    "están en la columna «Normal» de la tabla de valores de referencia y el sello no gotea."}}


def contenido(imagen_esquema=None, imagen_alineacion=None, archivos=()):
    bloques = [NOTA_EJEMPLO, FICHA, TEXTO_FUNCIONAMIENTO, NOTA_PRECAUCION, NOTA_PELIGRO, TABLA_REFERENCIA,
               GRAFICO_TEMPERATURA, GRAFICO_PARADAS, GRAFICO_TIEMPO, TEXTO_CIERRE]
    n = {id(b): i for i, b in enumerate(bloques)}
    b = lambda bloque: f"bloque:{n[id(bloque)]}"  # noqa: E731
    imagenes = {}
    for clave, adj, ancho, epigrafe in (("esquema", imagen_esquema, "completo", "Esquema con los puntos que se inspeccionan (los números se usan en las actividades)."),
                                        ("alineacion", imagen_alineacion, "mediano", "Cómo se mide la alineación y cuánto se tolera.")):
        if adj:
            bloques.append({"tipo": "imagen", "datos": {"adjunto_id": adj, "ancho": ancho, "epigrafe": epigrafe}})
            imagenes[clave] = f"bloque:{len(bloques) - 1}"
    # el orden libre: notas, ficha y esquema arriba; cada sección con lo que le corresponde debajo; los repuestos en el medio
    orden = [b(NOTA_EJEMPLO), b(FICHA), imagenes.get("esquema"), b(TEXTO_FUNCIONAMIENTO), b(NOTA_PELIGRO),
             "seccion:A", b(TABLA_REFERENCIA), b(NOTA_PRECAUCION), b(GRAFICO_TEMPERATURA),
             "seccion:B", "repuestos",
             "seccion:C", imagenes.get("alineacion"), b(GRAFICO_PARADAS), b(GRAFICO_TIEMPO), b(TEXTO_CIERRE)]
    return {"titulo": TITULO,
            "descripcion": "Mantenimiento preventivo de una bomba centrífuga: inspección mensual (A), lubricación por horas de uso (B) y revisión anual (C).",
            "seguridad": SEGURIDAD, "repuestos": REPUESTOS, "secciones": SECCIONES,
            "bloques": [{**x, "ubicacion": "general"} for x in bloques], "orden": [t for t in orden if t],
            "archivos": list(archivos)}


def main():
    inicializar()
    with transaccion() as c:
        if c.execute("SELECT 1 FROM instructivos WHERE titulo=?", (TITULO,)).fetchone():
            print("El instructivo de ejemplo ya existe: no se crea otro.")
            return
    it = sv.crear_instructivo(USUARIO, **contenido())
    subir = lambda nombre: sv.subir_adjunto(USUARIO, it["id"], nombre=nombre, datos=(ARCHIVOS / nombre).read_bytes())["id"]  # noqa: E731
    esquema, alineacion = subir("esquema_bomba.png"), subir("alineacion.png")
    archivos = [subir("ficha_tecnica_bomba.pdf"), subir("mediciones_bomba.csv")]
    final = sv.revisar_instructivo(USUARIO, it["id"], motivo="Se agregan el esquema de puntos de inspección, el de alineación, "
                                   "la ficha técnica y la planilla de mediciones.",
                                   **contenido(esquema, alineacion, archivos))
    print(f"Creado {final['codigo']} (revisión {final['revision']}): {TITULO}")


if __name__ == "__main__":
    main()
