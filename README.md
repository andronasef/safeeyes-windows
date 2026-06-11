<img src="https://raw.githubusercontent.com/slgobinath/safeeyes/master/safeeyes/platform/icons/hicolor/64x64/apps/io.github.slgobinath.SafeEyes.png" align="left">

# Safe Eyes (Cross-Platform)

[![Translation status](https://hosted.weblate.org/widgets/safe-eyes/-/translations/svg-badge.svg)](https://hosted.weblate.org/engage/safe-eyes/?utm_source=widget)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

Protect your eyes from eye strain (asthenopia): Safe Eyes sits quietly in your
system tray and reminds you to take regular short and long breaks while you work
long hours at the computer, guiding you through quick eye-relaxing exercises.

> **About this fork.** The upstream [Safe Eyes](https://github.com/slgobinath/safeeyes)
> is a Linux-only GTK4/PyGObject app. **This fork migrates the UI to
> [PySide6 (Qt)](https://doc.qt.io/qtforpython/) to make Safe Eyes genuinely
> cross-platform.** Windows is built and verified; Linux runs from source on Qt;
> macOS is architecturally supported but untested (stubs only). The break
> scheduler, plugins and 40+ translations are shared across all platforms.

---

## Table of contents

- [Features](#features)
- [Platform support](#platform-support)
- [Quick start](#quick-start)
- [Installation & setup](#installation--setup)
  - [Windows — installer](#windows--installer)
  - [Windows — run from source](#windows--run-from-source)
  - [Linux — run from source](#linux--run-from-source)
- [Usage](#usage)
- [File locations](#file-locations)
- [Building the Windows release](#building-the-windows-release)
- [Architecture](#architecture)
- [Plugins](#plugins)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Translations](#translations)
- [Credits & license](#credits--license)

---

## Features

- ⏰ **Scheduled short and long breaks** with eye-relaxing exercises.
- 🖥️ **Fullscreen break screen on every monitor**, always on top, with a fade-in.
- ⌨️ **System-wide keyboard blocking during breaks** so you can't accidentally
  skip (Windows low-level hook / X11 grab).
- 💤 **Smart pause** — automatically pauses when you're idle and resumes on activity.
- 🔕 **Do Not Disturb** — skips breaks while a fullscreen app / presentation is active.
- 🔔 **Pre-break notification** and **post-break sound**.
- 🔒 **Lock screen after long breaks** (optional).
- ⏯️ **Pause media players** during a break (Linux MPRIS; Windows where supported).
- 🧩 **Plugin system** — every feature above is a plugin; bring your own.
- 🌍 **40+ translations**.
- 🛰️ **Single-instance CLI** — control a running instance from another terminal
  (`-t`, `--status`, `-q`, …).

## Platform support

| Platform | Status | UI toolkit | Notes |
|----------|--------|-----------|-------|
| **Windows 10/11** | ✅ Built & verified | PySide6/Qt | Bundled `.exe` + installer, or run from source |
| **Linux (X11 & Wayland)** | ✅ Runs from source (Qt port) | PySide6/Qt | Idle/lock/fullscreen/media via X11/Wayland/D-Bus |
| **macOS** | 🚧 Architecturally open | PySide6/Qt | OS-integration is stubbed; untested |

## Quick start

Already have it set up? Launch it:

```powershell
# Windows (from a source checkout)
.\.venv\Scripts\python.exe -m safeeyes
```

```bash
# Linux (from a source checkout)
python3 -m safeeyes
```

Safe Eyes runs in the **system tray** — right-click the tray icon for Enable/Disable,
Take a break, Settings, About and Quit. The first break is ~15 minutes away by
default; run `... -m safeeyes -t` to trigger one immediately.

---

## Installation & setup

### Windows — installer

If a built installer is available (see [Building the Windows release](#building-the-windows-release)),
run `SafeEyes-<version>-setup.exe`. It performs a **per-user install** (no admin
required), adds a Start Menu entry, and can optionally start Safe Eyes at login.
Launch it from the Start Menu afterwards.

### Windows — run from source

You need **Python 3.10+** (3.12 recommended). From a *Developer PowerShell* /
terminal in the project root:

```powershell
# 1. Create an isolated virtual environment (keeps your global Python clean)
py -m venv .venv

# 2. Install runtime dependencies into it
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install PySide6 babel packaging

# 3. Compile the translation catalogs (.po -> .mo) once
.\.venv\Scripts\python.exe build_messages.py

# 4. Run it
.\.venv\Scripts\python.exe -m safeeyes
```

Optional extras: `croniter` (for the Health Statistics plugin), `winsdk` (for
pausing media via Windows System Media Transport Controls).

> **Tip:** activate the venv (`.\.venv\Scripts\Activate.ps1`) and you can then
> just type `python -m safeeyes`. If activation is blocked, run
> `Set-ExecutionPolicy -Scope Process RemoteSigned` once in that terminal.

### Linux — run from source

Install the runtime dependencies (Qt is pulled in via pip):

- `python3` (>= 3.10)
- `python3-pyside6` **or** `pip install PySide6`
- `python3-babel`, `python3-packaging`
- `python3-xlib` (X11)
- **Optional:** `python3-croniter` (Health Statistics), `python3-pywayland`
  (smart pause on Wayland), `xprintidle` (smart pause on X11)

```bash
git clone <this-repo-url> safeeyes
cd safeeyes
python3 -m venv .venv && source .venv/bin/activate
pip install PySide6 babel packaging python-xlib
python build_messages.py        # compile translations
python -m safeeyes
```

Or install into the environment (this compiles translations automatically):

```bash
pip install .
safeeyes
```

> Running from source means desktop/window icons may be incomplete because the
> hicolor icons aren't installed under `/usr/share/icons`. Installing the package
> resolves this.

---

## Usage

Safe Eyes is a tray application. The same executable also acts as a **CLI client**:
when an instance is already running, a second invocation forwards the command to
it over a local socket and exits.

```text
Usage: safeeyes [OPTION]

  -a, --about         show the about dialog
  -s, --settings      show the settings dialog
  -t, --take-break    take a break now
  -b, --short-break   take a short break now
  -l, --long-break    take a long break now
  -d, --disable       disable the currently running instance
  -e, --enable        enable the currently running instance
  -q, --quit          quit the running instance and exit
      --status        print the status of the running instance and exit
      --debug         start in debug mode (verbose logging to the log file)
      --version       show the version and exit
  -h, --help          show this help and exit
```

Examples:

```powershell
.\.venv\Scripts\python.exe -m safeeyes -t        # take a break now
.\.venv\Scripts\python.exe -m safeeyes --status  # what's the next break?
.\.venv\Scripts\python.exe -m safeeyes -q        # quit the running instance
```

**During a break the keyboard is blocked system-wide** (by design). Use the mouse
to click *Skip*/*Postpone* (when enabled), or run `safeeyes -q` from another
terminal. `Ctrl+Alt+Del` is always available as an escape hatch.

## File locations

| | Windows | Linux |
|--|---------|-------|
| Config | `%APPDATA%\SafeEyes\safeeyes.json` | `~/.config/safeeyes/safeeyes.json` |
| Log | `%APPDATA%\SafeEyes\safeeyes.log` | `~/safeeyes.log` |
| Autostart | `HKCU\…\Run` registry entry | `~/.config/autostart/*.desktop` |

---

## Building the Windows release

Build the standalone `.exe` (no Python install needed on the target machine) with
[PyInstaller](https://pyinstaller.org/), then optionally wrap it in an installer
with [Inno Setup](https://jrsoftware.org/isinfo.php).

```powershell
# 1. Install the build tool into the venv
.\.venv\Scripts\python.exe -m pip install pyinstaller

# 2. Make sure translations are compiled (so they get bundled)
.\.venv\Scripts\python.exe build_messages.py

# 3. Build the onedir bundle -> dist\SafeEyes\SafeEyes.exe
.\.venv\Scripts\pyinstaller.exe packaging\windows\safeeyes.spec --noconfirm

# 4. (Optional) Build the installer -> packaging\windows\installer\SafeEyes-<ver>-setup.exe
#    Requires Inno Setup 6 (ISCC.exe on PATH).
ISCC packaging\windows\installer.iss
```

The PyInstaller spec ships the plugin tree as data (plugins load dynamically),
adds the hidden imports those plugins need, and trims unused Qt modules
(WebEngine/Quick/Qml/3D/Charts/…). The installer script installs per-user, adds
Start Menu / optional desktop & startup shortcuts, and quits a running instance
before uninstalling.

---

## Architecture

The port keeps OS- and toolkit-specific code isolated so the core stays portable
and testable:

```
safeeyes/
├── core.py            Break scheduler (toolkit-independent)
├── model.py           Breaks, plugins, tray actions (no UI imports)
├── mainloop.py        The ONLY Qt timer/marshalling shim the core/plugins use
├── qt/                ALL Qt UI lives here
│   ├── application.py     QApplication controller (wires everything together)
│   ├── break_screen.py    Fullscreen break window
│   ├── settings_dialog.py, about_dialog.py, required_plugin_dialog.py
│   ├── single_instance.py QLocalServer/QLocalSocket + CLI forwarding
│   ├── system_tray.py, icons.py, qss.py, markup.py
├── platform_api/      OS integration (toolkit-independent, per-OS backends)
│   ├── idle / keyboard_block / lock / fullscreen / media / suspend / signals
│   └── autostart
├── plugins/           Each feature is a plugin loaded dynamically at runtime
└── config/            Default settings, QSS theme, locale (.po/.mo)
```

Key idea: **the core and plugins never import Qt directly** — they schedule
timers and marshal callbacks through `mainloop.py`, and reach the OS through
`platform_api`. This is what makes the same code run on Linux, Windows and
(eventually) macOS.

## Plugins

Bundled plugins: **Tray Icon**, **Notification**, **Audible Alert**,
**Smart Pause**, **Screensaver** (lock screen), **Do Not Disturb** (skip on
fullscreen), **Media Control**, **Health Statistics**, **Limit Consecutive
Skipping**. Enable/disable and configure them in **Settings → Plugins**.

Third-party plugins live at
[safeeyes-plugins](https://github.com/slgobinath/safeeyes-plugins), which also
documents how to write your own.

## Development

```bash
pip install pytest time-machine ruff mypy   # or: pip install --group dev
pytest                 # run the test suite
ruff check             # lint
ruff format --check    # formatting
mypy safeeyes          # type-check
```

When adding translatable strings (`_("text")` in Python), run
`python validate_po.py --extract` to update the template (needs `polib`), and
`python validate_po.py --validate` to check them.

## Troubleshooting

**"I take a break but nothing happens."** Two plugins can legitimately suppress a
break:
- **Smart Pause** pauses Safe Eyes when there's no keyboard/mouse activity — it
  won't fire a break while it thinks you're idle.
- **Do Not Disturb** skips breaks while a fullscreen app or presentation mode is
  active.

  Disable them in **Settings → Plugins** (`safeeyes -s`) if you want breaks
  regardless, or make sure you're active and not in a fullscreen window.

**The keyboard seems locked.** That's intentional during a break. Click
*Skip*/*Postpone*, run `safeeyes -q` from another terminal, or press
`Ctrl+Alt+Del`.

**`--version` / `--status` print nothing on Windows.** The bundled `.exe` is a
windowed (no-console) app, so its stdout isn't shown in a terminal. Running from
source (`python -m safeeyes --status`) prints normally.

**Logs.** Run with `--debug` and inspect the log file (see
[File locations](#file-locations)).

## Translations

Translations are managed on [Weblate](https://hosted.weblate.org/engage/safe-eyes/).
If your language is listed, add or improve translations there; if not,
[open an issue](https://github.com/slgobinath/safeeyes/issues) to have it added.

<a href="https://hosted.weblate.org/engage/safe-eyes/"><img src="https://hosted.weblate.org/widget/safe-eyes/horizontal-auto.svg" alt="Translation status"></a>

## Credits & license

Safe Eyes was created by [Gobinath Loganathan](https://github.com/slgobinath) and
contributors. This cross-platform (PySide6/Qt) port builds on that work.

Licensed under the **GNU General Public License v3** (or later). See
[`LICENSES/GPL-3.0-or-later.txt`](LICENSES/GPL-3.0-or-later.txt).
