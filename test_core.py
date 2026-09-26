import tempfile
import unittest
from pathlib import Path
from unittest import mock

import core


class ConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.config = Path(tmp.name) / "config.json"
        patcher = mock.patch.object(core, "CONFIG_PATH", self.config)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_missing_file_gives_empty_list(self) -> None:
        self.assertEqual(core.load_apps(), [])

    def test_broken_file_is_kept_aside(self) -> None:
        self.config.write_text("{not json", encoding="utf-8")
        self.assertEqual(core.load_apps(), [])
        self.assertFalse(self.config.exists())
        self.assertEqual(self.config.with_suffix(".broken.json").read_text(encoding="utf-8"), "{not json")

    def test_save_then_load_cleans_entries(self) -> None:
        core.save_apps([
            {"name": "Trình duyệt", "path": r"C:\Thư mục có dấu cách\app.exe", "args": "--a", "fullscreen": True},
            {"path": r"C:\a\notes.lnk", "delay": 5},
            {"name": "x", "path": r"C:\b.exe", "args": 3, "fullscreen": "yes"},
            {"name": "no path"},
            "garbage",
        ])
        self.assertEqual(core.load_apps(), [
            {"name": "Trình duyệt", "path": r"C:\Thư mục có dấu cách\app.exe", "args": "--a", "fullscreen": True},
            {"name": "notes", "path": r"C:\a\notes.lnk", "args": "", "fullscreen": False},
            {"name": "x", "path": r"C:\b.exe", "args": "", "fullscreen": False},
        ])
        self.assertFalse(self.config.with_suffix(".tmp").exists())


class LaunchTest(unittest.TestCase):
    def test_launch_continues_after_error_and_tracks_fullscreen(self) -> None:
        apps = [
            {"name": "full", "path": r"C:\full.exe", "args": "", "fullscreen": True},
            {"name": "missing", "path": r"C:\missing.exe", "args": "", "fullscreen": True},
            {"name": "doc", "path": r"C:\doc.lnk", "args": "", "fullscreen": False},
        ]
        opened = []

        def fake_execute(app):
            opened.append(app["path"])
            if "missing" in app["path"]:
                raise FileNotFoundError(2, "not found")
            return 42

        with mock.patch.dict(core.os.environ, {"_PYI_APPLICATION_HOME_DIR": r"C:\gone"}), \
                mock.patch.object(core, "_shell_execute", fake_execute), \
                mock.patch.object(core, "_maximize_windows") as maximize:
            core.launch_all(apps)
            self.assertNotIn("_PYI_APPLICATION_HOME_DIR", core.os.environ)

        self.assertEqual(opened, [r"C:\full.exe", r"C:\missing.exe", r"C:\doc.lnk"])
        maximize.assert_called_once_with({42: r"C:\full.exe"})

    def test_owner_follows_parent_chain(self) -> None:
        # Update.exe (10) mở Discord.exe (11), Discord.exe mở tiến trình con (12).
        parents = {12: 11, 11: 10, 10: 1, 20: 1, 0: 0}
        roots = {10: "discord"}
        self.assertEqual(core.owner_of(12, parents, roots), 10)
        self.assertIsNone(core.owner_of(20, parents, roots))
        self.assertIsNone(core.owner_of(0, parents, roots))

    def test_maximize_survives_exited_launcher(self) -> None:
        # Lần quét 2 không còn tiến trình 11 nhưng cửa sổ của 12 vẫn thuộc app gốc 10.
        snapshots = iter([{11: 10, 30: 1}, {12: 11, 30: 1}])
        windows = iter([[(500, 30)], [(500, 30), (600, 12)]])
        with mock.patch.object(core, "_parent_map", lambda: next(snapshots)), \
                mock.patch.object(core, "_app_windows", lambda: next(windows)), \
                mock.patch.object(core, "_user32") as user32, \
                mock.patch.object(core.time, "sleep"):
            core._maximize_windows({10: "discord"})
        user32.ShowWindowAsync.assert_called_once_with(600, core.SW_MAXIMIZE)


if __name__ == "__main__":
    unittest.main()
