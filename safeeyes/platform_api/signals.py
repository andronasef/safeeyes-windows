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
"""Cross-platform Ctrl+C (SIGINT) handling for the Qt main loop.

Qt's ``QApplication.exec()`` blocks in C++ and does not yield to Python's
between-bytecode signal delivery, so a plain ``signal.signal`` handler would
never run while the loop is idle. We therefore set a flag from the C-level
handler and poll it from a short repeating timer that runs inside the Qt loop
(the same approach works on Windows, which lacks ``GLib.unix_signal_add``).
"""

import signal
import typing

from safeeyes import mainloop

_POLL_INTERVAL_MS = 200


def install_sigint(on_interrupt: typing.Callable[[], None]) -> None:
    """Install a SIGINT (Ctrl+C) handler that calls ``on_interrupt`` once.

    After the first interrupt the handler restores Python's default behaviour so
    a second Ctrl+C can force-quit if the graceful shutdown hangs (matching the
    original behaviour).
    """
    state: dict[str, typing.Any] = {"interrupted": False, "timer": None}

    def signal_handler(signum, frame) -> None:
        state["interrupted"] = True

    def poll() -> None:
        if not state["interrupted"]:
            return
        # Restore the default handler so a second Ctrl+C force-quits, stop
        # polling, then run the graceful shutdown once.
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        mainloop.cancel(state["timer"])
        state["timer"] = None
        on_interrupt()

    signal.signal(signal.SIGINT, signal_handler)
    state["timer"] = mainloop.schedule_repeating_ms(_POLL_INTERVAL_MS, poll)
