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
"""Resolve the Safe Eyes version (toolkit-independent)."""

import re
import sys
from importlib import metadata
from pathlib import Path

# Baked-in fallback, used by frozen bundles (PyInstaller) where neither
# pyproject.toml nor installed-package metadata is available. Keep in sync with
# the version in pyproject.toml.
_FALLBACK_VERSION = "3.5.1"


def get_version() -> str:
    # In a frozen bundle there is no source tree or dist metadata to read.
    if getattr(sys, "frozen", False):
        return _FALLBACK_VERSION

    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"

    # Running from a source checkout: use the local project metadata.
    if pyproject_path.is_file():
        pyproject_text = pyproject_path.read_text(encoding="utf-8")

        try:
            import tomllib

            pyproject = tomllib.loads(pyproject_text)
            version = pyproject["project"]["version"]
            return f"{version}+development"
        except ModuleNotFoundError:
            pass
        except (ValueError, KeyError, TypeError):
            # Fall back to regex parsing for compatibility and resilience.
            pass

        match = re.search(
            r'(?ms)^\[project\].*?^version\s*=\s*"([^"]+)"',
            pyproject_text,
        )
        if match is None:
            raise RuntimeError("Could not parse project version from pyproject.toml")

        return f"{match.group(1)}+development"

    # Installed package: use distribution metadata.
    try:
        return metadata.version("safeeyes")
    except metadata.PackageNotFoundError:
        return _FALLBACK_VERSION
