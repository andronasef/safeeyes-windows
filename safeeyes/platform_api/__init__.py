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
"""Platform abstraction layer for Safe Eyes.

The original Safe Eyes is Linux-only and talks directly to X11, Wayland and
D-Bus. To support Windows (and keep the door open for other platforms) the
platform-specific plumbing lives here behind a small, OS-neutral API, chosen
once at import time. The rest of the application stays unaware of the platform.

This module intentionally has no heavy imports so it can be imported very early
(e.g. from ``safeeyes.utility``) without pulling in GTK or any OS bindings.
"""

import sys

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MAC = sys.platform == "darwin"
