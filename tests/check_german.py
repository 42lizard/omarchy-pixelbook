"""Check displayed labels against real XKB output, including shifted keys."""
import ctypes as c
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / ".build/wvkbd-v0.20"
xkb = c.CDLL("libxkbcommon.so.0")
xkb.xkb_context_new.argtypes = [c.c_int]
xkb.xkb_context_new.restype = c.c_void_p
xkb.xkb_keymap_new_from_string.argtypes = [c.c_void_p, c.c_char_p, c.c_int, c.c_int]
xkb.xkb_keymap_new_from_string.restype = c.c_void_p
xkb.xkb_state_new.argtypes = [c.c_void_p]
xkb.xkb_state_new.restype = c.c_void_p
xkb.xkb_state_update_mask.argtypes = [c.c_void_p] + [c.c_uint] * 6
xkb.xkb_state_key_get_utf8.argtypes = [c.c_void_p, c.c_uint, c.c_char_p, c.c_size_t]
context = xkb.xkb_context_new(0)
keymap = xkb.xkb_keymap_new_from_string(context, (source / "german.xkb").read_bytes(), 1, 0)
assert keymap, "German keymap failed to compile"
state = xkb.xkb_state_new(keymap)
codes = {name: int(value) for name, value in re.findall(
    r"^#define\s+(KEY_\w+)\s+(\d+)\s*$",
    Path("/usr/include/linux/input-event-codes.h").read_text(), re.M)}
checked = 0
for line in (ROOT / "keyboard/german-keys.h").read_text().splitlines():
    match = re.match(r'\s*\{("(?:[^"\\]|\\.)*"), ("(?:[^"\\]|\\.)*"), [0-9.]+, Code, (KEY_\w+)', line)
    if not match:
        continue
    low, high = map(json.loads, match.groups()[:2])
    if len(low) != 1 or len(high) != 1 or low in "←↓↑→⌫":
        continue
    for shift, label in ((0, low), (1, high)):
        forced_altgr = "code_mod = AltGr" in line
        assert not forced_altgr or "reset_mod = true" in line
        mask = 128 if forced_altgr else shift
        xkb.xkb_state_update_mask(state, mask, 0, 0, 0, 0, 0)
        output = c.create_string_buffer(32)
        xkb.xkb_state_key_get_utf8(state, codes[match[3]] + 8, output, 32)
        assert output.value.decode() == label, (line, label, output.value.decode())
        checked += 1
assert checked == 96, checked
config = (source / "config.german.h").read_text()
assert config.count("  German,") == 2, "German must be the default in both orientations"
print(f"PASS: {checked} normal, shifted and AltGr outputs match their labels; both orientations use German")
