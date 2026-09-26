import logging
import sys
from pathlib import Path

import webview

import catalog
import core

# Bản exe mang theo frontend/dist trong thư mục giải nén _MEIPASS.
INDEX_HTML = Path(getattr(sys, "_MEIPASS", core.ROOT)) / "frontend" / "dist" / "index.html"
# Bản exe không có file này, pywebview tự lấy icon của exe.
ICON = core.ROOT / "logo.ico"

log = logging.getLogger("coconut.ui")


class Api:
    def __init__(self) -> None:
        self._window = None

    def get_state(self) -> dict:
        return {"apps": core.load_apps(), "startup": core.is_startup_enabled()}

    def save_apps(self, apps: list[dict]) -> None:
        core.save_apps(apps)

    def list_apps(self) -> list[dict]:
        return catalog.list_apps()

    def pick_app(self) -> dict | None:
        paths = self._window.create_file_dialog(
            webview.FileDialog.OPEN,
            file_types=("Ứng dụng (*.exe;*.lnk)", "Tất cả tệp (*.*)"),
        )
        if not paths:
            return None
        path = Path(paths[0])
        return {"name": path.stem, "path": str(path), "args": "", "detail": ""}

    def set_startup(self, enabled: bool) -> bool:
        if enabled:
            core.enable_startup()
        else:
            core.disable_startup()
        return core.is_startup_enabled()


def run() -> None:
    if not INDEX_HTML.exists():
        log.error("missing %s, run npm run build in frontend", INDEX_HTML)
        raise SystemExit(1)
    api = Api()
    api._window = webview.create_window(
        "Coconut Auto Launch",
        str(INDEX_HTML),
        js_api=api,
        width=880,
        height=600,
        min_size=(640, 440),
        background_color="#E6F3FA",
    )
    webview.start(icon=str(ICON))
