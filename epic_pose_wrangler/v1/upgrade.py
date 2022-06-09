#  Copyright Epic Games, Inc. All Rights Reserved.
import collections
import json
import os
import tempfile
import uuid

from maya import cmds

from epic_pose_wrangler.log import LOG
from epic_pose_wrangler.v1 import poseWrangler


def upgrade_scene(clear_scene=True):
    drivers = cmds.ls(type='UE4RBFSolverNode')
    output_data = collections.OrderedDict()
    for driver in drivers:

        driver_data = collections.OrderedDict()
        driver_obj = poseWrangler.UE4PoseDriver(existing_interpolator=driver)

        solver = driver_obj.solver
        driver_name = driver_obj.name.replace("_UE4RBFSolver", "_UERBFSolver")
        driver_data['solver_name'] = driver_name
        solver_attrs = cmds.listAttr(solver, keyable=True)
        for solver_attr in solver_attrs:
            try:
                value = cmds.getAttr(solver + "." + solver_attr)
            except:
                continue
            driver_data[solver_attr] = value

        driver_data['drivers'] = [driver_obj.driving_transform]
        driver_data['driven_transforms'] = driver_obj.driven_transforms
        driver_data['mode'] = cmds.getAttr("{driver}.mode".format(driver=driver))
        driver_data['radius'] = cmds.getAttr("{driver}.radius".format(driver=driver))
        driver_data['weightThreshold'] = cmds.getAttr("{driver}.weightThreshold".format(driver=driver))
        driver_data['automaticRadius'] = cmds.getAttr("{driver}.automaticRadius".format(driver=driver))
        driver_data['distanceMethod'] = cmds.getAttr("{driver}.distanceMethod".format(driver=driver))
        driver_data['poses'] = collections.OrderedDict()
        driver_transform = driver_obj.driving_transform
        sorted_poses = sorted([p for p in driver_obj.pose_dict.keys()])
        for pose in sorted_poses:
            mx_list = driver_obj.pose_dict[pose]
            driver_obj.assume_pose(pose)
            pose_data = {
                "drivers": [cmds.xform(driver_transform, query=True, matrix=True, objectSpace=True)],
                "driven": {transform: cmds.xform(transform, query=True, matrix=True, objectSpace=True)
                           for transform in driver_obj.driven_transforms},
                "function_type": "DefaultFunctionType",
                "scale_factor": 1.0,
                "distance_method": "DefaultMethod"
            }
            # Changing default pose name
            if pose == 'base_pose':
                pose = 'default'
            driver_data['poses'][pose] = pose_data
        output_data[driver_name] = driver_data

        # zero the pose
        driver_obj.assume_pose("base_pose")
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, "pose_wrangler-{uuid}.json".format(uuid=uuid.uuid4()))
    with open(file_path, 'w') as outfile:

        json.dump(output_data, outfile, indent=4, separators=(",", ":"))

    LOG.debug("Writing scene to {file_path}".format(file_path=file_path))
    if clear_scene:
        cmds.delete(cmds.ls(type='UE4RBFSolverNode'))
        cmds.delete(cmds.ls(type='UE4PoseBlenderNode'))
        cmds.delete(cmds.ls('*_pose', type='network'))
        for joint in cmds.ls(type='joint'):
            for attr in ['mx_pose', 'ue4_rbf_solver', 'blenderNode']:
                if cmds.attributeQuery(attr, node=joint, exists=True):
                    cmds.deleteAttr("{joint}.{attr}".format(joint=joint, attr=attr))
    return file_path
