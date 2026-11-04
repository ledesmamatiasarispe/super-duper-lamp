"""python -m app (o MantenimientoRomero.exe, la versión compilada)  ->  levanta la app en http://localhost:8095
(y en la red, para las tablets de planta). La versión compilada además abre el navegador al arrancar.
MANT_PUERTO cambia el puerto y MANT_NAVEGADOR=0 evita abrir el navegador (para pruebas o un servidor sin pantalla)."""
import os
import threading
import webbrowser

import uvicorn

from app.main import app
from app.version import COMPILADA, VERSION

PUERTO = int(os.environ.get("MANT_PUERTO", "8095"))

if __name__ == "__main__":
    print(f"Mantenimiento Romero {VERSION} - http://localhost:{PUERTO}  (cerrar esta ventana apaga la app)")
    if COMPILADA and os.environ.get("MANT_NAVEGADOR", "1") != "0":
        threading.Timer(2, webbrowser.open, [f"http://localhost:{PUERTO}"]).start()
    # el objeto app directo (no "app.main:app"): compilada, uvicorn no puede importar el módulo por nombre
    uvicorn.run(app, host="0.0.0.0", port=PUERTO)
