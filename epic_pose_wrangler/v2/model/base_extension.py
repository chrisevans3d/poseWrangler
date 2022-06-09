#  Copyright Epic Games, Inc. All Rights Reserved.
from epic_pose_wrangler.model import exceptions


class PoseWranglerExtension(object):
    """
    Base class for extending pose wrangler with custom utilities that can be dynamically added to the UI
    """
    __category__ = ""

    def __init__(self, display_view=False, api=None):
        super(PoseWranglerExtension, self).__init__()
        self._display_view = display_view
        self._view = None
        self._api = api

    @property
    def api(self):
        """
        Get the current API

        :return: Reference to the main API interface
        :rtype: pose_wrangler.v2.main.UERBFAPI
        """

        return self._api

    @property
    def view(self):
        """
        Get the current view widget. This should be overridden by custom extensions if you wish to embed a UI for this
        extension into the main PoseWrangler UI.

        :return: Reference to the PySide widget associated with this extension
        :rtype: QWidget or None
        """
        return self._view

    def execute(self, context=None, **kwargs):
        """
        Generic entrypoint for executing the extension.

        :param: context: pose wrangler context containing current solver and all solvers
        :type context: pose_wrangler.v2.model.context.PoseWranglerContext or None
        """
        raise exceptions.PoseWranglerFunctionalityNotImplemented(
            "'execute' function has not been implemented for {class_name}".format(
                class_name=self.__class__.__name__
            )
        )

    def on_context_changed(self, new_context):
        """
        Context event called when the current solver is set via the API

        :param new_context: pose wrangler context containing current solver and all solvers
        :type new_context: pose_wrangler.v2.model.context.PoseWranglerContext or None
        """
        pass
