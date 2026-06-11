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
"""Process-wide shared :class:`QSystemTrayIcon`.

Both the tray-icon plugin (menu + status icon) and the notification plugin
(balloon/toast messages) need a system-tray presence. On Windows a tray icon
must be visible for ``showMessage`` to surface a toast, so sharing a single
``QSystemTrayIcon`` avoids two competing icons in the notification area.

The icon is created lazily on first use and torn down on application exit.
"""

import typing

from PySide6.QtWidgets import QSystemTrayIcon

from safeeyes.qt import icons

_tray_icon: typing.Optional[QSystemTrayIcon] = None


def is_available() -> bool:
    """Whether the platform currently has a usable system tray."""
    return QSystemTrayIcon.isSystemTrayAvailable()


def get_tray_icon() -> QSystemTrayIcon:
    """Return the shared tray icon, creating and showing it on first use."""
    global _tray_icon
    if _tray_icon is None:
        _tray_icon = QSystemTrayIcon()
        _tray_icon.setIcon(icons.app_icon())
        _tray_icon.setToolTip("Safe Eyes")
        _tray_icon.show()
    return _tray_icon


def destroy() -> None:
    """Hide and dispose of the shared tray icon (called on application exit)."""
    global _tray_icon
    if _tray_icon is not None:
        _tray_icon.hide()
        _tray_icon.setContextMenu(None)
        _tray_icon.deleteLater()
        _tray_icon = None
