"""Compila la app para distribuir: dist/UltraMantenimiento/ (el .exe y _internal/) y el paquete que se sube al
release de GitHub, dist/UltraMantenimiento-v<VERSION>-win64.zip con su .sha256 (el actualizador no instala sin él).

    .venv/Scripts/python.exe herramientas/compilar.py                 (local)
    .venv/Scripts/python.exe herramientas/compilar.py --tag v1.2.0    (en GitHub Actions: exige que el tag sea la versión)

Para publicar una versión: subir VERSION en app/version.py, y crear y empujar el tag "v" + VERSION; el workflow
.github/workflows/release.yml compila y arma el release. La carpeta data/ nunca va en el paquete: es de cada instalación."""
import argparse
import hashlib
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from app.version import VERSION  # noqa: E402

NOMBRE = "UltraMantenimiento"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tag", help="tag del release (v + VERSION); si no coincide, no se compila")
    tag = p.parse_args().tag
    if tag and tag != "v" + VERSION:
        sys.exit(f"El tag {tag} no coincide con la versión de app/version.py ({VERSION}): subí VERSION antes de etiquetar.")
    dist, build = RAIZ / "dist", RAIZ / "build"
    shutil.rmtree(dist / NOMBRE, ignore_errors=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--console",
                    "--name", NOMBRE, "--icon", str(RAIZ / "herramientas" / "ultramantenimiento.ico"), "--distpath", str(dist), "--workpath", str(build), "--specpath", str(build),
                    "--add-data", f"{RAIZ / 'frontend'}{';' if sys.platform == 'win32' else ':'}frontend",
                    "--collect-submodules", "uvicorn", "--collect-submodules", "app",
                    "--exclude-module", "pytest", str(RAIZ / "app" / "__main__.py")], check=True, cwd=RAIZ)
    paquete = dist / f"{NOMBRE}-v{VERSION}-win64.zip"
    with zipfile.ZipFile(paquete, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted((dist / NOMBRE).rglob("*")):
            if f.is_file():
                z.write(f, Path(NOMBRE) / f.relative_to(dist / NOMBRE))
    digest = hashlib.sha256(paquete.read_bytes()).hexdigest()
    (dist / (paquete.name + ".sha256")).write_text(f"{digest}  {paquete.name}\n", encoding="ascii")
    print(f"Listo: {paquete} ({paquete.stat().st_size // (1024 * 1024)} MB)\nSHA-256: {digest}")


if __name__ == "__main__":
    main()
