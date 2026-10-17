#!/bin/sh
set -eu

case "$(uname -s)" in
    Darwin|Linux) ;;
    *) printf '%s\n' 'This installer supports macOS and Linux.' >&2; exit 1 ;;
esac

runtime=
for candidate in python3 python3.15 python3.14 python3.13 python3.12 python3.11; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
        runtime=$candidate
        break
    fi
done
if [ -z "$runtime" ]; then
    printf '%s\n' 'Python 3.11 or newer is required. Install Python and run this installer again.' >&2
    exit 1
fi

umask 077
exec "$runtime" - <<'PY'
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def install():
    home = Path(os.environ["HOME"])
    data = (home / ".local/share/arct").resolve()
    command = home / ".local/bin/arct"
    previous = None
    if command.is_symlink():
        target = command.resolve()
        previous = target.parent.parent
        if (target.name != "arct" or target.parent.name != "bin" or
                previous.parent != data or not previous.name.startswith("venv-") or
                not (previous / ".arct-installer").is_file()):
            raise OSError(f"Refusing to replace existing command: {command}. Move it aside and rerun.")
    elif os.path.lexists(command):
        raise OSError(f"Refusing to replace existing command: {command}. Move it aside and rerun.")

    data.mkdir(parents=True, exist_ok=True, mode=0o700)
    environment = Path(tempfile.mkdtemp(prefix="venv-", dir=data))
    temporary = None
    try:
        (environment / ".arct-installer").write_text("arct-cloud\n")
        subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)
        subprocess.run([str(environment / "bin/python"), "-m", "pip", "--disable-pip-version-check",
                        "install", "--no-input", "arct-cloud==0.1.0rc3"], check=True)
        executable = environment / "bin/arct"
        subprocess.run([str(executable), "--version"], check=True)
        command.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".arct-", dir=command.parent)
        os.close(descriptor)
        temporary = Path(name)
        temporary.unlink()
        temporary.symlink_to(executable)
        os.replace(temporary, command)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if not command.is_symlink() or command.resolve() != environment / "bin/arct":
            shutil.rmtree(environment)
    if previous is not None:
        shutil.rmtree(previous)

    shell = Path(os.environ.get("SHELL", "")).name
    profiles = []
    if shell == "bash":
        login = next((home / name for name in (".bash_profile", ".bash_login", ".profile")
                      if (home / name).exists()), home / ".profile")
        profiles = [home / ".bashrc", login]
    elif shell == "zsh":
        profiles = [Path(os.environ.get("ZDOTDIR") or home) / ".zshrc"]
    else:
        print("Automatic PATH setup supports bash and zsh. Configure your shell manually.")
    line = b'case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) export PATH="$HOME/.local/bin:$PATH" ;; esac'
    for profile in profiles:
        try:
            contents = profile.read_bytes() if profile.exists() else b""
            if line not in contents.splitlines():
                profile.parent.mkdir(parents=True, exist_ok=True)
                with profile.open("ab") as output:
                    output.write((b"\n" if contents and not contents.endswith(b"\n") else b"") + line + b"\n")
        except OSError as error:
            print(f"Could not configure {profile}: {error}. Add the PATH entry manually.", file=sys.stderr)
    print(f"Installed arct at {command}")
    print("Activate it in this terminal:")
    print('  fish_add_path --path "$HOME/.local/bin"' if shell == "fish" else '  export PATH="$HOME/.local/bin:$PATH"')


try:
    install()
except (OSError, KeyError, subprocess.CalledProcessError) as error:
    print(f"Installation failed: {error}", file=sys.stderr)
    sys.exit(1)
except KeyboardInterrupt:
    sys.exit(130)
PY
