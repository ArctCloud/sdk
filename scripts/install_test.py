import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


INSTALLER = Path(__file__).resolve().parents[1] / "install.sh"
STUB = r'''import os
from pathlib import Path
import sys

args = sys.argv[1:]
if args[0] == "-c":
    supported = os.environ.get("INSTALL_TEST_PYTHON")
    sys.exit(0 if not supported or Path(sys.argv[0]).name == supported else 1)
if args[:2] == ["-m", "venv"]:
    directory = Path(args[2]) / "bin"
    directory.mkdir()
    runtime = directory / "python"
    runtime.write_text(Path(__file__).read_text())
    runtime.chmod(0o700)
elif args[:2] == ["-m", "pip"]:
    if "arct-cloud==0.1.0rc3" not in args or os.environ.get("PIP_FIND_LINKS") != "/wheel fixtures":
        sys.exit("Incorrect package or lost pip settings")
    if os.environ.get("INSTALL_TEST_PIP_FAIL"):
        sys.exit("Simulated pip failure")
    command = Path(__file__).with_name("arct")
    command.write_text("#!/bin/sh\nprintf '%s\\n' '" + os.environ.get("INSTALL_TEST_RESULT", "arct 0.1.0rc3") + "'\n")
    command.chmod(0o700)
elif args == ["-"]:
    sys.executable = str(Path(__file__).resolve())
    if os.environ.get("INSTALL_TEST_INTERRUPT"):
        replace = os.replace
        def interrupt_after_replace(*args, **kwargs):
            replace(*args, **kwargs)
            raise KeyboardInterrupt
        os.replace = interrupt_after_replace
    exec(compile(sys.stdin.read(), "<installer>", "exec"))
else:
    sys.exit("Unexpected Python invocation: " + repr(args))
'''


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="arct installer ")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.home = self.root / "home with spaces"
        self.home.mkdir()
        self.bin = self.root / "commands"
        self.bin.mkdir()
        for name in ("python3", "python3.15", "python3.14", "python3.13", "python3.12", "python3.11"):
            path = self.bin / name
            path.write_text(f"#!{sys.executable}\n" + STUB)
            path.chmod(0o700)
        uname = self.bin / "uname"
        uname.write_text('#!/bin/sh\nprintf "%s\\n" "${INSTALL_TEST_OS:-Linux}"\n')
        uname.chmod(0o700)
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "SHELL": "/bin/bash",
            "PATH": f"{self.bin}:/usr/bin:/bin",
            "PIP_FIND_LINKS": "/wheel fixtures",
        }
        for name in ("ZDOTDIR", "INSTALL_TEST_PYTHON", "INSTALL_TEST_PIP_FAIL", "INSTALL_TEST_RESULT", "INSTALL_TEST_OS", "INSTALL_TEST_INTERRUPT"):
            self.env.pop(name, None)
        self.command = self.home / ".local/bin/arct"
        self.data = self.home / ".local/share/arct"

    def install(self, **env):
        with INSTALLER.open() as script:
            return subprocess.run(["/bin/sh"], stdin=script, env={**self.env, **env}, capture_output=True, text=True)

    def run_cli(self):
        return subprocess.check_output([str(self.command)], env=self.env, text=True).strip()

    def test_install_uses_private_environment_and_prints_activation(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_cli(), "arct 0.1.0rc3")
        self.assertTrue(self.command.is_symlink())
        self.assertEqual(self.command.resolve().parent.parent.parent, self.data.resolve())
        self.assertEqual(self.command.resolve().parent.parent.stat().st_mode & 0o777, 0o700)
        self.assertIn('export PATH="$HOME/.local/bin:$PATH"', result.stdout)

    def test_unsupported_python_fails_without_changes(self):
        result = self.install(INSTALL_TEST_PYTHON="none")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Python 3.11", result.stderr)
        self.assertFalse(self.data.exists())
        self.assertFalse(self.command.exists())

    def test_missing_python_fails_without_changes(self):
        for runtime in self.bin.glob("python*"):
            runtime.unlink()
        result = self.install(PATH=str(self.bin))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Python 3.11", result.stderr)
        self.assertFalse(self.data.exists())

    def test_versioned_python_is_used_when_python3_is_old(self):
        result = self.install(INSTALL_TEST_PYTHON="python3.11")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_cli(), "arct 0.1.0rc3")

    def test_unsupported_platform_fails_without_changes(self):
        result = self.install(INSTALL_TEST_OS="MINGW64_NT")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.data.exists())

    def test_failed_first_install_does_not_leave_command_or_environment(self):
        result = self.install(INSTALL_TEST_PIP_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.command.exists())
        self.assertEqual(list(self.data.glob("venv-*")), [])
        self.assertFalse((self.home / ".bashrc").exists())

    def test_failed_update_preserves_working_command(self):
        self.assertEqual(self.install().returncode, 0)
        old = self.command.resolve()
        profile = (self.home / ".bashrc").read_bytes()
        result = self.install(INSTALL_TEST_PIP_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.command.resolve(), old)
        self.assertEqual(self.run_cli(), "arct 0.1.0rc3")
        self.assertEqual((self.home / ".bashrc").read_bytes(), profile)
        self.assertEqual(list(self.data.glob("venv-*")), [old.parent.parent])

    def test_interrupt_after_activation_preserves_working_command(self):
        self.assertEqual(self.install().returncode, 0)
        old = self.command.resolve()
        result = self.install(INSTALL_TEST_INTERRUPT="1", INSTALL_TEST_RESULT="updated CLI")
        self.assertEqual(result.returncode, 130, result.stderr)
        self.assertTrue(self.command.exists(), "The active environment must survive interruption")
        self.assertNotEqual(self.command.resolve(), old)
        self.assertEqual(self.run_cli(), "updated CLI")
        self.assertTrue(old.exists())

    def test_repeat_install_replaces_owned_environment_and_keeps_profiles(self):
        profile = self.home / ".bashrc"
        profile.write_text("# User settings")
        login = self.home / ".bash_login"
        login.write_text("# User login\n")
        self.assertEqual(self.install().returncode, 0)
        old = self.command.resolve().parent.parent
        contents = profile.read_bytes(), login.read_bytes()
        result = self.install(INSTALL_TEST_RESULT="updated CLI")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_cli(), "updated CLI")
        self.assertFalse(old.exists())
        self.assertEqual((profile.read_bytes(), login.read_bytes()), contents)
        self.assertTrue(profile.read_text().startswith("# User settings\n"))
        self.assertFalse((self.home / ".bash_profile").exists())
        self.assertFalse((self.home / ".profile").exists())
        activated = subprocess.check_output(
            ["/bin/sh", "-c", '. "$HOME/.bashrc"; . "$HOME/.bashrc"; command -v arct; printf "%s" "$PATH"'],
            env=self.env, text=True,
        )
        self.assertEqual(activated.splitlines()[0], str(self.command))
        self.assertEqual(activated.splitlines()[1].split(":").count(str(self.command.parent)), 1)

    def test_zsh_respects_zdotdir_without_touching_other_profiles(self):
        zdotdir = self.home / "zsh settings"
        zdotdir.mkdir()
        profile = zdotdir / ".zshrc"
        profile.write_text("# User zsh\n")
        result = self.install(SHELL="/bin/zsh", ZDOTDIR=str(zdotdir))
        self.assertEqual(result.returncode, 0, result.stderr)
        contents = profile.read_bytes()
        self.assertTrue(contents.startswith(b"# User zsh\n"))
        self.assertEqual(self.install(SHELL="/bin/zsh", ZDOTDIR=str(zdotdir)).returncode, 0)
        self.assertEqual(profile.read_bytes(), contents)
        self.assertFalse((self.home / ".zshrc").exists())
        self.assertFalse((self.home / ".profile").exists())

    def test_unrelated_command_is_not_overwritten(self):
        self.command.parent.mkdir(parents=True)
        self.command.write_text("existing binary")
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.command.read_text(), "existing binary")
        self.assertEqual(list(self.data.glob("venv-*")), [])

    def test_unrelated_symlink_is_not_overwritten(self):
        other = self.root / "other command"
        other.write_text("existing binary")
        self.command.parent.mkdir(parents=True)
        self.command.symlink_to(other)
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.command.resolve(), other)

    def test_other_shells_print_manual_setup_without_profile_changes(self):
        result = self.install(SHELL="/usr/bin/fish")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("bash and zsh", result.stdout)
        self.assertFalse((self.home / ".profile").exists())


if __name__ == "__main__":
    unittest.main()
