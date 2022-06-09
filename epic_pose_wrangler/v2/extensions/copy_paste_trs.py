#  Copyright Epic Games, Inc. All Rights Reserved.

import traceback
from functools import partial

from maya import cmds

from epic_pose_wrangler.log import LOG
from epic_pose_wrangler.v2.model import base_extension, exceptions, pose_blender


class BakePosesToTimeline(base_extension.PoseWranglerExtension):
    __category__ = "Core Extensions"

    @property
    def view(self):
        if self._view is not None:
            return self._view
        from PySide2 import QtWidgets

        self._view = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        self._view.setLayout(layout)

        label = QtWidgets.QLabel("Copy/Paste Driven Transforms")
        layout.addWidget(label)

        button_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(button_layout)

        copy_button = QtWidgets.QPushButton("Copy")
        copy_button.clicked.connect(partial(self.copy_driven_trs, None))
        button_layout.addWidget(copy_button)

        paste_button = QtWidgets.QPushButton("Paste")
        button_layout.addWidget(paste_button)

        spin_label = QtWidgets.QLabel("Multiplier: ")
        button_layout.addWidget(spin_label)

        spin_box = QtWidgets.QDoubleSpinBox()
        spin_box.setMinimum(0.01)
        spin_box.setSingleStep(0.1)
        spin_box.setValue(1.0)
        button_layout.addWidget(spin_box)

        paste_button.clicked.connect(partial(self.paste_driven_trs, lambda: spin_box.value(), None))

        return self._view

    def execute(self, context=None, **kwargs):
        copy = kwargs.get('copy', False)
        driver = kwargs.get('driver', True)
        multiplier = kwargs.get('multiplier', 1.0)
        if context is None:
            context = self.api.get_context()
        if context.current_solver is not None:
            if copy:
                if driver:
                    self.copy_driver_trs()
                else:
                    self.copy_driven_trs()
            else:
                if driver:
                    self.paste_driver_trs(multiplier=multiplier)
                else:
                    self.paste_driven_trs(multiplier=multiplier)

    def copy_driven_trs(self, solver=None):
        """
        Copy the driven transforms translate, rotate and scale for the specified solver
        :param solver :type api.RBFNode: solver reference
        """
        context = self.api.get_context()
        solver = solver or context.current_solver
        CopyPasteTRS.copy_driven(solver)

    def paste_driven_trs(self, multiplier=1.0, solver=None):
        """
        Paste the driven transforms translate, rotate and scale based on the multiplier specified
        :param multiplier :type float: scale multiplier
        :param solver :type api.RBFNode: solver reference
        """
        # Get the solver if it hasn't been specified
        if callable(multiplier):
            multiplier = multiplier()
        context = self.api.get_context()
        solver = solver or context.current_solver
        edit_status = self.api.get_solver_edit_status(solver=solver)
        if not edit_status:
            self.api.edit_solver(edit=True, solver=solver)
        CopyPasteTRS.paste_driven(multiplier=multiplier)

    def copy_driver_trs(self, solver=None):
        """
        Copy the driver transforms translate, rotate and scale for the specified solver
        :param solver :type api.RBFNode: solver reference
        """
        context = self.api.get_context()
        # Get the solver if it hasn't been specified
        solver = solver or context.current_solver
        # Copy the driver transforms
        CopyPasteTRS.copy_driver(solver)

    def paste_driver_trs(self, multiplier=1.0):
        """
        Paste the driver transforms rotate and scale based on the multiplier specified
        :param multiplier :type float: scale multiplier
        """
        if callable(multiplier):
            multiplier = multiplier()
        CopyPasteTRS.paste_driver(multiplier=multiplier)


class TRSError(exceptions.exceptions.PoseWranglerException):
    pass


class CopyPasteTRS(object):
    """
    Class wrapper for copying and pasting TRS data
    """
    # Dicts to store the driver and driven data. Driver data is only used when auto generating poses
    TRS_DRIVEN_DATA = {}
    TRS_DRIVER_DATA = {}

    @classmethod
    def copy_driven(cls, solver):
        """
        Copy the driven transforms TRS data for the specified solver
        :param solver :type api.RBFNode: solver reference
        """
        cls._copy(
            transforms=solver.driven_nodes(pose_blender.UEPoseBlenderNode.node_type),
            target_datastore=cls.TRS_DRIVEN_DATA
        )

    @classmethod
    def paste_driven(cls, multiplier=1.0):
        """
        Paste the copied driven values onto the driven with the specified modifier
        :param multiplier :type float: multiplier value
        """
        cls._paste(multiplier=multiplier, target_datastore=cls.TRS_DRIVEN_DATA)

    @classmethod
    def copy_driver(cls, solver):
        """
        Copy the driver transforms TRS data for the specified solver
        :param solver :type api.RBFNode: solver reference
        """
        cls._copy(transforms=solver.drivers(), target_datastore=cls.TRS_DRIVER_DATA, attributes=['rotate', 'scale'])

    @classmethod
    def paste_driver(cls, multiplier=1.0):
        """
        Paste the copied driver values onto the driver with the specified modifier
        :param multiplier :type float: multiplier value
        """
        cls._paste(multiplier=multiplier, target_datastore=cls.TRS_DRIVER_DATA)

    @classmethod
    def _copy(cls, transforms, target_datastore, attributes=None):
        """
        Copy the specified transforms attributes to the specified datastore
        :param transforms :type list: list of maya transform nodes
        :param target_datastore :type dict: reference to cls.TRS_DRIVER_DATA or cls.TRS_DRIVEN_DATA
        :param attributes :type list: list of attribute names to store
        """
        # If no attributes are specified, use TRS
        if not attributes:
            attributes = ['translate', 'rotate', 'scale']
        # Clear the datastore before we copy
        target_datastore.clear()
        # For each transform, get the specified attributes and store them in a dictionary
        for transform in transforms:
            target_datastore[transform] = {attr: cmds.getAttr(
                "{transform}.{attr}".format(
                    transform=transform,
                    attr=attr
                )
            )[0]
                                           for attr in attributes}

        LOG.info("Successfully copied TRS for {transforms}".format(transforms=transforms))

    @classmethod
    def _paste(cls, multiplier, target_datastore):
        """
        Paste the attributes from the target_datastore multiplied by the given multiplier
        :param multiplier :type float: multiplier value
        :param target_datastore : type dict: reference to cls.TRS_DRIVER_DATA or cls.TRS_DRIVEN_DATA
        """
        # If the target datastore is empty, we can't paste
        if not target_datastore:
            raise TRSError("No data has been copied. Unable to paste")

        # Iterate through the items in the datastore
        for transform, data in target_datastore.items():
            # Iterate through the attribute names and values in the datastore
            for attr, values in data.items():
                # Set the attribute to the multiplied value
                try:
                    cmds.setAttr(
                        "{transform}.{attr}".format(transform=transform, attr=attr), values[0] * multiplier,
                                                                                     values[1] * multiplier,
                                                                                     values[2] * multiplier
                    )
                except:
                    traceback.print_exc()

            # Calculate and set the scale
            scale = [((s - 1.0) * multiplier) + 1 for s in data['scale']]
            try:
                cmds.setAttr("{driven}.scale".format(driven=transform), *scale)
            except:
                traceback.print_exc()

        LOG.info(
            "Successfully pasted TRS with multiplier: {multiplier} for {transforms}".format(
                multiplier=multiplier,
                transforms=list(target_datastore.keys())
            )
        )
