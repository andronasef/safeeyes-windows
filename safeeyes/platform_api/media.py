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
"""Media-player control abstraction (used by the mediacontrol plugin).

Linux uses MPRIS over D-Bus. Windows could use the System Media Transport
Controls (GSMTC) via the optional ``winsdk`` package; when it is not installed
this degrades gracefully to a no-op (there is simply no "Pause media" action).
"""

import logging
import re
import typing

from safeeyes.platform_api import IS_LINUX, IS_WINDOWS


def active_players() -> list:
    """Return opaque handles for media players currently playing."""
    if IS_LINUX:
        return _active_players_linux()
    if IS_WINDOWS:
        return _active_players_windows()
    return []


def pause(players: list) -> None:
    """Pause the given players (handles returned by :func:`active_players`)."""
    if IS_LINUX:
        _pause_linux(players)
    elif IS_WINDOWS:
        _pause_windows(players)


# --- Linux (MPRIS) --------------------------------------------------------


def _active_players_linux() -> list:
    import gi

    gi.require_version("Gio", "2.0")
    from gi.repository import Gio

    players = []
    dbus_proxy = Gio.DBusProxy.new_for_bus_sync(
        bus_type=Gio.BusType.SESSION,
        flags=Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES,
        info=None,
        name="org.freedesktop.DBus",
        object_path="/org/freedesktop/DBus",
        interface_name="org.freedesktop.DBus",
        cancellable=None,
    )

    for service in dbus_proxy.ListNames():
        if re.match("org.mpris.MediaPlayer2.", service):
            player = Gio.DBusProxy.new_for_bus_sync(
                bus_type=Gio.BusType.SESSION,
                flags=Gio.DBusProxyFlags.NONE,
                info=None,
                name=service,
                object_path="/org/mpris/MediaPlayer2",
                interface_name="org.mpris.MediaPlayer2.Player",
                cancellable=None,
            )
            playbackstatus = player.get_cached_property("PlaybackStatus")
            if playbackstatus is not None:
                if playbackstatus.unpack().lower() == "playing":
                    players.append(player)
            else:
                logging.warning("Failed to get PlaybackStatus for %s", service)

    return players


def _pause_linux(players: list) -> None:
    for player in players:
        player.Pause()


# --- Windows (GSMTC, optional) --------------------------------------------

_winsdk_sessions: typing.Optional[typing.Any] = None


def _gsmtc_manager():
    """Return the GSMTC session manager, or None if winsdk is unavailable."""
    try:
        import asyncio

        from winsdk.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as SessionManager,
        )
    except ImportError:
        return None

    try:
        return asyncio.run(SessionManager.request_async())
    except Exception as error:  # pragma: no cover - depends on host media stack
        logging.warning("GSMTC unavailable: %s", error)
        return None


def _active_players_windows() -> list:
    manager = _gsmtc_manager()
    if manager is None:
        return []

    from winsdk.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status,
    )

    playing = []
    for session in manager.get_sessions():
        info = session.get_playback_info()
        if info is not None and info.playback_status == Status.PLAYING:
            playing.append(session)
    return playing


def _pause_windows(players: list) -> None:
    import asyncio

    for session in players:
        try:
            asyncio.run(session.try_pause_async())
        except Exception as error:  # pragma: no cover
            logging.warning("Failed to pause media session: %s", error)
