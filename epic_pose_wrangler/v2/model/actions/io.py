#  Copyright Epic Games, Inc. All Rights Reserved.
from epic_pose_wrangler.v2.model import base_action


class ExportSelectedAction(base_action.BaseAction):
    __display_name__ = "Export Selected Solvers"
    __tooltip__ = "Exports the currently selected solver nodes in the scene to a JSON file"
    __category__ = "IO"

    @classmethod
    def validate(cls, ui_context):
        return bool(ui_context.current_solvers)

    def execute(self, ui_context=None, **kwargs):
        from PySide2 import QtWidgets

        if not ui_context:
            ui_context = self.api.get_ui_context()
        if not ui_context:
            return
        file_path = QtWidgets.QFileDialog.getSaveFileName(None, "Pose Wrangler File", "", "*.json")[0]
        # If no path is specified, exit early
        if file_path == "":
            return
        self.api.serialize_to_file(file_path, ui_context.current_solvers)


class ExportAllAction(base_action.BaseAction):
    __display_name__ = "Export All Solvers"
    __tooltip__ = "Exports all solver nodes in the scene to a JSON file"
    __category__ = "IO"

    @classmethod
    def validate(cls, ui_context):
        return bool(ui_context.current_solvers)

    def execute(self, ui_context=None, **kwargs):
        from PySide2 import QtWidgets

        if not ui_context:
            ui_context = self.api.get_ui_context()
        if not ui_context:
            return
        file_path = QtWidgets.QFileDialog.getSaveFileName(None, "Pose Wrangler File", "", "*.json")[0]
        # If no path is specified, exit early
        if file_path == "":
            return
        self.api.serialize_to_file(file_path, None)


class ImportFromFileAction(base_action.BaseAction):
    __display_name__ = "Import Solvers"
    __tooltip__ = "Imports solver nodes into the scene from a JSON file"
    __category__ = "IO"

    @classmethod
    def validate(cls, ui_context):
        return bool(ui_context.current_solvers)

    def execute(self, ui_context=None, **kwargs):
        from PySide2 import QtWidgets

        if not ui_context:
            ui_context = self.api.get_ui_context()
        if not ui_context:
            return
        file_path = QtWidgets.QFileDialog.getOpenFileName(None, "Pose Wrangler File", "", "*.json")[0]
        # If no path is specified, exit early
        if file_path == "":
            return
        self.api.deserialize_from_file(file_path)
