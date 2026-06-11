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
"""Fullscreen / do-not-disturb detection and power-source queries.

Used by the donotdisturb plugin to decide whether to skip a break. Windows uses
``SHQueryUserNotificationState`` (presentation/fullscreen/quiet modes) and
``GetSystemPowerStatus``; Linux keeps the existing Xlib/wlrctl/GNOME/KDE logic.
"""

import logging
import os

from safeeyes import utility
from safeeyes.platform_api import IS_LINUX, IS_MAC, IS_WINDOWS


def is_fullscreen_active(
    pre_break: bool,
    skip_break_window_classes: list,
    take_break_window_classes: list,
    unfullscreen_allowed: bool,
) -> bool:
    """Whether a break should be skipped because of a fullscreen / DND state."""
    if IS_WINDOWS:
        return _is_fullscreen_windows()
    if IS_MAC:
        return False
    return _is_fullscreen_linux(
        pre_break,
        skip_break_window_classes,
        take_break_window_classes,
        unfullscreen_allowed,
    )


def is_on_battery() -> bool:
    """Whether the computer is currently running on battery power."""
    if IS_WINDOWS:
        return _is_on_battery_windows()
    if IS_MAC:
        return False
    return _is_on_battery_linux()


# --- Windows --------------------------------------------------------------

# SHQueryUserNotificationState return values (shellapi.h QUERY_USER_NOTIFICATION_STATE).
# NOTE: these are 1-based; QUNS_ACCEPTS_NOTIFICATIONS (5) is the *normal* state.
_QUNS_BUSY = 2  # full-screen app running (do not disturb)
_QUNS_RUNNING_D3D_FULL_SCREEN = 3  # full-screen (exclusive) D3D app running
_QUNS_PRESENTATION_MODE = 4  # presentation mode (do not disturb)


def _is_fullscreen_windows() -> bool:
    import ctypes

    state = ctypes.c_int(0)
    try:
        # Returns S_OK (0) on success, writing the state into `state`.
        result = ctypes.windll.shell32.SHQueryUserNotificationState(
            ctypes.byref(state)
        )
    except (AttributeError, OSError) as error:
        logging.warning("SHQueryUserNotificationState failed: %s", error)
        return False

    if result != 0:
        return False

    if state.value in (
        _QUNS_BUSY,
        _QUNS_RUNNING_D3D_FULL_SCREEN,
        _QUNS_PRESENTATION_MODE,
    ):
        logging.info("Skipping break: fullscreen/presentation state %s", state.value)
        return True
    return False


def _is_on_battery_windows() -> bool:
    import ctypes

    class SYSTEM_POWER_STATUS(ctypes.Structure):
        _fields_ = [
            ("ACLineStatus", ctypes.c_byte),
            ("BatteryFlag", ctypes.c_byte),
            ("BatteryLifePercent", ctypes.c_byte),
            ("SystemStatusFlag", ctypes.c_byte),
            ("BatteryLifeTime", ctypes.c_ulong),
            ("BatteryFullLifeTime", ctypes.c_ulong),
        ]

    status = SYSTEM_POWER_STATUS()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return False
    # ACLineStatus: 0 = offline (on battery), 1 = online, 255 = unknown.
    return status.ACLineStatus == 0


# --- Linux ----------------------------------------------------------------


def _is_on_battery_linux() -> bool:
    on_battery = False
    try:
        available_power_sources = os.listdir("/sys/class/power_supply")
    except OSError:
        return False
    for power_source in available_power_sources:
        if "BAT" in power_source:
            battery_status = os.path.join(
                "/sys/class/power_supply", power_source, "status"
            )
            if os.path.isfile(battery_status):
                try:
                    with open(battery_status, "r") as status_file:
                        status = status_file.read()
                        if status:
                            on_battery = "discharging" in status.lower()
                except BaseException:
                    logging.error("Failed to read %s", battery_status)
            break
    return on_battery


def _window_class_matches(window_class: str, classes: list) -> bool:
    return any(map(lambda w: w in classes, window_class.split()))


def _is_fullscreen_linux(
    pre_break: bool,
    skip_break_window_classes: list,
    take_break_window_classes: list,
    unfullscreen_allowed: bool,
) -> bool:
    if utility.IS_WAYLAND:
        if utility.DESKTOP_ENVIRONMENT == "gnome":
            return _is_idle_inhibited_gnome()
        if utility.DESKTOP_ENVIRONMENT == "kde":
            return _is_idle_inhibited_kde()
        return _is_active_window_skipped_wayland()
    return _is_active_window_skipped_xorg(
        pre_break,
        skip_break_window_classes,
        take_break_window_classes,
        unfullscreen_allowed,
    )


