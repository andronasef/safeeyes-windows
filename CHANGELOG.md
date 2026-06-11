# Changelog

All notable changes to this fork are documented here. This project adheres to
[Keep a Changelog](https://keepachangelog.com/) conventions.

## [Unreleased] — Cross-platform (PySide6/Qt) port

This release migrates Safe Eyes from Linux-only **GTK4/PyGObject** to
**PySide6 (Qt)**, making it genuinely cross-platform. Windows is built and
verified; Linux runs from source on Qt; macOS is architecturally supported but
untested (stubbed OS integration). The break scheduler, plugin system and 40+
translations are shared across all platforms.

### Added

- **Windows support** — runs natively, packaged as a standalone PyInstaller
  `.exe` (`packaging/windows/safeeyes.spec`) with a per-user Inno Setup
  installer (`packaging/windows/installer.iss`).
- **Qt UI layer** (`safeeyes/qt/`): fullscreen break screen, settings/about/
  required-plugin dialogs, system tray, single-instance + CLI forwarding over
  `QLocalServer`/`QLocalSocket`, Pango→HTML markup, QSS theming.
- **Platform abstraction layer** (`safeeyes/platform_api/`) with per-OS backends:
  - `keyboard_block` — system-wide key blocking during breaks
    (Windows `WH_KEYBOARD_LL` hook / X11 root grab).
  - `idle` — smart pause (Windows `GetLastInputInfo` / X11 / GNOME / sway / Wayland).
  - `lock` — lock screen after long breaks (Windows `LockWorkStation` / Linux
    screensaver command or D-Bus).
  - `fullscreen` — do-not-disturb detection (Windows
    `SHQueryUserNotificationState` + battery / Linux X11/wlrctl/GNOME/KDE).
  - `media` — pause players (Linux MPRIS / Windows GSMTC where `winsdk` present).
  - `suspend` — pause/resume on sleep (Windows
    `PowerRegisterSuspendResumeNotification` / Linux login1 `PrepareForSleep`).
  - `autostart` — run at login (Windows `HKCU\…\Run` / Linux XDG `.desktop`).
- `safeeyes/mainloop.py` — a small Qt timer/marshalling shim; the only place the
  core and plugins touch the toolkit, keeping them portable and unit-testable.
- `build_messages.py` — cross-platform `.po` → `.mo` compiler for source runs.
- Per-platform config/log/path handling (Windows `%APPDATA%\SafeEyes`).
- `windows-media`, `packaging-windows` optional dependency extras.

### Changed

- **UI toolkit: GTK4/PyGObject → PySide6/Qt** across the entire application.
- Event loop: GLib timers → `QTimer` (via `mainloop.py`); cross-thread callbacks
  → a Qt queued-signal marshaller.
- CLI / single-instance: GApplication command-line handling → `argparse` +
  `QLocalServer`/`QLocalSocket`. Same flags
  (`-a/-s/-t/-b/-l/-d/-e/-q/--status/--debug/--version`) and exit codes.
- Plugins rewritten on Qt/`platform_api`: **tray icon** (`QSystemTrayIcon`+`QMenu`,
  replacing the D-Bus StatusNotifierItem implementation), **notification**
  (`QSystemTrayIcon.showMessage`), **audible alert** (`QSoundEffect`),
  **smart pause**, **screensaver**, **do not disturb**, **media control**.
- Translation build: `msgfmt` CLI → Babel (`setup.py`), so `.mo` files compile on
  Windows too; tolerant of empty date headers in Weblate `.po` files.
- `pyproject.toml`: `PyGObject` → `PySide6`; `python-xlib`/`pywayland` gated to
  Linux; classifiers updated for Qt + Windows + Linux.
- Version resolution falls back gracefully in frozen bundles.

### Removed

- All GTK code: `safeeyes/safeeyes.py`, `safeeyes/ui/*` and `safeeyes/glade/*`.
- Direct `gi`/GTK/GLib imports from `core.py`, `model.py`, `utility.py` and the
  plugins.

### Fixed

- Windows `locale.LC_MESSAGES` absence (POSIX-only) when setting up translations.
- Console `UnicodeEncodeError` printing status containing non-cp1252 characters.
- `donotdisturb` Windows fullscreen detection used the wrong
  `QUERY_USER_NOTIFICATION_STATE` enum values, causing **every break to be
  skipped**; corrected so only genuine fullscreen/presentation states skip.
- 64-bit `ctypes` pointer truncation that prevented the Windows keyboard hook
  from installing (declared `argtypes`/`restype`).

### Known limitations

- The bundled `.exe` is windowed, so `--version`/`--status` print nothing to a
  console (running from source prints normally).
- Do Not Disturb on Windows skips during any fullscreen/presentation state, which
  can be broader than desired; disable the plugin if unwanted.
- macOS OS-integration is stubbed and untested.
- Linux is validated for packaging and imports from this machine but its runtime
  (X11/Wayland/D-Bus) has not been exercised in this port pass.
