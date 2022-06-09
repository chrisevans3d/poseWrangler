import os

from PySide2 import QtCore

from epic_pose_wrangler.log import LOG
from epic_pose_wrangler.model import exceptions


class SettingsManager(object):
    """
    Settings Manager for reading/writing to PoseWrangler settings ini file
    """
    QSETTINGS = None

    def __init__(self):
        # Initialize the QSettings
        QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, os.environ['LOCALAPPDATA'])
        # Store the QSettings
        self.__class__.QSETTINGS = QtCore.QSettings(
            QtCore.QSettings.IniFormat,
            QtCore.QSettings.UserScope,
            "Epic Games",
            "PoseWrangler"
        )
        self.__class__.QSETTINGS.setFallbacksEnabled(False)
        LOG.debug("Successfully initialized SettingsManager")

    @classmethod
    def get_setting(cls, name):
        """
        Get the setting with the specified name
        :param name :type str: setting name
        :return :type str or None: setting value
        """
        # If the settings haven't been initialized, raise exception
        if cls.QSETTINGS is None:
            raise exceptions.PoseWranglerSettingsError("Unable to load settings, "
                                                       "{cls} must be initialized first".format(cls=cls))
        return cls.QSETTINGS.value(name, None)

    @classmethod
    def set_setting(cls, name, value):
        """
        Add/Overwrite the setting with the specified name and value
        :param name :type str: setting name
        :param value :type any: setting value
        """
        cls.QSETTINGS.setValue(name, value)
