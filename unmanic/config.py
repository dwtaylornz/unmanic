#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    unmanic.config.py

    Written by:               Josh.5 <jsunnex@gmail.com>
    Date:                     06 Dec 2018, (7:21 AM)

    Copyright:
           Copyright (C) Josh Sunnex - All Rights Reserved

           Permission is hereby granted, free of charge, to any person obtaining a copy
           of this software and associated documentation files (the "Software"), to deal
           in the Software without restriction, including without limitation the rights
           to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
           copies of the Software, and to permit persons to whom the Software is
           furnished to do so, subject to the following conditions:

           The above copyright notice and this permission notice shall be included in all
           copies or substantial portions of the Software.

           THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
           EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
           MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
           IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
           DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
           OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
           OR OTHER DEALINGS IN THE SOFTWARE.

"""

import os
from unmanic import metadata
from unmanic.libs import unmodels, unlogger, unffmpeg
from unmanic.libs import common, history

import json

try:
    from json.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError

HOME_DIR = os.path.expanduser("~")
APP_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_DB_CONFIG = {
    # Database config
    "DATABASE": {
        "TYPE":           "SQLITE",
        "FILE":           os.path.join(HOME_DIR, '.unmanic', 'config', 'unmanic.db'),
        "MIGRATIONS_DIR": os.path.join(APP_DIR, 'migrations'),
    }
}


class CONFIG(object):
    app_version = ''

    def __init__(self):
        # Non config items (objects)
        self.name = "Config"
        self.settings = None

        # Set default db config
        self.DATABASE = None
        self.apply_default_db_settings()
        # Run DB migrations
        self.run_db_migrations()
        # Init DB connection and read settings
        self.import_settings_from_db()
        # Import env variables
        self.import_settings_from_env()
        # Finally, read config from file and override all above settings.
        self.import_settings_from_file()
        # Apply settings to the unmanic logger
        self.setup_unmanic_logger()
        # Set the supported codecs (for destination)
        self.SUPPORTED_CODECS = unffmpeg.Info().get_all_supported_codecs()
        # Set the supported containers (for destination)
        self.SUPPORTED_CONTAINERS = unffmpeg.containers.get_all_containers()
        # TODO: Remove temporary beta data migration
        history_logging = history.History(self)
        history_logging.migrate_old_beta_data()

    def _log(self, message, message2='', level="info"):
        """
        Generic logging method. Can be implemented on any unmanic class

        :param message:
        :param message2:
        :param level:
        :return:
        """
        # TODO: Format all classes with this to fetch a logger
        unmanic_logging = unlogger.UnmanicLogger.__call__()
        logger = unmanic_logging.get_logger(self.name)
        if logger:
            message = common.format_message(message, message2)
            getattr(logger, level)(message)
        else:
            print("Unmanic.{} - ERROR!!! Failed to find logger".format(self.name))

    def get_config_as_dict(self):
        """
        Return a dictionary of configuration fields and their current values

        :return:
        """
        config_dict = {}
        # Create a copy of this class's dict
        if self.settings:
            config_dict = self.settings.get_current_field_values_dict()
        else:
            # TODO: Set this to debug logging
            self._log("Something went wrong. The settings variable is not set.", level="info")
        # Return dictionary of config items
        return config_dict

    def get_config_keys(self):
        """
        Return a list of configuration fields

        :return:
        """
        keys = self.get_config_as_dict().keys()
        keys = [item.upper() for item in keys]
        return keys

    def setup_unmanic_logger(self):
        """
        Pass configuration to the global logger

        :return:
        """
        unmanic_logging = unlogger.UnmanicLogger.__call__()
        unmanic_logging.setup_logger(self)

    def apply_default_db_settings(self):
        """
        Read default DB settings.
        These may be overwritten by what is read from the settings.json file

        :return:
        """

        for setting in DEFAULT_DB_CONFIG:
            setattr(self, setting, DEFAULT_DB_CONFIG[setting])

    def run_db_migrations(self):
        """
        Run application DB migrations

        :return:
        """
        migrations = unmodels.Migrations(self.DATABASE)
        migrations.run_all()

    def import_settings_from_db(self):
        """
        Read configuration from DB.
        If configuration does not yet exist, create it first.

        Configuration is applied to this class with uppercase field names
        for the sake of simplifying reading throughout the rest of the application.

        :return:
        """
        unmodels.Database.select_database(self.DATABASE)
        # Fetch current settings (create it if nothing yet exists)
        db_settings = unmodels.Settings()
        try:
            # Fetch a single row (get() will raise DoesNotExist exception if no results are found)
            self.settings = db_settings.select().limit(1).get()
        except:
            # Create settings (defaults will be applied)
            self.settings = db_settings.create()
        # Check if key is a valid setting
        current_settings = self.settings.get_current_field_values_dict()
        for setting in current_settings:
            # Import settings
            self.set_config_item(setting.upper(), current_settings[setting], save_settings=False)

    def import_settings_from_env(self):
        """
        Read configuration from environment variables.
        This is useful for running in a docker container or for unit testing.

        :return:
        """
        for setting in self.get_config_keys():
            if setting in os.environ:
                self.set_config_item(setting, os.environ.get(setting), save_settings=False)

    def import_settings_from_file(self):
        """
        Read configuration from the settings JSON file.

        :return:
        """
        # TODO: If DATABASE settings have changed, then rerun
        #       self.run_db_migrations()
        #       self.import_settings_from_db()
        if not os.path.exists(self.CONFIG_PATH):
            os.makedirs(self.CONFIG_PATH)
        settings_file = os.path.join(self.CONFIG_PATH, 'settings.json')
        if os.path.exists(settings_file):
            data = {}
            try:
                with open(settings_file) as infile:
                    data = json.load(infile)
            except Exception as e:
                self._log("Exception in reading saved settings from file:", message2=str(e), level="exception")
            current_config = self.get_config_keys()
            for item in current_config:
                if item in data:
                    self.set_config_item(item, data[item], save_settings=False)

    def write_settings_to_file(self):
        """
        Dump current settings to the settings JSON file.

        :return:
        """
        if not os.path.exists(self.CONFIG_PATH):
            os.makedirs(self.CONFIG_PATH)
        settings_file = os.path.join(self.CONFIG_PATH, 'settings.json')
        data = self.get_config_as_dict()
        data = {k.upper(): v for k, v in data.items()}
        # Append database settings
        data['DATABASE'] = self.DATABASE
        result = common.json_dump_to_file(data, settings_file)
        if not result['success']:
            for message in result['errors']:
                self._log("Exception in writing settings to file:", message2=str(message), level="exception")

    def set_config_item(self, key, value, save_settings=True):
        """
        Assigns a value to a given configuration field.
        This is applied to both this class and the Settings Model.

        If 'save_settings' is set to False, then settings are only
        assigned and not saved to either file or database.

        :param key:
        :param value:
        :param save_settings:
        :return:
        """
        if key == 'DATABASE':
            # Only save database settings to file
            # Database settings are not stored in the database O_o
            self.__dict__[key] = value
            if save_settings:
                self.write_settings_to_file()
        else:
            # Get lowercase value of key
            field_id = key.lower()
            # Check if key is a valid setting
            if field_id not in self.settings.get_current_field_values_dict().keys():
                self._log("Attempting to save unknown key", message2=str(key), level="warning")
                # Do not proceed if this is any key other than the database
                return
            # Parse field value by it's type for this setting (bool, string, etc.)
            parsed_field_value = self.settings.parse_field_value_by_type(field_id, value)
            # Assign value to setting field
            setattr(self.settings, field_id, parsed_field_value)
            # Assign field type converted value to class variable
            setattr(self, key, parsed_field_value)
            # Save settings (if requested)
            if save_settings:
                self.write_settings_to_file()
                self.settings.save()

    def allowed_search_extensions(self):
        """
        Return a tuple of the configured extensions to search for.

        :return:
        """
        if isinstance(self.SEARCH_EXTENSIONS, str):
            # Split the comma separated sting into a list
            value = self.SEARCH_EXTENSIONS.split(",")
            # Strip all whitespace (including within the item as extensions dont have any whitespace)
            value = [item.replace(' ', '') for item in value]
            # Remove empty values from the list
            value = [item for item in value if item]
            return value
        return list(self.SEARCH_EXTENSIONS)

    def file_ends_in_allowed_search_extensions(self, file_name):
        # Get the file extension
        file_extension = os.path.splitext(file_name)[-1][1:]
        # Ensure the file's extension is lowercase
        file_extension = file_extension.lower()
        self._log("Check file_extension", file_extension, level="debug")
        # Get the list of configured extensions to search for
        allowed_search_extensions = self.allowed_search_extensions()
        self._log("Check allowed_search_extensions", allowed_search_extensions, level="debug")
        # Check if it ends with one of the allowed search extensions
        if file_extension in allowed_search_extensions:
            return True
        return False

    def get_supported_audio_codecs(self):
        """
        Return a list of audio codecs supported by unmanic

        :return:
        """
        if 'audio' not in self.SUPPORTED_CODECS:
            return {}
        return self.SUPPORTED_CODECS['audio']

    def get_supported_video_codecs(self):
        """
        Return a list of video codecs supported by unmanic

        :return:
        """
        if 'video' not in self.SUPPORTED_CODECS:
            return {}
        return self.SUPPORTED_CODECS['video']

    def get_configured_audio_encoder(self):
        if 'audio' not in self.SUPPORTED_CODECS:
            return ''
        return self.AUDIO_STREAM_ENCODER

    def get_configured_video_encoder(self):
        if 'video' not in self.SUPPORTED_CODECS:
            return ''
        return self.SUPPORTED_CODECS['video'][self.VIDEO_CODEC]['encoders'][0]

    def read_version(self):
        """
        Return the application's version number as a string

        :return:
        """
        if not self.app_version:
            self.app_version = metadata.read_version_string('long')
        return self.app_version
