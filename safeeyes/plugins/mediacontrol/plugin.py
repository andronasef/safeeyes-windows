#!/usr/bin/env python
# Safe Eyes is a utility to remind you to take break frequently
# to protect your eyes from eye strain.

# Copyright (C) 2019  Gobinath

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
"""Media Control plugin lets users to pause currently playing media player from
the break screen.
"""

import os

from safeeyes.model import TrayAction
from safeeyes.platform_api import media

tray_icon_path = None


def init(ctx, safeeyes_config, plugin_config):
    """Initialize the screensaver plugin."""
    global tray_icon_path
    tray_icon_path = os.path.join(plugin_config["path"], "resource/pause.png")


def get_tray_action(break_obj):
    """Return TrayAction only if there is a media player currently playing."""
    players = media.active_players()
    if players:
        return TrayAction.build(
            "Pause media",
            tray_icon_path,
            "media-playback-pause",
            lambda: media.pause(players),
        )
