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
"""Safe Eyes tray icon plugin (Qt/PySide6 port).

The menu model is built by :meth:`TrayIcon.get_items` as a toolkit-neutral list
of dicts; :meth:`TrayIcon._build_menu` turns that into a ``QMenu`` attached to
the shared :class:`QSystemTrayIcon`. This replaces the previous freedesktop
StatusNotifierItem / com.canonical.dbusmenu D-Bus implementation.
"""

import datetime
import logging
import typing

from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from safeeyes import mainloop, utility
from safeeyes.context import Context
from safeeyes.model import BreakType
from safeeyes.qt import icons, system_tray
from safeeyes.translations import translate as _

"""
Safe Eyes tray icon plugin
"""

tray_icon: typing.Optional["TrayIcon"] = None
safeeyes_config = None


class TrayIcon:
    """Create and show the tray icon along with the tray menu."""

    def __init__(self, context: Context, plugin_config):
        self.context = context
        self.on_show_settings = context.api.show_settings
        self.on_show_about = context.api.show_about
        self.quit = context.api.quit
        self.enable_safeeyes = context.api.enable_safeeyes
        self.disable_safeeyes = context.api.disable_safeeyes
        self.take_break = context.api.take_break
        self.has_breaks = context.api.has_breaks
        self.get_break_time = context.api.get_break_time
        self.plugin_config = plugin_config
        self.date_time = None
        self.active = True
        self.wakeup_time = None
        self.allow_disabling = plugin_config["allow_disabling"]
        self.menu_locked = False

        self._animation_timer: typing.Optional[mainloop.Timer] = None
        self._animation_icon_enabled = False
        self._resume_timer: typing.Optional[mainloop.Timer] = None
        # Keep a reference to the live QMenu so it is not garbage-collected
        # while shown by the tray icon.
        self._menu: typing.Optional[QMenu] = None
        self._current_icon = icons.TRAY_ENABLED

        self._tray = system_tray.get_tray_icon()
        self._tray.activated.connect(self._on_activated)
        self._set_icon(icons.TRAY_ENABLED)

        self.update_menu()
        self.update_tooltip()

    def initialize(self, plugin_config):
        """Initialize the tray icon by setting the config."""
        self.plugin_config = plugin_config
        self.allow_disabling = plugin_config["allow_disabling"]

        self.update_menu()
        self.update_tooltip()

    def unregister(self) -> None:
        self.stop_animation()
        self.__clear_resume_timer()
        try:
            self._tray.activated.disconnect(self._on_activated)
        except (RuntimeError, TypeError):
            pass
        self._tray.setContextMenu(None)
        self._menu = None

    # -- icon / menu rendering --------------------------------------------

    def _set_icon(self, name: str) -> None:
        self._current_icon = name
        self._tray.setIcon(icons.themed_icon(name))

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.MiddleClick:
            self.on_secondary_activate()

    def _build_menu(self, items) -> QMenu:
        menu = QMenu()
        self._populate_menu(menu, items)
        return menu

    def _populate_menu(self, menu: QMenu, items) -> None:
        for item in items:
            if item.get("hidden", False):
                continue

            if item.get("type") == "separator":
                menu.addSeparator()
                continue

            children = item.get("children")
            if children is not None:
                submenu = menu.addMenu(item["label"])
                submenu.setEnabled(item.get("enabled", True))
                if "icon-name" in item:
                    submenu.setIcon(icons.themed_icon(item["icon-name"]))
                self._populate_menu(submenu, children)
                continue

            action = menu.addAction(item["label"])
            action.setEnabled(item.get("enabled", True))
            if "icon-name" in item:
                action.setIcon(icons.themed_icon(item["icon-name"]))

            callback = item.get("callback")
            if callback is not None:
                action.triggered.connect(
                    lambda checked=False, cb=callback: cb()
                )

    def get_items(self):
        breaks_found = self.has_breaks()

        info_message = _("No Breaks Available")

        if breaks_found:
            if self.active:
                next_break = self.get_next_break_time()

                if next_break is not None:
                    (next_time, next_long_time, next_is_long) = next_break

                    if next_long_time:
                        if next_is_long:
                            info_message = _("Next long break at %s") % (next_long_time)
                        else:
                            info_message = _("Next breaks at %(short)s/%(long)s") % {
                                "short": next_time,
                                "long": next_long_time,
                            }
                    else:
                        info_message = _("Next break at %s") % (next_time)
            else:
                if self.wakeup_time:
                    info_message = _("Disabled until %s") % utility.format_time(
                        self.wakeup_time
                    )
                else:
                    info_message = _("Disabled until restart")

        disable_items = []

        if self.allow_disabling:
            disable_option_dynamic_id = 13

            for disable_option in self.plugin_config["disable_options"]:
                time_in_minutes = time_in_x = disable_option["time"]

                # Validate time value
                if not isinstance(time_in_minutes, int) or time_in_minutes <= 0:
                    logging.error(
                        "Invalid time in disable option: " + str(time_in_minutes)
                    )
                    continue
                time_unit = disable_option["unit"].lower()
                if time_unit == "seconds" or time_unit == "second":
                    time_in_minutes = int(time_in_minutes / 60)
                    label = self.context["locale"].ngettext(
                        "For %(num)d Second", "For %(num)d Seconds", time_in_x
                    ) % {"num": time_in_x}
                elif time_unit == "minutes" or time_unit == "minute":
                    time_in_minutes = int(time_in_minutes * 1)
                    label = self.context["locale"].ngettext(
                        "For %(num)d Minute", "For %(num)d Minutes", time_in_x
                    ) % {"num": time_in_x}
                elif time_unit == "hours" or time_unit == "hour":
                    time_in_minutes = int(time_in_minutes * 60)
                    label = self.context["locale"].ngettext(
                        "For %(num)d Hour", "For %(num)d Hours", time_in_x
                    ) % {"num": time_in_x}
                else:
                    # Invalid unit
                    logging.error(
                        "Invalid unit in disable option: " + str(disable_option)
                    )
                    continue

                ttw = time_in_minutes
                disable_items.append(
                    {
                        "id": disable_option_dynamic_id,
                        "label": label,
                        "callback": lambda ttw=ttw: self.on_disable_clicked(ttw),
                    }
                )

                disable_option_dynamic_id += 1

            disable_items.append(
                {
                    "id": 12,
                    "label": _("Until restart"),
                    "callback": lambda: self.on_disable_clicked(-1),
                }
            )

        return [
            {
                "id": 1,
                "label": info_message,
                "icon-name": "io.github.slgobinath.SafeEyes-timer",
                "enabled": breaks_found and self.active,
            },
            {
                "id": 2,
                "type": "separator",
            },
            {
                "id": 3,
                "label": _("Enable Safe Eyes"),
                "enabled": breaks_found and not self.active,
                "callback": self.on_enable_clicked,
                "hidden": not self.allow_disabling,
            },
            {
                "id": 4,
                "label": _("Disable Safe Eyes"),
                "enabled": breaks_found and self.active and not self.menu_locked,
                "children-display": "submenu",
                "children": disable_items,
                "hidden": not self.allow_disabling,
            },
            {
                "id": 5,
                "label": _("Take a break now"),
                "enabled": breaks_found and self.active and not self.menu_locked,
                "children-display": "submenu",
                "children": [
                    {
                        "id": 9,
                        "label": _("Any break"),
                        "callback": lambda: self.on_manual_break_clicked(None),
                    },
                    {
                        "id": 10,
                        "label": _("Short break"),
                        "callback": lambda: self.on_manual_break_clicked(
                            BreakType.SHORT_BREAK
                        ),
                    },
                    {
                        "id": 11,
                        "label": _("Long break"),
                        "callback": lambda: self.on_manual_break_clicked(
                            BreakType.LONG_BREAK
                        ),
                    },
                ],
            },
            {
                "id": 6,
                "label": _("Settings"),
                "enabled": not self.menu_locked,
                "callback": self.show_settings,
            },
            {
                "id": 7,
                "label": _("About"),
                "callback": self.show_about,
            },
            {
                "id": 8,
                "label": _("Quit"),
                "enabled": not self.menu_locked,
                "callback": self.quit_safe_eyes,
                "hidden": not self.allow_disabling,
            },
        ]

    def update_menu(self):
        new_menu = self._build_menu(self.get_items())
        old_menu = self._menu
        self._menu = new_menu
        self._tray.setContextMenu(new_menu)
        if old_menu is not None:
            old_menu.deleteLater()

    def update_tooltip(self):
        next_break = self.get_next_break_time()

        if next_break is not None and self.plugin_config.get(
            "show_time_in_tray", False
        ):
            (next_time, next_long_time, _next_is_long) = next_break

            if next_long_time and self.plugin_config.get(
                "show_long_time_in_tray", False
            ):
                description = next_long_time
            else:
                description = next_time
            tooltip = "Safe Eyes - %s" % description
        else:
            tooltip = "Safe Eyes"

        self._tray.setToolTip(tooltip)

    def quit_safe_eyes(self):
        """Handle Quit menu action.

        This action terminates the application.
        """
        self.active = True
        self.__clear_resume_timer()

        self.quit()

    def show_settings(self) -> None:
        """Handle Settings menu action.

        This action shows the Settings dialog.
        """
        self.on_show_settings()

    def show_about(self) -> None:
        """Handle About menu action.

        This action shows the About dialog.
        """
        self.on_show_about()

    def next_break_time(self, dateTime):
        """Update the next break time to be displayed in the menu and
        optionally in the tray icon.
        """
        logging.info("Update next break information")
        self.date_time = dateTime
        self.update_menu()
        self.update_tooltip()

    def get_next_break_time(self):
        if not (self.has_breaks() and self.active and self.date_time):
            return None

        formatted_time = utility.format_time(self.get_break_time())
        long_time = self.get_break_time(BreakType.LONG_BREAK)

        if long_time:
            long_time = utility.format_time(long_time)
            if long_time == formatted_time:
                return (long_time, long_time, True)
            else:
                return (formatted_time, long_time, False)

        return (formatted_time, None, False)

    def on_manual_break_clicked(self, break_type):
        """Trigger a break manually."""
        self.take_break(break_type)

    def on_secondary_activate(self) -> None:
        """Handle a middle-click on the tray icon."""
        if not self.active or self.menu_locked:
            return

        if not self.has_breaks(BreakType.SHORT_BREAK):
            return

        self.on_manual_break_clicked(BreakType.SHORT_BREAK)

    def on_enable_clicked(self):
        """Handle 'Enable Safe Eyes' menu action.

        This action enables the application if it is currently disabled.
        """
        if not self.active:
            self.enable_ui()
            self.enable_safeeyes()
            self.__clear_resume_timer()

    def on_disable_clicked(self, time_to_wait):
        """Handle the menu actions of all the sub menus of 'Disable Safe Eyes'.

        This action disables the application if it is currently active.
        """
        if self.active:
            self.disable_ui()

            if time_to_wait <= 0:
                info = _("Disabled until restart")
                self.disable_safeeyes(info)
                self.wakeup_time = None
            else:
                self.wakeup_time = datetime.datetime.now() + datetime.timedelta(
                    minutes=time_to_wait
                )
                info = _("Disabled until %s") % utility.format_time(self.wakeup_time)
                self.disable_safeeyes(info)
                self.__clear_resume_timer()
                self._resume_timer = mainloop.schedule_seconds(
                    time_to_wait * 60, self.__resume
                )
            self.update_menu()

    def lock_menu(self):
        """This method is called by the core to prevent user from disabling
        Safe Eyes after the notification.
        """
        if self.active:
            self.menu_locked = True
            self.update_menu()

    def unlock_menu(self):
        """This method is called by the core to activate the menu after the the
        break.
        """
        if self.active:
            self.menu_locked = False
            self.update_menu()

    def disable_ui(self):
        """Change the UI to disabled state."""
        if self.active:
            logging.info("Disable Safe Eyes")
            self.active = False

            self._set_icon(icons.TRAY_DISABLED)
            self.update_menu()

    def enable_ui(self):
        """Change the UI to enabled state."""
        if not self.active:
            logging.info("Enable Safe Eyes")
            self.active = True

            self._set_icon(icons.TRAY_ENABLED)
            self.update_menu()

    def __resume(self):
        """Reenable Safe Eyes after the given timeout."""
        self._resume_timer = None

        if not self.active:
            self.on_enable_clicked()

    def __clear_resume_timer(self):
        mainloop.cancel(self._resume_timer)
        self._resume_timer = None

    def start_animation(self) -> None:
        if self._animation_timer is not None:
            self.stop_animation()

        self._animation_icon_enabled = False

        self._animation_timer = mainloop.schedule_repeating_ms(500, self._do_animate)

    def _do_animate(self) -> None:
        if not self.active:
            mainloop.cancel(self._animation_timer)
            self._animation_timer = None
            return

        if self._animation_icon_enabled:
            self._set_icon(icons.TRAY_ENABLED)
        else:
            self._set_icon(icons.TRAY_DISABLED)

        self._animation_icon_enabled = not self._animation_icon_enabled

    def stop_animation(self) -> None:
        mainloop.cancel(self._animation_timer)
        self._animation_timer = None

        if self.active:
            self._set_icon(icons.TRAY_ENABLED)
        else:
            self._set_icon(icons.TRAY_DISABLED)


def init(ctx, safeeyes_cfg, plugin_config):
    """Initialize the tray icon."""
    global tray_icon
    global safeeyes_config
    logging.debug("Initialize Tray Icon plugin")
    safeeyes_config = safeeyes_cfg
    if not tray_icon:
        tray_icon = TrayIcon(ctx, plugin_config)
    else:
        tray_icon.initialize(plugin_config)


def update_next_break(break_obj, next_break_time):
    """Update the next break time."""
    tray_icon.next_break_time(next_break_time)


def on_pre_break(break_obj):
    """Disable the menu if strict_break is enabled."""
    if safeeyes_config.get("strict_break"):
        tray_icon.lock_menu()
    tray_icon.start_animation()


def on_start_break(break_obj):
    tray_icon.stop_animation()


def on_stop_break():
    tray_icon.unlock_menu()


def on_start():
    """Enable the tray icon."""
    tray_icon.enable_ui()


def on_stop():
    """Disable the tray icon."""
    tray_icon.disable_ui()


def disable() -> None:
    """Disable the tray icon plugin."""
    global tray_icon

    if tray_icon:
        tray_icon.unregister()
        tray_icon = None
