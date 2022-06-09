# Copyright Epic Games, Inc. All Rights Reserved.

from PySide2 import QtWidgets
from PySide2 import QtCore
from PySide2 import QtUiTools

import os

import maya.cmds as cmds
import maya.OpenMaya as OpenMaya
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

from epic_pose_wrangler.log import LOG
from epic_pose_wrangler.view import log_widget
from epic_pose_wrangler.v1 import poseWrangler, upgrade
from epic_pose_wrangler.v1 import palette


class EventUpgrade(QtCore.QObject):
    upgrade = QtCore.Signal(str)


class PoseWrangler(MayaQWidgetDockableMixin, QtWidgets.QMainWindow):
    """
    class for the pose wranglerUI
    """

    ui_name = "poseWranglerWindow"

    def __init__(self, parent=None):
        super(PoseWrangler, self).__init__(parent)
        self.event_upgrade_dispatch = EventUpgrade()
        # Load the dependent plugin
        plugin_versions = [{
            "name": "MayaUE4RBFPlugin_{}".format(cmds.about(version=True)),
            "node_name": "UE4RBFSolverNode"
        },
            {
                "name": "MayaUE4RBFPlugin{}".format(cmds.about(version=True)),
                "node_name": "UE4RBFSolverNode"
            },
            {"name": "MayaUERBFPlugin".format(cmds.about(version=True)), "node_name": "UERBFSolverNode"}]

        QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, os.environ['LOCALAPPDATA'])
        self._settings = QtCore.QSettings(
            QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, "Epic Games",
            "PoseWrangler"
        )
        self._settings.setFallbacksEnabled(False)

        for plugin_version in plugin_versions:
            plugin_name = plugin_version['name']
            node_name = plugin_version['node_name']
            if cmds.pluginInfo(plugin_name, q=True, loaded=True):
                self._node_name = node_name
                break
            else:
                try:
                    cmds.loadPlugin(plugin_name)
                    self._node_name = node_name
                    break
                except RuntimeError as e:
                    pass
        else:
            raise RuntimeError("Unable to load valid RBF plugin version")

        # Load the UI file
        file_path = os.path.dirname(__file__) + "/poseWranglerUI.ui"
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

        self.setWindowTitle("Pose Wrangler")
        # Embed the UI window inside this widget
        self.setCentralWidget(self.win)

        # buttons
        self.win.add_pose_BTN.pressed.connect(self.add_pose)

        # refresh the driver cmd list
        self.load_drivers()

        # hook up utils UI
        self.win.bake_poses_BTN.pressed.connect(self.bake_poses)

        self.win.pose_LIST.itemSelectionChanged.connect(self.pose_changed)
        self.win.edit_pose_BTN.pressed.connect(self.edit_pose)
        self.win.delete_pose_BTN.pressed.connect(self.delete_pose)

        self.win.driver_LIST.itemSelectionChanged.connect(self.driver_changed)
        self.win.driver_LIST.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.win.driver_LIST.customContextMenuRequested.connect(self.driver_popup)

        self.win.driven_transforms_LIST.itemSelectionChanged.connect(self.driven_changed)

        self.win.select_driver_BTN.pressed.connect(self.select_driver)
        self.win.add_driven_BTN.pressed.connect(self.add_new_driven)

        self.win.mirror_pose_BTN.pressed.connect(self.mirror_pose)

        self.win.copy_driven_trs_BTN.pressed.connect(self.copy_driven_trs)
        self.win.paste_driven_trs_BTN.pressed.connect(self.paste_driven_trs)

        self.win.create_driver_BTN.pressed.connect(self.create_driver)
        self.win.delete_driver_BTN.pressed.connect(self.delete_driver)

        # setup the 'driving enabled' check box functionality
        self.win.toggle_edit_BTN.clicked.connect(self.toggle_edit)
        self.win.refresh_BTN.clicked.connect(self.load_drivers)

        self.win.driver_transform_LINE.setReadOnly(True)
        self.win.upgrade_scene_BTN.pressed.connect(self._upgrade_scene)

        self._log_widget = log_widget.LogWidget()
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self._log_widget.log_dock)
        LOG.addHandler(self._log_widget)
        # refresh the tree
        self.load_poses()

        self.set_stylesheet()

        self._driver = None

    def set_stylesheet(self):
        """set the theming and styling here"""
        self.setStyleSheet(palette.getPaletteString())

    def driver_popup(self, point):
        """add  right click menu"""

        selected_solvers = self.get_selected_solvers()
        solver = None
        if selected_solvers:
            solver = selected_solvers[-1]

        """--------------------------EDIT----------------------------"""

        edit_action = QtWidgets.QAction("Edit", self)
        edit_action.triggered.connect(self.edit_driver)

        enable_action = QtWidgets.QAction("Finish Editing (Enable)", self)
        enable_action.triggered.connect(self.enable_driver)

        """--------------------------SELECTION----------------------------"""

        select_driver_action = QtWidgets.QAction("Select Driver Transform", self)
        select_driver_action.triggered.connect(self.select_driver)

        select_solver_action = QtWidgets.QAction("Select Solver Node", self)
        select_solver_action.triggered.connect(self.select_solver)

        select_driven_action = QtWidgets.QAction("Select Driven Transform(s)", self)
        select_driven_action.triggered.connect(self.select_driven)

        """--------------------------MIRROR----------------------------"""

        mirror_driver_action = QtWidgets.QAction("Mirror Selected Drivers", self)
        mirror_driver_action.triggered.connect(self.mirror_driver)

        """----------------------IMPORT/EXPORT----------------------------"""

        export_driver_action = QtWidgets.QAction("Export Selected Drivers", self)
        export_driver_action.triggered.connect(self.export_driver)

        import_driver_action = QtWidgets.QAction("Import Driver(s)", self)
        import_driver_action.triggered.connect(self.import_drivers)

        export_all_action = QtWidgets.QAction("Export All Drivers", self)
        export_all_action.triggered.connect(self.export_all)

        """--------------------------ADD----------------------------"""

        add_driven_action = QtWidgets.QAction("Add Driven Transform(s)", self)
        add_driven_action.triggered.connect(self.add_new_driven)

        """--------------------------UTILITIES----------------------------"""

        zero_base_pose_action = QtWidgets.QAction("Zero Base Pose Transforms", self)
        zero_base_pose_action.triggered.connect(self.zero_base_poses)

        menu = QtWidgets.QMenu("Options:", self.win.driver_LIST)

        select_menu = QtWidgets.QMenu("Select:", menu)
        select_menu.addAction(select_driver_action)
        select_menu.addAction(select_driven_action)
        select_menu.addAction(select_solver_action)

        mirror_menu = QtWidgets.QMenu("Mirror:", menu)
        mirror_menu.addAction(mirror_driver_action)

        import_export_menu = QtWidgets.QMenu("Import/Export:", menu)

        if solver:
            import_export_menu.addAction(export_driver_action)
            import_export_menu.addAction(export_all_action)
            import_export_menu.addSeparator()
        import_export_menu.addAction(import_driver_action)

        add_menu = QtWidgets.QMenu("Add:", menu)
        add_menu.addAction(add_driven_action)

        utilities_menu = QtWidgets.QMenu("Utilities:", menu)
        utilities_menu.addAction(zero_base_pose_action)

        if solver:
            # if the solver is enabled show the edit and otherwise show the enable
            if solver.is_enabled:
                menu.addAction(edit_action)
            else:
                menu.addAction(enable_action)
            menu.addSeparator()
            menu.addMenu(select_menu)
            menu.addMenu(add_menu)
            menu.addMenu(mirror_menu)
            menu.addMenu(utilities_menu)

        menu.addMenu(import_export_menu)

        menu.popup(self.win.driver_LIST.mapToGlobal(point))

    def get_selected_solvers(self):
        """gets the selected solvers"""

        selected_items = self.win.driver_LIST.selectedItems()

        selected_solvers = []
        if selected_items:
            for item in selected_items:
                solver = item.data(QtCore.Qt.UserRole)
                selected_solvers.append(solver)
        return selected_solvers

    def get_selected_poses(self):
        """gets the selected poses"""

        selected_items = self.win.pose_LIST.selectedItems()
        selected_poses = []
        if selected_items:
            for item in selected_items:
                pose = item.text()
                selected_poses.append(pose)
        return selected_poses

    def add_pose(self):
        """add a new pose to the driver"""

        selected_solvers = self.get_selected_solvers()

        if not selected_solvers:
            OpenMaya.MGlobal.displayError('PoseWrangler: You must have a driver selected!')
            return

        solver = selected_solvers[-1]
        pose_name, ok = QtWidgets.QInputDialog.getText(self, 'text', 'Pose Name:')
        if pose_name:
            solver.add_pose(pose_name)
            # self.win.edit_pose_BTN.setEnabled(True)
            self.load_poses()
        else:
            cmds.warning('PoseWrangler: You must enter a pose name to add a pose.')

    def edit_pose(self):
        """updates the current pose"""

        poses = self.get_selected_poses()
        if not poses:
            return
        pose = poses[-1]
        selected_solvers = self.get_selected_solvers()
        if not selected_solvers:
            OpenMaya.MGlobal.displayError('PoseWrangler: You must have a driver selected!')
            return

        solver = selected_solvers[-1]
        solver.update_pose(pose)

    def delete_pose(self):
        """deletes the selected pose"""

        poses = self.get_selected_poses()
        if not poses:
            return
        pose = poses[-1]
        selected_solvers = self.get_selected_solvers()
        if not selected_solvers:
            OpenMaya.MGlobal.displayError('PoseWrangler: You must have a driver selected!')
            return

        solver = selected_solvers[-1]
        solver.delete_pose(pose)
        self.load_poses()

    def driver_changed(self):
        """function that gets called with the driver/solver is clicked"""

        selected_solvers = self.get_selected_solvers()

        self.win.driven_transforms_LIST.clear()
        if selected_solvers:
            solver = selected_solvers[-1]
            driven_transforms = solver.driven_transforms
            if driven_transforms:
                for transform in driven_transforms:
                    item = QtWidgets.QListWidgetItem(transform)
                    self.win.driven_transforms_LIST.addItem(item)
        else:
            self.win.driver_transform_LINE.setText("")

        self.refresh_ui_state()
        self.load_poses()

    def driven_changed(self):
        """select the driven transforms when picked in the UI"""

        selected_items = self.win.driven_transforms_LIST.selectedItems()
        cmds.select(cl=1)
        for item in selected_items:
            cmds.select(item.text(), add=1)

    def select_driver(self):
        """selects the driver(s)"""

        cmds.select(cl=1)
        selected_solvers = self.get_selected_solvers()
        for solver in selected_solvers:
            cmds.select(solver.driving_transform, add=1)

    def select_driven(self):
        """selects the driven"""
        cmds.select(cl=1)
        selected_solvers = self.get_selected_solvers()
        for solver in selected_solvers:
            cmds.select(solver.driven_transforms, add=1)

    def select_solver(self):
        """selects the solver DG node"""

        cmds.select(cl=1)
        selected_solvers = self.get_selected_solvers()
        for solver in selected_solvers:
            cmds.select(solver.name, add=1)

    def bake_poses(self):
        """bakes the poses to the timeline"""

        selected_solvers = self.get_selected_solvers()
        if selected_solvers:
            for solver in selected_solvers:
                solver.bake_poses_to_timeline()

    def add_new_driven(self):
        """adds new driven transforms to the selected drivers"""

        selected_items = self.win.driver_LIST.selectedItems()

        sl = cmds.ls(sl=1)
        if not sl:
            OpenMaya.MGlobal.displayError("No driven object selected, please select a driven object to add")

        selected_solvers = self.get_selected_solvers()
        if selected_solvers:
            for solver in selected_solvers:
                for s in sl:
                    solver.add_driven(s)

        self.load_drivers(selected_items[-1].text())

    def edit_driver(self):
        """set the drivers into edit mode"""
        selected_solvers = self.get_selected_solvers()
        if selected_solvers:
            for solver in selected_solvers:
                solver.is_driving(False)

        self.refresh_ui_state()

    def enable_driver(self):
        """enables the drivers into finishes edit mode"""
        selected_solvers = self.get_selected_solvers()
        if selected_solvers:
            for solver in selected_solvers:
                solver.is_driving(True)

        self.refresh_ui_state()

    def toggle_edit(self):
        """toggle the edit"""

        selected_solvers = self.get_selected_solvers()
        if selected_solvers:
            solver = selected_solvers[-1]
            if solver.is_enabled:
                solver.is_driving(False)
            else:
                solver.is_driving(True)

        self.refresh_ui_state()

    def refresh_ui_state(self):
        """refresh the UI state"""

        selected_solvers = self.get_selected_solvers()
        if selected_solvers:
            solver = selected_solvers[-1]

            self.win.driver_transform_LINE.setText(solver.driving_transform)

            # enable buttons that should be available when the driver is selected
            self.win.toggle_edit_BTN.setEnabled(True)
            self.win.delete_driver_BTN.setEnabled(True)

            if solver.is_enabled:
                self.win.toggle_edit_BTN.setText("EDIT")
            else:
                self.win.toggle_edit_BTN.setText("FINISH EDITING (ENABLE)")

            self.win.add_pose_BTN.setEnabled(True)
            self.win.add_driven_BTN.setEnabled(True)
            self.win.select_driver_BTN.setEnabled(True)

            self.win.copy_driven_trs_BTN.setEnabled(True)
            self.win.paste_driven_trs_BTN.setEnabled(True)

            selected_poses = self.get_selected_poses()
            if selected_poses:
                self.win.edit_pose_BTN.setEnabled(True)
                self.win.delete_pose_BTN.setEnabled(True)
                self.win.mirror_pose_BTN.setEnabled(True)

        else:
            self.win.add_pose_BTN.setEnabled(False)
            self.win.add_driven_BTN.setEnabled(False)

            self.win.toggle_edit_BTN.setEnabled(False)
            self.win.delete_driver_BTN.setEnabled(False)
            self.win.driver_transform_LINE.setText("")
            self.win.select_driver_BTN.setEnabled(False)

            # pose buttons
            self.win.edit_pose_BTN.setEnabled(False)
            self.win.delete_pose_BTN.setEnabled(False)
            self.win.mirror_pose_BTN.setEnabled(False)

            self.win.copy_driven_trs_BTN.setEnabled(False)
            self.win.paste_driven_trs_BTN.setEnabled(False)

        for i in range(self.win.driver_LIST.count()):
            item = self.win.driver_LIST.item(i)
            solver = item.data(QtCore.Qt.UserRole)
            if not solver.is_enabled:
                item.setText(solver.name + " (Editing)")
            else:
                item.setText(solver.name)

    def pose_changed(self):
        """called when the pose selection is changed"""

        selected_poses = self.get_selected_poses()
        if selected_poses:
            selected_pose = selected_poses[-1]
            selected_solvers = self.get_selected_solvers()
            solver = selected_solvers[-1]
            if selected_pose in solver.pose_dict.keys():
                solver.assume_pose(selected_pose)
            else:
                cmds.warning('Pose ' + selected_pose + ' not found in pose dictionary')
        self.refresh_ui_state()

    def load_drivers(self, selected=None):
        """loads all the RBF node drivers into the driver list widget"""

        self.win.driver_LIST.clear()
        drivers = [node for node in cmds.ls(type=self._node_name)]
        selected_item = None
        for driver in drivers:
            item = QtWidgets.QListWidgetItem(driver)
            solver = poseWrangler.UE4PoseDriver(existing_interpolator=driver)
            item.setData(QtCore.Qt.UserRole, solver)
            if selected and selected == driver:
                selected_item = item

            self.win.driver_LIST.addItem(item)

        self.win.driver_LIST.sortItems(QtCore.Qt.AscendingOrder)
        if selected_item:
            self.win.driver_LIST.setCurrentItem(selected_item)

        self.refresh_ui_state()
        self.load_poses()

    def load_poses(self):
        """loads the poses for the current driver"""

        self.win.pose_LIST.clear()
        selected_solvers = self.get_selected_solvers()
        if selected_solvers:
            solver = selected_solvers[-1]
            for target in solver.pose_dict.keys() or []:
                item = QtWidgets.QListWidgetItem()
                item.setText(target)
                item.setData(QtCore.Qt.UserRole, target)

                self.win.pose_LIST.addItem(item)

        # sort the items
        self.win.pose_LIST.sortItems(QtCore.Qt.AscendingOrder)

    def mirror_pose(self):
        """mirrors the selected pose for the current driver"""

        selected_solvers = self.get_selected_solvers()
        if not selected_solvers:
            return

        solver = selected_solvers[-1]
        selected_poses = self.get_selected_poses()
        if selected_poses:
            for selected_pose in selected_poses:
                pose_dict = solver.pose_dict
                if selected_pose in pose_dict.keys():
                    poseWrangler.mirror_pose_driver(
                        solver.name, pose=selected_pose
                    )
                else:
                    cmds.warning('Pose ' + selected_pose + ' not found in pose dictionary')

    def mirror_driver(self):
        """mirrors all poses for the selected drivers"""

        selected_solvers = self.get_selected_solvers()
        for solver in selected_solvers:
            poseWrangler.mirror_pose_driver(solver.name)

        self.load_drivers()

    def import_drivers(self, file_path=""):
        """imports the drivers"""

        path = file_path or QtWidgets.QFileDialog.getOpenFileName(
            self, "Pose Wrangler Format",
            "", "JSON (*.json)"
        )[0]
        if path == "":
            return

        if not os.path.isfile(path):
            OpenMaya.MGlobal.displayError(path + " is not a valid file.")
            return

        poseWrangler.import_drivers(path)

        self.load_drivers()
        self.load_poses()

    def export_driver(self):
        """exports the selected drivers"""

        selected_solvers = self.get_selected_solvers()
        solver_names = []
        for solver in selected_solvers:
            solver_names.append(solver.name)

        self._export(solver_names)

    def export_all(self):
        """exports all rbf nodes"""
        nodes = cmds.ls(type=self._node_name)
        if not nodes:
            return

        self._export(nodes)

    def _export(self, drivers):
        """exports the drivers passed in"""

        file_path = QtWidgets.QFileDialog.getSaveFileName(None, "Pose Wrangler Format", "", "*.json")[0]
        if file_path == "":
            return

            # do the export
        poseWrangler.export_drivers(drivers, file_path)

    def create_driver(self):
        """creates a new driver"""

        sel = cmds.ls(sl=1)
        if not sel:
            OpenMaya.MGlobal.displayError(
                'PoseWrangler: You must select a driving transform to CREATE a pose interpolator'
            )
            return

        # takes all driven and the driving input is last
        interp_name, ok = QtWidgets.QInputDialog.getText(self, 'text', 'Driver Name:')
        if interp_name:
            driver = poseWrangler.UE4PoseDriver()
            driver.create_pose_driver_system(interp_name, sel[-1], sel[0:-1])
            self._current_solver = driver
        # refresh the combobox and set this interpolator as current
        self.load_drivers(selected=self._current_solver.name if self._current_solver else None)

    def delete_driver(self):
        """deletes the selected drivers"""

        selected_solvers = self.get_selected_solvers()
        if selected_solvers:
            for solver in selected_solvers:
                solver.delete()

        self.load_drivers()
        self.load_poses()

    def copy_driven_trs(self):
        """copies the driven TRS for pasting in different poses"""

        selected_solvers = self.get_selected_solvers()
        if selected_solvers:
            for solver in selected_solvers:
                solver.copy_driven_trs()

    def paste_driven_trs(self):
        """pastes the driven TRS and lets you multiply it"""

        mult = self.paste_mult_DSPN.value()
        selected_solvers = self.get_selected_solvers()
        if selected_solvers:
            for solver in selected_solvers:
                solver.paste_driven_trs(mult=mult)

    def zero_base_poses(self):
        """zeros out the selected solver base poses"""

        selected_solvers = self.get_selected_solvers()
        if selected_solvers:
            for solver in selected_solvers:
                solver.zero_base_pose()

    def _upgrade_scene(self):
        file_path = upgrade.upgrade_scene(clear_scene=True)
        LOG.info("Successfully Exported Current Scene")
        self.event_upgrade_dispatch.upgrade.emit(file_path)
        self.close()


def showUI():
    """show the UI"""
    pose_wrangler_widget = PoseWrangler()
    # show the UI
    pose_wrangler_widget.show(dockable=True)
