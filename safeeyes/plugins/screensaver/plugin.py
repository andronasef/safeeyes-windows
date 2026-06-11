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
"""Screensaver plugin locks the desktop using native screensaver application,
after long breaks.
"""

import logging
import os
import typing

from safeeyes import utility
from safeeyes.model import TrayAction
from safeeyes.platform_api import lock

context = None
is_long_break: bool = False
user_locked_screen = False
lock_screen_command: lock.LockAction = None
min_seconds = 0
seconds_passed = 0
tray_icon_path = None
icon_lock_later_path = None


def __lock_screen_later():
    global user_locked_screen
    user_locked_screen = True


def __lock_screen_now() -> None:
    lock.lock_screen(lock_screen_command)


def init(ctx, safeeyes_config, plugin_config):
    """Initialize the screensaver plugin."""
    global context
    global lock_screen_command
    global min_seconds
    global tray_icon_path
    global icon_lock_later_path
    logging.debug("Initialize Screensaver plugin")
    context = ctx
    min_seconds = plugin_config["min_seconds"]
    tray_icon_path = os.path.join(plugin_config["path"], "resource/lock.png")
    icon_lock_later_path = os.path.join(
        plugin_config["path"], "resource/rotation-lock-symbolic.svg"
    )
    if plugin_config["command"]:
        lock_screen_command = plugin_config["command"].split()
    else:
        lock_screen_command = lock.detect_lock_command()


def on_start_break(break_obj):
    """Determine the break type and only if it is a long break, enable the
    is_long_break flag.
    """
    global is_long_break
    global seconds_passed
    global user_locked_screen
    user_locked_screen = False
    seconds_passed = 0

    is_long_break = break_obj.is_long_break()


def on_countdown(countdown, seconds):
    """Keep track of seconds passed from the beginning of long break."""
    global seconds_passed
    seconds_passed = seconds


def on_stop_break():
    """Lock the screen after a long break if the user has not skipped within
    min_seconds.
    """
    if user_locked_screen or (is_long_break and seconds_passed >= min_seconds):
        __lock_screen_now()


def get_tray_action(break_obj) -> list[TrayAction]:
    return [
        TrayAction.build(
            "Lock screen now",
            tray_icon_path,
            "system-lock-screen",
            __lock_screen_now,
            single_use=False,
        ),
        TrayAction.build(
            "Lock screen after break",
            icon_lock_later_path,
            "dialog-password",
            __lock_screen_later,
        ),
    ]
