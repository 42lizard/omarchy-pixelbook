# Omarchy Pixelbook

Tablet-mode screen rotation and a German on-screen keyboard for the original Google Pixelbook running Omarchy and Hyprland.

The setup was tested on Omarchy 4.0.6, Hyprland 0.56.2 (Lua configuration), Fcitx 5.1.23 and wvkbd 0.20. Other Omarchy/Hyprland versions and other convertible laptops have not been verified.

## What it does

- Rotates the internal display, touchscreen and pen together in tablet/tent mode. Returns to normal landscape in laptop mode; holds the last orientation while the sensor is flat or undecided.
- Shows the on-screen keyboard when a text field gains focus in tablet mode and hides it when text focus is lost. A top-bar keyboard button provides a manual toggle in either mode.
- Uses German QWERTZ in both orientations, with ä, ö, ü, ß, @, € and a symbols layer.
- Keeps Fcitx running with its existing configuration. The helper polls Fcitx's read-only context/focus metadata every 250 ms in tablet mode; wvkbd only provides the keyboard surface and virtual keystrokes. Typed text is not logged.
- Restarts wvkbd if it exits unexpectedly.

This is a local integration, not a complete iPad/Android input stack. Automatic activation depends on applications reporting text focus to Fcitx. The manual toggle covers applications that do not.

## Audio setup

Audio on the tested Pixelbook was configured separately using [WeirdTreeThing/chromebook-linux-audio](https://github.com/WeirdTreeThing/chromebook-linux-audio). That setup added Intel AVS driver options, Chromebook-specific ALSA UCM profiles and a WirePlumber headroom adjustment.

For audio on a fresh installation, follow that project's current hardware-specific instructions. This repository's installer and uninstaller do not install, modify or remove the audio setup.

## Install on a fresh Omarchy system

Clone this repository and enter it:

```sh
git clone https://github.com/42lizard/omarchy-pixelbook.git
cd omarchy-pixelbook
```

Install the system dependencies and narrow tablet-switch permission rule:

```sh
./setup-system
```

This step invokes sudo, installs build/runtime packages with pacman, and installs `70-pixelbook-tablet-switch.rules`. That rule gives the active local session access to the device named `Tablet Mode Switch`. It does not add your account to the `input` group or grant access to keyboard events. Existing different rules are preserved and reported.

Build the keyboard, then install the user files:

```sh
./build-keyboard
./install
```

Run `install` as your desktop user in the running Hyprland session. Fcitx must be running; on Omarchy it normally is. The build downloads upstream wvkbd **v0.20**, verifies its SHA-512 checksum, and applies this repository's German layout overlay. No upstream source or binaries are committed here. The German XKB keymap is generated from the system's `de` layout at build time; this keyboard does not dynamically follow later physical keyboard layout switches.

The installer copies the helpers, keyboard binary and two user services, adds Hyprland startup entries, adds the keyboard bar button and adds missing Brave/Chromium Wayland input flags. It validates Hyprland before starting the helpers. It backs up originals under `~/.local/state/omarchy-pixelbook/backups/`. Running it again is a no-op; uninstall before replacing an installed version.

Existing Fcitx settings, other bindings, keyd settings, monitor resolution/scale and unrelated shell settings are preserved. An existing conflicting browser flag is reported and preserved. Symlinked destination files are rejected so dotfile repositories are not silently overwritten. The automatic installer uses the standard `~/.config` and `~/.local` locations; custom XDG directory layouts require manual integration.

**Fully quit and reopen Brave/Chromium** for their input flags to take effect. The installer does not close your browser. A logout/login can be needed if the tablet-switch access rule has not taken effect.

## Check it

Fold the Pixelbook back, rotate it, and tap a browser form field. Check `z y ä ö ü ß @ €`, Shift, the symbols layer and both screen orientations. Return to laptop mode and check that the screen is landscape and the keyboard disappears. The keyboard button should still allow a manual show/hide.

```sh
systemctl --user status pixelbook-autorotate pixelbook-osk
journalctl --user -u pixelbook-autorotate -u pixelbook-osk -n 50
```

To stop the trial for the current session:

```sh
systemctl --user stop pixelbook-osk pixelbook-autorotate
```

Rotation restores normal landscape when stopped. To start again:

```sh
systemctl --user start pixelbook-autorotate pixelbook-osk
```

## Uninstall

```sh
./uninstall
```

Untouched managed files are removed or their originals restored. Later changes in shared configuration files are retained while the installer's startup block, button and contributed browser flags are removed. Modified helper files or an edited keyboard button are preserved and reported. Backups are retained. If this installation replaced an older working setup, its original files are restored.

System packages and the udev rule are left installed. To explicitly remove the matching rule as well:

```sh
./setup-system --remove-rule
```

## Limits and known issue

- Rotation targets `eDP-1`, the Pixelbook WCOM50C1 touchscreen/pen and the device named `Tablet Mode Switch`. These identifiers are in `bin/pixelbook-autorotate`; porting to another machine requires checking its devices and sensor orientation.
- Sensor orientation comes from iio-sensor-proxy. This repository does not configure firmware, kernel drivers, audio or suspend.
- Fcitx focus detection parses `Controller1.DebugInfo`, a diagnostic interface whose output can change between versions. An unrecognized format hides the keyboard and reports an error; Fcitx is not disabled or reconfigured.
- A single wvkbd 0.20 SIGSEGV was observed in its Wayland drawing callback during testing. The helper restarted it two seconds later. The underlying drawing bug is unresolved; the German layout does not claim to fix it.
- Automatic activation has been exercised with GTK text/non-text focus and used successfully in the live Pixelbook session. The physical folding/rotation behaviour was confirmed on that machine. Lock-screen typing and login-screen support are not provided by this integration.
- This package does not add a new policy to disable the physical keyboard or touchpad in tablet mode. It preserves the machine's existing behaviour.

## Development checks

No desktop or root changes are made by the installer tests:

```sh
python -m unittest discover -s tests -v
./build-keyboard
python tests/check_german.py
```

For an offline build, supply the verified upstream archive:

```sh
./build-keyboard --archive /path/to/wvkbd-0.20.tar.gz
```

The build files stay in `.build/`, which Git ignores. The installer also supports staging into a temporary home that contains a minimal Omarchy shell configuration:

```sh
./install --home /tmp/pixelbook-test-home --no-start
./uninstall --home /tmp/pixelbook-test-home --no-start
```

## License and upstream

GPL-3.0; see [LICENSE](LICENSE). The keyboard overlay is derived from [wvkbd](https://git.sr.ht/~proycon/wvkbd), originally by John Sullivan and maintained by the Sxmo project. See [NOTICE](NOTICE) for provenance. Upstream licenses and copyright notices remain in the downloaded source tree.
