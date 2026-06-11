#!/usr/bin/env python3
# Safe Eyes is a utility to remind you to take break frequently
# to protect your eyes from eye strain.

# Copyright (C) 2016  Gobinath

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
"""Safe Eyes is a utility to remind you to take break frequently to protect
your eyes from eye strain.

This is the Qt/PySide6 entry point. Single-instance behaviour and CLI command
forwarding (formerly GApplication HANDLES_COMMAND_LINE) are implemented via a
QLocalServer; see :mod:`safeeyes.qt.single_instance`.
"""

import argparse
import logging
import sys
import typing

from safeeyes import translations, utility
from safeeyes.model import BreakType
from safeeyes.platform_api import signals
from safeeyes.qt import single_instance
from safeeyes.qt.application import (
    CMD_ABOUT,
    CMD_DISABLE,
    CMD_ENABLE,
    CMD_LONG_BREAK,
    CMD_PING,
    CMD_QUIT,
    CMD_SETTINGS,
    CMD_SHORT_BREAK,
    CMD_STATUS,
    CMD_TAKE_BREAK,
    SAFE_EYES_VERSION,
    SafeEyesApp,
)
from safeeyes.translations import translate as _

safe_eyes: typing.Optional[SafeEyesApp] = None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="safeeyes",
        description=_(
            "Safe Eyes protects your eyes from eye strain by reminding you to"
            " take breaks."
        ),
        add_help=True,
    )
    parser.add_argument(
        "-a", "--about", action="store_true", help=_("show the about dialog")
    )
    parser.add_argument(
        "-s", "--settings", action="store_true", help=_("show the settings dialog")
    )
    parser.add_argument(
        "-t", "--take-break", action="store_true", help=_("Take a break now").lower()
    )
    parser.add_argument(
        "-b",
        "--short-break",
        action="store_true",
        help=_("take a short break now").lower(),
    )
    parser.add_argument(
        "-l",
        "--long-break",
        action="store_true",
        help=_("take a long break now").lower(),
    )
    parser.add_argument(
        "-d",
        "--disable",
        action="store_true",
        help=_("disable the currently running Safe Eyes instance"),
    )
    parser.add_argument(
        "-e",
        "--enable",
        action="store_true",
        help=_("enable the currently running Safe Eyes instance"),
    )
    parser.add_argument(
        "-q",
        "--quit",
        action="store_true",
        help=_("quit the running Safe Eyes instance and exit"),
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help=_("print the status of running Safe Eyes instance and exit"),
    )
    parser.add_argument(
        "--debug", action="store_true", help=_("start Safe Eyes in debug mode")
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="show program's version number and exit",
    )
    return parser


def _command_from_args(args: argparse.Namespace) -> typing.Optional[str]:
    """Map parsed flags to a single remote command, or None for a plain launch.

    Activation/about/settings/take-break flags are mutually handled in priority
    order, matching the GTK behaviour.
    """
    if args.status:
        return CMD_STATUS
    if args.quit:
        return CMD_QUIT
    if args.enable:
        return CMD_ENABLE
    if args.disable:
        return CMD_DISABLE
    if args.about:
        return CMD_ABOUT
    if args.settings:
        return CMD_SETTINGS
    if args.short_break:
        return CMD_SHORT_BREAK
    if args.long_break:
        return CMD_LONG_BREAK
    if args.take_break:
        return CMD_TAKE_BREAK
    return None


def _force_utf8_output() -> None:
    """Make stdout/stderr tolerate non-ASCII text.

    Status strings carry locale-formatted times that can include characters
    (e.g. U+202F narrow no-break space) outside the Windows console's legacy
    cp1252 codec, which would otherwise raise UnicodeEncodeError on print().
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main() -> int:
    """Start Safe Eyes (or forward a command to a running instance)."""
    global safe_eyes

    _force_utf8_output()

    parser = _build_parser()
    args = parser.parse_args()

    if args.version:
        print(f"Safe Eyes {SAFE_EYES_VERSION}")
        return 0

    utility.initialize_logging(args.debug)
    utility.initialize_platform()
    utility.cleanup_old_user_stylesheet()

    if args.short_break and args.long_break:
        print(
            "Cannot combine -b/--short-break with -l/--long-break",
            file=sys.stderr,
        )
        return 1

    system_locale = translations.setup()

    # QApplication must exist before QLocalSocket so its synchronous waits can
    # dispatch events. Creating it does not show any window.
    from PySide6.QtWidgets import QApplication

    from safeeyes.qt import icons

    qapp = QApplication(sys.argv)
    qapp.setApplicationName("Safe Eyes")
    qapp.setApplicationDisplayName("Safe Eyes")
    qapp.setDesktopFileName("io.github.slgobinath.SafeEyes")
    qapp.setWindowIcon(icons.app_icon())
    # Break windows come and go; the app must outlive them.
    qapp.setQuitOnLastWindowClosed(False)

    command = _command_from_args(args)

    # Probe for / forward to an already-running primary instance.
    probe = command if command is not None else CMD_PING
    connected, reply = single_instance.send_command(
        probe, expect_reply=(command == CMD_STATUS)
    )

    if connected:
        if command == CMD_STATUS:
            print(reply if reply is not None else "")
        elif command is None:
            logging.info("Safe Eyes is already running")
        return 0

    # No running instance: this process becomes the primary.
    if command in (CMD_ENABLE, CMD_DISABLE, CMD_STATUS, CMD_QUIT):
        print(_("Safe Eyes is not running"))
        return 1

    logging.info("Primary instance")

    safe_eyes = SafeEyesApp(qapp, system_locale)

    server = single_instance.CommandServer(safe_eyes.handle_command)
    if not server.listen():
        logging.error("Could not start the single-instance server")

    safe_eyes.start()

    # Handle Ctrl+C gracefully on the Qt loop.
    signals.install_sigint(sigint_caught)

    # Apply a startup command that does not require a remote instance.
    if command == CMD_ABOUT:
        safe_eyes.show_about()
    elif command == CMD_SETTINGS:
        safe_eyes.show_settings()
    elif command == CMD_TAKE_BREAK:
        safe_eyes.take_break(None)
    elif command == CMD_SHORT_BREAK:
        safe_eyes.take_break(BreakType.SHORT_BREAK)
    elif command == CMD_LONG_BREAK:
        safe_eyes.take_break(BreakType.LONG_BREAK)

    return qapp.exec()


def sigint_caught() -> None:
    global safe_eyes

    if safe_eyes is not None:
        safe_eyes.quit()
    else:
        sys.exit(0)


if __name__ == "__main__":
    sys.exit(main())
