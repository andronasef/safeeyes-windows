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
"""Safe Eyes pre-break notification plugin (Qt/PySide6 port).

Shows a cross-platform balloon/toast via the shared ``QSystemTrayIcon``
(``showMessage``), replacing the freedesktop libnotify backend.
"""

import logging

from PySide6.QtWidgets import QSystemTrayIcon

from safeeyes import utility
from safeeyes.model import BreakType
from safeeyes.qt import icons, system_tray
from safeeyes.translations import translate as _

context = None
warning_time = 10
# How long the pre-break toast stays up. The break starts after warning_time
# seconds, at which point on_start_break clears it anyway.
NOTIFICATION_TIMEOUT_MS = 15000


def init(ctx, safeeyes_config, plugin_config):
    """Initialize the plugin."""
    global context
    global warning_time
    logging.debug("Initialize Notification plugin")
    context = ctx
    warning_time = safeeyes_config.get("pre_break_warning_time")


def on_pre_break(break_obj):
    """Show the notification."""
    if not system_tray.is_available():
        logging.warning("System tray unavailable; cannot show notification")
        return

    logging.info("Show the notification")
    if break_obj.type == BreakType.SHORT_BREAK:
        message = _("Ready for a short break in %s seconds") % warning_time
    else:
        message = _("Ready for a long break in %s seconds") % warning_time

    def show():
        tray = system_tray.get_tray_icon()
        tray.showMessage(
            "Safe Eyes", message, icons.app_icon(), NOTIFICATION_TIMEOUT_MS
        )

    utility.execute_main_thread(show)


def on_start_break(break_obj):
    """Close the notification."""
    logging.info("Close pre-break notification")

    def hide():
        # There is no per-message dismissal in QSystemTrayIcon; an empty message
        # request is the documented way to retract the current balloon.
        tray = system_tray.get_tray_icon()
        tray.showMessage("", "", QSystemTrayIcon.MessageIcon.NoIcon, 1)

    utility.execute_main_thread(hide)
