#!/usr/bin/env python
# Safe Eyes is a utility to remind you to take break frequently
# to protect your eyes from eye strain.

# Copyright (C) 2017  Gobinath
# Copyright (C) 2026  Mel Dafert <m@dafert.at>

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
"""This module contains the Config class and related logic around handling the
configuration file.
"""

import copy
import logging
from packaging.version import parse
import os
import shutil
import typing

from safeeyes import utility


class Config:
    """The configuration of Safe Eyes."""

    __user_config: dict[str, typing.Any]
    __system_config: dict[str, typing.Any]

    @classmethod
    def load(cls) -> "Config":
        # Read the config files
        user_config = utility.load_json(utility.CONFIG_FILE_PATH)
        user_config_disk = copy.deepcopy(user_config)
        system_config = utility.load_json(utility.SYSTEM_CONFIG_FILE_PATH)
        # If there any breaking changes in long_breaks, short_breaks or any other keys,
        # use the force_upgrade_keys list
        force_upgrade_keys: list[str] = []
        # force_upgrade_keys = ['long_breaks', 'short_breaks']

        if user_config is None:
            cls._initialize_config()
            user_config = copy.deepcopy(system_config)
            cfg = cls(user_config, system_config)
            cfg.save()

            # This gets called when the configuration file is not present, which
            # happens just after installation or manual deletion of
            # .config/safeeyes/safeeyes.json file. In this case, we want to force the
            # creation of a startup entry
            cls._create_startup_entry(force=True)
            return cfg
        else:
            system_config_version = system_config["meta"]["config_version"]
            meta_obj = user_config.get("meta", None)
            if meta_obj is None:
                # Corrupted user config
                user_config = copy.deepcopy(system_config)
            else:
                user_config_version = str(meta_obj.get("config_version", "0.0.0"))
                if parse(user_config_version) != parse(system_config_version):
                    # Update the user config
                    new_user_config = copy.deepcopy(system_config)
                    cls.__merge_dictionary(
                        user_config, new_user_config, force_upgrade_keys
                    )
                    user_config = new_user_config

        utility.merge_plugins(user_config)

        cfg = cls(user_config, system_config)

        if user_config != user_config_disk:
            cfg.save()

        # if _create_startup_entry finds a broken autostart symlink, it will repair
        # it
        cls._create_startup_entry(force=False)

        return cfg

    def __init__(
        self,
        user_config: dict[str, typing.Any],
        system_config: dict[str, typing.Any],
    ):
        self.__user_config = user_config
        self.__system_config = system_config

    @classmethod
    def __merge_dictionary(cls, old_dict, new_dict, force_upgrade_keys: list[str]):
        """Merge the dictionaries."""
        for key in new_dict:
            if key == "meta" or key in force_upgrade_keys:
                continue
            if key in old_dict:
                new_value = new_dict[key]
                old_value = old_dict[key]
                if type(new_value) is type(old_value):
                    # Both properties have same type
                    if isinstance(new_value, dict):
                        cls.__merge_dictionary(old_value, new_value, force_upgrade_keys)
                    else:
                        new_dict[key] = old_value

    def clone(self) -> "Config":
        config = Config(
            user_config=copy.deepcopy(self.__user_config),
            system_config=self.__system_config,
        )
        return config

    def save(self) -> None:
        """Save the configuration to file."""
        logging.debug("Writing config to disk")
        utility.write_json(utility.CONFIG_FILE_PATH, self.__user_config)

    def get(self, key, default_value=None):
        """Get the value."""
        value = self.__user_config.get(key, default_value)
        if value is None:
            value = self.__system_config.get(key, None)
        return value

    def set(self, key, value):
        """Set the value."""
        self.__user_config[key] = value

    def __eq__(self, config):
        return self.__user_config == config.__user_config

    def __ne__(self, config):
        return self.__user_config != config.__user_config

    @classmethod
    def reset_config(cls) -> "Config":
        cls._initialize_config()

        # This calls _create_startup_entry()
        return Config.load()

    @classmethod
    def _initialize_config(cls) -> None:
        """Create the config file in XDG_CONFIG_HOME(or
        ~/.config)/safeeyes directory.
        """
        logging.info("Copy the config files to XDG_CONFIG_HOME(or ~/.config)/safeeyes")

        # Remove the ~/.config/safeeyes/safeeyes.json file
        utility.delete(utility.CONFIG_FILE_PATH)

        if not os.path.isdir(utility.CONFIG_DIRECTORY):
            utility.mkdir(utility.CONFIG_DIRECTORY)

        # Copy the safeeyes.json
        shutil.copy2(utility.SYSTEM_CONFIG_FILE_PATH, utility.CONFIG_FILE_PATH)

        # Add write permission (e.g. if original file was stored in /nix/store)
        os.chmod(utility.CONFIG_FILE_PATH, 0o600)

    @classmethod
    def _create_startup_entry(cls, force: bool = False) -> None:
        """Create start up entry (platform-specific)."""
        from safeeyes.platform_api import autostart

        autostart.create_startup_entry(force=force)
