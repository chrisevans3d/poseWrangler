#  Copyright Epic Games, Inc. All Rights Reserved.
import os

from epic_pose_wrangler.log import LOG
from epic_pose_wrangler.model.plugin_manager import PluginManager


class PoseWrangler(object):
    """
    Main entrypoint for interacting with PoseWrangler. Will handle loading the correct version of the tool based on the
    available version of the plugin
    """

    def __init__(self, view=True):
        # Get the current version of the tool
        self._api = PluginManager.get_pose_wrangler(view=view, parent=self)

    @property
    def api(self):
        return self._api

    def upgrade(self, file_path=None, delete_file=False):
        """
        Restart pose_wrangler with the specified serialized solver data file
        :param file_path :type str: path to serialized json data
        :param delete_file :type bool: should the file be deleted once the upgrade has completed?
        """
        LOG.info("Rebooting PoseWrangler")
        self._api = PluginManager.get_pose_wrangler(view=self._api.view, parent=self, file_path=file_path)
        if delete_file:
            os.remove(file_path)
