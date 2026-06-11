# Safe Eyes is a utility to remind you to take break frequently
# to protect your eyes from eye strain.

# Copyright (C) 2017  Gobinath

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Build Qt icons from the toolkit-neutral :class:`safeeyes.model.IconSpec`."""

import os

from PySide6.QtGui import QIcon

from safeeyes import utility
from safeeyes.model import IconSpec

APP_ICON_NAME = "io.github.slgobinath.SafeEyes"
TRAY_ENABLED = "io.github.slgobinath.SafeEyes-enabled"
TRAY_DISABLED = "io.github.slgobinath.SafeEyes-disabled"
TRAY_TIMER = "io.github.slgobinath.SafeEyes-timer"

# Bundled hicolor icons, used as a fallback where there is no XDG icon theme
# (Windows/macOS) and as the source for the QSystemTrayIcon.
_HICOLOR_DIR = os.path.join(utility.SYSTEM_ICONS, "hicolor")


def _bundled_icon(name: str) -> QIcon:
    """Assemble a multi-resolution QIcon from the bundled hicolor PNGs.

    Scans ``hicolor/<size>/{apps,status}/<name>.png`` and adds every size found
    so Qt can pick the best resolution for the current tray/display scale.
    """
    icon = QIcon()
    if not os.path.isdir(_HICOLOR_DIR):
        return icon

    for size_dir in os.listdir(_HICOLOR_DIR):
        for category in ("apps", "status"):
            png = os.path.join(_HICOLOR_DIR, size_dir, category, name + ".png")
            if os.path.isfile(png):
                icon.addFile(png)
    return icon


def themed_icon(name: str) -> QIcon:
    """Resolve a themed icon name to a QIcon.

    Uses the platform icon theme (Linux) when it has the icon, otherwise falls
    back to the bundled hicolor PNGs (Windows/macOS, or incomplete Linux themes).
    """
    icon = QIcon.fromTheme(name)
    if not icon.isNull():
        return icon
    return _bundled_icon(name)


def app_icon() -> QIcon:
    """Return the Safe Eyes application icon."""
    return themed_icon(APP_ICON_NAME)


def icon_from_spec(spec: IconSpec) -> QIcon:
    """Return a ``QIcon`` for the given icon spec.

    A file-path spec loads directly; a themed-name spec is resolved via the
    platform icon theme (Linux), falling back to a file of that name if present
    (so bundled PNGs work on Windows/macOS where there is no XDG icon theme).
    """
    if not spec.system_icon and os.path.isfile(spec.icon):
        return QIcon(spec.icon)

    icon = themed_icon(spec.icon)
    if icon.isNull() and os.path.isfile(spec.icon):
        return QIcon(spec.icon)
    return icon
