import hashlib
import os
from pathlib import Path
import subprocess

from release_check import check

ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    version = check("cli", os.environ.get("GITHUB_REF_NAME", ""))
    output = ROOT / "dist/cli"
    output.mkdir(parents=True, exist_ok=True)
    checksums = []
    for platform in ("linux", "darwin", "windows"):
        for architecture in ("amd64", "arm64"):
            filename = f"arct_{version}_{platform}_{architecture}" + (".exe" if platform == "windows" else "")
            target = output / filename
            env = dict(os.environ, CGO_ENABLED="0", GOOS=platform, GOARCH=architecture)
            subprocess.run(["go", "build", "-trimpath", "-ldflags=-s -w", "-o", str(target), "./cmd/arct"], cwd=ROOT / "go", env=env, check=True)
            checksums.append(f"{hashlib.sha256(target.read_bytes()).hexdigest()}  {filename}\n")
    (output / "SHA256SUMS").write_text("".join(checksums))
