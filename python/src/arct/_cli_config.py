import ctypes
import json
import os
from pathlib import Path
import stat
import sys
import tempfile


def config_file():
    root = os.environ.get("XDG_CONFIG_HOME")
    if not root:
        if sys.platform == "win32":
            root = os.environ.get("APPDATA")
            if not root:
                raise OSError("cannot locate configuration directory")
        elif sys.platform == "darwin":
            root = Path.home() / "Library" / "Application Support"
        else:
            root = Path.home() / ".config"
    return Path(root) / "arct" / "config.json"


def _private(path, directory=False):
    if os.name != "nt":
        os.chmod(path, 0o700 if directory else 0o600)
        return
    from ctypes import wintypes
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    pointer = ctypes.c_void_p
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, pointer, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi.ConvertSidToStringSidW.argtypes = [pointer, ctypes.POINTER(wintypes.LPWSTR)]
    advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(pointer), pointer]
    advapi.SetFileSecurityW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, pointer]
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.LocalFree.argtypes = [pointer]
    handle = wintypes.HANDLE()
    sid = wintypes.LPWSTR()
    descriptor = pointer()
    try:
        if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(handle)):
            raise OSError("cannot resolve credential owner")
        size = wintypes.DWORD()
        advapi.GetTokenInformation(handle, 1, None, 0, ctypes.byref(size))
        user = ctypes.create_string_buffer(size.value)
        if not advapi.GetTokenInformation(handle, 1, user, size, ctypes.byref(size)):
            raise OSError("cannot resolve credential owner")
        if not advapi.ConvertSidToStringSidW(ctypes.cast(user, ctypes.POINTER(pointer))[0], ctypes.byref(sid)):
            raise OSError("cannot resolve credential owner")
        flags = "OICI" if directory else ""
        sddl = f"D:P(A;{flags};FA;;;{sid.value})(A;{flags};FA;;;SY)"
        if not advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, ctypes.byref(descriptor), None):
            raise OSError("cannot create credential ACL")
        if not advapi.SetFileSecurityW(str(path), 4 | 0x80000000, descriptor):
            raise OSError("cannot restrict credential ACL")
    finally:
        if descriptor:
            kernel.LocalFree(descriptor)
        if sid:
            kernel.LocalFree(ctypes.cast(sid, pointer))
        if handle:
            kernel.CloseHandle(handle)


def load():
    path = config_file()
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {"active": "", "contexts": {}}
    if not stat.S_ISREG(info.st_mode):
        raise OSError("credential file must be a regular file")
    if os.name == "nt":
        _private(path)
    elif info.st_mode & 0o077:
        raise OSError("credential file requires owner-only permissions (0600)")
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(fd, encoding="utf-8") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise OSError("credential file must be a regular file")
            value = json.load(stream)
        active, contexts = value.get("active", ""), value.get("contexts", {})
        if contexts is None:
            contexts = {}
        if not isinstance(active, str) or not isinstance(contexts, dict):
            raise ValueError
        for name, item in contexts.items():
            if not isinstance(item, dict) or not isinstance(item.get("token", ""), str) or not isinstance(item.get("base_url", ""), str):
                raise ValueError
        return {"active": active, "contexts": contexts}
    except (ValueError, TypeError, AttributeError, UnicodeError):
        raise OSError("invalid credential configuration") from None


def save(value):
    path = config_file()
    directory = path.parent
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or directory.is_symlink():
        raise OSError("credential directory must be a real directory")
    if path.is_symlink() or path.exists() and not stat.S_ISREG(path.lstat().st_mode):
        raise OSError("credential file must be a regular file")
    _private(directory, True)
    fd, temporary = tempfile.mkstemp(prefix=".config-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            _private(temporary)
            json.dump(value, stream)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
