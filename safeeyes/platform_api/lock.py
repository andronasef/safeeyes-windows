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
"""Screen locking abstraction.

Windows uses ``LockWorkStation`` (user32). Linux detects the desktop's
screensaver command or D-Bus lock method. macOS is a stub for now.
"""

import logging
import os
import typing

from safeeyes import utility
from safeeyes.platform_api import IS_LINUX, IS_MAC, IS_WINDOWS

# A lock action is either an argv list to execute or a zero-arg callable.
LockAction = typing.Union[list, typing.Callable[[], None], None]


def detect_lock_command() -> LockAction:
    """Return a platform-appropriate lock action, or None if none is found.

    The screensaver plugin uses this when the user has not configured an
    explicit command.
    """
    if IS_WINDOWS:
        return _lock_windows
    if IS_MAC:
        return _lock_mac
    return _detect_linux_lock_command()


def lock_screen(action: LockAction = None) -> None:
    """Lock the screen using ``action`` (or the detected default)."""
    if action is None:
        action = detect_lock_command()
    if action is None:
        logging.info("No screen-lock method available on this platform")
        return
    if isinstance(action, list):
        utility.execute_command(action)
    else:
        action()


# --- Windows --------------------------------------------------------------


def _lock_windows() -> None:
    import ctypes

    logging.info("Locking the workstation (Windows)")
    if not ctypes.windll.user32.LockWorkStation():
        logging.error("LockWorkStation failed")


# --- macOS ----------------------------------------------------------------


def _lock_mac() -> None:
    # macOS is architecturally open but untested; CGSession can lock the screen.
    logging.info("Screen lock is not implemented on macOS")


# --- Linux ----------------------------------------------------------------


def _detect_linux_lock_command() -> LockAction:
    """Detect the lock command based on the current Linux desktop environment.

    Possible results:
        Modern GNOME:               DBus: org.gnome.ScreenSaver.Lock
        Old Gnome, Unity, Budgie:   ['gnome-screensaver-command', '--lock']
        Cinnamon:                   ['cinnamon-screensaver-command', '--lock']
        Pantheon, LXDE:             ['light-locker-command', '--lock']
        Mate:                       ['mate-screensaver-command', '--lock']
        KDE:                        DBus: org.freedesktop.ScreenSaver.Lock
        XFCE:                       ['xflock4']
        Otherwise:                  None
    """
    desktop_session = os.environ.get("DESKTOP_SESSION")
    current_desktop = os.environ.get("XDG_CURRENT_DESKTOP")
    if desktop_session is not None:
        desktop_session = desktop_session.lower()
        if (
            "xfce" in desktop_session
            or desktop_session.startswith("xubuntu")
            or (current_desktop is not None and "xfce" in current_desktop)
        ) and utility.command_exist("xflock4"):
            return ["xflock4"]
        elif desktop_session == "cinnamon" and utility.command_exist(
            "cinnamon-screensaver-command"
        ):
            return ["cinnamon-screensaver-command", "--lock"]
        elif (
            desktop_session == "pantheon" or desktop_session.startswith("lubuntu")
        ) and utility.command_exist("light-locker-command"):
            return ["light-locker-command", "--lock"]
        elif desktop_session == "mate" and utility.command_exist(
            "mate-screensaver-command"
        ):
            return ["mate-screensaver-command", "--lock"]
        elif (
            desktop_session == "kde"
            or "plasma" in desktop_session
            or desktop_session.startswith("kubuntu")
            or os.environ.get("KDE_FULL_SESSION") == "true"
        ):
            return lambda: _lock_linux_dbus(
                destination="org.freedesktop.ScreenSaver",
                path="/ScreenSaver",
                method="Lock",
            )
        elif (
            desktop_session in ["gnome", "unity", "budgie-desktop"]
            or desktop_session.startswith("ubuntu")
            or desktop_session.startswith("gnome")
        ):
            if utility.command_exist("gnome-screensaver-command"):
                return ["gnome-screensaver-command", "--lock"]
            return lambda: _lock_linux_dbus(
                destination="org.gnome.ScreenSaver",
                path="/org/gnome/ScreenSaver",
                method="Lock",
            )
        elif gd_session := os.environ.get("GNOME_DESKTOP_SESSION_ID"):
            if "deprecated" not in gd_session and utility.command_exist(
                "gnome-screensaver-command"
            ):
                return ["gnome-screensaver-command", "--lock"]
    return None


def _lock_linux_dbus(destination: str, path: str, method: str) -> None:
    """Call a screensaver Lock method over the session bus."""
    if not IS_LINUX:
        return
    import gi

    gi.require_version("Gio", "2.0")
    from gi.repository import Gio

    dbus_proxy = Gio.DBusProxy.new_for_bus_sync(
        bus_type=Gio.BusType.SESSION,
        flags=Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES,
        info=None,
        name=destination,
        object_path=path,
        interface_name=destination,
    )
    dbus_proxy.call_sync(method, None, Gio.DBusCallFlags.NONE, -1)
