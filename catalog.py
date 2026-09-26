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
    links = [app for app in start_menu_links() if not (profiles and app["name"] == "Google Chrome")]
    unique = {}
    for app in [*profiles, *links, *packaged_apps()]:
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
