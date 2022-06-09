#  Copyright Epic Games, Inc. All Rights Reserved.
from epic_pose_wrangler.log import LOG


class PoseWranglerException(Exception):
    """
    Base Exception for PoseWrangler related errors
    """

    def __init__(self, message):
        super(PoseWranglerException, self).__init__(message)
        # Log the message as an error
        LOG.error(message)


class InvalidPoseWranglerPlugin(PoseWranglerException, RuntimeError):
    """
    Exception raised when no valid plugins could be loaded
    """


class PoseWranglerSettingsError(PoseWranglerException):
    """
    Raised when a setting is invalid
    """


class InvalidMirrorMapping(PoseWranglerSettingsError):
    """
    Raised when the mirror mapping is incorrect
    """


class PoseWranglerIOError(PoseWranglerException):
    """
    Raised when issues with serialization/deserialization arise
    """


class PoseWranglerFunctionalityNotImplemented(PoseWranglerException):
    """
    Raised when pose wrangler functionality hasn't been implemented yet
    """
