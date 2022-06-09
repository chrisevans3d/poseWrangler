#  Copyright Epic Games, Inc. All Rights Reserved.
import inspect
import json
import os
import sys

from maya.api import OpenMaya as om

from epic_pose_wrangler.log import LOG
from epic_pose_wrangler.model import mirror_mapping, settings, exceptions
from epic_pose_wrangler.model.api import RBFAPI
from epic_pose_wrangler.v2.model import api, base_action, base_extension, pose_blender, context, utils
from epic_pose_wrangler.v2.model import exceptions as api_exceptions


class UERBFAPI(RBFAPI):
    """
    Main entry point for interacting with the UERBFSolverNode and UEPoseBlenderNode

    >>> from epic_pose_wrangler.v2 import main
    >>> rbf_api = main.UERBFAPI(view=False)
    >>> rbf_api.create_rbf_solver(solver_name="ExampleSolver", drivers=['leg_l'])
    """
    VERSION = "2.0.0"

    def __init__(self, view=False, parent=None, file_path=None):
        super(UERBFAPI, self).__init__(view=view, parent=parent)

        self._view = None

        # Set up a default mirror mapping
        self._mirror_mapping = mirror_mapping.MirrorMapping()
        # Instantiate a settings manager to restore settings from previous sessions
        self._settings_manager = settings.SettingsManager()
        # Empty var to store the current solver for convenience so that you don't have to pass the solver through
        # every time you call a function
        self._current_solver = None
        # Empty list to store any core and custom actions used to extend the functionality of PoseWrangler
        self._extensions = []

        # If view is requested, import and build the UI. We use a local import so that any QtWidget dependencies
        # won't be loaded if the user is running from mayapy
        if view:
            from epic_pose_wrangler.v2.view import pose_wrangler_window
            self._view = pose_wrangler_window.PoseWranglerWindow()
            # Connect up the views events to the appropriate functions
            self._setup_view_events()

        # Load the contents of the current scene
        LOG.info("Loading PoseWrangler...")
        self.load()
        # If a file path is specified, deserialize and load it
        if file_path:
            self.deserialize_from_file(file_path=file_path)

    @property
    def extensions(self):
        """
        :return: list of pose wrangler extensions currently loaded
        :rtype: list[pose_wrangler.v2.model.base_extension.PoseWranglerExtension]
        """
        return self._extensions

    @property
    def view(self):
        """
        :return: reference to the ui QWidget
        :rtype: QtWidgets.QWidget or None
        """
        return self._view

    @property
    def current_solver(self):
        """
        :return: reference to the current solver
        :rtype: api.RBFNode or None
        """
        return self._current_solver

    @current_solver.setter
    def current_solver(self, solver):
        # If the specified solver is not an RBFNode class, raise exception
        if not isinstance(solver, api.RBFNode):
            raise api_exceptions.InvalidSolverError(
                "Solver is not a valid {node_type} node".format(node_type=api.RBFNode)
            )
        # Set the current solver
        self._current_solver = solver
        solvers = self.rbf_solvers
        for action in self._extensions:
            action.on_context_changed(
                context.PoseWranglerContext(current_solver=solver, solvers=solvers)
            )
        # If we are displaying the view, update it with the current selection
        if self._view:
            # Generate a kwarg dict.
            kwargs = {
                "solver": solver,
                # We want to store a reference to the MObject in case the name of the  node is changed and the
                # user doesn't refresh the UI
                "drivers": {driver: om.MGlobal.getSelectionListByName(driver).getDependNode(0) for driver in
                            solver.drivers()},
                # We want to display both the driven transforms and connected blendshapes.
                # NOTE: Blendshapes will only be found if connected up via this API. For more info see:
                # self.create_blendshape or self.add_blendshape
                "driven_transforms": {
                    'transform': solver.driven_nodes(pose_blender.UEPoseBlenderNode.node_type),
                    'blendshape': {mesh: solver.get_pose_for_blendshape_mesh(mesh) for mesh in
                                   solver.driven_nodes(type='blendShape')}
                },
                "poses": solver.poses()
            }
            # Load the solver settings in the view with the given kwargs
            self._view.load_solver_settings(**kwargs)

    @property
    def mirror_mapping(self):
        """
        :return: reference to the currently loaded mirror mapping
        :rtype: mirror_mapping.MirrorMapping object
        """
        return self._mirror_mapping

    @property
    def rbf_solvers(self):
        """
        :return: list of rbf solvers in the scene
        :rtype: list
        """
        return api.RBFNode.find_all()

    # ================================================ Solvers ======================================================= #

    def create_rbf_solver(self, solver_name, drivers=None):
        """
        Create an rbf solver node with the given name and the specified driver transforms

        :param solver_name: name of the solver node
        :type solver_name: str
        :param drivers: list of driver transform node names
        :type drivers: list
        :return: RBFNode ref
        :rtype: api.RBFNode
        """
        # If no drivers are specified, grab the current selection
        drivers = drivers or utils.get_selection(_type='transform')
        LOG.debug("Creating RBF solver '{name}' with drivers: {drivers}".format(name=solver_name, drivers=drivers))
        # Create the solver
        solver = api.RBFNode.create(solver_name)
        # If drivers have been specified, add them
        if drivers:
            self.add_drivers(drivers=drivers, solver=solver)
        # If we are in UI mode, add the solver to the view
        if self._view:
            self._view.add_rbf_solver(solver)
        # Set the current solver
        self.current_solver = solver
        # Set the current solver to edit mode
        self.edit_solver(edit=True, solver=solver)
        # Return the new solver
        return solver

    def delete_rbf_solver(self, solver=None):
        """
        Delete the specified solver

        :param solver:  solver reference
        :type solver: api.RBFNode
        """
        # If no solver is specified, grab the current solver
        solver = solver or self._current_solver
        # Delete the solver
        solver.delete()
        # If we are using the UI, delete the solver
        if self._view:
            self._view.delete_solver(solver)
        # If the current solver is this solver, set current to None
        if self._current_solver == solver:
            self._current_solver = None

    def edit_solver(self, edit=True, solver=None):
        """
        Edit or finish editing the specified solver. Enables pose creation/driven node changes via the ui

        :param edit:  set edit mode on or off
        :type edit: bool
        :param solver: solver reference
        :type solver: api.RBFNode
        """
        # If no solver is specified, grab the current solver
        solver = solver or self._current_solver
        # Edit the solver
        solver.edit_solver(edit=edit)
        # If we have a ui, update the edit mode status
        if self._view:
            self._view.edit_solver(solver=solver, edit=edit)
        LOG.debug("Setting edit status: {status} for solver: {solver}".format(status=edit, solver=solver))
        self.current_solver = solver

    def mirror_rbf_solver(self, solver=None):
        """
        Mirror the current solver

        :param solver: solver reference
        :type solver: api.RBFNode
        :return: mirrored solver reference
        :rtype: api.RBFNode
        """
        # If no solver is specified, grab the current solver
        solver = solver or self._current_solver
        mirrored_solver = solver.mirror(self.mirror_mapping)
        if self._view:
            self._load_view()

        # Set the current solver to the new solver
        self.current_solver = mirrored_solver
        # Return the new solver
        return mirrored_solver

    def get_rbf_solver_by_name(self, solver_name):
        """
        Searches the scene for an rbf solver with the given name. Case insensitive

        :param solver_name: Solver node name
        :type solver_name: str
        :return: found node or None
        :rtype: api.RBFNode or None
        """
        for solver in api.RBFNode.find_all():
            if str(solver).lower() == solver_name.lower():
                return solver

    # ================================================ Drivers ======================================================= #

    def add_drivers(self, drivers=None, solver=None):
        """
        Add the specified drivers to the specified solver

        :param drivers: list of transform nodes
        :type drivers: list
        :param solver: solver reference
        :type solver: api.RBFNode
        """
        # If no solver is specified, grab the current solver
        solver = solver or self._current_solver
        # If we already have more than one pose, we can't add a new driver (would require manually updating every pose)
        if solver.num_poses() > 1:
            raise api_exceptions.InvalidPoseIndex("Too many poses have been created, unable to add a new driver.")
        # Check if we have a default pose
        if solver.has_pose(pose_name='default'):
            # Delete the current rest pose if found
            solver.delete_pose(pose_name='default')
        # Add new drivers
        solver.add_driver(transform_nodes=drivers)
        # Create the new rest pose with all the drivers
        solver.add_pose_from_current(pose_name='default')
        # Set the current solver
        self.current_solver = solver

    def remove_drivers(self, drivers, solver=None):
        """
        Remove the specified drivers from the specified solver

        :param drivers: list of driver transform nodes
        :type drivers: list
        :param solver: solver reference
        :type solver: api.RBFNode
        """
        # Get the solver if it hasn't been specified
        solver = solver or self._current_solver
        # Remove the drivers from the solver
        solver.remove_drivers(drivers)
        # Have to re-wrap solver due to a bug with targets array indexing
        self.current_solver = api.RBFNode(str(solver))

    # ================================================ Driven ======================================================== #

    def add_driven_transforms(self, driven_nodes=None, solver=None, edit=False):
        """
        Add driven transforms to the specified solver

        :param driven_nodes: list of transform nodes
        :type driven_nodes: list
        :param solver: solver reference
        :type solver: api.RBFNode
        :param edit: should this transform not be connected to the pose blender output upon creation
        :type edit: bool
        """
        # Get the solver if it hasn't been specified
        solver = solver or self._current_solver
        solver.add_driven_transforms(driven_nodes, edit=edit)
        # Update the current solver
        self.current_solver = solver

    def remove_driven(self, driven_nodes, solver=None):
        """
        Remove driven transforms from the specified solver

        :param driven_nodes: list of transform nodes
        :type driven_nodes: list
        :param solver: solver reference
        :type solver: api.RBFNode
        """
        # Get the solver if it hasn't been specified
        solver = solver or self._current_solver
        solver.remove_driven_transforms(driven_nodes)
        # Update the current solver
        self.current_solver = solver

    # ============================================== Blendshapes ===================================================== #

    def add_blendshape(self, pose_name, mesh_name, base_mesh, solver=None):
        """
        Add an existing blendshape for the current pose

        :param pose_name: name of the pose the blendshape is associated with
        :type pose_name: str
        :param mesh_name: name of the existing blendshape mesh
        :type mesh_name: str
        :param base_mesh: name of the mesh the blendshape mesh is derived from
        :type base_mesh: str
        :param solver: solver reference
        :type solver: api.RBFNode
        """
        # Ensure we have a solver
        solver = solver or self._current_solver
        # Add the blendshape
        solver.add_existing_blendshape(pose_name, mesh_name, base_mesh)
        self.current_solver = solver

    def create_blendshape(self, pose_name, mesh_name=None, edit=False, solver=None):
        """
        Create a new blendshape for the given pose and mesh

        :param pose_name: name of the pose to create this blendshape for
        :type pose_name: str
        :param mesh_name: name of the mesh to create the blendshape from
        :type mesh_name: str
        :param edit: should this blendshape be edited straight away
        :type edit: bool
        :param solver: solver reference
        :type solver: api.RBFNode
        :return: name of the newly created blendshape mesh
        :rtype: str
        """
        # Ensure we have a solver
        solver = solver or self._current_solver
        # Create a new blendshape mesh at the specified pose
        blendshape_mesh_name = solver.create_blendshape(pose_name, mesh_name)
        # If we are editing, change the mode
        if edit:
            self.edit_blendshape(pose_name=pose_name, edit=True, solver=solver)
        else:
            # If we aren't editing, update the current solver
            self.current_solver = solver
        # Return the name of the new blendshape mesh
        return blendshape_mesh_name

    def delete_blendshape(self, pose_name, solver=None):
        """
        Delete the blendshape associated with the specified pose

        :param pose_name: name of the pose to delete blendshapes for
        :type pose_name: str
        :param solver: solver reference
        :type solver: api.RBFNode
        """
        # Ensure we have a solver
        solver = solver or self._current_solver
        # Delete the blendshape mesh at the specified pose
        solver.delete_blendshape(pose_name, delete_mesh=True)
        # Set the current solver
        self.current_solver = solver

    def edit_blendshape(self, pose_name, edit=True, solver=None):
        """
        Edit or finish editing the blendshape associated with the specified pose name

        :param pose_name: name of the pose the blendshape is associated with
        :type pose_name: str
        :param edit: True = enable editing, False =  finish editing
        :type edit: bool
        :param solver: solver reference
        :type solver: api.RBFNode
        """
        # Ensure we have a solver
        solver = solver or self._current_solver
        # Edit or finish editing the blendshape
        solver.edit_blendshape(pose_name, edit=edit)
        # Set the current solver
        self.current_solver = solver
        # If we have a ui, update the blendshapes status
        if self._view:
            self._view.edit_blendshape(pose_name, edit=edit)

    def isolate_blendshape(self, pose_name, isolate=True, solver=None):
        """
        Isolate the blendshape associated with the specified pose name, disabling all other blendshapes.

        :param pose_name: name of the pose the blendshape is associated with
        :type pose_name: str
        :param isolate: True = isolate the blendshape, False = reconnect all disconnected blendshapes
        :type isolate: bool
        :param solver: solver reference
        :type solver: api.RBFNode
        """
        # Ensure we have a solver
        solver = solver or self._current_solver
        # Isolate or un-isolate the blendshape
        solver.isolate_blendshape(pose_name=pose_name, isolate=isolate)
        # Set the current solver
        self.current_solver = solver

    # ================================================= Poses ======================================================== #

    def create_pose(self, pose_name, solver=None):
        """
        Create a new pose for the specified solver

        :param pose_name: name of the new pose
        :type pose_name: str
        :param solver: solver reference
        :type solver: api.RBFNode
        """
        # Ensure we have a solver
        solver = solver or self._current_solver
        # Create a new pose from the current position
        solver.add_pose_from_current(pose_name=pose_name)
        # Set the current solver
        self.current_solver = solver

    def delete_pose(self, pose_name, solver=None):
        """
        Remove a pose from the given solver

        :param pose_name: name of the pose to remove
        :type pose_name: str
        :param solver: solver reference
        :type solver: api.RBFNode
        """
        # Ensure we have a solver
        solver = solver or self._current_solver
        # Delete the pose
        solver.delete_pose(pose_name)
        # Set the current solver
        self.current_solver = solver

    def go_to_pose(self, pose_name, solver=None):
        """
        Move the driver/driven transforms to the given pose

        :param pose_name: name of the pose
        :type pose_name: str
        :param solver: solver reference
        :type solver: api.RBFNode
        """
        # Ensure we have a solver
        solver = solver or self._current_solver
        # Go to the pose
        solver.go_to_pose(pose_name=pose_name)

    def mirror_pose(self, pose_name, solver=None):
        """
        Mirror a pose to the mirror of the current solver

        :param pose_name: name of the pose
        :type pose_name: str
        :param solver: solver reference
        :type solver: api.RBFNode
        """
        # Ensure we have a solver
        solver = solver or self._current_solver
        # Mirror the pose
        solver.mirror_pose(pose_name=pose_name, mirror_mapping=self.mirror_mapping)
        # Reload all the solvers
        self.load()
        # Set the current solver
        self.current_solver = solver

    def mute_pose(self, pose_name, mute=True, solver=None):
        """
        Mute or unmute the specified pose, removing all influences of the pose from the solver.
        NOTE: This will affect the solver radius if automatic radius is enabled.

        :param pose_name: name of the pose
        :type pose_name: str
        :param mute: mute or unmute the pose
        :type mute: bool
        :param solver: solver reference
        :type solver: api.RBFNode
        """
        # Ensure we have a solver
        solver = solver or self._current_solver
        # Mute or unmute the pose
        solver.mute_pose(pose_name=pose_name, mute=mute)
        # Set the current solver
        self.current_solver = solver

    def rename_pose(self, pose_name, new_pose_name, solver=None):
        """
        Rename a pose on the given solver

        :param pose_name: name of the pose
        :type pose_name: str
        :param new_pose_name: new name of the pose
        :type new_pose_name: str
        :param solver: solver reference
        :type solver: api.RBFNode
        """
        # Ensure we have a solver
        solver = solver or self._current_solver
        # Get the current pose index
        pose_index = solver.pose_index(pose_name=pose_name)
        # Rename the pose at the given index
        solver.rename_pose(pose_index=pose_index, pose_name=new_pose_name)
        # Update the current solver
        self.current_solver = solver

    def update_pose(self, pose_name, solver=None):
        """
        Update the pose for the given solver

        :param pose_name: name of the pose to update
        :type pose_name: str
        :param solver: solver reference
        :type solver: api.RBFNode
        """
        # Ensure we have a solver
        solver = solver or self._current_solver
        # Update the pose with the current driver/driven positions
        solver.add_pose_from_current(pose_name, update=True)
        LOG.info("Updated {pose_name}".format(pose_name=pose_name))

        self.current_solver = solver

    # ================================================== IO ========================================================== #

    def deserialize_from_file(self, file_path, solver_names=None):
        """
        Deserialize solvers from a specific file.

        :param file_path: json file to load
        :type file_path: str
        """
        # Check the path exists
        if not os.path.exists(file_path):
            raise exceptions.PoseWranglerIOError(
                "Unable to deserialize from {file_path}, path does not exist".format(file_path=file_path)
            )
        if solver_names is None:
            solver_names = []
        # Load the json file and deserialize
        with open(file_path, 'r') as f:
            data = json.loads(f.read())
        self.deserialize(data, solver_names=solver_names)
        LOG.debug("Successfully loaded solvers: {solvers}".format(solvers=solver_names or list(data.keys())))
        LOG.info(
            "Successfully loaded {num_solvers} solver(s) from {file_path}".format(
                num_solvers=len(data),
                file_path=file_path
            )
        )

    def serialize_to_file(self, file_path, solvers=None):
        """
        Serialize the specified solvers to a file

        :param file_path: json file to serialize
        :type file_path: str
        :param solvers: list of api.RBFNode to serialize
        :type solvers: list
        """
        # Check that the directory exists before writing to it
        if not os.path.exists(os.path.dirname(file_path)):
            os.makedirs(file_path)
        # Dump the serialized data to the json file
        with open(file_path, 'w') as f:
            data = self.serialize(solvers=solvers)
            LOG.debug("Successfully serialized solvers: {solvers}".format(solvers=list(data.keys())))
            f.write(json.dumps(data))
            LOG.info(
                "Successfully exported {num_solvers} solver(s) to {file_path}".format(
                    num_solvers=len(data),
                    file_path=file_path
                )
            )

    def deserialize(self, data, solver_names=None):
        """
        Deserialize and load the solvers from the data specified

        :param data: serialized solver data
        :type data: dict
        :param solver_names: list of solver names to load from the data
        :type solver_names: list, optional
        """
        for solver_name, solver_data in data.items():
            if solver_names and solver_name in solver_names or not solver_names:
                api.RBFNode.create_from_data(solver_data)
        self.load()

    def serialize(self, solvers=None):
        """
        Serialize the specified solvers

        :param solvers: list of api.RBFNode to serialize
        :type solvers: list
        :return: serialized solver data
        :rtype: dict
        """
        return {str(solver): solver.data() for solver in solvers or self.rbf_solvers}

    def load(self):
        """
        Load the default pose wrangler settings
        """
        # Set the mirror mapping from user settings
        self.set_mirror_mapping()
        self._load_extensions()

        if self._view:
            self._load_view()

    # =============================================== Utilities ====================================================== #

    def get_context(self):
        """
        Get the current solver context

        :return: pose wrangler context containing the current solver and all rbf solvers
        :rtype: context.PoseWranglerContext
        """
        return context.PoseWranglerContext(current_solver=self.current_solver, solvers=self.rbf_solvers)

    def get_ui_context(self):
        """
        If the ui is available, return the ui context

        :return: ui context containing the current state of the ui
        :rtype: ui_context.PoseWranglerUIContext or None
        """
        if self._view:
            return self._view.get_context()

    def get_extension_by_type(self, class_ref):
        """
        Get a reference to one of the loaded extensions from a class type

        :param class_ref: reference to an extension class
        :type class_ref: base_extension.PoseWranglerExtension
        :return: reference to a loaded extension if one is loaded
        :rtype: base_extension.PoseWranglerExtension instance or None
        """
        extensions = [extension for extension in self._extensions if isinstance(extension, class_ref)]
        if not extensions:
            return
        return extensions[0]

    def set_mirror_mapping(self, path=None):
        """
        Set the mirror mapping from a file

        :param path: path to json mirror mapping file
        :type path: str
        """
        # If no path is specified, get the path stored in the settings manager
        if path is None:
            path = self._settings_manager.get_setting("MirrorMappingFile")
        if path:
            # If the path doesnt exist, raise an exception
            if not os.path.exists(path):
                raise exceptions.InvalidMirrorMapping("Unable to find mapping file: {file}".format(file=path))
            # Set the new mirror mapping
            self._mirror_mapping = mirror_mapping.MirrorMapping(file_path=path)
            self._settings_manager.set_setting("MirrorMappingFile", path)
        # If we are using the UI, update the mirror mapping file path
        if self._view:
            self._view.update_mirror_mapping_file(self._mirror_mapping.file_path)

    def get_solver_edit_status(self, solver):
        """
        Check if the current solver is in 'Edit' mode

        :param solver: solver reference
        :type solver: api.RBFNode
        :return: True = in edit mode, False = not in edit mode
        :rtype: bool
        """
        # Get the solver if it hasn't been specified
        solver = solver or self._current_solver
        return solver.get_solver_edit_status()

    def _get_valid_actions(self, ui_context):
        """
        Gets the valid actions base on the ui context
        :param ui_context :type PoseWranglerUIContext: current selection state of the UI
        """
        if not self._view:
            return
        # Find all the available actions
        found_actions = []
        # Iterate through all the modules currently loaded
        for module in list(sys.modules.values()):
            try:
                # Find all the classes in the module that inherit from BaseAction
                found_actions.extend(
                    [obj for name, obj in inspect.getmembers(module, inspect.isclass) if
                     issubclass(
                         obj, base_action.BaseAction
                     ) and obj != base_action.BaseAction
                     and obj not in found_actions]
                )
            except ImportError:
                continue

        # Create the actions
        self._view.valid_actions.clear()
        self._view.valid_actions.extend([action(api=self) for action in found_actions])

    def _load_extensions(self):
        """
        Loads any core and custom extensions found in the sys.modules
        """
        # Find all the available extensions
        found_extensions = []
        # Iterate through all the modules currently loaded
        for module in list(sys.modules.values()):
            try:
                # Find all the classes in the module that inherit from BaseAction
                found_extensions.extend(
                    [obj for name, obj in inspect.getmembers(module, inspect.isclass) if
                     issubclass(
                         obj, base_extension.PoseWranglerExtension
                     ) and obj != base_extension.PoseWranglerExtension
                     and obj not in found_extensions]
                )
            except ImportError:
                continue

        # Create the extensions
        self._extensions = [extension(display_view=bool(self._view), api=self) for extension in found_extensions]

        # If we are using the UI, show the actions
        if self._view:
            self._view.display_extensions(self._extensions)

    def _load_view(self):
        """
        Refresh the UI with the latest solvers
        """
        if not self._view:
            return
        # If we have a ui, clear it before we load fresh data
        self._view.clear()
        # Bool to keep track if we have a solver that has edits to it
        existing_edit = None
        # Iterate through all the solvers in the scene
        for solver in self.rbf_solvers:
            # Get the solvers edit status
            edit = self.get_solver_edit_status(solver)
            # If we have an existing edit and this solver has also been edited
            if existing_edit is not None and edit:
                # Finish editing this solver
                self.edit_solver(edit=False, solver=solver)
                # Update the edit status accordingly
                edit = False
            # Otherwise if no existing edit and we have an edit
            elif edit:
                # Store the existing edit
                existing_edit = solver
            # Add the solver to the view with its edit status
            self._view.add_rbf_solver(solver, edit=edit)

    def _set_current_solver(self, solver):
        """
        UI Event to update the current solver
        :param solver :type api.RBFNode: solver reference
        """
        self.current_solver = solver

    # noinspection DuplicatedCode
    def _setup_view_events(self):
        """
        Connect up all of the ui signals to their corresponding functions
        """
        # Only works if we have a view
        if not self._view:
            return
        # Connect up all the ui events
        # Solver Events
        self._view.event_create_solver.connect(self.create_rbf_solver)
        self._view.event_delete_solver.connect(self.delete_rbf_solver)
        self._view.event_edit_solver.connect(self.edit_solver)
        self._view.event_mirror_solver.connect(self.mirror_rbf_solver)
        self._view.event_refresh_solvers.connect(self._load_view)
        self._view.event_set_current_solver.connect(self._set_current_solver)
        # Driver Events
        self._view.event_add_drivers.connect(self.add_drivers)
        self._view.event_remove_drivers.connect(self.remove_drivers)
        self._view.event_export_drivers.connect(self.serialize_to_file)
        self._view.event_import_drivers.connect(self.deserialize_from_file)
        # Driven Events
        self._view.event_add_driven.connect(self.add_driven_transforms)
        self._view.event_remove_driven.connect(self.remove_driven)
        # Pose Events
        self._view.event_add_pose.connect(self.create_pose)
        self._view.event_delete_pose.connect(self.delete_pose)
        self._view.event_go_to_pose.connect(self.go_to_pose)
        self._view.event_mirror_pose.connect(self.mirror_pose)
        self._view.event_rename_pose.connect(self.rename_pose)
        self._view.event_update_pose.connect(self.update_pose)
        self._view.event_mute_pose.connect(self.mute_pose)
        # Blendshape Events
        self._view.event_create_blendshape.connect(self.create_blendshape)
        self._view.event_add_blendshape.connect(self.add_blendshape)
        self._view.event_edit_blendshape.connect(self.edit_blendshape)
        # Utility Events
        self._view.event_get_valid_actions.connect(self._get_valid_actions)
        self._view.event_select.connect(utils.set_selection)
        self._view.event_set_mirror_mapping.connect(self.set_mirror_mapping)


if __name__ == '__main__':
    import ctypes

    from PySide2 import QtWidgets

    myappid = 'EpicGames.PoseWrangler'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    app = QtWidgets.QApplication(sys.argv)
    tool = UERBFAPI(view=True)
    app.exec_()
