from PySide2 import QtGui
from PySide2 import QtWidgets
from PySide2 import QtCore
from PySide2 import QtUiTools


from shiboken2 import wrapInstance
import pyside2uic as pysideuic

import time
import os
import traceback
import datetime
import os.path as path

import maya.cmds as cmds
import maya.OpenMaya as OpenMaya
import maya.OpenMayaUI as OpenMayaUI

import xml.etree.ElementTree as xml
from cStringIO import StringIO

import ui_window
import qt_util
import poseWrangler
import palette


########################################################################
########################################################################

#The UI file must live in the same place as this file
uiPath = os.path.dirname(__file__) + "/poseWranglerUI.ui"
form_class, base_class = qt_util.load_ui(uiPath)


class PoseWrangler(ui_window.UIWindow, form_class):
    """class for the pose wranglerUI"""

    ui_name = "poseWranglerWindow"

    def __init__(self, parent=qt_util.maya_window()):
        super(PoseWrangler, self).__init__(parent)

        self.setupUi(self)
        self.setWindowTitle("Pose Wrangler UI")

        # buttons
        self.add_pose_BTN.pressed.connect(self.add_pose)

        #self.setCentralWidget(self.win)

        if not cmds.pluginInfo('MayaUE4RBFPlugin2018', q=True, loaded=True):
            cmds.loadPlugin('MayaUE4RBFPlugin2018')

        # refresh the driver cmd list
        self.load_drivers()

        # calling create from the combobox
        #self.pose_driver_CMB.currentIndexChanged.connect(self.pose_driver_changed_FN)

        # hook up utils UI
        self.bake_poses_BTN.pressed.connect(self.bake_poses)

        self.pose_LIST.itemSelectionChanged.connect(self.pose_changed)
        self.edit_pose_BTN.pressed.connect(self.edit_pose)
        self.delete_pose_BTN.pressed.connect(self.delete_pose)

        self.driver_LIST.itemSelectionChanged.connect(self.driver_changed)
        self.driver_LIST.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.driver_LIST.customContextMenuRequested.connect(self.driver_popup)

        self.driven_transforms_LIST.itemSelectionChanged.connect(self.driven_changed)

        self.select_driver_BTN.pressed.connect(self.select_driver)
        self.add_driven_BTN.pressed.connect(self.add_new_driven)

        self.mirror_pose_BTN.pressed.connect(self.mirror_pose)

        self.copy_driven_trs_BTN.pressed.connect(self.copy_driven_trs)
        self.paste_driven_trs_BTN.pressed.connect(self.paste_driven_trs)

        self.create_driver_BTN.pressed.connect(self.create_driver)
        self.delete_driver_BTN.pressed.connect(self.delete_driver)

        # setup the 'driving enabled' check box functionality
        self.toggle_edit_BTN.clicked.connect(self.toggle_edit)
        self.refresh_BTN.clicked.connect(self.load_drivers)

        self.driver_transform_LINE.setReadOnly(True)

        # refresh the tree
        self.load_poses()

        self.set_stylesheet()

    def show(self):
        super(PoseWrangler, self).show()


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

        menu = QtWidgets.QMenu("Options:", self.driver_LIST)

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
            #if the solver is enabled show the edit and otherwise show the enable
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

        menu.popup(self.driver_LIST.mapToGlobal(point))



    def get_selected_solvers(self):
        """gets the selected solvers"""

        selected_items = self.driver_LIST.selectedItems()

        selected_solvers = []
        if selected_items:
            for item in selected_items:
                solver = item.data(QtCore.Qt.UserRole)
                selected_solvers.append(solver)
        return selected_solvers


    def get_selected_poses(self):
        """gets the selected poses"""

        selected_items = self.pose_LIST.selectedItems()
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
            #self.edit_pose_BTN.setEnabled(True)
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

        self.driven_transforms_LIST.clear()
        if selected_solvers:
            solver = selected_solvers[-1]
            driven_transforms = solver.driven_transforms
            if driven_transforms:
                for transform in driven_transforms:
                    item = QtWidgets.QListWidgetItem(transform)
                    self.driven_transforms_LIST.addItem(item)
        else:
            self.driver_transform_LINE.setText("")

        self.refresh_ui_state()
        self.load_poses()

    def driven_changed(self):
        """select the driven transforms when picked in the UI"""

        selected_items = self.driven_transforms_LIST.selectedItems()
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

        selected_items = self.driver_LIST.selectedItems()

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

            self.driver_transform_LINE.setText(solver.driving_transform)

            #enable buttons that should be available when the driver is selected
            self.toggle_edit_BTN.setEnabled(True)
            self.delete_driver_BTN.setEnabled(True)

            if solver.is_enabled:
                self.toggle_edit_BTN.setText("EDIT")
            else:
                self.toggle_edit_BTN.setText("FINISH EDITING (ENABLE)")

            self.add_pose_BTN.setEnabled(True)
            self.add_driven_BTN.setEnabled(True)
            self.select_driver_BTN.setEnabled(True)

            self.copy_driven_trs_BTN.setEnabled(True)
            self.paste_driven_trs_BTN.setEnabled(True)

            selected_poses = self.get_selected_poses()
            if selected_poses:
                self.edit_pose_BTN.setEnabled(True)
                self.delete_pose_BTN.setEnabled(True)
                self.mirror_pose_BTN.setEnabled(True)

        else:
            self.add_pose_BTN.setEnabled(False)
            self.add_driven_BTN.setEnabled(False)

            self.toggle_edit_BTN.setEnabled(False)
            self.delete_driver_BTN.setEnabled(False)
            self.driver_transform_LINE.setText("")
            self.select_driver_BTN.setEnabled(False)

            #pose buttons
            self.edit_pose_BTN.setEnabled(False)
            self.delete_pose_BTN.setEnabled(False)
            self.mirror_pose_BTN.setEnabled(False)

            self.copy_driven_trs_BTN.setEnabled(False)
            self.paste_driven_trs_BTN.setEnabled(False)

        for i in range(self.driver_LIST.count()):
            item = self.driver_LIST.item(i)
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

        self.driver_LIST.clear()
        self.drivers = [node for node in cmds.ls(type='UE4RBFSolverNode')]
        selectedItem = None
        if self.drivers:
            for driver in self.drivers:
                item = QtWidgets.QListWidgetItem(driver)
                solver = poseWrangler.UE4PoseDriver(existing_interpolator=driver)
                item.setData(QtCore.Qt.UserRole, solver)
                if selected:
                    if selected == driver:
                        selectedItem = item

                self.driver_LIST.addItem(item)

        self.driver_LIST.sortItems( QtCore.Qt.AscendingOrder)
        if selectedItem:
            self.driver_LIST.setCurrentItem(selectedItem)

        self.refresh_ui_state()
        self.load_poses()

    def load_poses(self):
        """loads the poses for the current driver"""
        
        self.pose_LIST.clear()
        selected_solvers = self.get_selected_solvers()
        if selected_solvers:
            solver = selected_solvers[-1]
            for target in solver.pose_dict.keys() or []:
                item = QtWidgets.QListWidgetItem()
                item.setText(target)
                item.setData(QtCore.Qt.UserRole, target)

                self.pose_LIST.addItem(item)

        #sort the items
        self.pose_LIST.sortItems(QtCore.Qt.AscendingOrder)
        
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
                    poseWrangler.mirror_pose_driver(solver.name, pose=selected_pose)
                else:
                    cmds.warning('Pose ' + selected_pose + ' not found in pose dictionary')

            
    def mirror_driver(self):
        """mirrors all poses for the selected drivers"""

        selected_solvers = self.get_selected_solvers()
        for solver in selected_solvers:
            poseWrangler.mirror_pose_driver(solver.name)


        self.load_drivers()
            

    def import_drivers(self):
        """imports the drivers"""

        file_path = QtWidgets.QFileDialog.getOpenFileName(self, "Pose Wrangler Format", "", "JSON (*.json)")[0]
        if file_path == "":
            return
        
        if not os.path.isfile(file_path):
            OpenMaya.MGlobal.displayError(file_path + " is not a valid file.")
            return
        
        poseWrangler.import_drivers(file_path)

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
        nodes = cmds.ls(type='UE4RBFSolverNode')
        if not nodes:
            return        
        
        self._export(nodes)
        
        
    def _export(self, drivers):
        """exports the drivers passed in"""

        file_path = QtWidgets.QFileDialog.getSaveFileName(None, "Pose Wrangler Format", "", "*.json")[0]
        if file_path == "":
            return        
        
        #do the export
        poseWrangler.export_drivers(drivers, file_path)

    def create_driver(self):
        """creates a new driver"""

        sel = cmds.ls(sl=1)
        if not sel:
            OpenMaya.MGlobal.displayError('PoseWrangler: You must select a driving transform to CREATE a pose interpolator')
            return

        # takes all driven and the driving input is last
        interp_name, ok = QtWidgets.QInputDialog.getText(self, 'text', 'Driver Name:')
        if interp_name:
            driver = poseWrangler.UE4PoseDriver()
            driver.create_pose_driver_system(interp_name, sel[-1], sel[0:-1])
            self.current_solver = driver
        # refresh the combobox and set this interpolator as current
        self.load_drivers(selected=self.current_solver.name)


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


def showUI():
    """show the UI"""

    #show the UI
    PoseWrangler.showUI()
