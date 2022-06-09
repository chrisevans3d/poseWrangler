#  Copyright Epic Games, Inc. All Rights Reserved.

import traceback
from functools import partial

from maya import cmds

from epic_pose_wrangler.log import LOG
from epic_pose_wrangler.v2.model import base_extension, pose_blender


class BakePosesToTimeline(base_extension.PoseWranglerExtension):
    __category__ = "Core Extensions"

    @property
    def view(self):
        if self._view is not None:
            return self._view
        from PySide2 import QtWidgets
        self._view = QtWidgets.QPushButton("Bake Poses To Timeline")
        self._view.clicked.connect(partial(self.execute, None))
        return self._view

    def execute(self, context=None, **kwargs):
        if context is None:
            context = self.api.get_context()
        if context.current_solver is not None:
            bake_poses_to_timeline(solver=context.current_solver, view=self._display_view)


def bake_poses_to_timeline(start_frame=0, anim_layer=None, solver=None, view=False):
    """
    Bakes the poses to the timeline and sets the time range to the given animation.
    :param start_frame :type int: start frame of he baked animation
    :param anim_layer :type str: if given the animations will be baked on that layer or created if it doesn't exist
    :param solver :type api.RBFNode: solver reference
    :param view :type bool: is the view present
    """
    # Grab all the transforms for the solver
    transforms = solver.drivers()
    transforms.extend(solver.driven_nodes(pose_blender.UEPoseBlenderNode.node_type))

    bake_enabled = True
    pose_list = []
    # Set default anim layer if one isn't specified
    if not anim_layer:
        anim_layer = "BaseAnimation"
    # If the layer doesnt exist, create it
    if not cmds.animLayer(anim_layer, query=True, exists=True):
        cmds.animLayer(anim_layer)
    try:
        cmds.autoKeyframe(e=1, st=0)
        # If we are running with the view, provide a popup
        if view:
            from PySide2 import QtWidgets
            msg = ("This will bake the poses to the timeline, change your time range, "
                   "and delete inputs on driving and driven transforms.\n"
                   "Do you want this to happen?")

            ret = QtWidgets.QMessageBox.warning(
                None, "WARNING: DESTRUCTIVE FUNCTION", msg,
                QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel,
                QtWidgets.QMessageBox.Cancel
            )
            if ret == QtWidgets.QMessageBox.StandardButton.Ok:
                bake_enabled = True
                cmds.undoInfo(openChunk=True, undoName='Bake poses to timeline')
            else:
                bake_enabled = False

        # If we are baking, do the bake
        if bake_enabled:
            i = start_frame
            for pose_name in solver.poses():
                # let's key it on the previous and next frames before we pose it
                cmds.select(transforms)
                cmds.animLayer(anim_layer, addSelectedObjects=True, e=True)
                cmds.setKeyframe(transforms, t=[(i - 1), (i + 1)], animLayer=anim_layer)

                # assume the pose
                solver.go_to_pose(pose_name)

                cmds.setKeyframe(transforms, t=[i], animLayer=anim_layer)

                pose_list.append(pose_name)

                # increment to next keyframe
                i += 1

            # set the range to the number of keyframes
            cmds.playbackOptions(minTime=0, maxTime=i, animationStartTime=0, animationEndTime=i - 1)
            cmds.dgdirty(a=1)
            return pose_list

        cmds.dgdirty(a=1)
    except Exception as e:
        LOG.error(traceback.format_exc())
    finally:
        cmds.undoInfo(closeChunk=True)
