import json
import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="omarchy-pixelbook-test-")
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.shell = self.home / ".config/omarchy/shell.json"
        self.shell.parent.mkdir(parents=True)
        self.shell.write_text(json.dumps({"version": 1, "bar": {"layout": {
            "left": [{"id": "existing"}], "center": [], "right": []}}, "idle": {"lock": 123}}))
        self.autostart = self.home / ".config/hypr/autostart.lua"
        self.autostart.parent.mkdir(parents=True)
        self.autostart.write_text('-- personal startup\no.launch_on_start("keep-me")\n')
        self.brave = self.home / ".config/brave-flags.conf"
        self.brave.write_text("--enable-wayland-ime\n--custom-option=yes\n")
        self.binary = self.home / "fixture-keyboard"
        self.binary.write_text("#!/bin/sh\nexit 0\n")
        self.binary.chmod(0o755)

    def command(self, name, ok=True):
        command = [str(ROOT / name), "--home", str(self.home), "--no-start"]
        if name == "install":
            command += ["--keyboard-binary", str(self.binary)]
        result = subprocess.run(command, capture_output=True, text=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def test_roundtrip_restores_originals_and_install_is_idempotent(self):
        paths = [self.shell, self.autostart, self.brave]
        originals = {p: p.read_bytes() for p in paths}
        self.command("install")
        installed = {p: p.read_bytes() for p in paths}
        self.command("install")
        self.assertEqual(installed, {p: p.read_bytes() for p in paths})
        self.assertEqual(self.brave.read_text().count("--enable-wayland-ime"), 1)
        self.command("uninstall")
        self.command("install")
        self.command("uninstall")
        self.assertEqual(originals, {p: p.read_bytes() for p in paths})
        self.assertFalse((self.home / ".config/chromium-flags.conf").exists())
        self.assertFalse((self.home / ".local/bin/pixelbook-osk").exists())
        self.command("uninstall")

    def test_mid_install_write_failure_rolls_back(self):
        loader = importlib.machinery.SourceFileLoader("pixelbook_installer", str(ROOT / "install"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        installer = importlib.util.module_from_spec(spec)
        loader.exec_module(installer)
        original = self.autostart.read_bytes()
        real_write = installer.write
        writes = 0

        def fail_third_write(*args):
            nonlocal writes
            writes += 1
            if writes == 3:
                raise OSError("simulated disk failure")
            return real_write(*args)

        argv = [str(ROOT / "install"), "--home", str(self.home), "--no-start",
                "--keyboard-binary", str(self.binary)]
        with patch("sys.argv", argv), patch.object(installer, "write", fail_third_write):
            with self.assertRaises(OSError):
                installer.main()
        self.assertEqual(self.autostart.read_bytes(), original)
        self.assertFalse((self.home / ".local/bin/pixelbook-osk").exists())
        self.assertFalse((self.home / ".local/bin/pixelbook-autorotate").exists())
        self.assertFalse((self.home / ".local/state/omarchy-pixelbook/install.json").exists())

    def test_later_user_changes_survive(self):
        self.command("install")
        self.autostart.write_text(self.autostart.read_text() + '-- added later\n')
        self.brave.write_text(self.brave.read_text() + '--later-flag\n')
        settings = json.loads(self.shell.read_text())
        settings["idle"]["lock"] = 999
        # A user may move the button after installing.
        widget = settings["bar"]["layout"]["right"].pop(0)
        settings["bar"]["layout"]["left"].append(widget)
        self.shell.write_text(json.dumps(settings))
        self.command("uninstall")
        self.assertIn('-- added later', self.autostart.read_text())
        self.assertNotIn('pixelbook-osk.service', self.autostart.read_text())
        self.assertIn('--later-flag', self.brave.read_text())
        self.assertIn('--enable-wayland-ime', self.brave.read_text())
        self.assertNotIn('--wayland-text-input-version', self.brave.read_text())
        settings = json.loads(self.shell.read_text())
        self.assertEqual(settings["idle"]["lock"], 999)
        self.assertEqual(settings["bar"]["layout"]["left"], [{"id": "existing"}])

    def test_existing_helpers_and_widget_are_restored(self):
        old = self.home / ".local/bin/pixelbook-osk"
        old.parent.mkdir(parents=True)
        old.write_text('previous helper')
        old.chmod(0o700)
        self.autostart.write_text(self.autostart.read_text() +
            'o.exec_on_start("systemctl --user start pixelbook-osk.service")\n')
        settings = json.loads(self.shell.read_text())
        previous_widget = {"id": "pixelbook.osk", "onClick": "previous-command"}
        settings["bar"]["layout"]["right"].append(previous_widget)
        self.shell.write_text(json.dumps(settings))
        self.command("install")
        self.assertEqual(self.autostart.read_text().count('start pixelbook-osk.service'), 1)
        self.command("uninstall")
        self.assertEqual(old.read_text(), 'previous helper')
        self.assertEqual(old.stat().st_mode & 0o777, 0o700)
        self.assertEqual(json.loads(self.shell.read_text())["bar"]["layout"]["right"], [previous_widget])

    def test_modified_helper_is_not_deleted(self):
        self.command("install")
        helper = self.home / ".local/bin/pixelbook-osk"
        helper.write_text('my modified helper')
        result = self.command("uninstall")
        self.assertEqual(helper.read_text(), 'my modified helper')
        self.assertIn('Preserved modified file', result.stdout)

    def test_invalid_json_does_not_change_anything(self):
        self.shell.write_text('{invalid')
        original = self.autostart.read_bytes()
        self.command("install", ok=False)
        self.assertEqual(self.autostart.read_bytes(), original)
        self.assertFalse((self.home / ".local/bin/pixelbook-osk").exists())

    def test_symlink_is_preserved_and_install_aborts(self):
        actual = self.home / "actual-flags"
        actual.write_text("keep this")
        self.brave.unlink()
        self.brave.symlink_to(actual)
        self.command("install", ok=False)
        self.assertTrue(self.brave.is_symlink())
        self.assertEqual(actual.read_text(), "keep this")
        self.assertFalse((self.home / ".local/bin/pixelbook-osk").exists())

    def test_conflicting_browser_flag_is_preserved(self):
        self.brave.write_text('--ozone-platform=x11\n')
        result = self.command("install")
        self.assertIn('Preserving', result.stdout)
        self.assertIn('--ozone-platform=x11', self.brave.read_text())
        self.assertNotIn('--ozone-platform=wayland', self.brave.read_text())


if __name__ == "__main__":
    unittest.main()
