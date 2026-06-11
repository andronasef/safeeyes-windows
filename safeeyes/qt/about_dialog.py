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
"""The About dialog (Qt/PySide6 port of ui/about_dialog.py)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from safeeyes.qt import icons
from safeeyes.translations import translate as _

_LICENSE = (
    "This program is free software: you can redistribute it and/or modify\n"
    "it under the terms of the GNU General Public License as published by\n"
    "the Free Software Foundation, either version 3 of the License, or\n"
    "(at your option) any later version.\n\n"
    "This program is distributed in the hope that it will be useful,\n"
    "but WITHOUT ANY WARRANTY; without even the implied warranty of\n"
    "MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the\n"
    "GNU General Public License for more details.\n\n"
    "You should have received a copy of the GNU General Public License\n"
    "along with this program.  If not, see <https://www.gnu.org/licenses/>."
)

_HOMEPAGE = "https://slgobinath.github.io/safeeyes"
_CONTRIBUTORS = "https://github.com/slgobinath/safeeyes/graphs/contributors?type=a"
_TRANSLATE = (
    "https://github.com/slgobinath/safeeyes?tab=readme-ov-file"
    "#how-you-can-help-improving-translation-of-safe-eyes"
)


def _link(label: str, uri: str) -> QLabel:
    link = QLabel(f'<a href="{uri}">{label}</a>')
    link.setOpenExternalLinks(True)
    link.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return link


class AboutDialog(QDialog):
    """Shows the application name with version, description, license and links."""

    def __init__(self, version: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Safe Eyes")
        self.setWindowIcon(icons.app_icon())
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)

        app_icon = QLabel()
        app_icon.setPixmap(icons.app_icon().pixmap(72, 72))
        app_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(app_icon)

        app_name = QLabel("Safe Eyes " + version)
        app_name.setObjectName("lbl_app_name")
        app_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = app_name.font()
        font.setBold(True)
        app_name.setFont(font)
        layout.addWidget(app_name)

        description = QLabel(
            _(
                "Safe Eyes protects your eyes from eye strain (asthenopia) by"
                " reminding you to take breaks while you're working long hours at"
                " the computer"
            )
        )
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(description)

        layout.addWidget(_link(_HOMEPAGE, _HOMEPAGE))

        layout.addWidget(QLabel(_("License") + ":"))
        license_view = QPlainTextEdit(_LICENSE)
        license_view.setReadOnly(True)
        layout.addWidget(license_view)

        buttons = QHBoxLayout()
        buttons.addWidget(_link(_("List of Contributors"), _CONTRIBUTORS))
        btn_close = QPushButton(_("Close"))
        btn_close.clicked.connect(self.close)
        buttons.addWidget(btn_close)
        buttons.addWidget(_link(_("Help us translate this app"), _TRANSLATE))
        layout.addLayout(buttons)

    def show(self) -> None:
        self.setWindowState(Qt.WindowState.WindowActive)
        super().show()
        self.raise_()
        self.activateWindow()
