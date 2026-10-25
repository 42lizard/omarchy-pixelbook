import os
from pathlib import Path
import signal
import tempfile
import types
import unittest
from unittest.mock import patch

from test_helpers import load


class AutomaticActivationTests(unittest.TestCase):
    def run_helper(self, attached, manual=False):
        osk = load("pixelbook-osk")
        child = types.SimpleNamespace(poll=lambda: None, send_signal=lambda value: signals.append(value),
                                      terminate=lambda: None, wait=lambda **kwargs: None)
        signals = []
        handlers = {}
        tick = 0

        def sleep(seconds):
            nonlocal tick
            if seconds != 0.25:
                return
            if manual and tick == 0:
                handlers[signal.SIGUSR1]()
            tick += 1
            if tick == len(attached):
                handlers[signal.SIGTERM]()

        bus = types.SimpleNamespace(close=lambda: None, get_object=lambda *args: None)
        with tempfile.TemporaryDirectory() as runtime, \
                patch.dict(os.environ, {"XDG_RUNTIME_DIR": runtime}), \
                patch("sys.argv", ["pixelbook-osk"]), \
                patch.object(osk, "tablet_mode", return_value=True), \
                patch.object(osk, "external_keyboard_connected", side_effect=lambda: attached[tick], create=True), \
                patch.object(osk, "focused_context", return_value="same-text-field"), \
                patch.object(osk.subprocess, "Popen", return_value=child), \
                patch.object(osk.signal, "signal", side_effect=lambda sig, fn: handlers.update({sig: fn})), \
                patch.object(osk.time, "sleep", side_effect=sleep), \
                patch.object(osk.time, "monotonic", side_effect=lambda: float(tick)), \
                patch.object(osk.dbus, "SessionBus", return_value=bus, create=True), \
                patch.object(osk.dbus, "Interface", return_value=object(), create=True):
            osk.main()
        return signals

    def test_connect_hides_and_disconnect_reopens_without_focus_change(self):
        self.assertEqual(self.run_helper([False, True, False]),
                         [signal.SIGUSR2, signal.SIGUSR1, signal.SIGUSR2])

    def test_external_keyboard_blocks_initial_automatic_show(self):
        self.assertEqual(self.run_helper([True, True]), [signal.SIGUSR1])

    def test_manual_toggle_still_works_with_external_keyboard(self):
        self.assertEqual(self.run_helper([True, True], manual=True),
                         [signal.SIGUSR1, signal.SIGRTMIN])


class DeviceDetectionTests(unittest.TestCase):
    def setUp(self):
        self.osk = load("pixelbook-osk")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.inputs = self.root / "sys/class/input"
        self.inputs.mkdir(parents=True)

    def device(self, bus, virtual=False, uhid=False):
        parent = "virtual/input" if virtual else "virtual/misc/uhid" if uhid else "pci/usb"
        device = self.root / "sys/devices" / parent / "input0"
        (device / "id").mkdir(parents=True)
        (device / "id/bustype").write_text(bus)
        event = device / "event0"
        event.mkdir()
        (event / "device").symlink_to(device)
        (self.inputs / "event0").symlink_to(event)

    def detect(self, properties):
        result = types.SimpleNamespace(stdout=properties)
        with patch.object(self.osk.subprocess, "run", return_value=result) as query:
            found = self.osk.external_keyboard_connected(self.inputs)
        return found, query

    def test_usb_keyboard_is_detected(self):
        self.device("0003")
        self.assertTrue(self.detect("ID_INPUT_KEYBOARD=1\nID_BUS=usb\n")[0])

    def test_bluetooth_uhid_keyboard_is_detected(self):
        self.device("0005", uhid=True)
        self.assertTrue(self.detect("ID_INPUT_KEYBOARD=1\n")[0])

    def test_usb_mouse_does_not_suppress_keyboard(self):
        self.device("0003")
        self.assertFalse(self.detect("ID_INPUT_MOUSE=1\nID_BUS=usb\n")[0])

    def test_internal_keyboard_does_not_suppress_keyboard(self):
        self.device("0011")
        found, query = self.detect("ID_INPUT_KEYBOARD=1\n")
        self.assertFalse(found)
        query.assert_not_called()

    def test_keyd_virtual_usb_keyboard_is_ignored(self):
        self.device("0003", virtual=True)
        found, query = self.detect("ID_INPUT_KEYBOARD=1\nID_BUS=usb\n")
        self.assertFalse(found)
        query.assert_not_called()


if __name__ == "__main__":
    unittest.main()
