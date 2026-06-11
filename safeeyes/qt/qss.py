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
"""Load and apply the Qt stylesheet (QSS).

Replaces the GTK ``Gtk.CssProvider`` two-priority loading: the system stylesheet
is applied first, then any user override is appended (later rules win in QSS).
"""

import logging
import os
import typing

from PySide6.QtWidgets import QApplication


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        logging.warning("Failed reading stylesheet %s", path)
        return ""


def apply_styles(
    app: QApplication,
    system_qss_path: str,
    user_qss_path: typing.Optional[str] = None,
) -> None:
    """Apply the system stylesheet, then the user override if present."""
    css = ""
    if os.path.isfile(system_qss_path):
        css += _read(system_qss_path)
    else:
        logging.warning("Failed loading required stylesheet %s", system_qss_path)

    if user_qss_path and os.path.isfile(user_qss_path):
        css += "\n" + _read(user_qss_path)

    app.setStyleSheet(css)
