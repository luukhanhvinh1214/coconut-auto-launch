import logging
from pathlib import Path

import webview

import core

INDEX_HTML = core.ROOT / "frontend" / "dist" / "index.html"

log = logging.getLogger("coconut.ui")


class Api:
    def __init__(self) -> None:
        self._window = None

    def get_state(self) -> dict:
        return {"apps": core.load_apps(), "startup": core.is_startup_enabled()}

    def save_apps(self, apps: list[dict]) -> None:
        core.save_apps(apps)

    def pick_app(self) -> dict | None:
        paths = self._window.create_file_dialog(
            webview.FileDialog.OPEN,
            file_types=("Ứng dụng (*.exe;*.lnk)", "Tất cả tệp (*.*)"),
        )
        if not paths:
            return None
        path = Path(paths[0])
        return {"name": path.stem, "path": str(path), "delay": 0}

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
    webview.start()
