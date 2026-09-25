import logging
import sys

import core


def main() -> None:
    logging.basicConfig(
        filename=core.LOG_PATH,
        encoding="utf-8",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # pythonw không có console, lỗi không bắt phải vào file log.
    sys.excepthook = lambda *exc: logging.critical("unhandled error", exc_info=exc)
    if "--startup" in sys.argv:
        apps = core.load_apps()
        logging.info("startup run with %d apps", len(apps))
        core.launch_all(apps)
    else:
        import ui
        ui.run()


if __name__ == "__main__":
    main()
