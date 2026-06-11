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
"""Single-instance enforcement and CLI command forwarding.

Replaces the GApplication HANDLES_COMMAND_LINE machinery. The primary instance
owns a ``QLocalServer`` named after the app id; subsequent launches connect with
a ``QLocalSocket``, forward their command, optionally read a reply (for
``--status``) and exit. This is cross-platform: a named pipe on Windows and a
Unix domain socket on Linux/macOS.
"""

import logging
import typing

from PySide6.QtCore import QObject
from PySide6.QtNetwork import QLocalServer, QLocalSocket

SERVER_NAME = "io.github.slgobinath.SafeEyes"

# Sentinel exchanged so a reply-expecting client (e.g. --status) can tell "the
# command produced no output" apart from "the connection dropped".
_NO_REPLY = "\x00"
_CONNECT_TIMEOUT_MS = 500
_REPLY_TIMEOUT_MS = 2000


class CommandServer(QObject):
    """Listens for commands forwarded by secondary instances."""

    def __init__(
        self, dispatch: typing.Callable[[str], typing.Optional[str]]
    ) -> None:
        super().__init__()
        self._dispatch = dispatch
        self._server = QLocalServer()
        self._server.newConnection.connect(self._on_new_connection)

    def listen(self) -> bool:
        """Start listening, clearing any stale socket left by a crash first."""
        # On Linux a hard kill leaves the socket file behind; removeServer wipes
        # it so listen() does not fail with AddressInUseError. No-op on Windows.
        QLocalServer.removeServer(SERVER_NAME)
        if not self._server.listen(SERVER_NAME):
            logging.error(
                "Failed to listen on %s: %s",
                SERVER_NAME,
                self._server.errorString(),
            )
            return False
        return True

    def close(self) -> None:
        self._server.close()

    def _on_new_connection(self) -> None:
        socket = self._server.nextPendingConnection()
        if socket is None:
            return
        socket.readyRead.connect(lambda: self._handle(socket))

    def _handle(self, socket: QLocalSocket) -> None:
        command = bytes(socket.readAll()).decode("utf-8").strip()
        if not command:
            return

        logging.info("Received remote command: %s", command)
        reply: typing.Optional[str] = None
        try:
            reply = self._dispatch(command)
        except Exception:
            logging.exception("Error handling remote command %s", command)

        payload = reply if reply is not None else _NO_REPLY
        socket.write((payload + "\n").encode("utf-8"))
        socket.flush()
        socket.waitForBytesWritten(_REPLY_TIMEOUT_MS)
        socket.disconnectFromServer()


def send_command(
    command: str, expect_reply: bool = False
) -> typing.Tuple[bool, typing.Optional[str]]:
    """Forward ``command`` to a running primary instance.

    Returns ``(connected, reply)``. ``connected`` is False when no primary
    instance is running (this process should become the primary). ``reply`` is
    the primary's response text for ``expect_reply`` commands, else None.
    """
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    if not socket.waitForConnected(_CONNECT_TIMEOUT_MS):
        return (False, None)

    socket.write((command + "\n").encode("utf-8"))
    socket.flush()
    socket.waitForBytesWritten(_CONNECT_TIMEOUT_MS)

    reply: typing.Optional[str] = None
    if socket.waitForReadyRead(_REPLY_TIMEOUT_MS):
        raw = bytes(socket.readAll()).decode("utf-8").strip()
        if raw and raw != _NO_REPLY:
            reply = raw

    socket.disconnectFromServer()
    return (True, reply if expect_reply else None)
