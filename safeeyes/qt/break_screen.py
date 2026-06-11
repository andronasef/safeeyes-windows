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
"""The fullscreen break screen (Qt/PySide6 port of ui/break_screen.py)."""

import logging
import os
import typing

from PySide6.QtCore import QPropertyAnimation, Qt
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from safeeyes.configuration import Config
from safeeyes.context import Context
from safeeyes.model import Break, TrayAction
from safeeyes.platform_api import keyboard_block
from safeeyes.qt import icons, markup
from safeeyes.translations import translate as _


class BreakScreen:
    """Creates and manages one fullscreen window per monitor during a break."""

    windows: list["BreakScreenWindow"]

    def __init__(
        self,
        context: Context,
        on_skipped: typing.Callable[[], None],
        on_postponed: typing.Callable[[], None],
    ) -> None:
        self.context = context
        self.on_skipped = on_skipped
        self.on_postponed = on_postponed
        self.windows = []

        self.enable_postpone = False
        self.enable_shortcut = False
        self.shortcut_disable_time = 2
        self.fade_in_break_screen = True
        self.fade_in_break_screen_duration = 1500
        self.strict_break = False
        self.show_skip_button = False
        self.show_postpone_button = False

    def initialize(self, config: Config) -> None:
        """Initialize the internal properties from configuration."""
        logging.info("Initialize the break screen")
        self.enable_postpone = config.get("allow_postpone", False)
        self.shortcut_disable_time = config.get("shortcut_disable_time", 2)
        self.fade_in_break_screen = config.get("fade_in_break_screen", True)
        self.fade_in_break_screen_duration = config.get(
            "fade_in_break_screen_duration", 1500
        )
        self.strict_break = config.get("strict_break", False)

    def skip_break(self) -> None:
        logging.info("User skipped the break")
        self.on_skipped()
        self.close()

    def postpone_break(self) -> None:
        logging.info("User postponed the break")
        self.on_postponed()
        self.close()

    def on_skip_clicked(self) -> None:
        if self.enable_shortcut:
            self.skip_break()

    def on_postpone_clicked(self) -> None:
        if self.enable_shortcut:
            self.postpone_break()

    def show_count_down(self, countdown: int, seconds: int) -> None:
        """Show/update the countdown on all screens."""
        self.enable_shortcut = self.shortcut_disable_time <= seconds
        mins, secs = divmod(countdown, 60)
        timeformat = "{:02d}:{:02d}".format(mins, secs)
        for window in self.windows:
            window.set_count_down(timeformat, self.enable_shortcut)

    def show_message(
        self,
        break_obj: Break,
        widget: str,
        tray_actions: typing.Optional[list[TrayAction]] = None,
    ) -> None:
        """Show the break screen with the given message on all displays."""
        if tray_actions is None:
            tray_actions = []

        message = break_obj.name
        image_path = break_obj.image
        self.enable_shortcut = self.shortcut_disable_time <= 0

        skip_button_disabled = self.context.get("skip_button_disabled", False)
        self.show_skip_button = not self.strict_break and not skip_button_disabled

        postpone_button_disabled = self.context.get("postpone_button_disabled", False)
        self.show_postpone_button = (
            self.enable_postpone and not postpone_button_disabled
        )

        target_opacity = 0.9 if self.context.desktop == "kde" else 1.0

        # Block global keyboard shortcuts so the user cannot bypass the break
        # (Qt's own grab is in-app only). Released again in close().
        keyboard_block.block()

        screens = QGuiApplication.screens()
        logging.info("Show break screens in %d display(s)", len(screens))

        for screen in screens:
            window = BreakScreenWindow(
                message=message,
                image_path=image_path,
                widget_markup=widget,
                tray_actions=tray_actions,
                show_postpone=self.show_postpone_button,
                on_postpone=self.on_postpone_clicked,
                show_skip=self.show_skip_button,
                on_skip=self.on_skip_clicked,
                enable_shortcut=self.enable_shortcut,
                fade_in_duration_ms=self.fade_in_break_screen_duration,
                on_key_shortcut=self._on_key_shortcut,
            )
            self.windows.append(window)
            window.show_on(screen, target_opacity, self.fade_in_break_screen)

    def _on_key_shortcut(self, action: str) -> None:
        """Handle a skip/postpone shortcut key pressed on a break window."""
        if not self.enable_shortcut:
            return
        if action == "postpone" and self.show_postpone_button:
            self.postpone_break()
        elif action == "skip" and self.show_skip_button:
            self.skip_break()

    def close(self) -> None:
        """Close all break screens."""
        logging.info("Close the break screen(s)")
        keyboard_block.unblock()
        for window in self.windows:
            window.stop_and_close()
        self.windows.clear()


