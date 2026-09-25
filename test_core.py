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
            {"name": "Trình duyệt", "path": r"C:\Thư mục có dấu cách\app.exe", "delay": "5"},
            {"path": r"C:\a\notes.lnk", "delay": -3},
            {"name": "x", "path": r"C:\b.exe", "delay": ""},
            {"name": "no path"},
            "garbage",
        ])
        self.assertEqual(core.load_apps(), [
            {"name": "Trình duyệt", "path": r"C:\Thư mục có dấu cách\app.exe", "delay": 5},
            {"name": "notes", "path": r"C:\a\notes.lnk", "delay": 0},
            {"name": "x", "path": r"C:\b.exe", "delay": 0},
        ])
        self.assertFalse(self.config.with_suffix(".tmp").exists())


class LaunchTest(unittest.TestCase):
    def test_launch_order_waits_and_continues_after_error(self) -> None:
        apps = [
            {"name": "late", "path": r"C:\late.exe", "delay": 10},
            {"name": "missing", "path": r"C:\missing.exe", "delay": 0},
            {"name": "doc", "path": r"C:\doc.lnk", "delay": 0},
        ]
        opened = []

        def fake_startfile(path, **kwargs):
            opened.append((str(path), kwargs))
            if "missing" in str(path):
                raise FileNotFoundError(2, "not found")

        with mock.patch.object(core.os, "startfile", fake_startfile), \
                mock.patch.object(core.time, "sleep") as sleep, \
                mock.patch.object(core.time, "monotonic", return_value=100.0):
            core.launch_all(apps)

        self.assertEqual(opened, [
            (r"C:\missing.exe", {"cwd": "C:\\"}),
            (r"C:\doc.lnk", {}),
            (r"C:\late.exe", {"cwd": "C:\\"}),
        ])
        sleep.assert_called_once_with(10.0)


if __name__ == "__main__":
    unittest.main()
