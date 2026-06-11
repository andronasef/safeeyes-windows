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
"""The Settings dialog and its sub-dialogs (Qt/PySide6 port).

Mirrors ui/settings_dialog.py: a tabbed Settings window plus break-item and
plugin-item rows, per-plugin and per-break settings dialogs, the new-break
dialog, and the INT/TEXT/BOOL setting factories. Settings are committed when a
window is closed (matching the GTK close-request behaviour).
"""

import math
import os
import typing

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from safeeyes import utility
from safeeyes.configuration import Config
from safeeyes.model import PluginDependency
from safeeyes.qt import icons
from safeeyes.translations import translate as _


def _group(title: str) -> typing.Tuple[QFrame, QVBoxLayout]:
    """Build a titled, framed group box and return (frame, inner layout)."""
    frame = QFrame()
    frame.setFrameShape(QFrame.Shape.StyledPanel)
    outer = QVBoxLayout(frame)
    label = QLabel(title)
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    outer.addWidget(label)
    inner = QVBoxLayout()
    outer.addLayout(inner)
    return frame, inner


def _scaled_image_icon(path: str) -> QIcon:
    pixmap = QPixmap(path)
    if pixmap.isNull():
        return QIcon.fromTheme("image-missing")
    return QIcon(
        pixmap.scaled(
            16,
            16,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    )


# --- setting item factories ----------------------------------------------


class IntItem(QWidget):
    def __init__(
        self, name: str, value: float, min_value: float, max_value: float
    ) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(_(name)))
        layout.addStretch()
        self.spin = QSpinBox()
        self.spin.setRange(int(min_value), int(max_value))
        self.spin.setValue(int(value))
        layout.addWidget(self.spin)

    def get_value(self) -> int:
        return self.spin.value()


class TextItem(QWidget):
    def __init__(self, name: str, value: str) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(_(name)))
        layout.addStretch()
        self.edit = QLineEdit(value)
        layout.addWidget(self.edit)

    def get_value(self) -> str:
        return self.edit.text()


class BoolItem(QWidget):
    def __init__(self, name: str, value: bool) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(_(name)))
        layout.addStretch()
        self.check = QCheckBox()
        self.check.setChecked(bool(value))
        layout.addWidget(self.check)

    def get_value(self) -> bool:
        return self.check.isChecked()


# --- list rows -------------------------------------------------------------


class BreakItem(QWidget):
    """A single break row with name, properties and delete buttons."""

    def __init__(
        self,
        break_name: str,
        on_properties: typing.Callable[[], None],
        on_delete: typing.Callable[[], None],
    ) -> None:
        super().__init__()
        self.on_properties = on_properties
        self.on_delete = on_delete

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        self.lbl_name = QLabel(_(break_name))
        layout.addWidget(self.lbl_name)
        layout.addStretch()

        btn_props = QPushButton(QIcon.fromTheme("document-properties"), "")
        btn_props.setToolTip(_("Properties"))
        btn_props.clicked.connect(lambda: self.on_properties())
        layout.addWidget(btn_props)

        btn_delete = QPushButton(QIcon.fromTheme("edit-delete"), "")
        btn_delete.setToolTip(_("Delete"))
        btn_delete.clicked.connect(lambda: self.on_delete())
        layout.addWidget(btn_delete)

    def set_break_name(self, break_name: str) -> None:
        self.lbl_name.setText(_(break_name))


