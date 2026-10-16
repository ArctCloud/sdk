import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import venv

ROOT = Path(__file__).resolve().parents[1]


def run(args, **kwargs):
    subprocess.run(args, check=True, **kwargs)


def smoke(package):
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        if package == "python":
            wheel, = (ROOT / "python/dist").glob("*.whl")
            venv.EnvBuilder(with_pip=True).create(temp / "venv")
            executable = temp / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            run([str(executable), "-m", "pip", "install", str(wheel)], cwd=temp)
            run([str(executable), "-I", "-c", "from arct import Arct, AsyncArct, __version__; from importlib.metadata import version; from importlib.resources import files; assert __version__ == version('arct-cloud'); assert files('arct').joinpath('py.typed').is_file()"], cwd=temp)
        elif package == "typescript":
            npm = "npm.cmd" if os.name == "nt" else "npm"
            result = subprocess.run([npm, "pack", "--json", "--pack-destination", str(temp)], cwd=ROOT / "typescript", check=True, capture_output=True, text=True)
            archive = temp / json.loads(result.stdout)[0]["filename"]
            (temp / "package.json").write_text('{"private":true,"type":"module"}\n')
            run([npm, "install", "--ignore-scripts", "--no-audit", "--no-fund", str(archive)], cwd=temp)
            run(["node", "--input-type=module", "-e", "import { Arct } from '@arct-cloud/sdk'; if (typeof Arct !== 'function') throw new Error('Missing Arct export');"], cwd=temp)
        else:
            executable = temp / ("arct.exe" if os.name == "nt" else "arct")
            run(["go", "build", "-trimpath", "-o", str(executable), "./cmd/arct"], cwd=ROOT / "go")
            run([str(executable), "--help"], cwd=temp)
            result = subprocess.run([str(executable), "--version"], cwd=temp, check=True, capture_output=True, text=True)
            if (ROOT / "go/VERSION").read_text().strip() != result.stdout.strip():
                raise SystemExit("CLI version does not match go/VERSION")
    print(f"Installed {package} artifact smoke passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("package", choices=["python", "typescript", "cli"])
    smoke(parser.parse_args().package)
