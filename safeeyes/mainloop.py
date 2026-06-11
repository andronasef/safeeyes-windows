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
"""Toolkit main-loop shim.

This is the ONLY module outside ``safeeyes/qt`` that touches the UI toolkit. The
core scheduler and the plugins schedule timers and marshal callbacks onto the GUI
thread through this small API, so they stay independent of Qt (which keeps the
core unit-testable and the door open for other toolkits/platforms).

The API intentionally mirrors the handful of GLib primitives the app used before:
``GLib.timeout_add_seconds`` → :func:`schedule_seconds`, ``GLib.source_remove`` →
:meth:`Timer.cancel`, ``GLib.idle_add`` (from worker threads) →
:func:`post_to_main_thread`.
"""

import logging
import typing

from PySide6.QtCore import QObject, QTimer, Qt, Signal


class Timer:
    """Handle for a scheduled callback; cancellable like ``GLib.source_remove``."""

    def __init__(self, qtimer: QTimer) -> None:
        self._qtimer = qtimer

    def cancel(self) -> None:
        self._qtimer.stop()
        _active_timers.discard(self)


# QTimer objects are kept alive here so they are not garbage-collected before they
# fire (a stopped/dropped QTimer never triggers its callback).
_active_timers: typing.Set[Timer] = set()


def _schedule(ms: int, callback: typing.Callable[[], None], repeating: bool) -> Timer:
    qtimer = QTimer()
    qtimer.setSingleShot(not repeating)
    timer = Timer(qtimer)

    def _fire() -> None:
        if not repeating:
            _active_timers.discard(timer)
        callback()

    qtimer.timeout.connect(_fire)
    _active_timers.add(timer)
    qtimer.start(max(0, ms))
    return timer


def schedule_ms(ms: int, callback: typing.Callable[[], None]) -> Timer:
    """Run ``callback`` once after ``ms`` milliseconds."""
    return _schedule(ms, callback, repeating=False)


def schedule_seconds(seconds: float, callback: typing.Callable[[], None]) -> Timer:
    """Run ``callback`` once after ``seconds`` seconds (GLib.timeout_add_seconds)."""
    return _schedule(int(seconds * 1000), callback, repeating=False)


def schedule_repeating_ms(ms: int, callback: typing.Callable[[], None]) -> Timer:
    """Run ``callback`` every ``ms`` milliseconds until cancelled."""
    return _schedule(ms, callback, repeating=True)


def cancel(timer: typing.Optional[Timer]) -> None:
    """Cancel a scheduled timer (no-op if ``None``)."""
    if timer is not None:
        timer.cancel()


class _Marshaller(QObject):
    """Delivers a callable onto the thread this object lives on (the GUI thread).

    Emitting the signal from any thread, with a queued connection, causes the slot
    to run on the marshaller's home thread.
    """

    _invoke = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._invoke.connect(self._run, Qt.ConnectionType.QueuedConnection)

    def _run(self, fn: typing.Callable[[], None]) -> None:
        try:
            fn()
        except Exception:
            logging.exception("Error in main-thread callback")

    def post(self, fn: typing.Callable[[], None]) -> None:
        self._invoke.emit(fn)


_marshaller: typing.Optional[_Marshaller] = None


def init() -> None:
    """Create the main-thread marshaller.

    Must be called once on the GUI thread after the QApplication exists.
    """
    global _marshaller
    if _marshaller is None:
        _marshaller = _Marshaller()


def post_to_main_thread(callback: typing.Callable[[], None]) -> None:
    """Schedule ``callback`` to run on the GUI thread (safe from any thread).

    Equivalent to the old ``utility.execute_main_thread`` / ``GLib.idle_add``.
    """
    if _marshaller is None:
        # Not initialised (e.g. headless tests, or before the app starts up).
        # Best effort: run inline on the caller's thread.
        callback()
        return
    _marshaller.post(callback)
