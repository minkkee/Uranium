# Copyright (c) 2015 Ultimaker B.V.
# Uranium is released under the terms of the AGPLv3 or higher.

import configparser
from copy import deepcopy

from UM.Signal import Signal, SignalEmitter
from UM.Settings import SettingsError
from UM.Logger import Logger
from UM.Settings.Validators.ResultCodes import ResultCodes

class Profile(SignalEmitter):
    ProfileVersion = 1

    def __init__(self, machine_manager, read_only = False):
        super().__init__()
        self._machine_manager = machine_manager
        self._changed_settings = {}
        self._name = "Unknown Profile"
        self._read_only = read_only

        self._active_instance = None
        self._machine_manager.activeMachineInstanceChanged.connect(self._onActiveInstanceChanged)
        self._onActiveInstanceChanged()

    nameChanged = Signal()

    def getName(self):
        return self._name

    def setName(self, name):
        if name != self._name:
            old_name = self._name
            self._name = name
            self.nameChanged.emit(self, old_name)

    def setReadOnly(self, read_only):
        self._read_only = read_only

    def isReadOnly(self):
        return self._read_only

    settingValueChanged = Signal()

    def setSettingValue(self, key, value):
        if not self._active_instance or not self._active_instance.getMachineDefinition().isUserSetting(key):
            Logger.log("w", "Tried to set value of non-user setting %s", key)
            return

        if key in self._changed_settings and self._changed_settings[key] == value:
            return

        self._changed_settings[key] = value
        self.settingValueChanged.emit(key)

    def getSettingValue(self, key):
        if not self._active_instance:
            return None

        setting = self._active_instance.getMachineDefinition().getSetting(key)
        if not setting:
            return None

        if key in self._changed_settings:
            return setting.parseValue(self._changed_settings[key])

        return self._active_instance.getSettingValue(key)

    def getChangedSettings(self):
        return self._changed_settings

    def getAllSettingValues(self, **kwargs):
        values = { }

        if not self._active_instance:
            return values

        settings = self._active_instance.getMachineDefinition().getAllSettings(include_machine = kwargs.get("include_machine", False))

        for setting in settings:
            key = setting.getKey()

            if key in self._changed_settings:
                values[key] = setting.parseValue(self._changed_settings[key])
                continue

            if self._active_instance.hasMachineSettingValue(key):
                values[key] = self._active_instance.getMachineSettingValue(key)

            values[key] = setting.getDefaultValue()

        return values

    def hasErrorValue(self):
        for key, value in self._changed_settings.items():
            valid = self._active_instance.getMachineDefinition().getSetting(key).validate(value)
            if valid == ResultCodes.min_value_error or valid == ResultCodes.max_value_error or valid == ResultCodes.not_valid_error:
                print("KEY ", key , " value" , value, " " , valid)
                return True

        return False

    def hasSettingValue(self, key):
        return key in self._changed_settings

    def resetSettingValue(self, key):
        if key not in self._changed_settings:
            return

        del self._changed_settings[key]
        self.settingValueChanged.emit(key)

    def loadFromFile(self, path):
        parser = configparser.ConfigParser()
        parser.read(path, "utf-8")

        if not parser.has_section("general"):
            raise SettingsError.InvalidFileError(path)

        if not parser.has_option("general", "version") or int(parser.get("general", "version")) != self.ProfileVersion:
            raise SettingsError.InvalidVersionError(path)

        self._name = parser.get("general", "name")

        if parser.has_section("settings"):
            for key, value in parser["settings"].items():
                self.setSettingValue(key, value)

    def saveToFile(self, file):
        parser = configparser.ConfigParser()

        parser.add_section("general")
        parser.set("general", "version", str(self.ProfileVersion))
        parser.set("general", "name", self._name)

        parser.add_section("settings")
        for setting_key in self._changed_settings:
            parser.set("settings", setting_key , str(self._changed_settings[setting_key]))
        
        with open(file, "wt", -1, "utf-8") as f:
            parser.write(f)

    def __deepcopy__(self, memo):
        copy = Profile(self._machine_manager, self._read_only)

        copy._changed_settings = deepcopy(self._changed_settings, memo)
        copy.setName(self._name)

        return copy

    def _onActiveInstanceChanged(self):
        self._active_instance = self._machine_manager.getActiveMachineInstance()
