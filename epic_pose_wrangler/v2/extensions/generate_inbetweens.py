#  Copyright Epic Games, Inc. All Rights Reserved.
from functools import partial

from epic_pose_wrangler.v2.model import base_extension
from epic_pose_wrangler.v2.extensions import copy_paste_trs


class GenerateInbetweens(base_extension.PoseWranglerExtension):
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

        generate_inbetweens_button = QtWidgets.QPushButton("Generate Inbetweens")
        button_layout.addWidget(generate_inbetweens_button)

        spin_label = QtWidgets.QLabel("Pose Count: ")
        button_layout.addWidget(spin_label)

        spin_box = QtWidgets.QSpinBox()
        spin_box.setMinimum(1)
        spin_box.setSingleStep(1)
        spin_box.setValue(1)
        button_layout.addWidget(spin_box)

        generate_inbetweens_button.clicked.connect(partial(self.generate_inbetweens, lambda: spin_box.value()))

        return self._view

    def generate_inbetweens(self, count=1, pose_prefix="pose"):
        """
        Generate inbetween poses between the current position and the default pose
        :param count :type int: number of poses to generate
        :param pose_prefix :type: name of the pose
        """
        context = self.api.get_context()
        if callable(count):
            count = count()

        solver = context.current_solver
        copy_paste_trs_action = self.api.get_extension_by_type(copy_paste_trs.BakePosesToTimeline)
        copy_paste_trs_action.copy_driven_trs(solver=solver)
        copy_paste_trs_action.copy_driver_trs(solver=solver)

        # Calculate the multiplier increment based on the number of desired poses
        multiplier_increment = 1.0 / float((count + 1))
        # Set the start multiplier
        multiplier = 1.0
        # Iterate through the number of desired poses
        for i in range(count):
            # Generate the new multiplier
            multiplier -= multiplier_increment
            # Paste the driver and driven translate, rotate and scale based on the new multiplier
            # Note: Driver only gets rotate and scale applied to it.
            copy_paste_trs_action.paste_driven_trs(multiplier)
            copy_paste_trs_action.paste_driver_trs(multiplier)
            # Create a new pose at this position
            self.api.create_pose(pose_name="{pose_prefix}_{i}".format(pose_prefix=pose_prefix, i=i), solver=solver)