def _is_active_window_skipped_wayland() -> bool:
    import subprocess

    cmdlist = ["wlrctl", "toplevel", "find", "state:fullscreen"]
    try:
        process = subprocess.Popen(cmdlist, stdout=subprocess.PIPE)
        process.communicate()[0]
        if process.returncode == 0:
            return True
        elif process.returncode == 1:
            return False
        elif process.returncode == 127:
            logging.warning(
                "Could not find wlrctl needed to detect fullscreen under wayland"
            )
            return False
    except subprocess.CalledProcessError:
        logging.warning("Error in finding full-screen application")
    return False


def _is_active_window_skipped_xorg(
    pre_break: bool,
    skip_break_window_classes: list,
    take_break_window_classes: list,
    unfullscreen_allowed: bool,
) -> bool:
    """Check for full-screen applications. Must run on the main thread."""
    logging.info("Searching for full-screen application")

    import Xlib

    def get_window_property(window, prop, proptype):
        result = window.get_full_property(prop, proptype)
        if result:
            return result.value
        return None

    def get_active_window(x11_display):
        root = x11_display.screen().root
        NET_ACTIVE_WINDOW = x11_display.intern_atom("_NET_ACTIVE_WINDOW")
        active_windows = get_window_property(
            root, NET_ACTIVE_WINDOW, Xlib.Xatom.WINDOW
        )
        if active_windows and active_windows[0]:
            active_window = active_windows[0]
            return x11_display.create_resource_object("window", active_window)
        return None

    x11_display = Xlib.display.Display()
    active_window = get_active_window(x11_display)

    if active_window:
        NET_WM_STATE = x11_display.intern_atom("_NET_WM_STATE")
        NET_WM_STATE_FULLSCREEN = x11_display.intern_atom("_NET_WM_STATE_FULLSCREEN")

        props = get_window_property(active_window, NET_WM_STATE, Xlib.Xatom.ATOM)
        is_fullscreen = props and NET_WM_STATE_FULLSCREEN in props.tolist()

        process_names = active_window.get_wm_class()

        if is_fullscreen:
            logging.info("fullscreen window found")

        if process_names:
            process_name = process_names[1].lower()
            if _window_class_matches(process_name, skip_break_window_classes):
                logging.info("found uninterruptible window")
                return True
            elif _window_class_matches(process_name, take_break_window_classes):
                logging.info("found interruptible window")
                if is_fullscreen and unfullscreen_allowed and not pre_break:
                    logging.info("interrupting interruptible window")
                    try:
                        root_window = x11_display.screen().root
                        cm_event = Xlib.protocol.event.ClientMessage(
                            window=active_window,
                            client_type=NET_WM_STATE,
                            data=(
                                32,
                                [
                                    0,  # _NET_WM_STATE_REMOVE
                                    NET_WM_STATE_FULLSCREEN,
                                    0,
                                    1,  # source indication
                                    0,
                                ],
                            ),
                        )
                        mask = (
                            Xlib.X.SubstructureRedirectMask
                            | Xlib.X.SubstructureNotifyMask
                        )
                        root_window.send_event(cm_event, event_mask=mask)
                        x11_display.sync()
                    except BaseException as e:
                        logging.error(
                            "Error in unfullscreen the window " + process_name,
                            exc_info=e,
                        )
                return False

        return bool(is_fullscreen)

    return False


def _is_idle_inhibited_gnome() -> bool:
    import gi

    gi.require_version("Gio", "2.0")
    from gi.repository import Gio

    dbus_proxy = Gio.DBusProxy.new_for_bus_sync(
        bus_type=Gio.BusType.SESSION,
        flags=Gio.DBusProxyFlags.NONE,
        info=None,
        name="org.gnome.SessionManager",
        object_path="/org/gnome/SessionManager",
        interface_name="org.gnome.SessionManager",
        cancellable=None,
    )
    result = dbus_proxy.get_cached_property("InhibitedActions").unpack()
    # Bit 4 (0b1000) indicates idle is inhibited.
    return bool(result & 0b1000)


def _is_idle_inhibited_kde() -> bool:
    import gi

    gi.require_version("Gio", "2.0")
    from gi.repository import Gio

    dbus_proxy = Gio.DBusProxy.new_for_bus_sync(
        bus_type=Gio.BusType.SESSION,
        flags=Gio.DBusProxyFlags.NONE,
        info=None,
        name="org.freedesktop.Notifications",
        object_path="/org/freedesktop/Notifications",
        interface_name="org.freedesktop.Notifications",
        cancellable=None,
    )
    prop = dbus_proxy.get_cached_property("Inhibited")
    if prop is None:
        return False
    return prop.unpack()
