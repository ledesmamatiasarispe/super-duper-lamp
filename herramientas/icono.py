"""Genera herramientas/ultramantenimiento.ico (el ícono del .exe) sin librerías de imágenes: dibuja la omega invertida con
la misma geometría que frontend/icono.svg (unidades de 0 a 64), con antialiasing por supermuestreo, y arma un .ico con
un PNG por tamaño. El .ico queda en el repositorio y compilar.py lo usa; regenerarlo solo si cambia el dibujo.

    .venv/Scripts/python.exe herramientas/icono.py"""
import struct
import zlib
from pathlib import Path

DESTINO = Path(__file__).resolve().parent / "ultramantenimiento.ico"
TAMANOS = (16, 24, 32, 48, 64, 128, 256)
AZUL, BLANCO = (0x17, 0x32, 0x4D), (255, 255, 255)
# la omega invertida (℧, estilo Ultramarines): anillo de centro (32, 34) y radios 10 a 22, cortado arriba en y=16 con
# una abertura de x=27 a 37, y dos remates horizontales hacia afuera. Los mismos números que el SVG.
CENTRO, R_INT, R_EXT, CORTE, ABERTURA = (32, 34), 10, 22, 16, (27, 37)
REMATES = ((7, 9, 27, 16), (37, 9, 57, 16))   # x0, y0, x1, y1


def _fondo(x, y, r=12.0):
    """Cuadrado redondeado de 64x64 (radio 12)."""
    cx, cy = min(max(x, r), 64 - r), min(max(y, r), 64 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r and 0 <= x <= 64 and 0 <= y <= 64


def _omega(x, y):
    if any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in REMATES):
        return True
    dx, dy = x - CENTRO[0], y - CENTRO[1]
    if not R_INT ** 2 <= dx * dx + dy * dy <= R_EXT ** 2 or y < CORTE:
        return False
    return not (ABERTURA[0] < x < ABERTURA[1] and y < CENTRO[1])


def _png(n: int) -> bytes:
    sub = 4   # 4x4 muestras por pixel
    filas = bytearray()
    for py in range(n):
        filas.append(0)
        for px in range(n):
            fondo = blanco = 0
            for sy in range(sub):
                for sx in range(sub):
                    x, y = (px + (sx + .5) / sub) * 64 / n, (py + (sy + .5) / sub) * 64 / n
                    if _fondo(x, y):
                        fondo += 1
                        blanco += _omega(x, y)
            total = sub * sub
            alfa = round(255 * fondo / total)
            mezcla = blanco / fondo if fondo else 0
            filas += bytes(round(a + (b - a) * mezcla) for a, b in zip(AZUL, BLANCO)) + bytes([alfa])

    def bloque(tipo, datos):
        return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + bloque(b"IHDR", struct.pack(">IIBBBBB", n, n, 8, 6, 0, 0, 0))
            + bloque(b"IDAT", zlib.compress(bytes(filas), 9)) + bloque(b"IEND", b""))


def generar(destino: Path = DESTINO) -> Path:
    pngs = [_png(n) for n in TAMANOS]
    cabecera = struct.pack("<HHH", 0, 1, len(pngs))
    offset, entradas = 6 + 16 * len(pngs), b""
    for n, datos in zip(TAMANOS, pngs):
        entradas += struct.pack("<BBBBHHII", n % 256, n % 256, 0, 0, 1, 32, len(datos), offset)
        offset += len(datos)
    destino.write_bytes(cabecera + entradas + b"".join(pngs))
    return destino


if __name__ == "__main__":
    print(generar())
