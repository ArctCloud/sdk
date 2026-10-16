import argparse
import json
import os
from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def check(package, tag, root=ROOT):
    if package == "python":
        version = tomllib.loads((root / "python/pyproject.toml").read_text())["project"]["version"]
        pattern = r"\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?"
    elif package == "typescript":
        version = json.loads((root / "typescript/package.json").read_text())["version"]
        pattern = r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?"
    elif package == "cli":
        version = (root / "go/VERSION").read_text().strip()
        pattern = r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?"
    else:
        raise ValueError("Unknown package")
    if not re.fullmatch(pattern, version) or tag != f"{package}-v{version}":
        raise ValueError(f"Tag must match {package}-v{version}")
    return version


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("package", choices=["python", "typescript", "cli"])
    args = parser.parse_args()
    try:
        print(check(args.package, os.environ.get("GITHUB_REF_NAME", "")))
    except ValueError as error:
        parser.exit(1, f"{error}\n")
