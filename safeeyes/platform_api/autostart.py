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
"""Cross-platform autostart (run-at-login) entry management.

On Linux an XDG ``.desktop`` autostart symlink is used. On Windows a value
under the ``HKCU\\...\\Run`` registry key is used instead.
"""

import logging
import os
import sys

from safeeyes import utility
from safeeyes.platform_api import IS_WINDOWS

# Windows registry autostart location.
_WIN_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_WIN_VALUE_NAME = "SafeEyes"


def create_startup_entry(force: bool = False) -> None:
    """Create (or repair) the autostart entry for the current platform.

    ``force`` mirrors the original semantics: when True the entry is always
    (re)created (used right after a fresh install); when False the entry is only
    repaired if a stale/broken one is found, never recreated if the user
    intentionally removed it.
    """
    if IS_WINDOWS:
        _create_startup_entry_windows(force)
    else:
        _create_startup_entry_linux(force)


def _create_startup_entry_linux(force: bool) -> None:
    """Create an XDG ``.desktop`` autostart symlink (Linux)."""
    startup_dir_path = os.path.join(utility.HOME_DIRECTORY, ".config/autostart")
    startup_entry = os.path.join(
        startup_dir_path, "io.github.slgobinath.SafeEyes.desktop"
    )
    # until Safe Eyes 2.1.5 the startup entry had another name
    # https://github.com/slgobinath/safeeyes/commit/684d16265a48794bb3fd670da67283fe4e2f591b#diff-0863348c2143a4928518a4d3661f150ba86d042bf5320b462ea2e960c36ed275L398
    obsolete_entry = os.path.join(startup_dir_path, "safeeyes.desktop")

    create_link = False

    if force:
        # if force is True, just create the link
        create_link = True
    else:
        # if force is False, we want to avoid creating the startup symlink if it was
        # manually deleted by the user, we want to create it only if a broken one is
        # found
        if os.path.islink(startup_entry):
            # if the link exists, check if it is broken
            try:
                os.stat(startup_entry)
            except FileNotFoundError:
                # a FileNotFoundError will get thrown if the startup symlink is
                # broken
                create_link = True

        if os.path.islink(obsolete_entry):
            # if a link with the old naming exists, delete it and create a new one
            create_link = True
            utility.delete(obsolete_entry)

    if create_link:
        # Create the folder if not exist
        utility.mkdir(startup_dir_path)

        # Remove existing files
        utility.delete(startup_entry)

        # Create the new startup entry
        try:
            os.symlink(utility.SYSTEM_DESKTOP_FILE, startup_entry)
        except OSError:
            logging.error("Failed to create startup entry at %s" % startup_entry)


def _create_startup_entry_windows(force: bool) -> None:
    """Create an ``HKCU\\...\\Run`` registry value (Windows).

    The Windows registry has no notion of a "broken" entry to repair, so the
    non-forced path is a no-op: the value either exists or the user removed it
    deliberately. The forced path (fresh install) writes the value.
    """
    if not force:
        return

    import winreg

    command = _windows_launch_command()
    try:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            _WIN_RUN_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, _WIN_VALUE_NAME, 0, winreg.REG_SZ, command)
        logging.debug("Created Windows startup entry: %s", command)
    except OSError:
        logging.error("Failed to create Windows startup entry")


def _windows_launch_command() -> str:
    """Build the command used to launch Safe Eyes at login on Windows.

    TODO(packaging/M6): once the app is frozen into an .exe this should point at
    the installed launcher; for a source/venv run we invoke the module with the
    windowed Python interpreter so no console window flashes on login.
    """
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'

    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    runner = pythonw if os.path.isfile(pythonw) else sys.executable
    return f'"{runner}" -m safeeyes'
