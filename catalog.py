import ctypes
import json
import logging
import os
import subprocess
from pathlib import Path

log = logging.getLogger("coconut.catalog")

START_MENUS = [
    Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs",
    Path(os.environ["PROGRAMDATA"]) / "Microsoft/Windows/Start Menu/Programs",
]
CSIDL_DESKTOPDIRECTORY = 0x10
CSIDL_COMMON_DESKTOPDIRECTORY = 0x19
CHROME_STATE = Path(os.environ["LOCALAPPDATA"]) / "Google/Chrome/User Data/Local State"
CHROME_EXES = [
    Path(os.environ[var]) / "Google/Chrome/Application/chrome.exe"
    for var in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")
    if var in os.environ
]
POWERSHELL = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
# App Store không có shortcut trong Start Menu, chỉ lấy được qua AppsFolder.
PACKAGED_APPS = (
    "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
    "Get-StartApps | Where-Object AppID -like '*!*' | ConvertTo-Json -Compress"
)


def list_apps() -> list[dict]:
    profiles = chrome_profiles()
    unique = {}
    for app in [*profiles, *start_menu_links(), *packaged_apps(), *desktop_items()]:
        if profiles and app["name"] == "Google Chrome":
            continue
        unique.setdefault((app["name"].casefold(), app["args"]), app)
    return sorted(unique.values(), key=lambda app: app["name"].casefold())


def chrome_profiles() -> list[dict]:
    exe = next((path for path in CHROME_EXES if path.is_file()), None)
    if exe is None:
        return []
    try:
        cache = json.loads(CHROME_STATE.read_text(encoding="utf-8"))["profile"]["info_cache"]
        return [
            {
                "name": f"Google Chrome - {info.get('name') or folder}",
                "path": str(exe),
                "args": f'--profile-directory="{folder}"',
                "detail": info.get("user_name", ""),
            }
            for folder, info in cache.items()
        ]
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        log.warning("cannot read chrome profiles: %s", exc)
        return []


def start_menu_links() -> list[dict]:
    return [
        {"name": link.stem, "path": str(link), "args": "", "detail": ""}
        for folder in START_MENUS
        for link in folder.rglob("*.lnk")
        if "uninstall" not in link.stem.lower()
    ]


def desktop_items() -> list[dict]:
    # App portable như UniKey không có shortcut trong Start Menu, chỉ nằm trên Desktop.
    folders = [_shell_folder(csidl) for csidl in (CSIDL_DESKTOPDIRECTORY, CSIDL_COMMON_DESKTOPDIRECTORY)]
    return [
        {"name": item.stem, "path": str(item), "args": "", "detail": ""}
        for folder in folders
        if folder
        for item in folder.glob("*")
        if item.suffix.lower() in (".lnk", ".exe") and "install" not in item.stem.lower()
    ]


def _shell_folder(csidl: int) -> Path | None:
    # Desktop có thể bị OneDrive chuyển chỗ, nên hỏi Windows thay vì ghép USERPROFILE\Desktop.
    buffer = ctypes.create_unicode_buffer(260)
    if ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buffer):
        log.warning("cannot find shell folder %#x", csidl)
        return None
    return Path(buffer.value)


def packaged_apps() -> list[dict]:
    try:
        result = subprocess.run(
            [str(POWERSHELL), "-NoProfile", "-NonInteractive", "-Command", PACKAGED_APPS],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=30,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        items = json.loads(result.stdout.decode("utf-8-sig") or "[]")
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        log.warning("cannot list store apps: %s", exc)
        return []
    if isinstance(items, dict):
        items = [items]
    return [
        {"name": item["Name"], "path": "shell:AppsFolder\\" + item["AppID"], "args": "", "detail": ""}
        for item in items
    ]
