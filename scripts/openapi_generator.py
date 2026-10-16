import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSION = '7.26.0'
SHA256 = '1760050094997b9cc790cc1350be095f15da8c08a996b184d3eadc4ccda5e35e'
JAR = ROOT / '.tools' / f'openapi-generator-cli-{VERSION}.jar'
URL = f'https://repo.maven.apache.org/maven2/org/openapitools/openapi-generator-cli/{VERSION}/{JAR.name}'


def bootstrap():
    JAR.parent.mkdir(exist_ok=True)
    if JAR.exists():
        if hashlib.sha256(JAR.read_bytes()).hexdigest() != SHA256:
            raise SystemExit('Generator checksum mismatch. Remove the cached jar and retry.')
        return JAR
    with urllib.request.urlopen(URL, timeout=60) as response:
        content = response.read()
    if hashlib.sha256(content).hexdigest() != SHA256:
        raise SystemExit('Downloaded generator checksum mismatch.')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=JAR.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        os.replace(temporary, JAR)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return JAR


if __name__ == '__main__':
    jar = bootstrap()
    if sys.argv[1:] != ['--download-only']:
        raise SystemExit(subprocess.call(['java', '-jar', str(jar), *sys.argv[1:]]))
