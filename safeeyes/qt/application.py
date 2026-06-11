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
"""Qt application controller for Safe Eyes.

Owns the runtime: Config + Context + plugins + the Qt break screen + the
scheduler running on the Qt event loop. Settings/about/required-plugin dialogs
(M4) and OS integration such as suspend handling (M5) are still stubbed.
"""

import atexit
import logging
import os
import typing

from safeeyes import mainloop, utility, version
from safeeyes.configuration import Config
from safeeyes.context import API, Context
from safeeyes.core import SafeEyesCore
from safeeyes.model import BreakType, RequiredPluginException, State
from safeeyes.platform_api import suspend
from safeeyes.plugin_manager import PluginManager
from safeeyes.qt import qss, system_tray
from safeeyes.qt.about_dialog import AboutDialog
from safeeyes.qt.break_screen import BreakScreen
from safeeyes.qt.required_plugin_dialog import RequiredPluginDialog
from safeeyes.qt.settings_dialog import SettingsDialog
from safeeyes.translations import translate as _

SAFE_EYES_VERSION = version.get_version()

SYSTEM_QSS_PATH = os.path.join(
    utility.BIN_DIRECTORY, "config", "style", "safeeyes_style.qss"
)
USER_QSS_PATH = os.path.join(
    utility.STYLE_SHEET_DIRECTORY, "safeeyes_custom_style.qss"
)

# Remote-command names exchanged over the single-instance socket. These mirror
# the CLI flags handled in __main__.
CMD_STATUS = "status"
CMD_QUIT = "quit"
CMD_ENABLE = "enable"
CMD_DISABLE = "disable"
CMD_ABOUT = "about"
CMD_SETTINGS = "settings"
CMD_TAKE_BREAK = "take-break"
CMD_SHORT_BREAK = "short-break"
CMD_LONG_BREAK = "long-break"
CMD_PING = "ping"