class BreakScreenWindow(QWidget):
    """A single fullscreen break window covering one monitor."""

    def __init__(
        self,
        message: str,
        image_path: typing.Optional[str],
        widget_markup: str,
        tray_actions: list[TrayAction],
        show_postpone: bool,
        on_postpone: typing.Callable[[], None],
        show_skip: bool,
        on_skip: typing.Callable[[], None],
        enable_shortcut: bool,
        fade_in_duration_ms: int,
        on_key_shortcut: typing.Callable[[str], None],
    ) -> None:
        super().__init__()

        self._image_path = image_path
        self._fade_in_duration_ms = max(1, fade_in_duration_ms)
        self._fade_anim: typing.Optional[QPropertyAnimation] = None
        self._on_key_shortcut = on_key_shortcut
        self._buttons: list[QPushButton] = []

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setObjectName("break_screen_root")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Black background even before the stylesheet is applied.
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), Qt.GlobalColor.black)
        self.setPalette(palette)
        # The window itself receives the skip/postpone keys (buttons are
        # explicitly non-focusable so Space/Esc don't activate them).
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._build_ui(
            message,
            widget_markup,
            tray_actions,
            show_postpone,
            on_postpone,
            show_skip,
            on_skip,
            enable_shortcut,
        )

    def _build_ui(
        self,
        message: str,
        widget_markup: str,
        tray_actions: list[TrayAction],
        show_postpone: bool,
        on_postpone: typing.Callable[[], None],
        show_skip: bool,
        on_skip: typing.Callable[[], None],
        enable_shortcut: bool,
    ) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Top toolbar (tray-action buttons), aligned to the top-right.
        toolbar = QWidget()
        toolbar.setObjectName("toolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.addStretch()
        for tray_action in tray_actions:
            button = QToolButton()
            button.setIcon(icons.icon_from_spec(tray_action.get_icon_spec()))
            button.setToolTip(_(tray_action.name))
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(
                lambda checked=False, a=tray_action: self._tray_action(a)
            )
            tray_action.add_toolbar_button(button)
            toolbar_layout.addWidget(button)
        outer.addWidget(toolbar, 0, Qt.AlignmentFlag.AlignTop)

        outer.addStretch()

        # Optional break image.
        self._img_label = QLabel()
        self._img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self._img_label, 0, Qt.AlignmentFlag.AlignCenter)

        # Message.
        self._msg_label = QLabel(message)
        self._msg_label.setObjectName("lbl_message")
        self._msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._msg_label.setWordWrap(True)
        outer.addWidget(self._msg_label, 0, Qt.AlignmentFlag.AlignCenter)

        # Countdown.
        self._count_label = QLabel("")
        self._count_label.setObjectName("lbl_count")
        self._count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self._count_label, 0, Qt.AlignmentFlag.AlignCenter)

        # Skip / postpone buttons.
        button_row = QHBoxLayout()
        button_row.addStretch()
        if show_postpone:
            btn_postpone = QPushButton(_("Postpone"))
            btn_postpone.setObjectName("btn_postpone")
            btn_postpone.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn_postpone.setEnabled(enable_shortcut)
            btn_postpone.clicked.connect(lambda: on_postpone())
            self._buttons.append(btn_postpone)
            button_row.addWidget(btn_postpone)
        if show_skip:
            btn_skip = QPushButton(_("Skip"))
            btn_skip.setObjectName("btn_skip")
            btn_skip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn_skip.setEnabled(enable_shortcut)
            btn_skip.clicked.connect(lambda: on_skip())
            self._buttons.append(btn_skip)
            button_row.addWidget(btn_skip)
        button_row.addStretch()
        outer.addLayout(button_row)

        # Plugin widget content (markup).
        self._widget_label = QLabel()
        self._widget_label.setObjectName("lbl_widget")
        self._widget_label.setTextFormat(Qt.TextFormat.RichText)
        self._widget_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._widget_label.setText(markup.pango_to_html(widget_markup))
        outer.addWidget(self._widget_label, 0, Qt.AlignmentFlag.AlignCenter)

        outer.addStretch()

    def show_on(self, screen, target_opacity: float, fade: bool) -> None:
        """Show this window fullscreen on the given QScreen."""
        geometry = screen.geometry()
        self.setScreen(screen)
        self.setGeometry(geometry)

        if self._image_path and os.path.isfile(self._image_path):
            pixmap = QPixmap(self._image_path)
            if not pixmap.isNull():
                max_w = max(1, geometry.width() * 8 // 10)
                max_h = max(1, geometry.height() * 3 // 10)
                self._img_label.setPixmap(
                    pixmap.scaled(
                        max_w,
                        max_h,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

        self.showFullScreen()

        if fade:
            self.setWindowOpacity(0.0)
            self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
            self._fade_anim.setDuration(self._fade_in_duration_ms)
            self._fade_anim.setStartValue(0.0)
            self._fade_anim.setEndValue(target_opacity)
            self._fade_anim.start()
        else:
            self.setWindowOpacity(target_opacity)

        self.raise_()
        self.activateWindow()
        self.setFocus()

    def set_count_down(self, count: str, enable_shortcut: bool) -> None:
        self._count_label.setText(count)
        for button in self._buttons:
            button.setEnabled(enable_shortcut)

    def _tray_action(self, tray_action: TrayAction) -> None:
        if tray_action.single_use:
            tray_action.reset()
        tray_action.action()

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._on_key_shortcut("skip")
            return
        if key == Qt.Key.Key_Space:
            self._on_key_shortcut("postpone")
            return
        super().keyPressEvent(event)

    def stop_and_close(self) -> None:
        if self._fade_anim is not None:
            self._fade_anim.stop()
            self._fade_anim = None
        self.close()
        self.deleteLater()
