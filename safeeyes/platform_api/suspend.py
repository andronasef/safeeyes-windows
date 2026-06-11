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
"""System suspend/resume notifications.

Lets Safe Eyes pause its scheduler when the machine sleeps and resume on wake.
Windows uses ``PowerRegisterSuspendResumeNotification`` with a callback (no
window required); Linux listens for login1 ``PrepareForSleep``. The callback is
always delivered on the GUI thread. macOS is a stub.
"""

import logging
import typing

from safeeyes import mainloop
from safeeyes.platform_api import IS_LINUX, IS_WINDOWS

# (sleeping: bool) -> None ; True = going to sleep, False = resuming.
SuspendCallback = typing.Callable[[bool], None]

_handle: typing.Optional["_SuspendHandle"] = None


def register(on_change: SuspendCallback) -> None:
    """Register ``on_change`` to be called on suspend (True) and resume (False)."""
    global _handle
    if _handle is not None:
        return

    def dispatch(sleeping: bool) -> None:
        # Backends may fire from another thread; hop to the GUI thread.
        mainloop.post_to_main_thread(lambda: on_change(sleeping))

    if IS_WINDOWS:
        _handle = _WindowsSuspend(dispatch)
    elif IS_LINUX:
        _handle = _LinuxSuspend(dispatch)
    else:
        logging.info("Suspend handling is not implemented on this platform")
        return

    try:
        _handle.register()
    except Exception:
        logging.exception("Failed to register for suspend/resume notifications")
        _handle = None


# --- Windows --------------------------------------------------------------


class _WindowsSuspend:
    def __init__(self, dispatch: SuspendCallback) -> None:
        self._dispatch = dispatch
        self._callback = None
        self._params = None
        self._registration = None

    def register(self) -> None:
        import ctypes
        from ctypes import wintypes

        DEVICE_NOTIFY_CALLBACK = 2
        PBT_APMSUSPEND = 0x0004
        PBT_APMRESUMEAUTOMATIC = 0x0012
        PBT_APMRESUMESUSPEND = 0x0007

        callback_type = ctypes.WINFUNCTYPE(
            wintypes.ULONG, wintypes.LPVOID, wintypes.DWORD, wintypes.LPVOID
        )

        def on_power_event(context, event_type, setting):
            if event_type == PBT_APMSUSPEND:
                self._dispatch(True)
            elif event_type in (PBT_APMRESUMEAUTOMATIC, PBT_APMRESUMESUSPEND):
                self._dispatch(False)
            return 0  # ERROR_SUCCESS

        class _SubscribeParams(ctypes.Structure):
            _fields_ = [
                ("Callback", callback_type),
                ("Context", wintypes.LPVOID),
            ]

        # Keep references alive for the lifetime of the registration.
        self._callback = callback_type(on_power_event)
        self._params = _SubscribeParams(self._callback, None)
        self._registration = wintypes.HANDLE()

        result = ctypes.windll.powrprof.PowerRegisterSuspendResumeNotification(
            DEVICE_NOTIFY_CALLBACK,
            ctypes.byref(self._params),
            ctypes.byref(self._registration),
        )
        if result != 0:
            raise OSError(
                f"PowerRegisterSuspendResumeNotification failed: {result}"
            )
        logging.info("Registered for Windows suspend/resume notifications")


# --- Linux ----------------------------------------------------------------


class _LinuxSuspend:
    def __init__(self, dispatch: SuspendCallback) -> None:
        self._dispatch = dispatch
        self._proxy = None

    def register(self) -> None:
        import gi

        gi.require_version("Gio", "2.0")
        from gi.repository import Gio

        self._proxy = Gio.DBusProxy.new_for_bus_sync(
            bus_type=Gio.BusType.SYSTEM,
            flags=Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES,
            info=None,
            name="org.freedesktop.login1",
            object_path="/org/freedesktop/login1",
            interface_name="org.freedesktop.login1.Manager",
            cancellable=None,
        )
        self._proxy.connect("g-signal", self._on_signal)
        logging.info("Registered for login1 PrepareForSleep notifications")

    def _on_signal(self, proxy, sender, signal, parameters) -> None:
        if signal != "PrepareForSleep":
            return
        (sleeping,) = parameters
        self._dispatch(bool(sleeping))
