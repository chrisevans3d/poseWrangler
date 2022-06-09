# Copyright Epic Games, Inc. All Rights Reserved.

import os
import webbrowser
from functools import partial

from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

from PySide2 import QtWidgets, QtGui
from PySide2 import QtCore
from PySide2 import QtUiTools

from epic_pose_wrangler.v2.view import ui_context
from epic_pose_wrangler.v2.view.widget import category
from epic_pose_wrangler.log import LOG
from epic_pose_wrangler.view import log_widget
from epic_pose_wrangler.model import settings


class PoseWranglerWindow(MayaQWidgetDockableMixin, QtWidgets.QMainWindow):
    """
    class for the pose wranglerUI
    """

    # Solver Signals
    event_create_solver = QtCore.Signal(str)
    event_delete_solver = QtCore.Signal(str)
    event_edit_solver = QtCore.Signal(bool, object)
    event_mirror_solver = QtCore.Signal(object)
    event_refresh_solvers = QtCore.Signal()
    event_set_current_solver = QtCore.Signal(object)
    # Driver Signals
    event_add_drivers = QtCore.Signal()
    event_remove_drivers = QtCore.Signal(list)
    event_import_drivers = QtCore.Signal(str)
    event_export_drivers = QtCore.Signal(str, list)
    # Driven Signals
    event_add_driven = QtCore.Signal(list, object, bool)
    event_remove_driven = QtCore.Signal(list, object)
    # Pose Signals
    event_add_pose = QtCore.Signal(str, object)
    event_delete_pose = QtCore.Signal(str, object)
    event_go_to_pose = QtCore.Signal(str, object)
    event_mirror_pose = QtCore.Signal(str, object)
    event_rename_pose = QtCore.Signal(str, str, object)
    event_update_pose = QtCore.Signal(str, object)
    event_mute_pose = QtCore.Signal(str, object, object)
    # Blendshape Signals
    event_create_blendshape = QtCore.Signal(str, str, bool, object)
    event_add_blendshape = QtCore.Signal(str, str, str, object)
    event_edit_blendshape = QtCore.Signal(str, bool, object)
    # Utility Signals
    event_get_valid_actions = QtCore.Signal(object)
    event_select = QtCore.Signal(list)
    event_set_mirror_mapping = QtCore.Signal(str)

    def __init__(self):
        super(PoseWranglerWindow, self).__init__()
        # Load the UI file
        file_path = os.path.dirname(__file__) + "/pose_wrangler_ui.ui"
        if os.path.exists(file_path):
            ui_file = QtCore.QFile(file_path)
            # Attempt to open and load the UI
            try:
                ui_file.open(QtCore.QFile.ReadOnly)
                loader = QtUiTools.QUiLoader()
                self.win = loader.load(ui_file)
            finally:
                # Always close the UI file regardless of loader result
                ui_file.close()
        else:
            raise ValueError('UI File does not exist on disk at path: {}'.format(file_path))
        icon_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'resources', 'icons')
        QtCore.QDir.setSearchPaths("PoseWrangler", [icon_folder])
        self.setWindowTitle("Pose Wrangler 2.0.0")

        # Embed the UI window inside this window
        self.setCentralWidget(self.win)
        self.setWindowIcon(QtGui.QIcon(QtGui.QPixmap("PoseWrangler:unreal.png")))

        # Solver Connections
        self.win.create_solver_BTN.pressed.connect(self._create_solver)
        self.win.delete_solver_BTN.pressed.connect(self._delete_solver)
        self.win.toggle_edit_BTN.clicked.connect(self._edit_solver_toggle)
        self.win.mirror_solver_BTN.pressed.connect(self._mirror_solver)
        self.win.refresh_BTN.clicked.connect(self._refresh_solvers)
        self.win.solver_LIST.itemSelectionChanged.connect(self._solver_selection_changed)
        self.win.solver_LIST.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.win.solver_LIST.customContextMenuRequested.connect(self._solver_context_menu_requested)

        # Driver Connections
        self.win.add_driver_BTN.pressed.connect(self._add_drivers)
        self.win.remove_driver_BTN.pressed.connect(self._remove_drivers)
        self.win.import_drivers_ACT.triggered.connect(self._import_drivers)
        self.win.export_drivers_ACT.triggered.connect(partial(self._export_drivers, True))
        self.win.export_selected_drivers_ACT.triggered.connect(self._export_drivers)
        self.win.driver_transforms_LIST.itemDoubleClicked.connect(
            partial(
                self._select_in_scene,
                self.win.driver_transforms_LIST
            )
        )
        self.win.driven_transforms_LIST.itemDoubleClicked.connect(
            partial(
                self._select_in_scene,
                self.win.driven_transforms_LIST
            )
        )

        # Driven Connections
        self.win.add_driven_BTN.pressed.connect(self._add_driven)
        self.win.remove_driven_BTN.pressed.connect(self._remove_driven)

        # Pose Connections
        self.win.add_pose_BTN.pressed.connect(self._create_pose)
        self.win.delete_pose_BTN.pressed.connect(self._delete_pose)
        self.win.edit_pose_BTN.pressed.connect(self._update_pose)
        self.win.mirror_pose_BTN.pressed.connect(self._mirror_pose)
        self.win.rename_pose_BTN.pressed.connect(self._rename_pose)
        self.win.mute_pose_BTN.pressed.connect(self._mute_pose)
        self.win.pose_LIST.itemSelectionChanged.connect(self._pose_selection_changed)

        # Blendshape Connections
        self.win.create_blendshape_BTN.pressed.connect(self._create_blendshape)
        self.win.add_existing_blendshape_BTN.pressed.connect(self._add_blendshape)
        self.win.edit_blendshape_BTN.pressed.connect(self._edit_blendshape)

        # Utility Connections
        self.win.mirror_mapping_BTN.clicked.connect(self.set_mirror_file)
        self.win.use_maya_style_ACT.triggered.connect(self._toggle_stylesheet)
        self.win.documentation_ACT.triggered.connect(self._open_documentation)

        self.win.use_maya_style_ACT.setChecked(bool(int(settings.SettingsManager.get_setting("UseMayaStyle") or 0)))

        # Create a log dock widget
        self._log_widget = log_widget.LogWidget()
        # Add the log widget as a handler for the current log to display log messages in the UI
        LOG.addHandler(self._log_widget)
        # Add the dock to the window
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self._log_widget.log_dock)

        # Set the stylesheet
        self._set_stylesheet()
        # Empty vars to store the currently edited solver and blendshape, None if not editing either
        self._editing_solver = None
        self._editing_blendshape = None
        self._valid_actions = []

        # Generate lists of UI elements for different UI states.
        # Solver context enables/disables the specified widgets when a solver is in edit mode or not
        self._solver_context_ui_elements = [self.win.add_pose_BTN, self.win.delete_pose_BTN,
                                            self.win.edit_pose_BTN, self.win.mirror_pose_BTN, self.win.mute_pose_BTN,
                                            self.win.add_driven_BTN, self.win.remove_driven_BTN,
                                            self.win.create_blendshape_BTN,
                                            self.win.add_existing_blendshape_BTN, self.win.edit_blendshape_BTN,
                                            self.win.add_driver_BTN, self.win.remove_driver_BTN,
                                            self.win.rename_pose_BTN]
        # Blendshape editing context enables/disables the specified widgets when a blendshape is being edited or not
        self._blendshape_editing_context_ui_elements = [self.win.add_pose_BTN, self.win.delete_pose_BTN,
                                                        self.win.edit_pose_BTN, self.win.mirror_pose_BTN,
                                                        self.win.mute_pose_BTN,
                                                        self.win.add_driven_BTN, self.win.remove_driven_BTN,
                                                        self.win.create_blendshape_BTN,
                                                        self.win.add_existing_blendshape_BTN,
                                                        self.win.add_driver_BTN, self.win.remove_driver_BTN,
                                                        self.win.create_solver_BTN, self.win.delete_solver_BTN,
                                                        self.win.toggle_edit_BTN, self.win.rename_pose_BTN]

        # Disable all the solver elements by default
        for element in self._solver_context_ui_elements:
            element.setEnabled(False)

        self.show(dockable=True)

    @property
    def valid_actions(self):
        return self._valid_actions

    def add_rbf_solver(self, solver, edit=False):
        """
        Add a solver to the view
        :param solver :type api.RBFNode: solver reference
        :param edit :type bool: is this solver in edit mode?
        """
        # Create a new widget item with the solver name
        item = QtWidgets.QListWidgetItem(str(solver))
        # Add the solver and the edit status as custom data on the item
        item.setData(QtCore.Qt.UserRole, {"solver": solver, "edit": edit})
        # If we are editing, keep track of it
        if edit:
            self._editing_solver = solver
        # Add the item to the solver list
        self.win.solver_LIST.addItem(item)

    def clear(self):
        """
        Clear all the lists in the UI
        """
        self.win.solver_LIST.clear()
        self.win.driver_transforms_LIST.clear()
        self.win.driven_transforms_LIST.clear()
        self.win.pose_LIST.clear()

    def delete_solver(self, solver):
        """
        Delete the specified solver from the view
        :param solver :type api.RBFNode: solver ref
        """
        # Iterate through the solvers
        for i in range(self.win.solver_LIST.count()):
            # Get the item
            item = self.win.solver_LIST.item(i)
            # If the solver matches the solver from the item data
            if item.data(QtCore.Qt.UserRole)['solver'] == solver:
                # Remove the item from the list and break early
                self.win.solver_LIST.takeItem(self.win.solver_LIST.row(item))
                break

    def display_extensions(self, extensions):
        """
        Adds any found extensions to the utilities dock
        :param extensions :type list: list of PoseWranglerExtension instances
        """
        # Clear the existing extension layout
        for i in reversed(range(0, self.win.extension_layout.count())):
            item = self.win.extension_layout.itemAt(i)
            if isinstance(item, QtWidgets.QWidgetItem):
                widget = item.widget()
                widget.deleteLater()
                del widget
            self.win.extension_layout.removeItem(item)

        categories = {}
        for extension in extensions:
            if extension.view:
                category_name = extension.__category__ or "Default"
                if category_name in categories:
                    category_widget = categories[category_name]
                else:
                    category_widget = category.CategoryWidget(category_name)
                    categories[category_name] = category_widget
                    self.win.extension_layout.addWidget(category_widget)
                category_widget.add_extension(extension.view)

        self.win.utilities_DOCK.setMinimumWidth(
            self.win.extension_layout.sizeHint().width() +
            self.win.action_scroll_area.verticalScrollBar().sizeHint().width()
        )

    def edit_blendshape(self, pose_name, edit=False):
        """
        Set the UI in blendshape edit mode or finish editing.
        :param pose_name :type str: name of the pose to edit or finish editing
        :param edit :type bool: True = edit mode, False = finish editing
        """
        # Iterate through all of the driven transforms in the list
        for i in range(self.win.driven_transforms_LIST.count()):
            # Get the item
            item = self.win.driven_transforms_LIST.item(i)
            # Find the custom data stored on the item
            item_data = item.data(QtCore.Qt.UserRole)
            # If the item type is a blendshape and the pose matches the current pose, break
            if item_data['type'] == 'blendshape' and item_data['pose_name'] == pose_name:
                break
        # If no break was hit, exit early because no match was found
        else:
            return
        # If we are editing
        if edit:
            # If we are already editing a blendshape, finish editing the previous one first
            if self._editing_blendshape is not None:
                # Get the existing item data from the currently edited blendshape
                existing_item_data = self._editing_blendshape.data(QtCore.Qt.UserRole)
                # Finish editing
                self.event_edit_blendshape.emit(
                    existing_item_data['pose_name'], False,
                    existing_item_data['solver']
                )
                # Update the icon
                self._editing_blendshape.setIcon(QtGui.QIcon(":/blendShape.png"))
            # Store a ref to the new blendshape being edited
            self._editing_blendshape = item
            # Update the button text
            self.win.edit_blendshape_BTN.setText("Finish Editing Blendshape")
            # Update the icon to show edit mode
            item.setIcon(QtGui.QIcon(":/fileTextureEdit.png"))
            # Disable all the non blendshape related ui elements
            for element in self._blendshape_editing_context_ui_elements:
                element.setEnabled(False)
        # If we are not editing
        else:
            # Clear the ref to the edited blendshape
            self._editing_blendshape = None
            # Revert the button text
            self.win.edit_blendshape_BTN.setText("Edit Blendshape")
            # Revert the icon
            item.setIcon(QtGui.QIcon(":/blendShape.png"))
            # Re-enable all the ui elements
            for element in self._blendshape_editing_context_ui_elements:
                element.setEnabled(True)
        # Store the edit status in the item data
        item_data['edit'] = edit
        # Update the item data on the widget
        item.setData(QtCore.Qt.UserRole, item_data)

    def edit_solver(self, solver, edit=False):
        """
        Set the UI in solver edit mode or finish editing.
        :param solver :type str: name of the solver to edit or finish editing
        :param edit :type bool: True = edit mode, False = finish editing
        """
        # Iterate through the solvers
        for i in range(self.win.solver_LIST.count()):
            # Get the widget item
            item = self.win.solver_LIST.item(i)
            # If the solver matches the item data, break
            if item.data(QtCore.Qt.UserRole)['solver'] == solver:
                break
        # No match found, return early
        else:
            return
        # Grab the item data for the item
        item_data = item.data(QtCore.Qt.UserRole)

        # If edit mode
        if edit:
            # If we are already editing a solver, finish editing that one first
            if self._editing_solver is not None:
                # Update the icon
                self._editing_solver.setIcon(QtGui.QIcon())
                # Finish editing
                self.event_edit_solver.emit(False, self._editing_solver)
            # Store the new item as the current edited solver
            self._editing_solver = item
            # Update the button text
            self.win.toggle_edit_BTN.setText("Finish Editing '{solver}'".format(solver=solver))
            # Set the edit icon
            item.setIcon(QtGui.QIcon(":/fileTextureEdit.png"))
        else:
            # Clear the current solver
            self._editing_solver = None
            # Revert the button text
            self.win.toggle_edit_BTN.setText("Edit Selected Driver")
            # Clear the edit icon
            item.setIcon(QtGui.QIcon())

        # Update the item data with the new edit status
        item_data['edit'] = edit
        # Set the item data
        item.setData(QtCore.Qt.UserRole, item_data)

        # Update the solver related ui elements with the current edit status
        for element in self._solver_context_ui_elements:
            element.setEnabled(edit)

        self.win.delete_solver_BTN.setEnabled(not edit)
        self.win.create_solver_BTN.setEnabled(not edit)
        self.win.refresh_BTN.setEnabled(not edit)
        self.win.mirror_solver_BTN.setEnabled(not edit)
        # If a pose is selected, go to it. This will cause transforms to pop if edits weren't saved
        self._pose_selection_changed()

    def get_context(self):
        """
        Gets the current state of the ui
        :return: PoseWranglerUIContext
        """
        return ui_context.PoseWranglerUIContext(
            current_solvers=[i.text() for i in self.win.solver_LIST.selectedItems()],
            current_poses=[i.text() for i in self.win.pose_LIST.selectedItems()],
            current_drivers=[i.text() for i in self.win.driver_transforms_LIST.selectedItems()],
            current_driven=[i.text() for i in self.win.driven_transforms_LIST.selectedItems()],
            solvers=[self.win.solver_LIST.item(i).text() for i in range(0, self.win.solver_LIST.count())],
            poses=[self.win.pose_LIST.item(i).text() for i in range(0, self.win.pose_LIST.count())],
            drivers=[self.win.driver_transforms_LIST.item(i).text() for i in
                     range(0, self.win.driver_transforms_LIST.count())],
            driven=[self.win.driven_transforms_LIST.item(i).text() for i in
                    range(0, self.win.driven_transforms_LIST.count())],
        )

    def load_solver_settings(self, solver, drivers, driven_transforms, poses):
        """
        Display the settings for the specified solver
        :param solver :type RBFNode: solver reference
        :param drivers :type dict: dictionary of driver name: driver data
        :param driven_transforms :type dict: dictionary of driven transform type: driven transforms
        :param poses :type dict: dictionary of pose data
        """
        # Grab the current selection from the driver, driven and pose list
        current_drivers = [i.text() for i in self.win.driver_transforms_LIST.selectedItems()]
        current_driven = [i.text() for i in self.win.driven_transforms_LIST.selectedItems()]
        current_poses = [i.text() for i in self.win.pose_LIST.selectedItems()]

        # Clear the driver, driven and pose lists
        self.win.driver_transforms_LIST.clear()
        self.win.driven_transforms_LIST.clear()
        self.win.pose_LIST.clear()

        # Iterate through each driver
        for driver_name, driver_data in drivers.items():
            # Create new item widget
            item = QtWidgets.QListWidgetItem(driver_name)
            # Set the icon to a joint
            item.setIcon(QtGui.QIcon(":/kinJoint.png"))
            # Add item to the list
            self.win.driver_transforms_LIST.addItem(item)
            # Set the item data so it can be referenced later
            item.setData(QtCore.Qt.UserRole, driver_data)

        # Iterate through the driven transforms transform nodes
        for driven_transform in driven_transforms['transform']:
            # Create new item widget
            item = QtWidgets.QListWidgetItem(driven_transform)
            # Store the solver and item type
            item.setData(QtCore.Qt.UserRole, {'type': 'transform', 'solver': solver})
            # Set the icon to a joint
            item.setIcon(QtGui.QIcon(":/kinJoint.png"))
            # Add item to the list
            self.win.driven_transforms_LIST.addItem(item)

        # Iterate through all the driven transforms blendshapes
        for blendshape_mesh, pose_name in driven_transforms['blendshape'].items():
            # Create new item widget
            item = QtWidgets.QListWidgetItem(blendshape_mesh)
            # Store the solver, pose associated with the blendshape and the item type
            item.setData(QtCore.Qt.UserRole, {'type': 'blendshape', 'pose_name': pose_name, 'solver': solver})
            # Set the icon to blendshape
            item.setIcon(QtGui.QIcon(":/blendShape.png"))
            # Add item to the list
            self.win.driven_transforms_LIST.addItem(item)

        # Iterate through the poses
        for pose, pose_data in poses.items():
            # Create item and add it to the list
            item = QtWidgets.QListWidgetItem(pose)
            self.win.pose_LIST.addItem(item)
            muted = not pose_data.get('target_enable', True)
            if muted:
                font = item.font()
                font.setStrikeOut(True)
                item.setFont(font)
            # Set icon to a pose
            item.setIcon(QtGui.QIcon(":/p-head.png"))

        # Iterate through the solvers
        for row in range(self.win.solver_LIST.count()):
            # Find the item
            item = self.win.solver_LIST.item(row)
            # If the current solver matches this item, select it
            if solver == item.data(QtCore.Qt.UserRole)['solver']:
                item.setSelected(True)
                break

        # Create a map between widgets: names of previously selected items
        existing_selection_to_list_map = {
            self.win.driver_transforms_LIST: current_drivers,
            self.win.driven_transforms_LIST: current_driven,
            self.win.pose_LIST: current_poses
        }
        # Iterate through the widgets: target selections
        for list_ref, current in existing_selection_to_list_map.items():
            # Block signals so we don't fire any selection changed events
            list_ref.blockSignals(True)
            # Iterate through the list widget
            for i in range(list_ref.count()):
                # Get the item
                item = list_ref.item(i)
                # Check if the text is in the list of currently selected items (case sensitive) and select/deselect
                # as appropriate
                if item.text() in current:
                    item.setSelected(True)
                else:
                    item.setSelected(False)
            # Unblock the signals
            list_ref.blockSignals(False)

    def set_mirror_file(self):
        """
        Open up a dialog to get a new mirror mapping file
        """
        # Open dialog
        result = QtWidgets.QFileDialog.getOpenFileName(
            self, "Mirror Mapping File",
            os.path.join(os.path.dirname(__file__), 'mirror_mappings'),
            "Mirror Mapping File (*.json)"
        )
        # If no file specified, exit early
        if not result[0]:
            return
        # Emit the event
        self.event_set_mirror_mapping.emit(result[0])

    def update_mirror_mapping_file(self, path):
        """
        Update the mirror mapping widget with the specified path
        :param path :type str: file path to the mirror mapping file
        """
        # Set the text
        self.win.mirror_mapping_LINE.setText(path)

    # ================================================ Solvers ======================================================= #

    def _create_solver(self):
        """
        Create a new solver with the given name
        """
        # Popup input widget to get the solver name
        interp_name, ok = QtWidgets.QInputDialog.getText(self, 'Create Solver', 'Solver Name:')
        # Hack to fix broken styling caused by using a QInputDialog
        self.win.create_solver_BTN.setEnabled(False)
        self.win.create_solver_BTN.setEnabled(True)
        # If no name, exit
        if not interp_name:
            return

        if not interp_name.lower().endswith('_uerbfsolver'):
            interp_name += "_UERBFSolver"
        # Trigger solver creation
        self.event_create_solver.emit(interp_name)

    def _delete_solver(self):
        """
        Delete selected solvers
        """
        # Get the current solver selection
        selected_items = self.win.solver_LIST.selectedItems()

        selected_solvers = []
        # Iterate through the selection in reverse
        for item in reversed(selected_items):
            # Grab the solver from the item data
            selected_solvers.append(item.data(QtCore.Qt.UserRole)['solver'])

        # Delete the solvers from the backend first
        for solver in selected_solvers:
            self.event_delete_solver.emit(solver)

    def _edit_solver_toggle(self):
        """
        Toggle edit mode for the currently selected driver
        """
        # Grab the current selection
        selection = self.win.solver_LIST.selectedItems()
        if selection:
            # Grab the last item
            item = selection[-1]
            # Get the item data
            item_data = item.data(QtCore.Qt.UserRole)
            # Get the solver
            solver = item_data['solver']
            # Trigger edit mode enabled/disabled depending on the solvers current edit state
            self.event_edit_solver.emit(not item_data.get('edit', False), solver)

    def _get_item_from_solver(self, solver):
        """
        Get the widget associated with this solver
        :param solver :type api.RBFNode: solver ref
        :return :type QtWidgets.QListWidgetItem or None: widget
        """
        # Iterate through the solver list
        for i in range(self.win.solver_LIST.count()):
            # Get the item
            item = self.win.solver_LIST.item(i)
            # If the solver stored in the item data matches, return it
            if item.data(QtCore.Qt.UserRole)['solver'] == solver:
                return item
        # No match found, returning None

    def _get_selected_solvers(self):
        """
        :return: List of current RBFNodes
        """
        # Get the solver from the item data for each item in the current selection
        return [item.data(QtCore.Qt.UserRole)['solver'] for item in self.win.solver_LIST.selectedItems()]

    def _mirror_solver(self):
        """
        Mirror the selected solvers
        """
        # For each solver, trigger mirroring
        for solver in self._get_selected_solvers():
            self.event_mirror_solver.emit(solver)

    def _refresh_solvers(self):
        """
        Refresh the solver list
        """
        self.event_refresh_solvers.emit()

    def _solver_selection_changed(self):
        """
        When the solver selection changes, update the driver/driven and poses list accordingly
        """
        # Get the current selection
        items = self.win.solver_LIST.selectedItems()
        # If we have a selection
        if items:
            # Grab the last selected item
            item = items[-1]
            # Grab the item data
            item_data = item.data(QtCore.Qt.UserRole)
            # Set the current solver to the solver associated with this widget
            self.event_set_current_solver.emit(item_data['solver'])
            # Get the solvers edit status
            edit = item_data.get('edit', False)
            # Enable/disable the ui elements accordingly
            for element in self._solver_context_ui_elements:
                element.setEnabled(edit)
            # If we are in edit mode
            if edit:
                # Update the button
                self.win.toggle_edit_BTN.setText("Finish Editing '{solver}'".format(solver=item_data['solver']))
                # Set the icon
                item.setIcon(QtGui.QIcon(":/fileTextureEdit.png"))
        # No selection, clear all the lists
        else:
            self.win.driver_transforms_LIST.clear()
            self.win.driven_transforms_LIST.clear()
            self.win.pose_LIST.clear()

    # ================================================ Drivers ======================================================= #

    def _add_drivers(self):
        """
        Add drivers.
        """
        # Emit nothing so that the current scene selection will be used
        self.event_add_drivers.emit()

    def _remove_drivers(self):
        """
        Remove the specified drivers
        """
        # Emit the selected drivers to be deleted
        self.event_remove_drivers.emit(
            [i.data(QtCore.Qt.UserRole)
             for i in self.win.driver_transforms_LIST.selectedItems()]
        )

    # ================================================ Driven ======================================================== #

    def _add_driven(self):
        """
        Add driven nodes to the solver
        """
        # Emit no driven nodes so that it uses scene selection, no solver so that it uses the current solver and set
        # edit mode to true
        self.event_add_driven.emit(None, None, True)

    def _remove_driven(self):
        """
        Remove driven transforms from the specified solver
        """
        # Get currently selected driven items
        items = self.win.driven_transforms_LIST.selectedItems()
        # Exit early if nothing is selected
        if not items:
            return
        # Get the solver for the last item (they should all have the same solver)
        solver = items[-1].data(QtCore.Qt.UserRole)['solver']
        # Trigger event to remove specified nodes for the solver
        self.event_remove_driven.emit([i.text() for i in items], solver)

    # ============================================== Blendshapes ===================================================== #

    def _add_blendshape(self):
        """
        Add an existing blendshape to the solver for the current pose
        """
        # Get current solver
        solver = self._get_selected_solvers()
        # Get current pose
        poses = self._get_selected_poses()
        if not solver or not poses:
            LOG.warning("Unable to add blendshape, please select a solver and a pose and try again")
            return
        self.event_add_blendshape.emit(poses[-1], "", "", solver[-1])

    def _create_blendshape(self):
        """
        Create a blendshape for the current solver at the current pose
        """
        # Get current solver
        solver = self._get_selected_solvers()
        # Get current pose
        poses = self._get_selected_poses()
        if not solver or not poses:
            LOG.warning("Unable to create blendshape, please select a solver and a pose and try again")
            return
        # Create a blendshape for the last pose selected, with the current mesh selection, in edit mode enabled and
        # for the last solver selected
        self.event_create_blendshape.emit(poses[-1], None, True, solver[-1])

    def _edit_blendshape(self):
        """
        Edit or finish editing the selected blendshape
        """
        # Get the current blendshape being edited
        blendshape = self._editing_blendshape
        # If none is being edited, see if we have a blendshape selected
        if blendshape is None:
            # Get all the blendshapes selected
            selection = [sel for sel in self.win.driven_transforms_LIST.selectedItems() if
                         sel.data(QtCore.Qt.UserRole)['type'] == 'blendshape']
            # Update the blendshape var
            if selection:
                blendshape = selection[-1]
        # If we have a blendshape
        if blendshape:
            # Get the item data
            item_data = blendshape.data(QtCore.Qt.UserRole)
            # Get the associated pose name and solver
            pose_name = item_data['pose_name']
            solver = item_data['solver']
            # Trigger editing the blendshape for the pose name, using the opposite to the current edit status and for
            # the associated solver
            self.event_edit_blendshape.emit(pose_name, not item_data.get('edit', False), solver)

    # ================================================= Poses ======================================================== #

    def _create_pose(self):
        """
        Create a new pose
        """
        # Get the current solver
        selected_solvers = self._get_selected_solvers()

        # Get the last selection
        solver = selected_solvers[-1]
        # Display popup to get pose name
        pose_name, ok = QtWidgets.QInputDialog.getText(self, 'Create Pose', 'Pose Name:')
        # Hack to fix broken styling caused by using a QInputDialog
        self.win.add_pose_BTN.setEnabled(False)
        self.win.add_pose_BTN.setEnabled(True)

        if pose_name:
            # If a pose name is specified, create pose
            self.event_add_pose.emit(pose_name, solver)

    def _delete_pose(self):
        """
        Delete the selected poses
        """
        # Get the currently selected poses
        poses = self._get_selected_poses()
        # Exit early if nothing is selected
        if not poses:
            return
        # Get the selected solver
        solver = self._get_selected_solvers()[-1]
        # Block the signals to stop UI event updates
        self.win.pose_LIST.blockSignals(True)
        # For each selected pose, delete it
        for pose_name in poses:
            self.event_delete_pose.emit(pose_name, solver)
        self.win.pose_LIST.blockSignals(False)

    def _get_selected_poses(self):
        """
        Get the selected poses
        :return :type list: list of selected pose names
        """
        return [item.text() for item in self.win.pose_LIST.selectedItems()]

    def _mirror_pose(self):
        """
        Mirror the selected poses
        """
        # Get the pose selection
        poses = self._get_selected_poses()
        # Exit early if nothing is selected
        if not poses:
            return
        # Get the selected solver
        solver = self._get_selected_solvers()[-1]
        # For each pose, mirror it. This will create a mirrored solver if it doesn't already exist
        for pose_name in poses:
            self.event_mirror_pose.emit(pose_name, solver)

    def _mute_pose(self):
        """
        Toggles the muted status for the poses the selected poses
        """
        # Get the pose selection
        poses = self._get_selected_poses()
        # Exit early if nothing is selected
        if not poses:
            return

        solver = self._get_selected_solvers()[-1]
        # For each pose, mirror it. This will create a mirrored solver if it doesn't already exist
        for pose_name in poses:
            self.event_mute_pose.emit(pose_name, None, solver)

    def _pose_selection_changed(self):
        """
        On pose selection changed, go to the new pose
        """
        # Get the current pose selection
        selected_poses = self._get_selected_poses()
        if selected_poses:
            # Get the last pose
            selected_pose = selected_poses[-1]
            # Get the selected solver
            solver = self._get_selected_solvers()[-1]
            # Go to pose
            self.event_go_to_pose.emit(selected_pose, solver)

    def _rename_pose(self):
        """
        Rename the currently selected pose
        """
        # Get the current pose selection
        poses = self._get_selected_poses()
        # Exit early if nothing is selected
        if not poses:
            return
        # Get the last selected pose name
        pose_name = poses[-1]
        # Get the current solver
        solver = self._get_selected_solvers()[-1]
        # Create a popup to get the new pose name
        new_name, ok = QtWidgets.QInputDialog.getText(self, 'Rename Pose', 'New Pose Name:')
        # Hack to fix broken styling caused by using a QInputDialog
        self.win.rename_pose_BTN.setEnabled(False)
        self.win.rename_pose_BTN.setEnabled(True)
        # Exit if no new name is specified
        if not new_name:
            return
        # Get the existing pose names
        existing_names = [self.win.pose_LIST.item(i).text().lower() for i in range(self.win.pose_LIST.count())]
        # If the pose name already exists, log it and exit
        if new_name.lower() in existing_names:
            LOG.error("Pose '{pose_name}' already exists".format(pose_name=new_name))
            return
        # Pose doesn't already exist, rename it
        self.event_rename_pose.emit(pose_name, new_name, solver)

    def _update_pose(self):
        """
        Update the pose for the given solver
        """

        # Get the current pose selection
        poses = self._get_selected_poses()
        # Exit early if nothing is selected
        if not poses:
            return
        # Get the last selected pose name
        pose_name = poses[-1]
        # Get the current solver
        solver = self._get_selected_solvers()[-1]
        # Update the pose
        self.event_update_pose.emit(pose_name, solver)

    # ================================================== IO ========================================================== #

    def _import_drivers(self):
        """
        Generate a popup to find a json file to import serialized solver data from
        """
        # Get a json file path
        file_path = QtWidgets.QFileDialog.getOpenFileName(None, "Pose Wrangler Format", "", "*.json")[0]
        # If no path is specified, exit early
        if file_path == "":
            return
        # Import the drivers
        self.event_import_drivers.emit(file_path)

    def _export_drivers(self, all_drivers=False):
        """
        Export drivers to a file
        :param all_drivers :type bool: should all drivers be exported or just the current selection?
        """
        # Get the export file path
        file_path = QtWidgets.QFileDialog.getSaveFileName(None, "Pose Wrangler Format", "", "*.json")[0]
        # If no path is specified, exit early
        if file_path == "":
            return

        # If all drivers is specified, get all solvers
        if all_drivers:
            target_solvers = []
        else:
            # Get the currently selected solvers
            target_solvers = self._get_selected_solvers()
            # If no solvers found, skip export
            if not target_solvers:
                LOG.warning("Unable to export. No solvers selected")
                return

        # Export drivers
        self.event_export_drivers.emit(file_path, target_solvers)

    # =============================================== Utilities ====================================================== #
    def _open_documentation(self):
        """
        Open the documentation
        """
        index_html = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '../..', 'docs', 'site', 'html', 'index.html')
        )
        webbrowser.open(index_html)

    def _set_stylesheet(self):
        """
        Load the style.qss file and set the stylesheet
        :return:
        """
        if bool(int(settings.SettingsManager.get_setting("UseMayaStyle") or 0)):
            styles_path = os.path.join(os.path.dirname(__file__), 'maya_style.qss')
        else:
            styles_path = os.path.join(os.path.dirname(__file__), 'style.qss')

        with open(styles_path) as style:
            self.setStyleSheet(style.read())

    def _toggle_stylesheet(self, use_maya_style=False):
        """
        Toggles between the maya and UE stylesheet
        :param use_maya_style :type bool: on or off
        """
        settings.SettingsManager.set_setting("UseMayaStyle", int(use_maya_style))
        self._set_stylesheet()

    def _select_in_scene(self, list_widget=None, item=None):
        """
        Select the specified items in the scene
        :param list_widget :type QtWidgets.QListWidget or None: optional list widget to select from
        :param item :type QtWidgets.QListWidgetItem or None: optional item to select
        """
        # If no item is provided, select all the items from the list widget specified
        if item is None:
            items = [list_widget.item(i).text() for i in range(list_widget.count())]
        # Otherwise select the current item
        else:
            items = [item.text()]
        # If we have items, select them
        if items:
            self.event_select.emit(items)

    def _solver_context_menu_requested(self, point):
        """
        Create a context menu for the solver list widget
        :param point :type QtCore.QPoint: screen position of the request
        """
        # Create a new menu
        menu = QtWidgets.QMenu(parent=self)
        self.event_get_valid_actions.emit(self.get_context())

        # Dict to store sub menu name: sub menu
        sub_menus = {}
        # Iterate through the valid actions
        for action in self._valid_actions:
            # Set the current menu to the base menu
            current_menu = menu
            # If the action has a category
            if action.__category__:
                # If the category doesn't already exist, create it
                if action.__category__ not in sub_menus:
                    sub_menus[action.__category__] = menu.addMenu(action.__category__)
                # Set the current menu to the category menu
                current_menu = sub_menus[action.__category__]
            # Create a new action on the current menu
            action_widget = current_menu.addAction(action.__display_name__)
            action_widget.setToolTip(action.__tooltip__)
            # Connect the action trigger to execute the action, passing through the action and data to execute
            action_widget.triggered.connect(partial(self._trigger_context_menu_action, action))
        # Draw the menu at the current cursor pos
        menu.exec_(QtGui.QCursor.pos())

    def _trigger_context_menu_action(self, action):
        """
        Execute the specified action with the given data
        :param action :type base_action.BaseAction: action class
        """
        # Execute the action with the data
        action.execute(ui_context=self.get_context())
