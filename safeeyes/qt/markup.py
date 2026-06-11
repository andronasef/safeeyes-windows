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
"""Convert the small Pango-markup subset used by plugins to Qt rich text.

Plugins build break-screen widget content as strings (see
``plugin_manager.get_break_screen_widgets``) using only a narrow subset of Pango
markup: ``<b>``/``</b>`` plus newlines, tabs and box-rule characters. GTK
rendered this via ``Gtk.Label.set_markup``; Qt's ``QLabel`` renders HTML rich
text, so we translate that subset here.
"""

import html
import re

_TAG_SPLIT = re.compile(r"(</?[bi]>)")


def pango_to_html(markup: str) -> str:
    """Translate the supported Pango subset to Qt-compatible HTML rich text."""
    if not markup:
        return ""

    parts = _TAG_SPLIT.split(markup)
    out = []
    for part in parts:
        if part in ("<b>", "</b>", "<i>", "</i>"):
            out.append(part)
        else:
            escaped = html.escape(part)
            # Preserve the alignment of box-rule separators / tabbed columns.
            escaped = escaped.replace("\t", "&nbsp;&nbsp;&nbsp;&nbsp;")
            escaped = escaped.replace("\n", "<br>")
            out.append(escaped)
    return "".join(out)
