import ctypes
import json
import logging
import os
import sys
import time
import winreg
from ctypes import wintypes
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
# Bản exe onefile chạy từ thư mục tạm, dữ liệu người dùng phải nằm cạnh file exe.
ROOT = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
LOG_PATH = ROOT / "coconut-auto-launch.log"

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APPROVED_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
VALUE_NAME = "CoconutAutoLaunch"

SW_SHOWNORMAL = 1
SW_MAXIMIZE = 3
SEE_MASK_NOCLOSEPROCESS = 0x40
SEE_MASK_NOASYNC = 0x100
# Không có cờ này thì đường dẫn hỏng bật hộp lỗi và chặn cả danh sách lúc đăng nhập.
SEE_MASK_FLAG_NO_UI = 0x400
GWL_STYLE = -16
GW_OWNER = 4
WS_MAXIMIZEBOX = 0x10000
TH32CS_SNAPPROCESS = 0x2
INVALID_HANDLE = ctypes.c_void_p(-1).value
# Lúc đăng nhập app như Discord có thể mất vài chục giây mới hiện cửa sổ chính.
MAXIMIZE_TIMEOUT = 60

log = logging.getLogger("coconut")


class _ShellExecuteInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", wintypes.ULONG),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIcon", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


class _ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

_shell32 = ctypes.WinDLL("shell32", use_last_error=True)
_shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(_ShellExecuteInfo)]
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.GetProcessId.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
_kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)]
_kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)]
_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.EnumWindows.argtypes = [_WNDENUMPROC, wintypes.LPARAM]
_user32.IsWindowVisible.argtypes = [wintypes.HWND]
_user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
_user32.GetWindow.restype = wintypes.HWND
_user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_user32.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]


def clean_apps(raw: object) -> list[dict]:
    apps = []
    for item in raw if isinstance(raw, list) else []:
        path = item.get("path") if isinstance(item, dict) else None
        if not isinstance(path, str) or not path:
            log.warning("skip invalid app entry: %r", item)
            continue
        name = item.get("name")
        args = item.get("args")
        apps.append({
            "name": name if isinstance(name, str) else Path(path).stem,
            "path": path,
            "args": args if isinstance(args, str) else "",
            "fullscreen": item.get("fullscreen") is True,
        })
    return apps


def load_apps() -> list[dict]:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("config root is not an object")
    except FileNotFoundError:
        return []
    except OSError as exc:
        log.error("cannot read %s: %s", CONFIG_PATH, exc)
        return []
    except ValueError as exc:
        broken = CONFIG_PATH.with_suffix(".broken.json")
        log.error("broken config %s, moved to %s: %s", CONFIG_PATH, broken, exc)
        # Giữ lại file hỏng để lần lưu sau không xoá mất dữ liệu người dùng.
        try:
            CONFIG_PATH.replace(broken)
        except OSError as move_exc:
            log.error("cannot move broken config: %s", move_exc)
        return []
    return clean_apps(data.get("apps"))


def save_apps(apps: list[dict]) -> None:
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps({"apps": clean_apps(apps)}, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, CONFIG_PATH)


def launch_all(apps: list[dict]) -> None:
    # App được mở kế thừa biến _PYI_* của bản exe, làm mọi exe PyInstaller mở từ app đó lỗi "Failed to load Python DLL".
    for name in [name for name in os.environ if name.upper().startswith("_PYI_")]:
        del os.environ[name]
    # ShellExecuteEx có thể gọi shell extension qua COM.
    ctypes.windll.ole32.CoInitializeEx(None, 0x6)
    fullscreen = {}
    for app in apps:
        try:
            pid = _shell_execute(app)
            log.info("launched %s", app["path"])
        except OSError as exc:
            log.error("cannot launch %s: %s", app["path"], exc)
            continue
        if app["fullscreen"]:
            if pid:
                fullscreen[pid] = app["path"]
            else:
                log.warning("no process to maximize for %s", app["path"])
    _maximize_windows(fullscreen)


