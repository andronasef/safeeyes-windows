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

import ctypes
import threading
import typing

from safeeyes import utility

from .interface import IdleMonitorInterface


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_ulong)]


def _system_idle_seconds() -> float:
    """Seconds since the last keyboard/mouse input, system-wide."""
    info = _LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(_LASTINPUTINFO)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    # GetTickCount and dwTime are both in milliseconds since boot and wrap
    # around every ~49.7 days; the unsigned subtraction handles wraparound.
    millis_since_boot = ctypes.windll.kernel32.GetTickCount()
    idle_millis = (millis_since_boot - info.dwTime) & 0xFFFFFFFF
    return idle_millis / 1000.0


class IdleMonitorWindows(IdleMonitorInterface):
    """IdleMonitorInterface implementation for Windows.

    Polls ``GetLastInputInfo`` every couple of seconds on a worker thread,
    mirroring the X11 backend's approach.
    """

    active: bool = False
    lock = threading.Lock()
    idle_condition = threading.Condition()

    def _is_active(self) -> bool:
        with self.lock:
            return self.active

    def _set_active(self, is_active: bool) -> None:
        with self.lock:
            self.active = is_active

    def init(self) -> None:
        # Probe once so a missing/unsupported API surfaces during init.
        _system_idle_seconds()

    def start_monitor(
        self,
        on_idle: typing.Callable[[], None],
        on_resumed: typing.Callable[[], None],
        idle_time: float,
    ) -> None:
        if not self._is_active():
            self._set_active(True)
            utility.start_thread(
                self._start_idle_monitor,
                on_idle=on_idle,
                on_resumed=on_resumed,
                idle_time=idle_time,
            )

    def is_monitor_running(self) -> bool:
        return self._is_active()

    def _start_idle_monitor(
        self,
        on_idle: typing.Callable[[], None],
        on_resumed: typing.Callable[[], None],
        idle_time: float,
    ) -> None:
        waiting_time = min(idle_time, 2)
        was_idle = False

        while self._is_active():
            self.idle_condition.acquire()
            self.idle_condition.wait(waiting_time)
            self.idle_condition.release()

            if self._is_active():
                system_idle_time = _system_idle_seconds()
                if system_idle_time >= idle_time and not was_idle:
                    was_idle = True
                    utility.execute_main_thread(on_idle)
                elif system_idle_time < idle_time and was_idle:
                    was_idle = False
                    utility.execute_main_thread(on_resumed)

    def stop_monitor(self) -> None:
        self._set_active(False)
        self.idle_condition.acquire()
        self.idle_condition.notify_all()
        self.idle_condition.release()

    def stop(self) -> None:
        pass
