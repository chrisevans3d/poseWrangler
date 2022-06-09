#  Copyright Epic Games, Inc. All Rights Reserved.
from maya import cmds

from epic_pose_wrangler.v2.model import base_action


class SelectSolverAction(base_action.BaseAction):
    __display_name__ = "Select Solver Node(s)"
    __tooltip__ = "Selects the currently selected solver nodes in the scene"
    __category__ = "Select"

    @classmethod
    def validate(cls, ui_context):
        return bool(ui_context.current_solvers)

    def execute(self, ui_context=None, **kwargs):
        if not ui_context:
            ui_context = self.api.get_ui_context()
        if not ui_context:
            return
        cmds.select(ui_context.current_solvers, replace=True)


class SelectDriverAction(base_action.BaseAction):
    __display_name__ = "Select Driver Node(s)"
    __tooltip__ = "Selects the driver nodes in the scene"
    __category__ = "Select"

    @classmethod
    def validate(cls, ui_context):
        return bool(ui_context.drivers)

    def execute(self, ui_context=None, **kwargs):
        if not ui_context:
            ui_context = self.api.get_ui_context()
        if not ui_context:
            return
        cmds.select(ui_context.drivers, replace=True)


class SelectDrivenAction(base_action.BaseAction):
    __display_name__ = "Select Driven Node(s)"
    __tooltip__ = "Selects the driven nodes in the scene"
    __category__ = "Select"

    @classmethod
    def validate(cls, ui_context):
        return bool(ui_context.driven)

    def execute(self, ui_context=None, **kwargs):
        if not ui_context:
            ui_context = self.api.get_ui_context()
        if not ui_context:
            return
        cmds.select(ui_context.driven, replace=True)