class SafeEyesApp:
    """Owns the Safe Eyes runtime on top of a QApplication."""

    required_plugin_dialog_active = False
    retry_errored_plugins_count = 0

    def __init__(self, qapp, system_locale) -> None:
        self.qapp = qapp
        self.system_locale = system_locale
        self.active = False
        self._status = ""
        self._settings_dialog: typing.Optional[SettingsDialog] = None
        self._about_dialog: typing.Optional[AboutDialog] = None
        self._required_plugin_dialog: typing.Optional[RequiredPluginDialog] = None

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        mainloop.init()
        logging.info("Starting up Application")

        self.config = Config.load()

        if self.config.get("persist_state"):
            session = utility.open_session()
        else:
            session = {"plugin": {}}

        self.context = Context(
            api=API(self),
            locale=self.system_locale,
            version=SAFE_EYES_VERSION,
            session=session,
        )

        qss.apply_styles(self.qapp, SYSTEM_QSS_PATH, USER_QSS_PATH)

        self.break_screen = BreakScreen(
            self.context, self.on_skipped, self.on_postponed
        )
        self.break_screen.initialize(self.config)
        self.plugins_manager = PluginManager()
        self.core = SafeEyesCore(self.context)
        self.core.on_pre_break += self.plugins_manager.pre_break
        self.core.on_start_break += self.on_start_break
        self.core.start_break += self.start_break
        self.core.on_count_down += self.countdown
        self.core.on_stop_break += self.stop_break
        self.core.on_update_next_break += self.update_next_break
        self.core.initialize(self.config)

        try:
            self.plugins_manager.init(self.context, self.config)
        except RequiredPluginException as e:
            self.show_required_plugin_dialog(e)

        atexit.register(self.persist_session)

        if (
            not self.plugins_manager.needs_retry()
            and not self.required_plugin_dialog_active
            and self.core.has_breaks()
        ):
            self.active = True
            self.context.state = State.START
            self.plugins_manager.start()
            self.core.start()
            suspend.register(self.handle_suspend_change)

        if self.plugins_manager.needs_retry():
            mainloop.schedule_seconds(1, self._retry_errored_plugins)

    def handle_suspend_change(self, sleeping: bool) -> None:
        """Pause the core on system suspend, resume it on wake."""
        if sleeping:
            if self.active:
                logging.info("Stop Safe Eyes due to system suspend")
                self.plugins_manager.stop()
                self.core.stop(True)
        else:
            if self.active and self.core.has_breaks():
                logging.info("Resume Safe Eyes after system wakeup")
                self.plugins_manager.start()
                self.core.start()

    def _retry_errored_plugins(self) -> None:
        if not self.plugins_manager.needs_retry():
            return

        logging.info("Retry loading errored plugin")
        self.plugins_manager.retry_errored_plugins()

        error = self.plugins_manager.get_retryable_error()

        if error is None:
            self.restart(self.config, set_active=True)
            return

        if self.retry_errored_plugins_count >= 3:
            self.show_required_plugin_dialog(error)
            return

        timeout = pow(2, self.retry_errored_plugins_count)
        self.retry_errored_plugins_count += 1

        mainloop.schedule_seconds(timeout, self._retry_errored_plugins)

    def restart(self, config, set_active=False) -> None:
        logging.info("Initialize SafeEyesCore with modified settings")

        self.config = config
        self.core.initialize(config)
        self.break_screen.initialize(config)

        try:
            self.plugins_manager.reload(self.context, self.config)
        except RequiredPluginException as e:
            self.show_required_plugin_dialog(e)
            return

        if set_active:
            self.active = True

        if self.active and self.core.has_breaks():
            self.core.start()
            self.plugins_manager.start()

    # -- core event hooks --------------------------------------------------

    def on_start_break(self, break_obj) -> bool:
        """Pass the break information to plugins."""
        if not self.plugins_manager.start_break(break_obj):
            return False
        return True

    def start_break(self, break_obj) -> None:
        """Pass the break information (incl. plugin widgets) to the screen."""
        widget = self.plugins_manager.get_break_screen_widgets(break_obj)
        actions = self.plugins_manager.get_break_screen_tray_actions(break_obj)
        self.break_screen.show_message(break_obj, widget, actions)

    def countdown(self, countdown, seconds) -> bool:
        self.break_screen.show_count_down(countdown, seconds)
        self.plugins_manager.countdown(countdown, seconds)
        return True

    def stop_break(self) -> bool:
        self.break_screen.close()
        self.plugins_manager.stop_break()
        return True

    def update_next_break(self, break_obj, break_time) -> None:
        self.plugins_manager.update_next_break(break_obj, break_time)
        self._status = _("Next break at %s") % (utility.format_time(break_time))
        if self.config.get("persist_state"):
            utility.write_json(utility.SESSION_FILE_PATH, self.context["session"])

    # -- break screen callbacks -------------------------------------------

    def on_skipped(self) -> None:
        logging.info("User skipped the break")
        self.core.skip()
        self.plugins_manager.stop_break()

    def on_postponed(self) -> None:
        logging.info("User postponed the break")
        self.core.postpone()
        self.plugins_manager.stop_break()

    # -- actions (also used via context.API and remote commands) -----------

    def take_break(self, break_type: typing.Optional[BreakType] = None) -> None:
        self.core.take_break(break_type)

    def enable_safeeyes(self, scheduled_next_break_time=-1) -> None:
        if (
            not self.required_plugin_dialog_active
            and not self.active
            and self.core.has_breaks()
        ):
            self.active = True
            self.core.start(scheduled_next_break_time)
            self.plugins_manager.start()

    def disable_safeeyes(self, status=None, is_resting=False) -> None:
        if self.active:
            self.active = False
            self.plugins_manager.stop()
            self.core.stop(is_resting)
            self._status = status if status is not None else _("Disabled until restart")

    def status(self) -> str:
        return self._status

    def show_settings(self, activation_token: typing.Optional[str] = None) -> None:
        """Show the Settings dialog (reusing an open one)."""
        if self._settings_dialog is None:
            logging.info("Show Settings dialog")
            self._settings_dialog = SettingsDialog(
                self.config.clone(), self.save_settings
            )
        self._settings_dialog.show()

    def show_about(self, activation_token: typing.Optional[str] = None) -> None:
        """Show the About dialog."""
        logging.info("Show About dialog")
        self._about_dialog = AboutDialog(SAFE_EYES_VERSION)
        self._about_dialog.show()

    def show_required_plugin_dialog(self, error: RequiredPluginException) -> None:
        """Show the required-plugin error dialog (quit or disable the plugin)."""
        self.required_plugin_dialog_active = True
        logging.info("Show RequiredPlugin dialog")
        plugin_id = error.get_plugin_id()
        self._required_plugin_dialog = RequiredPluginDialog(
            error.get_plugin_name(),
            error.get_message(),
            self.quit,
            lambda: self.disable_plugin(plugin_id),
        )
        self._required_plugin_dialog.show()

    def disable_plugin(self, plugin_id: str) -> None:
        """Temporarily disable a plugin and restart the core."""
        config = self.config.clone()
        for plugin in config.get("plugins"):
            if plugin["id"] == plugin_id:
                plugin["enabled"] = False
        self.required_plugin_dialog_active = False
        self.restart(config, set_active=True)

    def save_settings(self, config) -> None:
        """Persist settings from the dialog and restart the core if changed."""
        self._settings_dialog = None

        if self.config == config:
            return

        logging.info("Saving settings to safeeyes.json")
        if self.active:
            self.plugins_manager.stop()
            self.core.stop()

        config.save()
        self.persist_session()
        self.restart(config)

    def quit(self) -> None:
        logging.info("Quit Safe Eyes")
        if hasattr(self, "break_screen"):
            self.break_screen.close()
        if hasattr(self, "context"):
            self.context.state = State.QUIT
        if hasattr(self, "plugins_manager"):
            self.plugins_manager.stop()
        if hasattr(self, "core"):
            self.core.stop()
        if hasattr(self, "plugins_manager"):
            self.plugins_manager.exit()
        self.persist_session()
        system_tray.destroy()
        self.qapp.quit()

    # -- remote command dispatch (single-instance socket) ------------------

    def handle_command(self, command: str) -> typing.Optional[str]:
        """Handle a command forwarded by a secondary instance.

        Runs on the GUI thread (the local server lives on the main loop).
        Returns reply text for commands that produce output, else None.
        """
        if command == CMD_PING:
            # Liveness probe sent by a plain launch to detect a running instance.
            return None
        if command == CMD_STATUS:
            return self.status()
        if command == CMD_QUIT:
            self.quit()
        elif command == CMD_ENABLE:
            self.enable_safeeyes()
        elif command == CMD_DISABLE:
            self.disable_safeeyes()
        elif command == CMD_ABOUT:
            self.show_about()
        elif command == CMD_SETTINGS:
            self.show_settings()
        elif command == CMD_TAKE_BREAK:
            self.take_break()
        elif command == CMD_SHORT_BREAK:
            self.take_break(BreakType.SHORT_BREAK)
        elif command == CMD_LONG_BREAK:
            self.take_break(BreakType.LONG_BREAK)
        else:
            logging.warning("Unknown remote command: %s", command)
        return None

    def persist_session(self) -> None:
        """Save the session object to the session file."""
        if not hasattr(self, "config"):
            return
        if self.config.get("persist_state"):
            utility.write_json(utility.SESSION_FILE_PATH, self.context["session"])
        else:
            utility.delete(utility.SESSION_FILE_PATH)

    # context.API reaches the core through this attribute
    @property
    def safe_eyes_core(self) -> SafeEyesCore:
        return self.core
