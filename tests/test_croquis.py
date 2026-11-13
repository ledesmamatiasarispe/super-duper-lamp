"""El motor del croquis del mapa (frontend/croquis.js), probado con Node (tests/croquis_prueba.js): restricciones, cotas
que mandan, conflictos, grados de libertad, recortar, extender, equidistancia, simetría, imanes, copiar y pegar."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest


def test_motor_del_croquis():
    node = shutil.which("node")
    if not node:
        pytest.skip("No hay Node en esta PC.")
    r = subprocess.run([node, str(Path(__file__).with_name("croquis_prueba.js"))], capture_output=True, text=True, encoding="utf-8")
    assert r.stdout, r.stderr
    d = json.loads(r.stdout)
    assert d["errores"] == [] and d["casos"] >= 9, "\n".join(d["errores"])
