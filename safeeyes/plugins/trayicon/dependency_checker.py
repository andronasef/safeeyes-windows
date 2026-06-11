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

from safeeyes.model import PluginDependency
from safeeyes.translations import translate as _


def validate(plugin_config, plugin_settings):
    # Qt's QSystemTrayIcon backs the tray on every platform. On Linux this maps
    # to a StatusNotifierItem/XEmbed host; on Windows/macOS it is always
    # present. isSystemTrayAvailable() reports whether a host is currently
    # running (e.g. a freedesktop tray service on Linux).
    from PySide6.QtWidgets import QSystemTrayIcon

    if QSystemTrayIcon.isSystemTrayAvailable():
        return None

    return PluginDependency(
        message=_(
            "Please install service providing tray icons for your desktop"
            " environment."
        ),
        link="https://github.com/slgobinath/safeeyes/wiki/How-to-install-backend-for-Safe-Eyes-tray-icon",
        retryable=True,
    )