def _shell_execute(app: dict) -> int | None:
    path = Path(app["path"])
    info = _ShellExecuteInfo(
        cbSize=ctypes.sizeof(_ShellExecuteInfo),
        fMask=SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC | SEE_MASK_FLAG_NO_UI,
        lpFile=app["path"],
        lpParameters=app["args"] or None,
        lpDirectory=str(path.parent) if path.suffix.lower() == ".exe" else None,
        nShow=SW_MAXIMIZE if app["fullscreen"] else SW_SHOWNORMAL,
    )
    if not _shell32.ShellExecuteExW(ctypes.byref(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not info.hProcess:
        return None
    try:
        return _kernel32.GetProcessId(info.hProcess) or None
    finally:
        _kernel32.CloseHandle(info.hProcess)


def _maximize_windows(roots: dict[int, str]) -> None:
    # Nhiều app (Chrome, Electron, launcher kiểu Update.exe) bỏ qua nShow, nên tự phóng to cửa sổ đầu tiên của cây tiến trình.
    deadline = time.monotonic() + MAXIMIZE_TIMEOUT
    # Nhớ PID qua các lần quét vì tiến trình trung gian (Update.exe, bản tự khởi động lại) thoát giữa chừng.
    # ponytail: PID đã thoát có thể bị Windows cấp lại trong 60 giây, khi đó có thể phóng to nhầm một cửa sổ.
    owners = {pid: pid for pid in roots}
    while roots and time.monotonic() < deadline:
        parents = _parent_map()
        for pid in parents:
            ancestor = owner_of(pid, parents, owners)
            if ancestor is not None:
                owners[pid] = owners[ancestor]
        for hwnd, pid in _app_windows():
            root = owners.get(pid)
            if root in roots:
                _user32.ShowWindowAsync(hwnd, SW_MAXIMIZE)
                log.info("maximized %s", roots.pop(root))
        time.sleep(0.5)
    for path in roots.values():
        log.warning("no window to maximize for %s", path)


def owner_of(pid: int, parents: dict[int, int], known: dict[int, int | str]) -> int | None:
    for _ in range(32):
        if pid in known:
            return pid
        pid = parents.get(pid)
        if pid is None:
            return None
    return None


def _parent_map() -> dict[int, int]:
    snapshot = _kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE:
        log.error("cannot list processes: %s", ctypes.WinError(ctypes.get_last_error()))
        return {}
    try:
        entry = _ProcessEntry(dwSize=ctypes.sizeof(_ProcessEntry))
        parents = {}
        ok = _kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            parents[entry.th32ProcessID] = entry.th32ParentProcessID
            ok = _kernel32.Process32NextW(snapshot, ctypes.byref(entry))
        return parents
    finally:
        _kernel32.CloseHandle(snapshot)


def _app_windows() -> list[tuple[int, int]]:
    found = []

    def visit(hwnd: int, _: int) -> bool:
        # Chỉ lấy cửa sổ chính phóng to được, bỏ qua splash và hộp thoại con.
        if (_user32.IsWindowVisible(hwnd) and not _user32.GetWindow(hwnd, GW_OWNER)
                and _user32.GetWindowLongW(hwnd, GWL_STYLE) & WS_MAXIMIZEBOX):
            pid = wintypes.DWORD()
            _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            found.append((hwnd, pid.value))
        return True

    _user32.EnumWindows(_WNDENUMPROC(visit), 0)
    return found


def startup_command() -> str:
    if FROZEN:
        command = f'"{Path(sys.executable).resolve()}" --startup'
    else:
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        command = f'"{pythonw}" "{ROOT / "app.py"}" --startup'
    if len(command) > 260:
        raise ValueError(f"startup command longer than 260 characters: {command}")
    return command


def is_startup_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            command, _ = winreg.QueryValueEx(key, VALUE_NAME)
    except FileNotFoundError:
        return False
    if command != startup_command():
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APPROVED_KEY) as key:
            flags, _ = winreg.QueryValueEx(key, VALUE_NAME)
    except FileNotFoundError:
        return True
    # Task Manager đánh dấu tắt bằng bit thấp nhất của byte đầu.
    return not (flags and flags[0] & 1)


def enable_startup() -> None:
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, startup_command())
    _delete_value(APPROVED_KEY)


def disable_startup() -> None:
    _delete_value(RUN_KEY)
    _delete_value(APPROVED_KEY)


def _delete_value(subkey: str) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        pass
