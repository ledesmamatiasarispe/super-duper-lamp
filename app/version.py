"""Identidad de UltraMantenimiento: lo único que cambia de una app a otra en la configuración del núcleo.

VERSION se sube a mano antes de publicar, y el tag del release de GitHub tiene que ser "v" + VERSION
(herramientas/compilar.py lo controla). MANT_REPO reemplaza REPO (vacío desactiva la búsqueda de actualizaciones: así
corren los tests)."""
VERSION = "1.2.0"
APP = "UltraMantenimiento"      # identificador fijo: nombre del .exe, User-Agent, /api/version. No cambia nunca.
NOMBRE = "UltraMantenimiento"   # el nombre de fábrica que se ve (se cambia en Opciones)
SUBTITULO = "Fundición Romero"
PREFIJO = "MANT"                # variables de entorno: MANT_DB, MANT_PUERTO, MANT_REPO, MANT_NAVEGADOR
PUERTO = 8095
REPO = "ledesmamatiasarispe/super-duper-lamp"
LOGIN = "Legajo"
BASE = "mantenimiento"          # data/mantenimiento.db
