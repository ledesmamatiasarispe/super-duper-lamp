"""python -m app (o UltraMantenimiento.exe, la versión compilada)  ->  levanta la app en http://localhost:<puerto>
(y en la red, para las tablets de planta). La versión compilada además abre el navegador al arrancar.

El puerto se elige en Opciones (8095 si nunca se cambió; ver app/puerto.py). Si la app ya estaba abierta, abrirla de
nuevo solo abre el navegador. MANT_PUERTO fija el puerto y MANT_NAVEGADOR=0 evita abrir el navegador (para pruebas o
un servidor sin pantalla)."""
import os
import threading
import webbrowser

import uvicorn

from app import puerto as pto
from app.main import app
from app.version import APP, COMPILADA, VERSION

if __name__ == "__main__":
    abrir = COMPILADA and os.environ.get("MANT_NAVEGADOR", "1") != "0"
    puerto, ya_abierta = pto.al_arrancar()
    url = f"http://localhost:{puerto}"
    if ya_abierta:
        print(f"{APP} ya está funcionando: {url}")
        if abrir:
            webbrowser.open(url)
    else:
        if puerto != pto.configurado():
            print(f"El puerto {pto.configurado()} lo está usando otro programa: esta vez la app arranca en el {puerto}. "
                  "Se puede elegir otro en Opciones.")
        os.environ[pto.VARIABLE_ACTUAL] = str(puerto)
        print(f"{APP} {VERSION} - {url}  (cerrar esta ventana apaga la app)")
        if abrir:
            threading.Timer(2, webbrowser.open, [url]).start()
        # el objeto app directo (no "app.main:app"): compilada, uvicorn no puede importar el módulo por nombre
        uvicorn.run(app, host="0.0.0.0", port=puerto)
