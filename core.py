import json
import logging
import os
import sys
import time
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
LOG_PATH = ROOT / "coconut-auto-launch.log"

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APPROVED_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
VALUE_NAME = "CoconutAutoLaunch"

log = logging.getLogger("coconut")


def clean_apps(raw: object) -> list[dict]:
    apps = []
    for item in raw if isinstance(raw, list) else []:
        path = item.get("path") if isinstance(item, dict) else None
        if not isinstance(path, str) or not path:
            log.warning("skip invalid app entry: %r", item)
            continue
        name = item.get("name")
        try:
            delay = max(0, int(item.get("delay", 0)))
        except (TypeError, ValueError):
            delay = 0
        apps.append({
            "name": name if isinstance(name, str) else Path(path).stem,
            "path": path,
            "delay": delay,
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
    start = time.monotonic()
    for app in sorted(apps, key=lambda a: a["delay"]):
        wait = start + app["delay"] - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        path = Path(app["path"])
        try:
            if path.suffix.lower() == ".exe":
                os.startfile(path, cwd=str(path.parent))
            else:
                os.startfile(path)
            log.info("launched %s", path)
        except OSError as exc:
            log.error("cannot launch %s: %s", path, exc)


def startup_command() -> str:
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
