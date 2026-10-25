import importlib.machinery
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# These checks exercise pure decision/parsing functions, not the system DBus.
try:
    import dbus
except ImportError:
    sys.modules["dbus"] = types.ModuleType("dbus")


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_"), str(ROOT / "bin" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class RotationTests(unittest.TestCase):
    def test_laptop_always_restores_landscape(self):
        rotation = load("pixelbook-autorotate")
        for previous in (None, 0, 1, 2, 3):
            self.assertEqual(rotation.desired_transform(False, "left-up", previous), 0)

    def test_four_orientations_and_flat_retention(self):
        rotation = load("pixelbook-autorotate")
        for name, value in (("normal", 0), ("left-up", 1), ("bottom-up", 2), ("right-up", 3)):
            self.assertEqual(rotation.desired_transform(True, name, 0), value)
        self.assertEqual(rotation.desired_transform(True, "undefined", 3), 3)
        self.assertEqual(rotation.desired_transform(True, "undefined", None), 0)

    def test_display_touch_and_pen_receive_same_transform(self):
        rotation = load("pixelbook-autorotate")
        calls = []
        rotation.hypr = lambda *args: calls.append(args) or "ok"
        rotation.apply_transform(3)
        self.assertEqual(calls[0][0], "eval")
        expression = calls[0][1]
        self.assertIn('hl.monitor({ output = "eDP-1", transform = 3 })', expression)
        self.assertEqual(expression.count("transform = 3"), 4)
        for device in (*rotation.TOUCH, rotation.PEN):
            self.assertIn(device, expression)


class FocusTests(unittest.TestCase):
    def test_reports_focused_context_and_cleared_focus(self):
        osk = load("pixelbook-osk")
        metadata = ('Group [wayland:] has 2 InputContext(s)\n'
                    '  IC [abcdef123] program:browser frontend:wayland_v2 cap:1072 focus:1\n'
                    '  IC [001122] program:terminal frontend:wayland_v2 cap:1072 focus:0\n'
                    'Input Context without group\n')
        controller = types.SimpleNamespace(DebugInfo=lambda **kwargs: metadata)
        self.assertEqual(osk.focused_context(controller), "abcdef123")
        metadata = metadata.replace("focus:1", "focus:0")
        self.assertIsNone(osk.focused_context(controller))

    def test_unrecognized_diagnostic_format_fails_closed(self):
        osk = load("pixelbook-osk")
        controller = types.SimpleNamespace(DebugInfo=lambda **kwargs: "changed protocol")
        with self.assertRaises(RuntimeError):
            osk.focused_context(controller)


if __name__ == "__main__":
    unittest.main()
