#  Copyright Epic Games, Inc. All Rights Reserved.
from maya import cmds
from epic_pose_wrangler.v2.model import base_action, pose_blender


class ZeroDefaultPoseAction(base_action.BaseAction):
    __display_name__ = "Zero Default Pose Transforms"
    __tooltip__ = ""
    __category__ = "Utilities"

    @classmethod
    def validate(cls, ui_context):
        return bool(ui_context.current_solvers)

    def execute(self, ui_context=None, solver=None, **kwargs):
        from PySide2 import QtWidgets
        if not ui_context:
            ui_context = self.api.get_ui_context()
        if ui_context:
            solver = self.api.get_rbf_solver_by_name(ui_context.current_solvers[-1])
        if not solver:
            solver = self.api.current_solver

        # Go to the default pose
        solver.go_to_pose('default')
        # Assume edit is enabled
        edit = True
        if not self.api.get_solver_edit_status(solver):
            # If edit isn't enabled, store the current enabled state and enable editing
            edit = False
            self.api.edit_solver(edit=True, solver=solver)

        # Reset the driven transforms
        for node in solver.driven_nodes(type=pose_blender.UEPoseBlenderNode.node_type):
            cmds.setAttr('{node}.translate'.format(node=node), 0.0, 0.0, 0.0)
            cmds.setAttr('{node}.rotate'.format(node=node), 0.0, 0.0, 0.0)
            cmds.setAttr('{node}.scale'.format(node=node), 1.0, 1.0, 1.0)

        # Update the pose
        self.api.update_pose(pose_name='default', solver=solver)
        # Restore edit status
        self.api.edit_solver(edit=edit, solver=solver)