class PluginItem(QWidget):
    """A single plugin row: icon, name, description, enable + properties."""

    def __init__(
        self, plugin_config: dict, on_properties: typing.Callable[[], None]
    ) -> None:
        super().__init__()
        self.on_properties = on_properties
        self.plugin_config = plugin_config

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)

        self.icon_label = QLabel()
        if plugin_config["icon"]:
            self.icon_label.setPixmap(QPixmap(plugin_config["icon"]).scaled(
                24, 24,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        layout.addWidget(self.icon_label)

        text_col = QVBoxLayout()
        self.lbl_name = QLabel(_(plugin_config["meta"]["name"]))
        font = self.lbl_name.font()
        font.setBold(True)
        self.lbl_name.setFont(font)
        text_col.addWidget(self.lbl_name)
        self.lbl_description = QLabel()
        self.lbl_description.setWordWrap(True)
        text_col.addWidget(self.lbl_description)
        self._link_label = QLabel()
        self._link_label.setOpenExternalLinks(True)
        self._link_label.setVisible(False)
        text_col.addWidget(self._link_label)
        layout.addLayout(text_col, 1)

        self.btn_disable_errored = QPushButton(QIcon.fromTheme("process-stop"), "")
        self.btn_disable_errored.setToolTip(_("Disable permanently"))
        self.btn_disable_errored.setVisible(False)
        self.btn_disable_errored.clicked.connect(self._on_disable_errored)
        layout.addWidget(self.btn_disable_errored)

        self.btn_properties = QPushButton(QIcon.fromTheme("document-properties"), "")
        self.btn_properties.setToolTip(_("Properties"))
        self.btn_properties.clicked.connect(self._on_properties_clicked)
        layout.addWidget(self.btn_properties)

        self.switch_enable = QCheckBox()
        self.switch_enable.setChecked(plugin_config["enabled"])
        layout.addWidget(self.switch_enable)

        if plugin_config["error"]:
            message = plugin_config["meta"]["dependency_description"]
            if isinstance(message, PluginDependency):
                self.lbl_description.setText(_(message.message))
                if message.link is not None:
                    self._link_label.setText(
                        f'<a href="{message.link}">'
                        f'{_("Click here for more information")}</a>'
                    )
                self._link_label.setVisible(True)
            else:
                self.lbl_description.setText(_(message))
            self.lbl_name.setEnabled(False)
            self.lbl_description.setEnabled(False)
            self.switch_enable.setEnabled(False)
            self.btn_properties.setEnabled(False)
            if plugin_config["enabled"]:
                self.btn_disable_errored.setVisible(True)
        else:
            self.lbl_description.setText(_(plugin_config["meta"]["description"]))
            self.btn_properties.setEnabled(bool(plugin_config["settings"]))

    def is_enabled(self) -> bool:
        return self.switch_enable.isChecked()

    def _on_disable_errored(self) -> None:
        self.btn_disable_errored.setEnabled(False)
        self.switch_enable.setChecked(False)

    def _on_properties_clicked(self) -> None:
        if not self.plugin_config["error"] and self.plugin_config["settings"]:
            self.on_properties()


# --- sub-dialogs -----------------------------------------------------------


class PluginSettingsDialog(QDialog):
    """Builds a settings dialog from a plugin's setting definitions."""

    def __init__(self, parent, config: typing.Any) -> None:
        super().__init__(parent)
        self.config = config
        self.property_controls: list[dict] = []

        self.setWindowTitle(_(config["meta"]["name"]))
        self.setWindowIcon(icons.app_icon())
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        for setting in config.get("settings"):
            box: typing.Union[IntItem, BoolItem, TextItem]
            stype = setting["type"].upper()
            value = config["active_plugin_config"][setting["id"]]
            if stype == "INT":
                box = IntItem(
                    setting["label"],
                    value,
                    setting.get("min", 0),
                    setting.get("max", 120),
                )
            elif stype == "TEXT":
                box = TextItem(setting["label"], value)
            elif stype == "BOOL":
                box = BoolItem(setting["label"], value)
            else:
                continue

            self.property_controls.append({"key": setting["id"], "box": box})
            layout.addWidget(box)

        layout.addStretch()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        for control in self.property_controls:
            self.config["active_plugin_config"][control["key"]] = control[
                "box"
            ].get_value()
        super().closeEvent(event)

    def show(self) -> None:
        super().show()
        self.raise_()
        self.activateWindow()


class BreakSettingsDialog(QDialog):
    """Per-break settings: name, type, image, interval/duration/plugin overrides."""

    def __init__(
        self,
        parent,
        break_config: dict,
        is_short: bool,
        parent_config: Config,
        plugin_map: dict[str, str],
        on_close: typing.Callable[[dict], None],
        on_add: typing.Callable[[bool, dict], None],
        on_remove: typing.Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.break_config = break_config
        self.parent_config = parent_config
        self.is_short = is_short
        self.on_close = on_close
        self.on_add = on_add
        self.on_remove = on_remove
        self.plugin_check_buttons: dict[str, QCheckBox] = {}
        self._committed = False

        self.setWindowTitle(_("Break Settings"))
        self.setWindowIcon(icons.app_icon())
        self.setMinimumWidth(420)

        interval_overriden = break_config.get("interval", None) is not None
        duration_overriden = break_config.get("duration", None) is not None
        plugins_overriden = break_config.get("plugins", None) is not None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.cmb_type = QComboBox()
        self.cmb_type.addItems([_("Short"), _("Long")])
        self.cmb_type.setCurrentIndex(0 if is_short else 1)
        form.addRow(_("Type"), self.cmb_type)

        self.txt_break = QLineEdit(_(break_config["name"]))
        form.addRow(_("Break"), self.txt_break)

        self.btn_image = QPushButton(_("Select"))
        self.btn_image.clicked.connect(self.select_image)
        if "image" in break_config:
            self.btn_image.setIcon(_scaled_image_icon(break_config["image"]))
        form.addRow(_("Image"), self.btn_image)

        # Interval override group
        interval_frame, interval_layout = _group(_("Time to wait"))
        self.switch_override_interval = QCheckBox(_("Override"))
        self.switch_override_interval.setChecked(interval_overriden)
        self.switch_override_interval.toggled.connect(
            lambda s: self.spin_interval.setEnabled(s)
        )
        interval_layout.addWidget(self.switch_override_interval)
        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel(_("Time (in minutes)")))
        interval_row.addStretch()
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 120)
        interval_row.addWidget(self.spin_interval)
        interval_layout.addLayout(interval_row)
        layout.addWidget(interval_frame)

        if interval_overriden:
            self.spin_interval.setValue(break_config["interval"])
        elif is_short:
            self.spin_interval.setValue(parent_config.get("short_break_interval"))
        else:
            self.spin_interval.setValue(parent_config.get("long_break_interval"))

        # Duration override group
        duration_frame, duration_layout = _group(_("Duration"))
        self.switch_override_duration = QCheckBox(_("Override"))
        self.switch_override_duration.setChecked(duration_overriden)
        self.switch_override_duration.toggled.connect(
            lambda s: self.spin_duration.setEnabled(s)
        )
        duration_layout.addWidget(self.switch_override_duration)
        duration_row = QHBoxLayout()
        duration_row.addWidget(QLabel(_("Time (in seconds)")))
        duration_row.addStretch()
        self.spin_duration = QSpinBox()
        self.spin_duration.setRange(1, 3600)
        duration_row.addWidget(self.spin_duration)
        duration_layout.addLayout(duration_row)
        layout.addWidget(duration_frame)

        if duration_overriden:
            self.spin_duration.setValue(break_config["duration"])
        elif is_short:
            self.spin_duration.setValue(parent_config.get("short_break_duration"))
        else:
            self.spin_duration.setValue(parent_config.get("long_break_duration"))

        # Plugins override group
        plugins_frame, plugins_layout = _group(_("Plugins"))
        self.switch_override_plugins = QCheckBox(_("Override"))
        self.switch_override_plugins.setChecked(plugins_overriden)
        self.switch_override_plugins.toggled.connect(self._on_override_plugins)
        plugins_layout.addWidget(self.switch_override_plugins)
        grid = QGridLayout()
        row = col = 0
        for plugin_id, plugin_name in plugin_map.items():
            chk = QCheckBox(_(plugin_name))
            self.plugin_check_buttons[plugin_id] = chk
            grid.addWidget(chk, row, col)
            if plugins_overriden:
                chk.setChecked(plugin_id in break_config["plugins"])
            else:
                chk.setChecked(True)
            row += 1
            if row > 2:
                col += 1
                row = 0
        plugins_layout.addLayout(grid)
        layout.addWidget(plugins_frame)

        # Apply initial sensitivity.
        self.spin_interval.setEnabled(interval_overriden)
        self.spin_duration.setEnabled(duration_overriden)
        self._on_override_plugins(plugins_overriden)

    def _on_override_plugins(self, state: bool) -> None:
        for chk in self.plugin_check_buttons.values():
            chk.setEnabled(state)

    def select_image(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, _("Please select an image"), "", "PNG files (*.png)"
        )
        if path:
            self.break_config["image"] = path
            self.btn_image.setIcon(_scaled_image_icon(path))
        # Selecting nothing leaves the existing image untouched (matches the
        # GTK cancel path, which only cleared on an explicit empty selection).

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if not self._committed:
            self._committed = True
            self._commit()
        super().closeEvent(event)

    def _commit(self) -> None:
        break_name = self.txt_break.text().strip()
        if break_name:
            self.break_config["name"] = break_name

        if self.switch_override_interval.isChecked():
            self.break_config["interval"] = int(self.spin_interval.value())
        else:
            self.break_config.pop("interval", None)

        if self.switch_override_duration.isChecked():
            self.break_config["duration"] = int(self.spin_duration.value())
        else:
            self.break_config.pop("duration", None)

        if self.switch_override_plugins.isChecked():
            self.break_config["plugins"] = [
                pid
                for pid, chk in self.plugin_check_buttons.items()
                if chk.isChecked()
            ]
        else:
            self.break_config.pop("plugins", None)

        now_short = self.cmb_type.currentIndex() == 0
        if self.is_short and not now_short:
            self.parent_config.get("short_breaks").remove(self.break_config)
            self.parent_config.get("long_breaks").append(self.break_config)
            self.on_remove()
            self.on_add(False, self.break_config)
        elif not self.is_short and now_short:
            self.parent_config.get("long_breaks").remove(self.break_config)
            self.parent_config.get("short_breaks").append(self.break_config)
            self.on_remove()
            self.on_add(True, self.break_config)
        else:
            self.on_close(self.break_config)

    def show(self) -> None:
        super().show()
        self.raise_()
        self.activateWindow()


class NewBreakDialog(QDialog):
    """Create a new break (name + type), with explicit Save/Discard buttons."""

    def __init__(
        self,
        parent,
        parent_config: Config,
        on_add: typing.Callable[[bool, dict], None],
    ) -> None:
        super().__init__(parent)
        self.parent_config = parent_config
        self.on_add = on_add

        self.setWindowTitle(_("New Break"))
        self.setWindowIcon(icons.app_icon())
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.cmb_type = QComboBox()
        self.cmb_type.addItems([_("Short"), _("Long")])
        form.addRow(_("Type"), self.cmb_type)

        self.txt_break = QLineEdit()
        form.addRow(_("Break"), self.txt_break)

        buttons = QHBoxLayout()
        buttons.addStretch()
        btn_discard = QPushButton(_("Discard"))
        btn_discard.clicked.connect(self.close)
        buttons.addWidget(btn_discard)
        btn_save = QPushButton(_("Save"))
        btn_save.clicked.connect(self._save)
        buttons.addWidget(btn_save)
        layout.addLayout(buttons)

    def _save(self) -> None:
        break_config = {"name": self.txt_break.text().strip()}
        if self.cmb_type.currentIndex() == 0:
            self.parent_config.get("short_breaks").append(break_config)
            self.on_add(True, break_config)
        else:
            self.parent_config.get("long_breaks").append(break_config)
            self.on_add(False, break_config)
        self.close()

    def show(self) -> None:
        super().show()
        self.raise_()
        self.activateWindow()


# --- main dialog -----------------------------------------------------------


class SettingsDialog(QDialog):
    """The tabbed Settings window. Commits and saves on close."""

    def __init__(
        self,
        config: Config,
        on_save_settings: typing.Callable[[Config], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.on_save_settings = on_save_settings
        self.plugin_items: dict[str, PluginItem] = {}
        self.plugin_map: dict[str, str] = {}
        self.last_short_break_interval = config.get("short_break_interval")
        self._initializing = True
        self._infobar_shown = False
        self._child_dialogs: list[QDialog] = []
        self._committed = False

        self.setWindowTitle("Safe Eyes")
        self.setWindowIcon(icons.app_icon())
        self.resize(480, 680)

        self._tabs = QTabWidget()
        root = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addStretch()
        btn_reset = QPushButton(_("Reset"))
        btn_reset.clicked.connect(self.on_reset_clicked)
        header.addWidget(btn_reset)
        root.addLayout(header)
        root.addWidget(self._tabs)

        self._build_settings_tab()
        self._build_breaks_tab()
        self._build_plugins_tab()

        self.__initialize(config)
        self._initializing = False

    # -- tab construction --------------------------------------------------

    def _build_settings_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)

        # Short breaks group
        short_frame, short_layout = _group(_("Short Breaks"))
        self.spin_short_break_interval = self._spin(1, 60, 5)
        short_layout.addLayout(
            self._labeled(
                _("Interval between two breaks (in minutes)"),
                self.spin_short_break_interval,
            )
        )
        self.spin_short_break_duration = self._spin(1, 1800, 5)
        short_layout.addLayout(
            self._labeled(
                _("Break duration (in seconds)"), self.spin_short_break_duration
            )
        )
        layout.addWidget(short_frame)

        # Long breaks group
        long_frame, long_layout = _group(_("Long Breaks"))
        self.info_bar_long_break = QLabel(
            _("Long break interval must be a multiple of short break interval")
        )
        self.info_bar_long_break.setWordWrap(True)
        self.info_bar_long_break.setObjectName("info_bar_long_break")
        self.info_bar_long_break.setVisible(False)
        long_layout.addWidget(self.info_bar_long_break)
        self.spin_long_break_interval = self._spin(0, 120, 5)
        long_layout.addLayout(
            self._labeled(
                _("Interval between two breaks (in minutes)"),
                self.spin_long_break_interval,
            )
        )
        self.spin_long_break_duration = self._spin(1, 3600, 10, step=5)
        long_layout.addLayout(
            self._labeled(
                _("Break duration (in seconds)"), self.spin_long_break_duration
            )
        )
        layout.addWidget(long_frame)

        # Options group
        opt_frame, opt_layout = _group(_("Options"))
        self.spin_time_to_prepare = self._spin(1, 60, 5)
        opt_layout.addLayout(
            self._labeled(
                _("Time to prepare for a break (in seconds)"),
                self.spin_time_to_prepare,
            )
        )
        self.switch_fade_in_break_screen = QCheckBox()
        opt_layout.addLayout(
            self._labeled(
                _("Fade in when breaks start"), self.switch_fade_in_break_screen
            )
        )
        self.spin_fade_in_break_screen_duration = self._spin(1, 8000, 500, step=100)
        opt_layout.addLayout(
            self._labeled(
                _("Fade in duration (in milliseconds)"),
                self.spin_fade_in_break_screen_duration,
            )
        )
        self.switch_random_order = QCheckBox()
        opt_layout.addLayout(
            self._labeled(_("Show breaks in random order"), self.switch_random_order)
        )
        self.switch_strict_break = QCheckBox()
        opt_layout.addLayout(
            self._labeled(
                _("Strict break (No way to skip breaks)"), self.switch_strict_break
            )
        )
        self.switch_postpone = QCheckBox()
        self.switch_postpone.toggled.connect(self._on_postpone_toggled)
        opt_layout.addLayout(
            self._labeled(_("Allow postponing breaks"), self.switch_postpone)
        )
        self.spin_postpone_duration = self._spin(1, 15, 5)
        self.dropdown_postpone_unit = QComboBox()
        self.dropdown_postpone_unit.addItems([_("minutes"), _("seconds")])
        postpone_row = QHBoxLayout()
        postpone_row.addWidget(QLabel(_("Postponement duration in")))
        postpone_row.addStretch()
        postpone_row.addWidget(self.spin_postpone_duration)
        postpone_row.addWidget(self.dropdown_postpone_unit)
        opt_layout.addLayout(postpone_row)
        self.spin_disable_keyboard_shortcut = self._spin(0, 15, 5)
        opt_layout.addLayout(
            self._labeled(
                _("Skipping/postponing disabled period (in seconds)"),
                self.spin_disable_keyboard_shortcut,
            )
        )
        self.switch_persist = QCheckBox()
        opt_layout.addLayout(
            self._labeled(_("Persist the internal state"), self.switch_persist)
        )
        layout.addWidget(opt_frame)
        layout.addStretch()

        self._tabs.addTab(self._scroll(page), _("Settings"))

    def _build_breaks_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)

        short_frame, short_layout = _group(_("Short Breaks"))
        self._short_breaks_layout = QVBoxLayout()
        short_layout.addLayout(self._short_breaks_layout)
        btn_add_short = QPushButton(QIcon.fromTheme("list-add"), _("Add"))
        btn_add_short.clicked.connect(lambda: self.add_break())
        short_layout.addWidget(btn_add_short)
        layout.addWidget(short_frame)

        long_frame, long_layout = _group(_("Long Breaks"))
        self._long_breaks_layout = QVBoxLayout()
        long_layout.addLayout(self._long_breaks_layout)
        layout.addWidget(long_frame)
        layout.addStretch()

        self._tabs.addTab(self._scroll(page), _("Breaks"))

    def _build_plugins_tab(self) -> None:
        page = QWidget()
        self._plugins_layout = QVBoxLayout(page)
        self._plugins_layout.addStretch()
        self._tabs.addTab(self._scroll(page), _("Plugins"))

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _spin(minimum: int, maximum: int, page: int, step: int = 1) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        return spin

    @staticmethod
    def _labeled(text: str, control: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel(text))
        row.addStretch()
        row.addWidget(control)
        return row

    @staticmethod
    def _scroll(widget: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(widget)
        return area

    def __initialize(self, config: Config) -> None:
        self._infobar_shown = True
        for short_break in config.get("short_breaks"):
            self.__create_break_item(short_break, True)
        for long_break in config.get("long_breaks"):
            self.__create_break_item(long_break, False)

        for plugin_config in utility.load_plugins_config(config):
            item = self.__create_plugin_item(plugin_config)
            self._plugins_layout.insertWidget(
                self._plugins_layout.count() - 1, item
            )

        self.spin_short_break_duration.setValue(config.get("short_break_duration"))
        self.spin_long_break_duration.setValue(config.get("long_break_duration"))
        self.spin_short_break_interval.setValue(config.get("short_break_interval"))
        self.spin_long_break_interval.setRange(
            config.get("short_break_interval") * 2, 120
        )
        self.spin_long_break_interval.setValue(config.get("long_break_interval"))
        self.spin_time_to_prepare.setValue(config.get("pre_break_warning_time"))
        self.spin_postpone_duration.setValue(config.get("postpone_duration"))
        self.spin_fade_in_break_screen_duration.setValue(
            config.get("fade_in_break_screen_duration", 1500)
        )
        self.dropdown_postpone_unit.setCurrentIndex(
            1 if config.get("postpone_unit") == "seconds" else 0
        )
        self.spin_disable_keyboard_shortcut.setValue(
            config.get("shortcut_disable_time")
        )
        self.switch_strict_break.setChecked(config.get("strict_break"))
        self.switch_random_order.setChecked(config.get("random_order"))
        self.switch_postpone.setChecked(config.get("allow_postpone"))
        self.switch_fade_in_break_screen.setChecked(
            config.get("fade_in_break_screen", True)
        )
        self.switch_persist.setChecked(config.get("persist_state"))
        self._on_postpone_toggled(self.switch_postpone.isChecked())

        # Connect the interval coupling only after initial values are set, so it
        # does not fire (and pop the infobar) during initialization.
        self.last_short_break_interval = config.get("short_break_interval")
        self.spin_short_break_interval.valueChanged.connect(
            self._on_short_interval_changed
        )
        self.spin_long_break_interval.valueChanged.connect(
            self._on_long_interval_changed
        )
        self._infobar_shown = False

    # -- break list management ---------------------------------------------

    def __create_break_item(self, break_config: dict, is_short: bool) -> None:
        parent_layout = (
            self._short_breaks_layout if is_short else self._long_breaks_layout
        )

        item = BreakItem(
            break_name=break_config["name"],
            on_properties=lambda: self.__show_break_properties_dialog(
                break_config,
                is_short,
                on_close=lambda cfg: item.set_break_name(cfg["name"]),
                on_add=lambda short, cfg: self.__create_break_item(cfg, short),
                on_remove=lambda: self.__remove_item(item),
            ),
            on_delete=lambda: self.__delete_break(
                break_config, is_short, lambda: self.__remove_item(item)
            ),
        )
        parent_layout.addWidget(item)

    @staticmethod
    def __remove_item(item: QWidget) -> None:
        item.setParent(None)
        item.deleteLater()

    def __delete_break(
        self, break_config: dict, is_short: bool, on_remove: typing.Callable[[], None]
    ) -> None:
        confirm = QMessageBox(self)
        confirm.setIcon(QMessageBox.Icon.Warning)
        confirm.setWindowTitle("Safe Eyes")
        confirm.setText(_("Are you sure you want to delete this break?"))
        confirm.setInformativeText(_("You can't undo this action."))
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes
        )
        confirm.button(QMessageBox.StandardButton.Yes).setText(_("Delete"))
        confirm.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if confirm.exec() == QMessageBox.StandardButton.Yes:
            if is_short:
                self.config.get("short_breaks").remove(break_config)
            else:
                self.config.get("long_breaks").remove(break_config)
            on_remove()

    def __create_plugin_item(self, plugin_config: dict) -> PluginItem:
        item = PluginItem(
            plugin_config,
            on_properties=lambda: self.__show_plugin_properties_dialog(plugin_config),
        )
        self.plugin_items[plugin_config["id"]] = item
        if plugin_config.get("break_override_allowed", False):
            self.plugin_map[plugin_config["id"]] = plugin_config["meta"]["name"]
        return item

    def __show_plugin_properties_dialog(self, plugin_config: dict) -> None:
        dialog = PluginSettingsDialog(self, plugin_config)
        self._child_dialogs.append(dialog)
        dialog.show()

    def __show_break_properties_dialog(
        self,
        break_config: dict,
        is_short: bool,
        on_close: typing.Callable[[dict], None],
        on_add: typing.Callable[[bool, dict], None],
        on_remove: typing.Callable[[], None],
    ) -> None:
        dialog = BreakSettingsDialog(
            self,
            break_config,
            is_short,
            self.config,
            self.plugin_map,
            on_close,
            on_add,
            on_remove,
        )
        self._child_dialogs.append(dialog)
        dialog.show()

    def add_break(self) -> None:
        dialog = NewBreakDialog(
            self,
            self.config,
            lambda short, cfg: self.__create_break_item(cfg, short),
        )
        self._child_dialogs.append(dialog)
        dialog.show()

    # -- signal handlers ---------------------------------------------------

    def _on_postpone_toggled(self, _state: bool = False) -> None:
        enabled = self.switch_postpone.isChecked()
        self.spin_postpone_duration.setEnabled(enabled)
        self.dropdown_postpone_unit.setEnabled(enabled)

    def _on_short_interval_changed(self, _value: int = 0) -> None:
        short = self.spin_short_break_interval.value()
        long_value = self.spin_long_break_interval.value()
        self.spin_long_break_interval.setRange(short * 2, 120)
        self.spin_long_break_interval.setSingleStep(short)
        self.spin_long_break_interval.setValue(
            short * math.ceil(long_value / self.last_short_break_interval)
        )
        self.last_short_break_interval = short
        if not self._initializing and not self._infobar_shown:
            self._infobar_shown = True
            self.info_bar_long_break.setVisible(True)

    def _on_long_interval_changed(self, _value: int = 0) -> None:
        if not self._initializing and not self._infobar_shown:
            self._infobar_shown = True
            self.info_bar_long_break.setVisible(True)

    def on_reset_clicked(self) -> None:
        confirm = QMessageBox(self)
        confirm.setIcon(QMessageBox.Icon.Warning)
        confirm.setWindowTitle("Safe Eyes")
        confirm.setText(_("Are you sure you want to reset all settings to default?"))
        confirm.setInformativeText(_("You can't undo this action."))
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes
        )
        confirm.button(QMessageBox.StandardButton.Yes).setText(_("Reset"))
        confirm.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return

        self.config = Config.reset_config()
        self._clear_layout(self._short_breaks_layout)
        self._clear_layout(self._long_breaks_layout)
        self._clear_plugins()
        self.plugin_items.clear()
        self.plugin_map.clear()
        self._initializing = True
        self.__initialize(self.config)
        self._initializing = False

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _clear_plugins(self) -> None:
        # Keep the trailing stretch; remove only the plugin item widgets.
        for i in reversed(range(self._plugins_layout.count())):
            item = self._plugins_layout.itemAt(i)
            widget = item.widget()
            if widget is not None:
                self._plugins_layout.takeAt(i)
                widget.setParent(None)
                widget.deleteLater()

    # -- commit on close ---------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if not self._committed:
            self._committed = True
            self._commit()
        super().closeEvent(event)

    def _commit(self) -> None:
        c = self.config
        c.set("short_break_duration", self.spin_short_break_duration.value())
        c.set("long_break_duration", self.spin_long_break_duration.value())
        c.set("short_break_interval", self.spin_short_break_interval.value())
        c.set("long_break_interval", self.spin_long_break_interval.value())
        c.set("pre_break_warning_time", self.spin_time_to_prepare.value())
        c.set("postpone_duration", self.spin_postpone_duration.value())
        c.set(
            "fade_in_break_screen_duration",
            self.spin_fade_in_break_screen_duration.value(),
        )
        c.set(
            "postpone_unit",
            "seconds" if self.dropdown_postpone_unit.currentIndex() == 1 else "minutes",
        )
        c.set(
            "shortcut_disable_time", self.spin_disable_keyboard_shortcut.value()
        )
        c.set("strict_break", self.switch_strict_break.isChecked())
        c.set("random_order", self.switch_random_order.isChecked())
        c.set("allow_postpone", self.switch_postpone.isChecked())
        c.set("fade_in_break_screen", self.switch_fade_in_break_screen.isChecked())
        c.set("persist_state", self.switch_persist.isChecked())
        for plugin in c.get("plugins"):
            if plugin["id"] in self.plugin_items:
                plugin["enabled"] = self.plugin_items[plugin["id"]].is_enabled()

        self.on_save_settings(c)

    def show(self) -> None:
        super().show()
        self.raise_()
        self.activateWindow()
