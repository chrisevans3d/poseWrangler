#  Copyright Epic Games, Inc. All Rights Reserved.
from collections import OrderedDict

from maya import cmds

from epic_pose_wrangler.log import LOG
from epic_pose_wrangler.model import exceptions


class PluginManager:
    """
    Class for loading latest available plugin and managing pose_wrangler versions
    """
    # The name of the recommended solver
    RECOMMENDED_SOLVER = "UERBFSolverNode"
    # Empty list to keep track of the loaded solver nodes
    LOADED_NODES = []
    # Generate an ordered manifest of known plugin name variants with the newest plugins
    __PLUGIN_VERSIONS = OrderedDict(
        {
            "MayaUERBFPlugin_{}".format(cmds.about(version=True)): "UERBFSolverNode",
            "MayaUERBFPlugin{}".format(cmds.about(version=True)): "UERBFSolverNode",
            "MayaUERBFPlugin": "UERBFSolverNode",
            "MayaUE4RBFPlugin_{}".format(cmds.about(version=True)): "UE4RBFSolverNode",
            "MayaUE4RBFPlugin{}".format(cmds.about(version=True)): "UE4RBFSolverNode",
            "MayaUE4RBFPlugin": "UE4RBFSolverNode"}
    )

    @staticmethod
    def load_plugin():
        """
        Load any valid RBF plugins
        :return :type list: node names loaded
        """

        PluginManager.LOADED_NODES = []
        # Iterate through all of the valid plugin versions and attempt to load
        for plugin_name, solver_name in PluginManager.__PLUGIN_VERSIONS.items():
            # If the plugin is already loaded, add the solver name to the list of loaded nodes
            if cmds.pluginInfo(plugin_name, q=True, loaded=True) and solver_name not in PluginManager.LOADED_NODES:
                PluginManager.LOADED_NODES.append(solver_name)
            else:
                try:
                    # Attempt to load the plugin
                    cmds.loadPlugin(plugin_name)
                    # If the solver name is not already in the list, add it
                    if solver_name not in PluginManager.LOADED_NODES:
                        PluginManager.LOADED_NODES.append(solver_name)
                # Ignore errors
                except RuntimeError as e:
                    pass
        # If we have no loaded nodes no plugin loaded correctly
        if not PluginManager.LOADED_NODES:
            raise exceptions.InvalidPoseWranglerPlugin("Unable to load valid RBF plugin version.")

        return PluginManager.LOADED_NODES

    @staticmethod
    def is_scene_using_recommended_solver():
        """
        Scan the current scene to find which version of the solver is being used
        :return :type bool: is the recommended solver being used for all RBF nodes
        """
        solvers = []
        # Get a list of the solver names
        for solver_node_name in list(PluginManager.__PLUGIN_VERSIONS.values()):
            if solver_node_name not in solvers:
                solvers.append(solver_node_name)
        # Iterate through the solver names
        for solver_node_name in solvers:
            # Check if any solvers exist in the scene of the specified type and check if the solver name is the
            # recommended name. If we have old solvers in the scene, we aren't using the latest version.
            if cmds.ls(type=solver_node_name) and solver_node_name != PluginManager.RECOMMENDED_SOLVER:
                return False
        return True

    @staticmethod
    def get_pose_wrangler(view=True, parent=None, file_path=None):
        """
        Get the correct version of the pose wrangler tool depending on the available plugins and nodes in the scene
        :param view :type bool: Should we be displaying a UI to the user?
        :param parent :type main.PoseWrangler: reference to the main entry point for the tool, used for
        restarting/upgrading the tool
        :param file_path :type str: (optional) path to a json file containing serialized solver data
        :return :type object: reference to the currently loaded version of pose wrangler
        """
        # Load the RBF plugin
        loaded_nodes = PluginManager.load_plugin()
        # If the recommended solver is not loaded, fall back to the original pose wrangler implementation
        if PluginManager.RECOMMENDED_SOLVER not in loaded_nodes:
            LOG.warning("You are currently using an outdated plugin. Certain functionality may be limited.")
            from epic_pose_wrangler.v1 import main
            return main.UE4RBFAPI(view=view, parent=parent)
        # Bool to keep track of importing the newest api version
        import_failed = False
        # Check if the scene uses the latest solver
        if PluginManager.is_scene_using_recommended_solver():
            # Try and import the latest tool version
            try:
                from epic_pose_wrangler.v2 import main
                return main.UERBFAPI(view=view, parent=parent, file_path=file_path)
            except ImportError as e:
                LOG.error("Unable to import API v2, falling back to API v1 - {exception}".format(exception=e))
                import_failed = True
        # Fall back to API v1
        from epic_pose_wrangler.v1 import main
        # If the recommended solver is available but finds old nodes in the scene and imports correctly, provide
        # the option to upgrade to the latest version
        if not import_failed:
            main.UE4RBFAPI.UPGRADE_AVAILABLE = True
        return main.UE4RBFAPI(view=view, parent=parent)
