import contextlib
import importlib
import json
import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile


# Import the actual standalone updater without opening a log in the checkout.
with tempfile.TemporaryDirectory(prefix="mah-updater-import-") as import_dir:
    with contextlib.chdir(import_dir), patch(
        "logging.handlers.TimedRotatingFileHandler", return_value=logging.NullHandler()
    ):
        updater = importlib.import_module("updater")


class ResourceResetTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mah-resource-reset-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.enterContext(contextlib.chdir(self.root))
        self.assertEqual(Path.cwd().resolve(), self.root)
        self.enterContext(patch.object(updater, "ensure_mfw_not_running", return_value=True))
        self.enterContext(patch.object(updater, "start_mfw_process"))
        self.enterContext(patch.object(updater.time, "sleep"))
        self.enterContext(patch.object(updater, "print"))
        self.root_delete = self.enterContext(
            patch.object(
                updater,
                "safe_delete_all_except",
                side_effect=AssertionError("Resource reset must not clean the app directory"),
            )
        )
        self.preserved = {
            "MAH.exe": b"installed application",
            "_internal/python.exe": b"installed runtime",
            "agent/main.py": b"installed agent",
            "config/settings.json": b"user settings",
            "data/user.json": b"user data",
            "resource/base/pipeline/tasks.json": b"installed pipeline",
            "resource/base/model/ocr.onnx": b"installed model",
            "resource/resource_jp/pipeline/tasks.json": b"language pipeline",
        }
        for name, content in self.preserved.items():
            self.write(name, content)
        self.interface = {
            "name": "MAH",
            "version": "v1.3.2-alpha1",
            "resource_version": "old resources",
            "agent": {"child_args": ["./agent/main.py"]},
        }
        self.write("interface.json", json.dumps(self.interface).encode())
        self.write("resource/base/image/character/example/01/default/icon.png", b"old")
        self.write("resource/index/characters.json", b"{}")
        self.metadata = {
            "source": "github",
            "mode": "full",
            "target": "resource",
            "version": "new resources",
            "package_name": "resources.zip",
        }

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def make_package(self, prefix="", include_index=True):
        package = self.root / "update/new_version/resources.zip"
        package.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr(prefix + "image/character/example/01/default/icon.png", b"new")
            archive.writestr(prefix + "image/character/masakado/02/default/icon.png", b"added")
            if include_index:
                archive.writestr(prefix + "index/characters.json", b'{"updated": true}')
            archive.writestr(prefix + "README.md", b"resource notes")
            archive.writestr(prefix + "MAH.exe", b"unrelated file in package")
        self.write("update/new_version/update_metadata.json", json.dumps(self.metadata).encode())
        return package

    def assert_preserved(self):
        self.root_delete.assert_not_called()
        for name, content in self.preserved.items():
            self.assertEqual((self.root / name).read_bytes(), content, name)
        self.assertFalse((self.root / "image").exists())
        self.assertFalse((self.root / "index").exists())
        self.assertFalse((self.root / "README.md").exists())

    def assert_reset(self):
        self.assert_preserved()
        self.assertEqual(
            (self.root / "resource/base/image/character/example/01/default/icon.png").read_bytes(),
            b"new",
        )
        self.assertEqual(
            (self.root / "resource/base/image/character/masakado/02/default/icon.png").read_bytes(),
            b"added",
        )
        self.assertEqual(
            (self.root / "resource/index/characters.json").read_bytes(), b'{"updated": true}'
        )
        expected_interface = dict(self.interface, resource_version="new resources")
        self.assertEqual(json.loads((self.root / "interface.json").read_text()), expected_interface)

    def test_standard_resource_reset_only_overwrites_resource_files(self):
        for source in ("github", "mirror", "unknown"):
            with self.subTest(source=source):
                self.metadata["source"] = source
                self.make_package()
                updater.standard_update()
                self.assert_reset()

    def test_resource_full_update_accepts_wrapped_payload(self):
        package = self.make_package(prefix="mah_res/")
        self.assertTrue(updater.perform_full_update(str(package), "unused.json", self.metadata))
        self.assert_reset()

    def test_incomplete_resource_package_does_not_touch_installation(self):
        package = self.make_package(include_index=False)
        self.assertFalse(updater.perform_full_update(str(package), "unused.json", self.metadata))
        self.assert_preserved()
        self.assertEqual(json.loads((self.root / "interface.json").read_text()), self.interface)
        self.assertEqual(
            (self.root / "resource/base/image/character/example/01/default/icon.png").read_bytes(),
            b"old",
        )

    def test_broken_archive_does_not_touch_installation(self):
        package = self.write("update/new_version/resources.zip", b"not a zip archive")
        self.assertFalse(updater.perform_full_update(str(package), "unused.json", self.metadata))
        self.assert_preserved()
        self.assertEqual(json.loads((self.root / "interface.json").read_text()), self.interface)

    def test_software_full_update_keeps_existing_dispatch(self):
        package = self.make_package()
        with patch.object(updater, "_extract_zip_to_temp", return_value=None) as extract:
            self.assertFalse(
                updater.perform_full_update(
                    str(package), "unused.json", dict(self.metadata, target="software")
                )
            )
        extract.assert_called_once_with(package)


if __name__ == "__main__":
    unittest.main()
