#  Copyright Epic Games, Inc. All Rights Reserved.
"""
API v2 Specific exceptions
"""
from epic_pose_wrangler.model import exceptions


class MessageConnectionError(exceptions.PoseWranglerException):
    """
    Raised when message connections fail.
    """


class InvalidSolverError(exceptions.PoseWranglerException):
    """
    Raised when the incorrect solver type is specified
    """


class InvalidNodeType(exceptions.PoseWranglerException, TypeError):
    """
    Raised when the incorrect node type is specified
    """


class PoseWranglerAttributeError(exceptions.PoseWranglerException, AttributeError):
    """
    Raised when there is an issue getting/setting an attribute
    """


class PoseBlenderPoseError(exceptions.PoseWranglerException):
    """
    Generic error for issues with poses
    """


class InvalidPose(exceptions.PoseWranglerException):
    """
    Generic error for incorrect poses
    """


class InvalidPoseIndex(exceptions.PoseWranglerException):
    """
    Raised when issues arise surrounding the poses index
    """


class BlendshapeError(exceptions.PoseWranglerException):
    """
    Generic error for blendshape issues
    """
