#!/usr/bin/env python
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
"""Skip Fullscreen plugin skips the break if the active window is fullscreen."""

import logging

from safeeyes.platform_api import fullscreen

context = None
skip_break_window_classes: list[str] = []
take_break_window_classes: list[str] = []
unfullscreen_allowed = True
dnd_while_on_battery = False


def init(ctx, safeeyes_config, plugin_config):
    global context
    global skip_break_window_classes
    global take_break_window_classes
    global unfullscreen_allowed
    global dnd_while_on_battery
    logging.debug("Initialize Skip Fullscreen plugin")
    context = ctx
    skip_break_window_classes = _normalize_window_classes(
        plugin_config["skip_break_windows"]
    )
    take_break_window_classes = _normalize_window_classes(
        plugin_config["take_break_windows"]
    )
    unfullscreen_allowed = plugin_config["unfullscreen"]
    dnd_while_on_battery = plugin_config["while_on_battery"]


def _normalize_window_classes(classes_as_str: str):
    return [w.lower() for w in classes_as_str.split()]


def __should_skip_break(pre_break: bool) -> bool:
    skip_break = fullscreen.is_fullscreen_active(
        pre_break,
        skip_break_window_classes,
        take_break_window_classes,
        unfullscreen_allowed,
    )
    if dnd_while_on_battery and not skip_break:
        skip_break = fullscreen.is_on_battery()

    if skip_break:
        logging.info("Skipping break due to donotdisturb")

    return skip_break


def on_pre_break(break_obj):
    """Lifecycle method executes before the pre-break period."""
    return __should_skip_break(pre_break=True)


def on_start_break(break_obj):
    """Lifecycle method executes just before the break."""
    return __should_skip_break(pre_break=False)
