#  Copyright Epic Games, Inc. All Rights Reserved.
from epic_pose_wrangler.model.api import RBFAPI

from epic_pose_wrangler.v1 import poseWranglerUI, poseWrangler


class UE4RBFAPI(RBFAPI):
    VERSION = "1.0.0"

    def __init__(self, view=False, parent=None, file_path=None):
        super(UE4RBFAPI, self).__init__(view=view, parent=parent)
        if view:
            self._view = poseWranglerUI.PoseWrangler()
            self._view.event_upgrade_dispatch.upgrade.connect(self._upgrade)
            self._view.show(dockable=True)

    @property
    def view(self):
        return self._view

    @property
    def api_module(self):
        return poseWrangler

    def _upgrade(self, file_path):
        """
        Upgrade the scene to the new version
        :param file_path :type str: file path to the exported scene data
        """
        self._parent.upgrade(file_path, delete_file=True)
