"""Compila la app para distribuir: dist/<APP>/ (el .exe y _internal/) y el paquete que se sube al release de GitHub,
dist/<APP>-v<VERSION>-win64.zip con su .sha256 (el actualizador no instala sin él).

    .venv/Scripts/python.exe herramientas/compilar.py                 (local)
    .venv/Scripts/python.exe herramientas/compilar.py --tag v1.2.0    (en GitHub Actions: exige que el tag sea la versión)

Sirve igual para cualquier app hecha sobre el núcleo: toma APP y VERSION de app/version.py, y mete en el paquete el
frontend del núcleo y el de cada módulo (modulos/*/frontend). herramientas/icono.ico, si está, es el ícono del .exe.
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
from app.version import APP, VERSION  # noqa: E402

SEP = ";" if sys.platform == "win32" else ":"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tag", help="tag del release (v + VERSION); si no coincide, no se compila")
    tag = p.parse_args().tag
    if tag and tag != "v" + VERSION:
        sys.exit(f"El tag {tag} no coincide con la versión de app/version.py ({VERSION}): subí VERSION antes de etiquetar.")
    dist, build = RAIZ / "dist", RAIZ / "build"
    shutil.rmtree(dist / APP, ignore_errors=True)
    datos = ["--add-data", f"{RAIZ / 'nucleo' / 'frontend'}{SEP}nucleo/frontend"]
    for f in sorted((RAIZ / "modulos").glob("*/frontend")):
        datos += ["--add-data", f"{f}{SEP}{f.relative_to(RAIZ).as_posix()}"]
    if (RAIZ / "app" / "frontend").is_dir():
        datos += ["--add-data", f"{RAIZ / 'app' / 'frontend'}{SEP}app/frontend"]
    icono = RAIZ / "herramientas" / "icono.ico"
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--console", "--name", APP,
                    *(["--icon", str(icono)] if icono.exists() else []),
                    "--distpath", str(dist), "--workpath", str(build), "--specpath", str(build), *datos,
                    "--collect-submodules", "uvicorn", "--collect-submodules", "app", "--collect-submodules", "nucleo",
                    "--collect-submodules", "modulos", "--exclude-module", "pytest", str(RAIZ / "app" / "__main__.py")],
                   check=True, cwd=RAIZ)
    paquete = dist / f"{APP}-v{VERSION}-win64.zip"
    with zipfile.ZipFile(paquete, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted((dist / APP).rglob("*")):
            if f.is_file():
                z.write(f, Path(APP) / f.relative_to(dist / APP))
    digest = hashlib.sha256(paquete.read_bytes()).hexdigest()
    (dist / (paquete.name + ".sha256")).write_text(f"{digest}  {paquete.name}\n", encoding="ascii")
    print(f"Listo: {paquete} ({paquete.stat().st_size // (1024 * 1024)} MB)\nSHA-256: {digest}")


if __name__ == "__main__":
    main()
