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
"""Dialog shown when a required plugin is missing dependencies.

Qt/PySide6 port of ui/required_plugin_dialog.py. Closing the dialog (window
close or Quit) quits Safe Eyes; the user may instead disable the plugin.
"""

import typing

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from safeeyes.model import PluginDependency
from safeeyes.qt import icons
from safeeyes.translations import translate as _


class RequiredPluginDialog(QDialog):
    """Shows an error when a required plugin has missing dependencies."""

    def __init__(
        self,
        plugin_name: str,
        message: typing.Union[str, PluginDependency],
        on_quit: typing.Callable[[], None],
        on_disable_plugin: typing.Callable[[], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.on_quit = on_quit
        self.on_disable_plugin = on_disable_plugin
        self._resolved = False

        self.setWindowTitle("Safe Eyes")
        self.setWindowIcon(icons.app_icon())
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        header = QLabel(
            _("The required plugin '%s' is missing dependencies!") % _(plugin_name)
        )
        header.setWordWrap(True)
        font = header.font()
        font.setBold(True)
        header.setFont(font)
        layout.addWidget(header)

        if isinstance(message, PluginDependency):
            body = QLabel(_(message.message))
            body.setWordWrap(True)
            layout.addWidget(body)
            if message.link is not None:
                link = QLabel(
                    f'<a href="{message.link}">{_("Click here for more information")}</a>'
                )
                link.setOpenExternalLinks(True)
                layout.addWidget(link)
        else:
            body = QLabel(_(message))
            body.setWordWrap(True)
            layout.addWidget(body)

        buttons = QHBoxLayout()
        buttons.addStretch()
        btn_disable = QPushButton(_("Disable plugin permanently"))
        btn_disable.clicked.connect(self._disable_clicked)
        buttons.addWidget(btn_disable)
        btn_quit = QPushButton(_("Quit"))
        btn_quit.clicked.connect(self._quit_clicked)
        buttons.addWidget(btn_quit)
        layout.addLayout(buttons)

    def _quit_clicked(self) -> None:
        self._resolved = True
        self.close()
        self.on_quit()

    def _disable_clicked(self) -> None:
        self._resolved = True
        self.close()
        self.on_disable_plugin()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        # Closing via the window control is equivalent to choosing Quit, unless
        # the user already picked an explicit action.
        super().closeEvent(event)
        if not self._resolved:
            self._resolved = True
            self.on_quit()

    def show(self) -> None:
        super().show()
        self.raise_()
        self.activateWindow()
