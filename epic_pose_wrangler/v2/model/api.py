#  Copyright Epic Games, Inc. All Rights Reserved.

import math
import re

import six
import json
from collections import OrderedDict

from maya import cmds
from maya import OpenMaya
from maya.api import OpenMaya as om

from epic_pose_wrangler.log import LOG
from epic_pose_wrangler.v2.model import exceptions, pose_blender, utils


class RBFNode(object):
    node_type = 'UERBFSolverNode'

    def __init__(self, node):
        """
        Initialize RBFNode on give node

        >>> node = cmds.createNode('UERBFSolverNode')
        >>> RBFNode(node)
        """

        if not cmds.objectType(node, isAType=self.node_type):
            raise TypeError('Invalid "{}" node: "{}"'.format(self.node_type, node))

        self._node = node

    def __repr__(self):
        """
        Returns class string representation
        """
        return '<{}>: {}'.format(self.node_type, self)

    def __str__(self):
        """
        Returns class as string
        """
        return str(self._node)

    def __eq__(self, other):
        """
        Overrides equals operator to allow for different RBFNode instances to be matched against each other
        """
        return str(self) == str(other)

    def set_defaults(self):
        """
        Sets node default values
        """
        self.set_mode('Interpolative')
        self.set_radius(45)
        self.set_automatic_radius(False)

    # -------------------------------------------------------------------------

    @classmethod
    def create(cls, name=None):
        """
        Create RBF node

        >>> rbf_node = RBFNode.create()
        """

        if name is None:
            name = '{}#'.format(cls.node_type)
        active_selection = cmds.ls(selection=True)
        # create node
        node = cmds.createNode(cls.node_type, name=name)
        rbf_node = cls(node)
        rbf_node.set_defaults()
        cmds.select(active_selection, replace=True)

        return rbf_node

    @classmethod
    def create_from_data(cls, data):
        """
        Creates RBF network from dictionary

        >>> new_joint = cmds.createNode('joint')
        >>> data = {'drivers': [new_joint], 'poses': {'drivers': {'default': [[1,0,0,0,0,1,0,0,0,0,1,0,2,0,0,1]]}}}
        >>> RBFNode.create_from_data(data)
        """

        if not cmds.objExists(data['solver_name']):
            rbf_node = cls.create(name=data['solver_name'])
        else:
            rbf_node = cls(data['solver_name'])

        # add drivers
        drivers = data['drivers']
        for driver in drivers:
            if not rbf_node.has_driver(driver):
                rbf_node.add_driver(driver)

        # add controllers
        controllers = data.get('controllers', [])
        for controller in controllers:
            if not rbf_node.has_controller(controller):
                rbf_node.add_controller(controller)

        driven_transforms = data.get('driven_transforms', [])
        if driven_transforms:
            rbf_node.add_driven_transforms(driven_nodes=driven_transforms, edit=False)

        # add poses
        for pose_name, pose_data in data['poses'].items():
            drivers_matrices = pose_data['drivers']
            controllers_matrices = pose_data.get('controllers', [])
            driven_matrices = pose_data.get('driven', {})
            function_type = pose_data.get('function_type', 'DefaultFunctionType')
            distance_method = pose_data.get('distance_method', 'DefaultMethod')
            scale_factor = pose_data.get('scale_factor', 1.0)
            target_enable = pose_data.get('target_enable', True)

            rbf_node.add_pose(
                pose_name, drivers=drivers, matrices=drivers_matrices, driven_matrices=driven_matrices,
                controller_matrices=controllers_matrices, function_type=function_type,
                distance_method=distance_method, scale_factor=scale_factor, target_enable=target_enable
            )

        # set solver attributes
        attributes = ['radius', 'automaticRadius', 'weightThreshold', 'normalizeMethod']
        enum_attributes = ['mode', 'distanceMethod', 'normalizeMethod',
                           'functionType', 'twistAxis', 'inputMode']

        for attr in attributes:
            if attr in data:
                cmds.setAttr('{}.{}'.format(rbf_node, attr), data[attr])

        for attr in enum_attributes:
            if attr in data:
                value = data[attr]
                attr = "{node}.{attr}".format(node=rbf_node, attr=attr)
                rbf_node._set_enum_attribute(attr, value)

        return rbf_node

    @classmethod
    def find_all(cls):
        """
        Returns all RBF nodes in scene
        """
        return [cls(node) for node in cmds.ls(type=cls.node_type)]

    # ----------------------------------------------------------------------------------------------
    #                                       PARAMETERS
    # ----------------------------------------------------------------------------------------------

    def mode(self, enum_value=True):
        return cmds.getAttr('{}.mode'.format(self), asString=enum_value)

    def set_mode(self, value):
        self._set_enum_attribute('{}.mode'.format(self), value)

    def radius(self):
        return cmds.getAttr('{}.radius'.format(self))

    def set_radius(self, value):
        cmds.setAttr('{}.radius'.format(self), value)

    def automatic_radius(self):
        return cmds.getAttr('{}.automaticRadius'.format(self))

    def set_automatic_radius(self, value):
        cmds.setAttr('{}.automaticRadius'.format(self), value)

    def weight_threshold(self):
        return cmds.getAttr('{}.weightThreshold'.format(self))

    def set_weight_threshold(self, value):
        cmds.setAttr('{}.weightThreshold'.format(self), value)

    def distance_method(self, enum_value=True):
        return cmds.getAttr('{}.distanceMethod'.format(self), asString=enum_value)

    def set_distance_method(self, value):
        self._set_enum_attribute('{}.distanceMethod'.format(self), value)

    def normalize_method(self, enum_value=True):
        return cmds.getAttr('{}.normalizeMethod'.format(self), asString=enum_value)

    def set_normalize_method(self, value):
        self._set_enum_attribute('{}.normalizeMethod'.format(self), value)

    def function_type(self, enum_value=True):
        return cmds.getAttr('{}.functionType'.format(self), asString=enum_value)

    def set_function_type(self, value):
        self._set_enum_attribute('{}.functionType'.format(self), value)

    def twist_axis(self, enum_value=True):
        return cmds.getAttr('{}.twistAxis'.format(self), asString=enum_value)

    def set_twist_axis(self, value):
        self._set_enum_attribute('{}.twistAxis'.format(self), value)

    def input_mode(self, enum_value=True):
        return cmds.getAttr('{}.inputMode'.format(self), asString=enum_value)

    def set_input_mode(self, value):
        self._set_enum_attribute('{}.inputMode'.format(self), value)

    def data(self):
        """
        Returns dictionary with the setup
        """
        data = OrderedDict()
        data['solver_name'] = str(self)
        data['drivers'] = self.drivers()
        data['driven_transforms'] = self.driven_nodes(pose_blender.UEPoseBlenderNode.node_type)
        data['controllers'] = self.controllers()
        data['poses'] = self.poses()
        data['driven_attrs'] = self.driven_attributes()
        data['mode'] = self.mode(enum_value=False)
        data['radius'] = self.radius()
        data['automaticRadius'] = self.automatic_radius()
        data['weightThreshold'] = self.weight_threshold()
        data['distanceMethod'] = self.distance_method(enum_value=False)
        data['normalizeMethod'] = self.normalize_method(enum_value=False)
        data['functionType'] = self.function_type(enum_value=False)
        data['twistAxis'] = self.twist_axis(enum_value=False)
        data['inputMode'] = self.input_mode(enum_value=False)

        return data

    def export_data(self, file_path):
        """
        Exports data dictionary to disk
        """
        with open(file_path, 'w') as outfile:
            json.dump(self.data(), outfile, sort_keys=1, indent=4, separators=(",", ":"))

        return file_path

    def output_weights(self):
        """
        Returns output weights
        """
        return [cmds.getAttr(attr) for attr in self.output_attributes()]

    def output_attributes(self):
        """
        Returns output attributes
        """
        attributes = list()
        indices = cmds.getAttr('{}.outputs'.format(self), multiIndices=True)
        if indices:
            for pose_index in indices:
                attr = '{}.outputs[{}]'.format(self, pose_index)
                attributes.append(attr)

        return attributes

    def driven_attributes(self, type='blendShape'):
        """
        Returns output connections
        """
        driven_attributes = list()
        output_attributes = self.output_attributes()
        if output_attributes:
            for attr in output_attributes:
                con = cmds.listConnections(attr, destination=True, shapes=False, plugs=True, type=type) or []
                driven_attributes.append(con)

        return driven_attributes

    def driven_nodes(self, type='blendShape'):
        """
        Returns driven transform nodes
        :return:
        """
        driven = []
        if type == pose_blender.UEPoseBlenderNode.node_type:
            if cmds.attributeQuery("poseBlenders", node=self, exists=True):
                # Iterate through all the pose blenders
                for pose_blender_node_name in cmds.listConnections("{solver}.poseBlenders".format(solver=self)) or []:
                    # Get the pose blender wrapper from the node name
                    pose_blender_node = pose_blender.UEPoseBlenderNode(pose_blender_node_name)
                    driven.append(pose_blender_node.driven_transform)
        elif type == 'blendShape':
            for pose_index in range(self.num_poses()):
                attr = '{}.targets[{}].targetName'.format(self, pose_index)
                poses = cmds.listConnections(attr, type='transform') or []
                driven.extend(poses)
        return driven

    # ----------------------------------------------------------------------------------------------
    #                                           DRIVERS
    # ----------------------------------------------------------------------------------------------

    def num_drivers(self):
        """
        Returns number of drivers
        """
        return cmds.getAttr('{}.inputs'.format(self), size=True)

    def has_driver(self, transform_node):
        """
        Check if node is using this transform as input
        """
        return transform_node in self.drivers()

    def drivers(self):
        """
        Returns list of drivers
        """
        indices = cmds.getAttr('{}.inputs'.format(self), multiIndices=True)
        drivers = list()
        if indices:
            for i in indices:
                connections = cmds.listConnections('{}.inputs[{}]'.format(self, i))
                if connections:
                    drivers.append(connections[0])
                else:
                    raise RuntimeError('Unable to get driver at index: {}'.format(i))

        return drivers

    def add_driver(self, transform_nodes=None, controllers=None):
        """
        Adds driver to RBF Node
        """

        if transform_nodes is None:
            transform_nodes = cmds.ls(selection=True, type='transform')
        if self.num_poses() > 1:
            raise RuntimeError('Unable to add driver after poses have been added')

        if not isinstance(transform_nodes, (list, set, tuple)):
            transform_nodes = [transform_nodes]

        for transform_node in transform_nodes:
            if not cmds.objExists(transform_node):
                raise RuntimeError('Node not found: "{}"'.format(transform_node))

            if not cmds.objectType(transform_node, isAType='transform'):
                raise RuntimeError('Invalid transform node: "{}"'.format(transform_node))

            if self.has_driver(transform_node):
                raise RuntimeError('Already has driver "{}"'.format(transform_node))

            index = self.num_drivers()
            cmds.connectAttr('{}.matrix'.format(transform_node), '{}.inputs[{}]'.format(self, index))
            # set rest matrix
            rest_matrix = cmds.xform(transform_node, q=True, ws=False, matrix=True)
            cmds.setAttr('{}.inputsRest[{}]'.format(self, index), rest_matrix, type='matrix')

    def remove_drivers(self, transform_nodes):
        """
        Removes the specified drivers from this solver
        :param transform_nodes :type list: list of transform node names
        """
        # Get the valid driver names - converts from MObject to DagPath if MObjects are specified
        valid_drivers = []
        for driver in transform_nodes:
            # Check if its an MObject
            if isinstance(driver, om.MObject):
                # Get the fullPathName and add to list of valid drivers
                valid_drivers.append(om.MDagPath.getAPathTo(driver).fullPathName())
            else:
                # Check if the driver exists and get the full path name
                matching_driver = cmds.ls(driver, long=True)
                if matching_driver:
                    # Add to list of valid drivers
                    valid_drivers.append(matching_driver[0])

        LOG.debug("Removing drivers: '{drivers}' from solver: {solver}".format(drivers=valid_drivers, solver=self))
        # Get the existing drivers from the solver
        existing_drivers = self.drivers()
        # Create an empty dict to store the remaining {driver: pose_node}
        remaining_drivers = []
        poses_indices = cmds.getAttr('{solver}.targets'.format(solver=self), multiIndices=True) or []
        # Iterate through the existing drivers in reverse
        for index in reversed(range(len(existing_drivers))):
            # Grab the driver from the index
            existing_driver = existing_drivers[index]
            # Check that the driver exists
            matching_driver = cmds.ls(existing_driver, long=True)
            # If the driver doesn't exist, warn and continue
            if not matching_driver:
                LOG.warning(
                    "Could not find driver: {existing_driver} in the scene".format(
                        existing_driver=existing_driver
                    )
                )
                continue
            # Existing driver found
            existing_driver = matching_driver[0]
            # Remove the drivers connections from the solver
            cmds.removeMultiInstance('{solver}.inputs[{index}]'.format(solver=self, index=index), b=True)
            cmds.removeMultiInstance('{solver}.inputsRest[{index}]'.format(solver=self, index=index), b=True)
            for pose_index in poses_indices:
                cmds.removeMultiInstance(
                    '{solver}.targets[{pose_index}]'.format(
                        solver=self,
                        pose_index=pose_index,
                    ),
                    b=True
                )

            # If the driver is in the not valid drivers list we want to keep it
            if existing_driver not in valid_drivers:
                # Add it back to the list of drivers to reconnect
                remaining_drivers.append(existing_driver)

        # Iterate through the remaining drivers and reconnect them
        for index, driver in enumerate(remaining_drivers):
            cmds.connectAttr(
                '{driver}.matrix'.format(driver=driver), '{solver}.inputs[{index}]'.format(
                    solver=self,
                    index=index
                )
            )
            # set rest matrix
            rest_matrix = cmds.xform(driver, q=True, ws=False, matrix=True)
            cmds.setAttr('{}.inputsRest[{}]'.format(self, index), rest_matrix, type='matrix')

        # If we have any drivers left, recreate the default pose
        if self.drivers():
            self.add_pose_from_current('default')

    # ----------------------------------------------------------------------------------------------
    #                                         CONTROLLERS
    # ----------------------------------------------------------------------------------------------

    def num_controllers(self):
        """
        Returns number of controllers
        """
        return cmds.getAttr('{}.inputsControllers'.format(self), size=True)

    def has_controller(self, transform_node):
        """
        Check if node is using this transform as controller
        """
        return transform_node in self.controllers()

    def controllers(self):
        """
        Returns list of controllers
        """

        indices = cmds.getAttr('{}.inputsControllers'.format(self), multiIndices=True)
        controllers = list()
        if indices:
            for i in indices:
                connections = cmds.listConnections('{}.inputsControllers[{}]'.format(self, i))
                if connections:
                    controllers.append(connections[0])
                else:
                    raise RuntimeError('Unable to get controller at index: {}'.format(i))

        return controllers

    def add_controller(self, transform_nodes):
        """
        Adds controller to RBF Node
        """

        if self.num_poses():
            raise RuntimeError('Unable to add controller after poses have been added')

        if not isinstance(transform_nodes, (list, set, tuple)):
            transform_nodes = [transform_nodes]

        for transform_node in transform_nodes:

            if not cmds.objExists(transform_node):
                raise RuntimeError('Node not found: "{}"'.format(transform_node))

            if not cmds.objectType(transform_node, isAType='transform'):
                raise RuntimeError('Invalid transform node: "{}"'.format(transform_node))

            if self.has_controller(transform_node):
                raise RuntimeError('Already has controller "{}"'.format(transform_node))

            index = self.num_controllers()
            cmds.connectAttr('{}.message'.format(transform_node), '{}.inputsControllers[{}]'.format(self, index))

    # ----------------------------------------------------------------------------------------------
    #                                       DRIVEN TRANSFORMS
    # ----------------------------------------------------------------------------------------------
    def add_driven_transforms(self, driven_nodes=None, edit=False):
        """
        Add driven transforms to this node, creating UEPoseBlenderNodes where needed
        :param driven_nodes :type list: list of transform_node names
        :param edit :type bool: should we be editing the transforms on creation? When set to true, no connection is
        made from the output of the UEPoseBlenderNode to the driven transform translate, rotate and scale. When set
        to False, a decompose matrix is created and connected between the output of the UEPoseBlenderNode and the
        translate, rotate and scale of the driven transform.
        """
        # If no driven nodes are specified, grab the current selection
        if not driven_nodes:
            driven_nodes = cmds.ls(selection=True, type='transform')
        # If an iterable wasn't specified, convert it to a list
        if not isinstance(driven_nodes, (list, tuple, set)):
            driven_nodes = [driven_nodes]
        # For each driven node
        for node in driven_nodes:
            existing_connection = pose_blender.UEPoseBlenderNode.find_by_transform(node)
            if existing_connection:
                LOG.error(
                    "Driven transform {node} is already connected to {solver}. "
                    "Unable to add, skipping.".format(
                        node=node,
                        solver=existing_connection.rbf_solver
                    )
                )
                continue
            # Create a UEPoseBlender node
            pose_blender_node = pose_blender.UEPoseBlenderNode.create(driven_transform=node)
            # Create a message attr connection to the rbf solver node
            pose_blender_node.rbf_solver = "{solver}.poseBlenders".format(solver=self)
            # Connect each output attribute from the solver to the corresponding weight
            for index, attribute in enumerate(self.output_attributes()):
                pose_blender_node.set_weight(index=index, in_float_attr=attribute)
            # Set the mode to edit
            pose_blender_node.edit = edit

    def remove_driven_transforms(self, driven_nodes):
        """
        Remove the specified driven transforms from this solver
        :param driven_nodes :type list: list of transform names
        """
        # Can only remove transforms if we have connected UEPoseBlenderNodes
        if cmds.attributeQuery("poseBlenders", node=self, exists=True):
            # Iterate through the pose blender nodes
            for pose_blender_node_name in cmds.listConnections("{solver}.poseBlenders".format(solver=self)):
                # Generate an API wrapper for the UEPoseBlenderNode
                pose_blender_node = pose_blender.UEPoseBlenderNode(pose_blender_node_name)
                # If the pose blender's driven transform is in the list to remove
                if pose_blender_node.driven_transform in driven_nodes:
                    # Remove it from the list
                    driven_nodes.pop(driven_nodes.index(pose_blender_node.driven_transform))
                    # Delete the UEPoseBlenderNode
                    pose_blender_node.delete()
        # Iterate through the driven
        for driven_node in driven_nodes:
            # See if they are a blendshape and have an associated pose
            blendshape_pose = self.get_pose_for_blendshape_mesh(driven_node)
            if blendshape_pose:
                # Delete the blendshape
                self.delete_blendshape(pose_name=blendshape_pose)

    # ----------------------------------------------------------------------------------------------
    #                                           POSES
    # ----------------------------------------------------------------------------------------------

    def num_poses(self):
        """
        Returns number of poses
        """
        return cmds.getAttr('{}.targets'.format(self), size=True)

    def has_pose(self, pose_name):
        """
        Returns if pose already exists
        """
        return pose_name in self.poses()

    def pose_index(self, pose_name):
        """
        Returns pose index
        """

        poses_indices = cmds.getAttr('{}.targets'.format(self), multiIndices=True)
        if poses_indices:
            for pose_index in poses_indices:
                if pose_name == cmds.getAttr('{}.targets[{}].targetName'.format(self, pose_index)):
                    return pose_index

        return -1

    def pose(self, pose_name):
        """
        Returns pose matrices
        """

        pose_index = self.pose_index(pose_name)
        if pose_index == -1:
            raise exceptions.InvalidPose('Pose not found: "{}"'.format(pose_name))

        # ---------------------------------------------------------------------
        # get driver indices
        driver_indices = cmds.getAttr('{}.targets[{}].targetValues'.format(self, pose_index), multiIndices=True)
        if not driver_indices:
            raise exceptions.InvalidPose('Unable to get Driver indices')

        # just to be sure ...
        num_drivers = self.num_drivers()
        if len(driver_indices) != num_drivers:
            raise exceptions.InvalidPose('Invalid Driver Indices')

        # get matrices
        matrices = list()
        for driver_index in driver_indices:
            matrix = cmds.getAttr('{}.targets[{}].targetValues[{}]'.format(self, pose_index, driver_index))
            matrices.append(matrix)

        # ---------------------------------------------------------------------

        # get controller indices
        controller_indices = cmds.getAttr(
            '{}.targets[{}].targetControllers'.format(self, pose_index),
            multiIndices=True
        ) or []

        # just to be sure ...
        num_controllers = self.num_controllers()
        if len(controller_indices) != num_controllers:
            raise RuntimeError('Invalid Controller Indices')

        # get controller matrices
        controller_matrices = list()
        for controller_index in controller_indices:
            matrix = cmds.getAttr('{}.targets[{}].targetControllers[{}]'.format(self, pose_index, controller_index))
            controller_matrices.append(matrix)

        # ---------------------------------------------------------------------

        # get properties
        function_type = cmds.getAttr('{}.targets[{}].targetFunctionType'.format(self, pose_index), asString=True)
        scale_factor = cmds.getAttr('{}.targets[{}].targetScaleFactor'.format(self, pose_index), asString=True)
        distance_method = cmds.getAttr('{}.targets[{}].targetDistanceMethod'.format(self, pose_index), asString=True)

        pose_blender_data = {}
        if cmds.attributeQuery("poseBlenders", node=self, exists=True):
            for pose_blender_node_name in cmds.listConnections("{solver}.poseBlenders".format(solver=self)):
                # Get the pose blender wrapper from the node name
                pose_blender_node = pose_blender.UEPoseBlenderNode(pose_blender_node_name)
                pose_matrix = pose_blender_node.get_pose(index=pose_index)
                pose_blender_data[pose_blender_node.driven_transform] = pose_matrix

        pose_data = OrderedDict()
        pose_data['drivers'] = matrices
        pose_data['controllers'] = controller_matrices
        pose_data['driven'] = pose_blender_data
        pose_data['function_type'] = function_type
        pose_data['scale_factor'] = scale_factor
        pose_data['distance_method'] = distance_method
        pose_data['target_enable'] = cmds.getAttr(
            '{solver}.targets[{index}].targetEnable'.format(solver=self, index=pose_index)
        )
        pose_data['blendshape_data'] = self.get_blendshape_data_for_pose(pose_name) or []

        return pose_data

    def go_to_pose(self, pose_name):
        """
        Sets drivers or controllers to current pose
        :param pose_name :type str: name of the pose to move this solvers drivers/driven transform nodes to
        """

        # get drivers and controllers matrices
        pose = self.pose(pose_name)
        pose_index = self.pose_index(pose_name)

        # if not controllers, set drivers
        if not self.num_controllers():

            matrices = pose['drivers']
            for driver_index, driver in enumerate(self.drivers()):
                # TODO: check if translate, rotate and scale are free to change
                cmds.xform(driver, matrix=matrices[driver_index])

        # if controllers, set controllers
        else:
            matrices = pose['controllers']
            for controller_index, controller in enumerate(self.controllers()):
                # TODO: check if translate, rotate and scale are free to change
                cmds.xform(controller, matrix=matrices[controller_index])

        # If we have poseBlenders connected we need to create a matching pose on each of those
        if cmds.attributeQuery("poseBlenders", node=self, exists=True):
            for pose_blender_node_name in cmds.listConnections("{solver}.poseBlenders".format(solver=self)):
                # Get the pose blender wrapper from the node name
                pose_blender_node = pose_blender.UEPoseBlenderNode(pose_blender_node_name)
                pose_blender_node.go_to_pose(index=pose_index)

    def poses(self):
        """
        Returns dictionary with poses and their transformation.
        """

        poses = OrderedDict()
        poses_indices = cmds.getAttr('{}.targets'.format(self), multiIndices=True)
        if poses_indices:

            for pose_index in poses_indices:
                # get pose name
                pose_name = cmds.getAttr('{}.targets[{}].targetName'.format(self, pose_index))
                # BUG - sometimes an unnamed pose will appear when selecting the node causing issues with the indexing
                if pose_name:
                    # get pose transforms
                    poses[pose_name] = self.pose(pose_name)

        return poses

    def add_pose(
            self, pose_name, drivers=None, matrices=None, controller_matrices=None, driven_matrices=None,
            function_type='DefaultFunctionType', distance_method='DefaultMethod', scale_factor=1.0, target_enable=True,
            blendshape_data=None
    ):
        """
        Adds pose to RBF Node
        """
        if drivers and matrices is None:
            matrices = [cmds.xform(driver, q=True, matrix=True, objectSpace=True) for driver in drivers]
        if not self.num_drivers():
            raise exceptions.InvalidPose('You must add a driver first.')

        if self.has_pose(pose_name):
            raise exceptions.InvalidPose('Already a pose called: "{}"'.format(pose_name))

        if len(matrices) != self.num_drivers():
            raise exceptions.InvalidPose('Invalid number of matrices. Must match number of drivers.')

        if controller_matrices and len(controller_matrices) != self.num_controllers():
            raise exceptions.InvalidPose('Invalid number of controller matrices. Must match number of controllers.')

        if self.num_controllers() and not controller_matrices:
            raise exceptions.InvalidPose('Invalid number of controller matrices. Must match number of controllers.')

        # get new index
        pose_index = self.num_poses()

        # set matrices
        for driver_index, matrix in enumerate(matrices):
            attr = '{}.targets[{}].targetValues[{}]'.format(self, pose_index, driver_index)
            cmds.setAttr(attr, matrix, type='matrix')

        # set controller matrices
        if controller_matrices:
            for controller_index, matrix in enumerate(controller_matrices):
                attr = '{}.targets[{}].targetControllers[{}]'.format(self, pose_index, controller_index)
                cmds.setAttr(attr, matrix, type='matrix')

        # If we have poseBlenders connected we need to create a matching pose on each of those
        if cmds.attributeQuery("poseBlenders", node=self, exists=True):
            output_attr = "{solver}.outputs[{pose_index}]".format(solver=self, pose_index=pose_index)
            # Iterate through all the pose blenders
            for pose_blender_node_name in cmds.listConnections("{solver}.poseBlenders".format(solver=self)):
                # Get the pose blender wrapper from the node name
                pose_blender_node = pose_blender.UEPoseBlenderNode(pose_blender_node_name)
                # If we have driven matrices we need to set the pose from the matrix provided
                if driven_matrices and driven_matrices.get(pose_blender_node.driven_transform, False):
                    pose_blender_node.set_pose(
                        index=pose_index, pose_name=pose_name,
                        matrix=driven_matrices.get(pose_blender_node.driven_transform)
                    )
                else:
                    # Create a pose at the current position in the matching index
                    pose_blender_node.add_pose_from_current(pose_name=pose_name, index=pose_index)
                pose_blender_node.set_weight(index=pose_index, in_float_attr=output_attr)

        # set pose name
        cmds.setAttr('{}.targets[{}].targetName'.format(self, pose_index), pose_name, type='string')

        # create output instance
        cmds.getAttr('{}.outputs[{}]'.format(self, pose_index), type=True)
        # set the enabled status of the pose
        cmds.setAttr('{solver}.targets[{index}].targetEnable'.format(solver=self, index=pose_index), target_enable)

        if blendshape_data:
            for data in blendshape_data:
                blendshape_mesh = data['blendshape_mesh']
                blendshape_mesh_orig = data['orig_mesh']
                self.add_existing_blendshape(pose_name, blendshape_mesh, blendshape_mesh_orig)

    def update_pose(
            self, pose_name, drivers=None, matrices=None, controller_matrices=None,
            function_type='DefaultFunctionType', distance_method='DefaultMethod', scale_factor=1.0
    ):
        """
        Updates an existing pose on the RBF Node
        """
        if drivers and matrices is None:
            matrices = [cmds.xform(driver, q=True, matrix=True) for driver in drivers]

        if not self.has_pose(pose_name):
            raise RuntimeError('Pose "{}" does not exist'.format(pose_name))

        # get new index
        pose_index = self.pose_index(pose_name)

        # set matrices
        for driver_index, matrix in enumerate(matrices):
            attr = '{}.targets[{}].targetValues[{}]'.format(self, pose_index, driver_index)
            cmds.setAttr(attr, matrix, type='matrix')

        # set controller matrices
        if controller_matrices:
            for controller_index, matrix in enumerate(controller_matrices):
                attr = '{}.targets[{}].targetControllers[{}]'.format(self, pose_index, controller_index)
                cmds.setAttr(attr, matrix, type='matrix')

        # If we have poseBlenders connected we need to create a matching pose on each of those
        if cmds.attributeQuery("poseBlenders", node=self, exists=True):
            for pose_blender_node_name in cmds.listConnections("{solver}.poseBlenders".format(solver=self)):
                # Get the pose blender wrapper from the node name
                pose_blender_node = pose_blender.UEPoseBlenderNode(pose_blender_node_name)
                pose_blender_node.set_pose(index=pose_index)

    def add_pose_from_current(self, pose_name, update=False):
        """
        Adds current pose to RBF Node
        """

        # drivers
        matrices = list()
        drivers = self.drivers()
        for driver in drivers:
            matrix = cmds.xform(driver, q=True, matrix=True, objectSpace=True)
            matrices.append(matrix)

        # controllers
        controller_matrices = None
        if self.num_controllers():

            controller_matrices = list()

            for controller in self.controllers():
                matrix = cmds.xform(controller, q=True, matrix=True, objectSpace=True)
                controller_matrices.append(matrix)

        if update:
            self.update_pose(pose_name, drivers, matrices, controller_matrices)
        else:
            self.add_pose(
                pose_name=pose_name, drivers=drivers, matrices=matrices,
                controller_matrices=controller_matrices
            )

    def mirror_pose(self, pose_name, mirror_mapping, mirror_blendshapes=True):
        """
        Mirrors the specified pose using the given mirror mapping to determine the target drivers/driven transforms
        :param pose_name :type str: pose name to mirror
        :param mirror_mapping :type pose_wrangler.model.mirror_mapping.MirrorMapping: mirror mapping ref
        :param mirror_blendshapes :type bool: option to mirror blendshapes, stops infinite loop when pose is created via
        mirror_blendshape
        """
        # Get the name of the mirrored solver
        target_solver_name = self._get_mirrored_solver_name(mirror_mapping=mirror_mapping)
        # Check if the solver already exists
        match = [s for s in self.find_all() if str(s) == target_solver_name]
        # Force the base pose
        for solver in self.find_all():
            if solver == self:
                continue
            if solver.has_pose('default'):
                solver.go_to_pose('default')
        # If it does, use it
        if match:
            new_solver = match[0]
        # Otherwise create a new solver that is a mirror of this one
        else:
            new_solver = self.mirror(mirror_mapping=mirror_mapping, mirror_poses=False)

        # Go to the pose we want to mirror
        self.go_to_pose(pose_name=pose_name)
        # Store a list of all of the transforms affecting this pose
        transforms = self.drivers()
        # Generate a list of the mirrored transforms based on the transforms we found
        mirrored_transforms = self._get_mirrored_transforms(transforms, mirror_mapping=mirror_mapping)

        for index, source_transform in enumerate(transforms):
            target_transform = mirrored_transforms[index]

            rotate = cmds.getAttr("{source_transform}.rotate".format(source_transform=source_transform))[0]
            cmds.setAttr("{target_transform}.rotate".format(target_transform=target_transform), *rotate)

        transforms = self.driven_nodes(pose_blender.UEPoseBlenderNode.node_type)
        # Generate a list of the mirrored transforms based on the transforms we found
        mirrored_transforms = self._get_mirrored_transforms(transforms, mirror_mapping=mirror_mapping)

        # If we have poseBlenders connected we need to create a matching pose on each of those
        if cmds.attributeQuery("poseBlenders", node=new_solver, exists=True):
            for pose_blender_node_name in cmds.listConnections("{solver}.poseBlenders".format(solver=new_solver)):
                # Get the pose blender wrapper from the node name
                pose_blender_node = pose_blender.UEPoseBlenderNode(pose_blender_node_name)
                pose_blender_node.edit = True

        # Iterate through all of the source transforms
        for index, source_transform in enumerate(transforms):
            # Get the target transform at the same index
            target_transform = mirrored_transforms[index]
            # Need to get each transforms parent so that we can get the relative offset
            # Get the sources parent matrix
            source_parent_matrix = om.MMatrix(
                cmds.getAttr(
                    '{source_transform}.parentMatrix'.format(
                        source_transform=source_transform
                    )
                )
            )
            # Get the targets parent matrix
            target_parent_matrix = om.MMatrix(
                cmds.getAttr(
                    '{target_transform}.parentMatrix'.format(
                        target_transform=target_transform
                    )
                )
            )
            # Calculate the translation
            translate = om.MVector(
                *cmds.getAttr(
                    '{source_transform}.translate'.format(
                        source_transform=source_transform
                    )
                )
            )

            driver_mat_fn = om.MTransformationMatrix(om.MMatrix.kIdentity)
            driver_mat_fn.setTranslation(translate, om.MSpace.kWorld)
            driver_mat = driver_mat_fn.asMatrix()

            scale_matrix_fn = om.MTransformationMatrix(om.MMatrix.kIdentity)
            scale_matrix_fn.setScale([-1.0, 1.0, 1.0], om.MSpace.kWorld)
            scale_matrix = scale_matrix_fn.asMatrix()

            pos_matrix = driver_mat * source_parent_matrix
            pos_matrix = pos_matrix * scale_matrix
            pos_matrix = pos_matrix * target_parent_matrix.inverse()
            mat_fn = om.MTransformationMatrix(pos_matrix)

            cmds.setAttr(
                '{target_transform}.translate'.format(target_transform=target_transform),
                *mat_fn.translation(om.MSpace.kWorld)
            )

            # Calculate the rotation
            rotate = om.MVector(
                *cmds.getAttr(
                    '{source_transform}.rotate'.format(
                        source_transform=source_transform
                    )
                )
            )

            driver_mat_fn = om.MTransformationMatrix(om.MMatrix.kIdentity)
            # set the values to radians
            euler = om.MEulerRotation(*[math.radians(i) for i in rotate])

            driver_mat_fn.setRotation(euler)
            driver_matrix = driver_mat_fn.asMatrix()

            world_matrix = driver_matrix * source_parent_matrix
            rot_matrix = source_parent_matrix.inverse() * world_matrix
            rot_matrix_fn = om.MTransformationMatrix(rot_matrix)
            rot = rot_matrix_fn.rotation(asQuaternion=True)
            rot.x = rot.x * -1.0
            rot.w = rot.w * -1.0
            rot_matrix = rot.asMatrix()
            final_rot_matrix = target_parent_matrix * rot_matrix * target_parent_matrix.inverse()

            rot_matrix_fn = om.MTransformationMatrix(final_rot_matrix)
            rot = rot_matrix_fn.rotation(asQuaternion=False)
            m_rot = om.MVector(*[math.degrees(i) for i in rot])

            cmds.setAttr('{target_transform}.rotate'.format(target_transform=target_transform), *m_rot)

            # Assume scale is the same
            cmds.setAttr(
                "{target_transform}.scale".format(target_transform=target_transform),
                *cmds.getAttr("{source_transform}.scale".format(source_transform=source_transform))[0]
            )
        # Add a new pose on the mirrored solver with the same name, update if the pose already exists
        new_solver.add_pose_from_current(pose_name=pose_name, update=new_solver.has_pose(pose_name=pose_name))

        # Mirror blendshapes if option is specified
        if mirror_blendshapes:
            new_solver.delete_blendshape(pose_name=pose_name)
            self.mirror_blendshape(pose_name=pose_name, mirror_mapping=mirror_mapping)

        # If we have poseBlenders connected we need to create a matching pose on each of those
        if cmds.attributeQuery("poseBlenders", node=new_solver, exists=True):
            for pose_blender_node_name in cmds.listConnections("{solver}.poseBlenders".format(solver=new_solver)):
                # Get the pose blender wrapper from the node name
                pose_blender_node = pose_blender.UEPoseBlenderNode(pose_blender_node_name)
                pose_blender_node.edit = False

    def delete_pose(self, pose_name):
        """
        Delete the specified pose name
        :param pose_name :type str: pose name to delete
        """
        # If the pose doesn't exist, raise an exception
        if not self.has_pose(pose_name):
            raise exceptions.InvalidPose("Pose {pose_name} does not exist.".format(pose_name=pose_name))

        LOG.debug("Removing pose: '{pose_name}'".format(pose_name=pose_name))

        # Get the existing poses from the solver
        poses = self.poses()
        pose_index = self.pose_index(pose_name)

        # Disconnect all of the blendshapes
        for pose in poses.keys():
            self.delete_blendshape(pose)

        # Iterate through the existing drivers in reverse
        for index in reversed(range(len(list(poses.keys())))):
            # Remove the pose from the list of targets
            cmds.removeMultiInstance('{solver}.targets[{index}]'.format(solver=self, index=index), b=True)

        # Remove the deleted pose
        poses.pop(pose_name)

        # If we have poseBlenders connected we need to create a matching pose on each of those
        if cmds.attributeQuery("poseBlenders", node=self, exists=True):
            for pose_blender_node_name in cmds.listConnections("{solver}.poseBlenders".format(solver=self)):
                # Get the pose blender wrapper from the node name
                pose_blender_node = pose_blender.UEPoseBlenderNode(pose_blender_node_name)
                pose_blender_node.delete_pose(index=pose_index)

        # Iterate through the remaining poses and recreate them
        for pose_name, pose_data in poses.items():
            pose_data['controller_matrices'] = pose_data.pop('controllers')
            pose_data['matrices'] = pose_data.pop('drivers')
            pose_data['driven_matrices'] = pose_data.pop('driven')
            # Add the pose with the specified kwargs
            self.add_pose(pose_name=pose_name, **pose_data)

    def is_pose_muted(self, pose_name="", pose_index=-1):
        """
        Gets the current status of the pose if it is muted or not
        :param pose_name :type str: optional pose name
        :param pose_index :type index, optional pose index
        :return :type bool: True if the pose is muted, else False
        """
        # Get the pose index if name is specified and the index hasn't been
        if pose_index < 0 and pose_name:
            pose_index = self.pose_index(pose_name)
        elif not pose_name and pose_index < 0:
            raise exceptions.InvalidPoseIndex("Unable to query the mute status, no pose name or index specified")

        attr = '{solver}.targets[{index}].targetEnable'.format(solver=self, index=pose_index)
        return not cmds.getAttr(attr)

    def mute_pose(self, pose_name="", pose_index=-1, mute=True):
        """
        Mute or unmute the specified pose, removing all influences of the pose from the solver.
        NOTE: This will affect the solver radius if automatic radius is enabled.
        :param pose_name :type str: optional name of the pose
        :param pose_index :type index, optional pose index
        :param mute :type bool: mute or unmute the pose
        """
        # Get the pose index if name is specified and the index hasn't been
        if pose_index < 0 and pose_name:
            pose_index = self.pose_index(pose_name)
        elif not pose_name and pose_index < 0:
            raise exceptions.InvalidPoseIndex("Unable to query the mute status, no pose name or index specified")

        attr = '{solver}.targets[{index}].targetEnable'.format(solver=self, index=pose_index)
        if mute is None:
            mute = not self.is_pose_muted(pose_index=pose_index)
        cmds.setAttr(attr, not mute)
        return not mute

    def edit_solver(self, edit=True):
        """
        Edit or finish editing this solver
        :param edit :type bool: set edit mode on or off
        """
        # If we have poseBlenders connected we need to toggle the output connection based on the edit param
        if cmds.attributeQuery("poseBlenders", node=self, exists=True):
            # Iterate through all the pose blenders
            for pose_blender_node_name in cmds.listConnections("{solver}.poseBlenders".format(solver=self)):
                # Get the pose blender wrapper from the node name
                pose_blender_node = pose_blender.UEPoseBlenderNode(pose_blender_node_name)
                # Enable or disable edit mode on the blender
                pose_blender_node.edit = edit

        # Force the base pose
        for solver in self.find_all():
            if solver != self and solver.has_pose('default'):
                solver.go_to_pose('default')

    def get_solver_edit_status(self):
        """
        Gets this solvers edit status
        :return :type bool: True if in edit mode, False if not
        """
        # If we have poseBlenders connected we need to toggle the output connection based on the edit param
        if cmds.attributeQuery("poseBlenders", node=self, exists=True):
            # Iterate through all the pose blenders
            for pose_blender_node_name in cmds.listConnections("{solver}.poseBlenders".format(solver=self)):
                # Get the pose blender wrapper from the node name
                pose_blender_node = pose_blender.UEPoseBlenderNode(pose_blender_node_name)
                # If one blender node is in edit mode, then mark the solver as in edit mode
                if pose_blender_node.edit:
                    return True
        return False

    def get_pose_for_blendshape_mesh(self, mesh_name):
        """
        Get the pose name that the specified blendshape mesh corresponds to
        :param mesh_name :type str: mesh name
        :return :type str: the pose name this mesh is associated with
        """
        if not cmds.ls(mesh_name, type='transform'):
            return
        # If the blendshape doesn't have a poseName attr, it wasn't connected correctly via the API
        if not cmds.attributeQuery('poseName', node=mesh_name, exists=True):
            raise exceptions.BlendshapeError("Unable to find pose name for current blendshape")
        # Return the poseName value
        return cmds.getAttr("{mesh_name}.poseName".format(mesh_name=mesh_name))

    def create_blendshape(self, pose_name, mesh_name=None):
        """
        Create a blendshape for the specified pose name from the given mesh (or current selection if no mesh name is
        specified)
        :param pose_name :type str: pose name
        :param mesh_name :type str: mesh name (or None for current selection)
        """
        # If no mesh is specified grab the current selection
        if not mesh_name:
            mesh_name = cmds.ls(selection=True, type='transform')
            # If no mesh, error
            if not mesh_name:
                raise exceptions.BlendshapeError("Unable to create blendshape. No mesh was found")
            mesh_name = mesh_name[0]
        # If the mesh_name is not a shape node, get the shape node for the transform
        shapes = cmds.listRelatives(mesh_name, shapes=True, noIntermediate=True)
        if not shapes:
            raise exceptions.BlendshapeError(
                "Unable to create blendshape. No shape node was found for selected "
                "transform."
            )

        # Find the skin cluster to validate that we are working with a skinned mesh
        if not cmds.listConnections(shapes[0], type='skinCluster'):
            raise exceptions.BlendshapeError("Target mesh is not skinned")

        # Create the blendshape at the default pose. Once blendshapes have been created at the presumed pose using
        # cmds.invertShape() will convert them to the bind pose position, which is where they need to be for
        # pre-deformation blendshapes to work. In this case, we create a duplicate of the bind pose so that when we
        # go into edit mode it'll be recreated in the desired pose correctly.
        self.go_to_pose("default")
        self.isolate_blendshape(pose_name=pose_name, isolate=True)
        blendshape_mesh = cmds.duplicate(
            mesh_name, name="{solver}_{pose_name}_{mesh}".format(
                solver=self,
                pose_name=pose_name,
                mesh=mesh_name
            )
        )[0]
        self.add_existing_blendshape(pose_name, blendshape_mesh, mesh_name)
        return blendshape_mesh

    def add_existing_blendshape(self, pose_name, blendshape_mesh="", base_mesh=""):
        """
        Add an existing blendshape mesh and create a new blendshape for the specified pose
        :param pose_name :type str: pose name
        :param blendshape_mesh :type str: name of the blendshape mesh to add
        :param base_mesh :type str: mesh name
        """
        if not blendshape_mesh or not base_mesh:
            selection = cmds.ls(selection=True)
            if len(selection) != 2:
                raise exceptions.BlendshapeError(
                    "Invalid number of meshes selected, please select the blendshape mesh"
                    " followed by the base mesh."
                )
            blendshape_mesh, base_mesh = selection
        # Get the current pose index
        pose_index = self.pose_index(pose_name)
        # Generate the attribute str to get the target name
        attr = '{}.targets[{}].targetName'.format(self, pose_index)
        # If the blendshape mesh doesn't have a poseName attr, create it so we can link the solver to the blendshape
        # mesh
        if not cmds.attributeQuery('poseName', node=blendshape_mesh, exists=True):
            cmds.addAttr(blendshape_mesh, dt='string', longName='poseName')
        # Connect the attrs
        utils.connect_attr(attr, '{blendshape_mesh}.poseName'.format(blendshape_mesh=blendshape_mesh))

        # Generate the name for the blendshape attribute on the base mesh
        blendshape_attr = "{base_mesh}.blendShape".format(base_mesh=base_mesh)
        blendshape = None

        # Find the blendshape if it already exists
        if cmds.attributeQuery('blendShape', node=base_mesh, exists=True):
            blendshapes = cmds.listConnections(blendshape_attr, type='blendShape') or []
            if blendshapes:
                blendshape = blendshapes[0]

        # Create the blendshape if it does not
        if not blendshape:
            # Create a new blendshape from the given mesh
            blendshape = cmds.blendShape(
                base_mesh,
                name="{base_mesh}_blendShape".format(base_mesh=base_mesh),
                frontOfChain=True
            )[0]
            # Connect the blendshape_mesh to the blendshape via message attribute
            utils.message_connect(
                "{mesh}.blendShape".format(mesh=base_mesh),
                "{blendshape}.meshOrig".format(blendshape=blendshape)
            )

        if not cmds.attributeQuery("meshes", node=blendshape, exists=True):
            cmds.addAttr(blendshape, longName="meshes", attributeType='message', multi=True)

        target_index = utils.is_connected_to_array(
            '{mesh}.blendShape'.format(mesh=blendshape_mesh),
            "{blendshape}.meshes".format(blendshape=blendshape)
        )
        if target_index is None:
            target_index = utils.get_next_available_index_in_array("{blendshape}.meshes".format(blendshape=blendshape))
            # Connect the blendshape_mesh to the blendshape via message attribute
            utils.message_connect(
                "{mesh}.blendShape".format(mesh=blendshape_mesh),
                "{blendshape}.meshes".format(blendshape=blendshape), out_array=True
            )
        cmds.blendShape(blendshape, edit=True, target=(base_mesh, target_index, blendshape_mesh, 1.0))
        if utils.is_connected_to_array(
                "{blendshape_mesh}.meshOrig".format(blendshape_mesh=blendshape_mesh),
                "{mesh}.blendShapeMeshes".format(mesh=base_mesh)
        ) is None:
            # Connect the original mesh to the blendshape mesh via message attribute
            utils.message_connect(
                "{mesh}.blendShapeMeshes".format(mesh=base_mesh),
                "{blendshape_mesh}.meshOrig".format(blendshape_mesh=blendshape_mesh), in_array=True
            )

        self.isolate_blendshape(pose_name=pose_name, isolate=False)

    def edit_blendshape(self, pose_name, edit=False):
        """
        Edit the blendshape at the given pose. This will disconnect and isolate the specific blendshape
        :param pose_name: Pose name to edit
        :param edit: enable or disable editing
        :return:
        """
        # Go to the target pose so that we can create a new mesh to edit
        self.go_to_pose(pose_name=pose_name)
        # Get the blendshape data associated with this pose
        blendshape_data = self.get_blendshape_data_for_pose(pose_name=pose_name)
        if not blendshape_data:
            return
        for data in blendshape_data:
            orig_mesh = data['orig_mesh']
            blendshape_mesh = data['blendshape_mesh']
            blendshape_mesh_shape = data['blendshape_mesh_shape']
            blendshape_mesh_orig_index = data['blendshape_mesh_orig_index']
            mesh_index = data['mesh_index']
            pose_index = data['pose_index']
            blendshape = data['blendshape']
            pose_attr = data['pose_attr']

            mesh_index_attr = '{blendshape}.meshes[{mesh_index}]'.format(blendshape=blendshape, mesh_index=mesh_index)
            weight_index_attr = '{blendshape}.weight[{mesh_index}]'.format(blendshape=blendshape, mesh_index=mesh_index)
            output_attr = '{solver}.outputs[{pose_index}]'.format(solver=self, pose_index=pose_index)
            blendshape_mesh_plug = ('{blendshape_node}.inputTarget[{mesh_index}].inputTargetGroup[0].'
                                    'inputTargetItem[6000].inputGeomTarget'.format(
                blendshape_node=blendshape,
                mesh_index=mesh_index
            ))
            blendshape_mesh_orig_attr = '{mesh}.blendShapeMeshes[{blendshape_mesh_orig_index}]'.format(
                mesh=orig_mesh, blendshape_mesh_orig_index=blendshape_mesh_orig_index
            )

            if edit:
                # Isolate the current blendshape, removing all other blendshape influences so this blendshape can be
                # worked on in isolation
                self.isolate_blendshape(pose_name=pose_name, isolate=True)
                # Generate a new blendshape mesh from the current pose (so that we can edit the shape in place)
                new_blendshape_mesh = cmds.duplicate(
                    orig_mesh, name="{blendshape_mesh}_EDIT".format(
                        blendshape_mesh=blendshape_mesh
                    )
                )[0]
                self.delete_blendshape(pose_name=pose_name)
            else:
                # Select original mesh then new shape
                new_blendshape_mesh = cmds.invertShape(orig_mesh, blendshape_mesh)
                # Rename the blendshape mesh
                new_blendshape_mesh = cmds.rename(new_blendshape_mesh, blendshape_mesh.replace('_EDIT', ''))

                new_blendshape_mesh_shape = cmds.listRelatives(new_blendshape_mesh, type='shape')[0]
                # Handle the disconnect and reconnect of new attributes
                if cmds.isConnected(
                        '{blendshape_mesh_shape}.worldMesh[0]'.format(blendshape_mesh_shape=blendshape_mesh_shape),
                        blendshape_mesh_plug
                ):
                    cmds.disconnectAttr(
                        '{blendshape_mesh_shape}.worldMesh[0]'.format(
                            blendshape_mesh_shape=blendshape_mesh_shape
                        ), blendshape_mesh_plug
                    )

                # Disconnect the old blendshape mesh from the blendshape
                cmds.disconnectAttr(
                    '{blendshape_mesh}.blendShape'.format(blendshape_mesh=blendshape_mesh),
                    mesh_index_attr
                )

                # Disconnect the old blendshape mesh from the orig mesh
                cmds.disconnectAttr(
                    blendshape_mesh_orig_attr,
                    '{blendshape_mesh}.meshOrig'.format(blendshape_mesh=blendshape_mesh)
                )

                # Disconnect the old blendshape mesh from the solvers pose
                cmds.disconnectAttr(pose_attr, '{blendshape_mesh}.poseName'.format(blendshape_mesh=blendshape_mesh))

                # Delete the old blendshape mesh
                cmds.delete(blendshape_mesh)

            # Connected the new mesh to the blendshape
            utils.connect_attr(
                '{new_blendshape_mesh}.blendShape'.format(new_blendshape_mesh=new_blendshape_mesh),
                mesh_index_attr
            )

            # Connect the original mesh to the blendshape mesh via message attribute
            utils.message_connect(
                "{mesh}.blendShapeMeshes".format(mesh=orig_mesh),
                "{blendshape_mesh}.meshOrig".format(blendshape_mesh=new_blendshape_mesh),
                in_array=True
            )
            # If the blendshape mesh doesn't have a poseName attr, create it so we can link the solver to the blendshape
            # mesh
            if not cmds.attributeQuery('poseName', node=new_blendshape_mesh, exists=True):
                cmds.addAttr(new_blendshape_mesh, dt='string', longName='poseName')
            # Connect the new blendshape mesh up to the solver
            utils.connect_attr(pose_attr, '{blendshape_mesh}.poseName'.format(blendshape_mesh=new_blendshape_mesh))

            if edit:
                cmds.select(new_blendshape_mesh, replace=True)
                cmds.hide(orig_mesh)
            else:
                self.add_existing_blendshape(
                    pose_name=pose_name, blendshape_mesh=new_blendshape_mesh, base_mesh=orig_mesh
                )
                self.isolate_blendshape(pose_name=pose_name, isolate=False)
                cmds.hide(new_blendshape_mesh)
                cmds.showHidden(orig_mesh)

    def isolate_blendshape(self, pose_name, isolate=True):
        """
        Will disconnect or reconnect all of the blendshapes that aren't directly controlled by this pose
        :param pose_name :type str: name of the pose that the blendshape is at
        :param isolate :type bool: True will disconnect the blendshapes, False will reconnect
        """
        # Get the output attrs
        output_attributes = self.output_attributes()
        # Get the specified pose's index
        pose_index = self.pose_index(pose_name)
        # If we don't have any output attributes, there's nothing to isolate
        if output_attributes:
            # Force default pose on everything bar this solver
            for solver in self.find_all():
                if solver == self:
                    continue
                if solver.has_pose('default'):
                    solver.go_to_pose(pose_name='default')
            # If we are isolating, we want to disconnect all the other blendshapes connected to this solver
            if isolate:
                # Iterate through the output attributes
                for index, attr in enumerate(output_attributes):
                    # If the index is the specified pose, skip it because we want to keep this one connected
                    if index == pose_index:
                        continue
                    # List all the blendshape connections and disconnect each blendshape
                    connections = cmds.listConnections(
                        attr, destination=True, shapes=False,
                        plugs=True, type='blendShape'
                    ) or []
                    for con in connections:
                        # Disconnect
                        cmds.disconnectAttr(attr, con)
                        # Force the disconnected blendshapes weight to 0 so that it doesn't have any influence on the
                        # final rendered mesh
                        cmds.setAttr(con, 0.0)
            else:
                # Undo the isolation, reconnecting all the attributes
                for index, attr in enumerate(output_attributes):
                    # Generate the pose name attr for this index
                    pose_name_attr = '{}.targets[{}].targetName'.format(self, index)
                    # List connections to find all the transforms connected
                    transforms = cmds.listConnections(
                        pose_name_attr, type='transform', destination=True,
                        shapes=False
                    ) or []
                    # For each transform
                    for transform in transforms:
                        # Check if it has a blendshape attr, will be missing if blendshapes aren't added via the API
                        if cmds.attributeQuery("blendShape", node=transform, exists=True):
                            # Generate the blendshape attribute name
                            blendshape_attr = "{transform}.blendShape".format(transform=transform)
                            # Iterate through each connected blendshape
                            for blendshape in cmds.listConnections(blendshape_attr, type='blendShape') or []:
                                # Get list of connected blendshape mesh plugs
                                blendshape_mesh_plugs = cmds.listConnections(
                                    "{blendshape}.meshes".format(blendshape=blendshape),
                                    plugs=True
                                ) or []
                                if blendshape_attr not in blendshape_mesh_plugs:
                                    continue
                                target_index = blendshape_mesh_plugs.index(blendshape_attr)
                                # Connect the output attr to the blendshape
                                target_attr = "{blendshape}.weight[{index}]".format(
                                    blendshape=blendshape,
                                    index=target_index
                                )
                                if not cmds.isConnected(attr, target_attr):
                                    try:
                                        cmds.connectAttr(attr, target_attr)
                                    except RuntimeError as e:
                                        LOG.error(e)

    def mirror_blendshape(self, pose_name, mirror_mapping):
        """
        Mirrors the blendshape at the specified pose name. Will mirror the solver if it doesn't exist
        :param pose_name :type str: name of the pose this blendshape is associated with
        :param mirror_mapping :type pose_wrangler.model.mirror_mapping.MirrorMapping: mirror mapping ref
        """
        # Get the pose index for this name
        pose_index = self.pose_index(pose_name)
        # Generate the attribute str to get the target name
        attr = '{}.targets[{}].targetName'.format(self, pose_index)
        # Find the blendshape transform node connected
        blendshape_transforms = cmds.listConnections(attr, type='transform') or []
        # If we don't find one, the blendshape wasn't created via the API
        if not blendshape_transforms:
            LOG.debug("Unable to find blendshape associated with '{pose_name}' pose".format(pose_name=pose_name))
            return

        # Get the transform
        blendshape_transform = blendshape_transforms[0]

        # Get the original mesh
        original_mesh = cmds.listConnections(
            '{blendshape}.meshOrig'.format(blendshape=blendshape_transform),
            type='transform'
        ) or []

        if not original_mesh:
            raise exceptions.BlendshapeError(
                "Unable to find original mesh for blendshape: {blendshape}".format(
                    blendshape=blendshape_transform
                )
            )

        original_mesh = original_mesh[0]

        # Generate the mirrored name for the blendshape
        mirrored_blendshape_name = self._get_mirrored_transforms(
            [blendshape_transform], mirror_mapping,
            ignore_invalid_nodes=True
        )[0]
        if cmds.objExists(mirrored_blendshape_name):
            cmds.delete(mirrored_blendshape_name)

        # Duplicate the mesh with the new name
        mirrored_blendshape_mesh = cmds.duplicate(blendshape_transform, name=mirrored_blendshape_name)[0]
        # Get the name of the mirrored solver
        target_solver_name = self._get_mirrored_solver_name(mirror_mapping=mirror_mapping)
        # Check if the solver already exists
        match = [s for s in self.find_all() if str(s) == target_solver_name]
        # If it does, use it
        if match:
            new_solver = match[0]
        # Otherwise create a new solver that is a mirror of this one
        else:
            new_solver = self.mirror(mirror_mapping=mirror_mapping, mirror_poses=False)

        # If the solver doesn't have this pose, mirror it
        if not new_solver.has_pose(pose_name):
            self.mirror_pose(pose_name=pose_name, mirror_mapping=mirror_mapping)

        # Add the new blendshape mesh to the mirrored solver
        new_solver.add_existing_blendshape(
            pose_name, blendshape_mesh=mirrored_blendshape_mesh,
            base_mesh=original_mesh
        )

        blendshape_attr = "{base_mesh}.blendShape".format(base_mesh=original_mesh)
        blendshape = None
        if cmds.attributeQuery('blendShape', node=original_mesh, exists=True):
            blendshapes = cmds.listConnections(blendshape_attr, type='blendShape') or []
            if blendshapes:
                blendshape = blendshapes[0]
        if not blendshape:
            raise exceptions.BlendshapeError(
                "Unable to find blendshape for {mesh} pose: {pose}".format(
                    mesh=original_mesh,
                    pose=pose_name
                )
            )
        target_plug = "{blendshape_mesh}.blendShape".format(blendshape_mesh=mirrored_blendshape_mesh)
        blendshape_mesh_plugs = cmds.listConnections(
            "{blendshape}.meshes".format(blendshape=blendshape),
            plugs=True
        ) or []
        if target_plug not in blendshape_mesh_plugs:
            raise exceptions.BlendshapeError(
                "Unable to find {mesh} connection to {blendshape}".format(
                    mesh=original_mesh,
                    blendshape=blendshape
                )
            )
        target_index = blendshape_mesh_plugs.index(target_plug)
        # Find the mirror axis from the drivers
        current_drivers = [cmds.xform(driver, query=True, translation=True, worldSpace=True) for driver in
                           self.drivers()]
        mirrored_drivers = [cmds.xform(driver, query=True, translation=True, worldSpace=True) for driver in
                            new_solver.drivers()]

        # Find the mirrored axis
        mirror_axis = self._get_mirrored_axis(source_transforms=current_drivers, mirrored_transforms=mirrored_drivers)
        # HACK For some reason flipTarget fails to flip when called a single time
        # Mirror the blendshape along the target axis
        cmds.blendShape(
            blendshape, edit=True, symmetryAxis=mirror_axis, symmetrySpace=1,
            flipTarget=[(0, target_index)]
        )
        # Mirror the blendshape along the target axis
        cmds.blendShape(
            blendshape, edit=True, symmetryAxis=mirror_axis, symmetrySpace=1,
            flipTarget=[(0, target_index)]
        )
        blendshape_data = new_solver.get_blendshape_data_for_pose(pose_name=pose_name)
        parent = cmds.listRelatives(mirrored_blendshape_mesh, parent=True) or []
        cmds.delete(mirrored_blendshape_mesh)
        # Regenerate the blendshape mesh from the new mirrored blendshape
        new_mesh = cmds.sculptTarget(blendshape, edit=True, target=target_index, regenerate=True)[0]
        # Rename the new mesh so that it doesn't match the old blendshape name and get deleted
        new_mesh = cmds.rename(new_mesh, "{new_mesh}_TEMP".format(new_mesh=new_mesh))
        # Delete the original blendshape because the geometry isn't mirrored
        new_solver.delete_blendshape(pose_name, blendshape_data=blendshape_data)
        # Rename the mirrored mesh to the correct mirrored blendshape mesh name
        cmds.rename(new_mesh, mirrored_blendshape_mesh)
        cmds.hide(mirrored_blendshape_mesh)
        if parent:
            cmds.parent(mirrored_blendshape_mesh, parent)
        # Add the new mesh as a blendshape
        new_solver.add_existing_blendshape(pose_name, blendshape_mesh=mirrored_blendshape_mesh, base_mesh=original_mesh)

    def delete_blendshape(self, pose_name, blendshape_data=None, delete_mesh=False):
        """
        Delete the blendshape associated with the specified pose
        :param pose_name :type str: name of the pose to delete blendshapes for
        :param blendshape_data :type dict or None: optional blendshape data
        :param delete_mesh :type bool: True = mesh will be deleted, False = connections will be broken
        """
        # Delete all the blendshapes associated with the specified pose
        for data in blendshape_data or self.get_blendshape_data_for_pose(pose_name=pose_name):
            # Get the blendshape, blendshape mesh and target index from the blendshape data
            blendshape = data['blendshape']
            blendshape_mesh = data['blendshape_mesh']
            mesh_index = data['mesh_index']
            # Remove the attributes at the target index
            cmds.removeMultiInstance(
                '{blendshape}.meshes[{index}]'.format(
                    blendshape=blendshape,
                    index=mesh_index
                ), b=True
            )
            cmds.removeMultiInstance(
                '{blendshape}.weight[{index}]'.format(
                    blendshape=blendshape,
                    index=mesh_index
                ), b=True
            )
            cmds.removeMultiInstance(
                '{blendshape}.inputTarget[0].inputTargetGroup[{index}]'.format(
                    blendshape=blendshape,
                    index=mesh_index
                ), b=True
            )
            cmds.aliasAttr(
                'weight{index}'.format(index=mesh_index), '{blendshape}.weight[{index}]'.format(
                    blendshape=blendshape,
                    index=mesh_index
                )
            )

            pose_index = self.pose_index(pose_name=pose_name)

            from_attr = "{self}.targets[{pose_index}].targetName".format(self=self, pose_index=pose_index)
            to_attr = "{blendshape}.poseName".format(blendshape=blendshape_mesh)

            cmds.disconnectAttr(from_attr, to_attr)

            # Delete the mesh
            if cmds.objExists(blendshape_mesh) and delete_mesh:
                cmds.select(blendshape_mesh, replace=True)
                cmds.delete(blendshape_mesh)

    def get_blendshape_data_for_pose(self, pose_name):
        """
        Get all the blendshape data associated with the specified pose name
        :param pose_name :type str: pose name
        :return :type list of dictionaries: blendshape data
        """
        blendshape_data = []
        # Get the pose index for this name
        pose_index = self.pose_index(pose_name)
        if pose_index < 0:
            return blendshape_data
        # Generate the attribute str to get the target name
        target_name_attr = '{}.targets[{}].targetName'.format(self, pose_index)
        # Find the blendshape transform nodes connected
        blendshape_transforms = cmds.listConnections(target_name_attr, type='transform') or []
        # If we don't find one, the blendshape wasn't created via the API
        if not blendshape_transforms:
            return blendshape_data
        # Iterate through the transforms associated with the blendshape
        for blendshape_mesh in blendshape_transforms:
            blendshape_mesh_shape = cmds.listRelatives(blendshape_mesh, type='shape')[0]
            # Get the connected blendshapes
            blendshape_plug = '{transform}.blendShape'.format(transform=blendshape_mesh)
            blendshapes = cmds.listConnections(blendshape_plug, type='blendShape') or []
            if len(blendshapes) != 1:
                raise exceptions.BlendshapeError(
                    "Unable to find blendshape associated with {pose_name} for mesh: "
                    "{blendshape_mesh}".format(
                        pose_name=pose_name,
                        blendshape_mesh=blendshape_mesh
                    )
                )
            blendshape = blendshapes[0]
            # Get the original mesh that the blendshape is driving
            orig_mesh = cmds.listConnections(
                "{mesh}.meshOrig".format(mesh=blendshape_mesh, type='transform')
            )
            if not orig_mesh:
                raise exceptions.BlendshapeError(
                    "Unable to find original mesh for blendshape: "
                    "'{mesh}'".format(mesh=blendshape_mesh)
                )

            orig_mesh = orig_mesh[0]
            # Get the meshes connected to the blendshape
            blendshape_mesh_plugs = cmds.listConnections(
                "{blendshape}.meshes".format(blendshape=blendshape),
                plugs=True
            ) or []
            if blendshape_plug not in blendshape_mesh_plugs:
                LOG.warning(
                    "Could not find connection between mesh: {mesh} and blendshape: {blendshape}".format(
                        mesh=blendshape_mesh,
                        blendshape=blendshape
                    )
                )
                continue

            # Get the index that the blendshape mesh is connected to the blendshape
            target_index = blendshape_mesh_plugs.index(blendshape_plug)

            orig_mesh_plugs = cmds.listConnections(
                "{orig_mesh}.blendShapeMeshes".format(orig_mesh=orig_mesh),
                plugs=True
            ) or []

            blendshape_mesh_orig_plug = "{blendshape_mesh}.meshOrig".format(blendshape_mesh=blendshape_mesh)

            if blendshape_mesh_orig_plug not in orig_mesh_plugs:
                LOG.warning(
                    "Could not find connection between mesh: {mesh} and blendshape mesh: {blendshape}".format(
                        mesh=orig_mesh,
                        blendshape=blendshape_mesh
                    )
                )
                continue

            blendshape_mesh_orig_index = orig_mesh_plugs.index(blendshape_mesh_orig_plug)

            blendshape_data.append(
                {
                    # Blendshape Transform Node
                    'blendshape_mesh': blendshape_mesh,
                    # Blendshape Shape Node
                    'blendshape_mesh_shape': blendshape_mesh_shape,
                    # Original Mesh Transform Node
                    'orig_mesh': orig_mesh,
                    # Blendshape Node
                    'blendshape': blendshape,
                    # orig_mesh.blendShapeMeshes index for this blendshape mesh
                    'blendshape_mesh_orig_index': blendshape_mesh_orig_index,
                    # Index of the blendshape transform node on the blendshape node
                    'mesh_index': target_index,
                    # The attribute name
                    'pose_attr': target_name_attr,
                    'pose_index': pose_index
                }
            )
        return blendshape_data

    def pose_driven_attributes(self, pose_name):
        """
        Returns attributes driven by the pose output
        """

        pose_driven_attributes = list()

        if self.has_pose(pose_name):
            pose_index = self.pose_index(pose_name)
            pose_driven_attributes = self.driven_attributes()[pose_index]

        return pose_driven_attributes

    def pose_output_attribute(self, pose_name):
        """
        Returns the pose output attribute
        """

        if self.has_pose(pose_name):
            pose_index = self.pose_index(pose_name)
            return self.output_attributes()[pose_index]

    def pose_name(self, pose_index):
        """
        Returns pose name from index
        """

        poses_indices = cmds.getAttr('{}.targets'.format(self), multiIndices=True)
        if poses_indices and pose_index in poses_indices:
            return cmds.getAttr('{}.targets[{}].targetName'.format(self, pose_index))

        return None

    def rename_pose(self, pose_index, pose_name):
        """
        Renames a pose given an index
        """

        poses_indices = cmds.getAttr('{}.targets'.format(self), multiIndices=True)
        if poses_indices:
            if pose_index not in poses_indices:
                raise RuntimeError('Pose Index "{}" not found'.format(pose_index))

            if self.has_pose(pose_name):
                raise RuntimeError('Pose "{}" already exists'.format(pose_name))

            cmds.setAttr('{}.targets[{}].targetName'.format(self, pose_index), pose_name, type='string')

        return pose_name

    def unnamed_poses_indices(self):
        """
        Returns unnamed poses indices
        """

        unnamed_poses = list()
        poses_indices = cmds.getAttr('{}.targets'.format(self), multiIndices=True)
        for pose_index in poses_indices:
            if not self.pose_name(pose_index):
                unnamed_poses.append(pose_index)

        return unnamed_poses

    def name_unnamed_poses(self, basename='pose'):
        """
        Names unnamed poses with basename.

        NOTE: this is a utility for existing Metahuman scenes where
              the pose names are stored in network nodes.
        """

        pose_names = list()
        for pose_index in self.unnamed_poses_indices():

            # add index to basename
            pose_name = '{}_{}'.format(basename, pose_index)

            # make sure is unique name
            while self.has_pose(pose_name):
                pose_name = '{}_{}'.format(basename, pose_index + 1)

            self.rename_pose(pose_index, pose_name)
            pose_names.append(pose_name)

        return pose_names

    def mirror(self, mirror_mapping, mirror_poses=True):
        """
        Mirror this RBF Solver
        :param mirror_mapping :type pose_wrangler.model.mirror_mapping.MirrorMapping: mirror mapping ref
        :param mirror_poses :type bool: should we mirror poses too?
        :return :type RBFNode: mirrored RBF Solver wrapper
        """
        # Generate the target solver name from the current solver name
        target_rbf_solver_name = self._get_mirrored_solver_name(mirror_mapping=mirror_mapping)

        LOG.debug(
            "Creating mirrored solver: '{target_pose_driver_name}".format(
                target_pose_driver_name=target_rbf_solver_name
            )
        )
        # Serialize the solver data
        solver_data = self.data()
        # Grab the drivers  and driven from the serialized data
        mirrored_transform_data = {
            'drivers': solver_data.pop('drivers'),
            'driven_transforms': solver_data.pop('driven_transforms')
        }
        # Iterate through the drivers and driven transforms to find their mirrored counterpart
        for key, transforms in mirrored_transform_data.items():
            # Update the dict with the new transforms
            mirrored_transform_data[key] = self._get_mirrored_transforms(transforms, mirror_mapping)

        # Update the solver data with the new drivers
        solver_data['drivers'] = mirrored_transform_data.pop('drivers')
        # Update the solver data with the new driven transforms
        solver_data['driven_transforms'] = mirrored_transform_data.pop('driven_transforms')
        # Update the solver data with the new solver name
        solver_data['solver_name'] = target_rbf_solver_name

        # Remove pose data to iterate over later
        pose_data = solver_data.pop('poses')
        solver_data['poses'] = {}

        # Delete any existing solvers:
        for solver in [solver for solver in RBFNode.find_all() if str(solver) == target_rbf_solver_name]:
            solver.delete()
        # Create a new solver from the data
        mirrored_solver = RBFNode.create_from_data(solver_data)

        # If we are mirroring poses, iterate through each pose and mirror it
        if mirror_poses:
            for pose_name in pose_data.keys():
                self.mirror_pose(pose_name=pose_name, mirror_mapping=mirror_mapping)

            # Force the base pose
            for solver in self.find_all():
                if solver.has_pose('default'):
                    solver.go_to_pose('default')
        # If we aren't mirroring poses, create the default pose
        else:
            mirrored_solver.add_pose_from_current(pose_name='default')

        return mirrored_solver

    def delete(self):
        """
        Delete the Maya node associated with this class
        """
        # If we have blendshapes, disconnect them all
        if self.driven_nodes(type='blendShape'):
            for pose in self.poses().keys():
                self.delete_blendshape(pose)

        cmds.delete(self._node)

    # ----------------------------------------------------------------------------------------------
    #                                        ENUM UTILS
    # ----------------------------------------------------------------------------------------------

    def _set_enum_attribute(self, attribute, value):
        """
        Sets enum attribute either by string or index value
        """

        if isinstance(value, six.string_types):

            # get enum index
            selection_list = OpenMaya.MSelectionList()
            selection_list.add(attribute)

            plug = OpenMaya.MPlug()
            selection_list.getPlug(0, plug)

            mfn = OpenMaya.MFnEnumAttribute(plug.attribute())
            index = mfn.fieldIndex(value)

            cmds.setAttr(attribute, index)

        else:
            cmds.setAttr(attribute, value)

    def _get_mirrored_axis(self, source_transforms, mirrored_transforms):
        axis_names = 'xyz'
        for index, driver in enumerate(source_transforms):
            mirrored_driver = mirrored_transforms[index]
            for i, axis in enumerate(driver):
                if axis > 0 and mirrored_driver[i] > 0 or axis < 0 and mirrored_driver[i] < 0:
                    continue
                return axis_names[i]

    def _get_mirrored_solver_name(self, mirror_mapping):
        """
        Generate the mirrored solver name using the specified mirror mapping
        :param mirror_mapping :type pose_wrangler.model.mirror_mapping.MirrorMapping: mirror mapping ref
        :return :type str: mirrored solver name
        """
        # Grab the solver expression from the mirror mapping and check that this solver matches the correct naming
        match = re.match(mirror_mapping.solver_expression, str(self))
        # If it doesn't match, raise exception
        if not match:
            raise exceptions.exceptions.InvalidMirrorMapping(
                "Unable to mirror solver '{solver}'. The naming conventions do "
                "not match the mirror mapping specified: {expression}".format(
                    solver=self,
                    expression=mirror_mapping.solver_expression
                )
            )

        # Generate the new pose driver name
        target_rbf_solver_name = ""
        for group in match.groups():
            # If the the group matches the source solver syntax, change the group to be the target syntax.
            # I.e if the source is _l_, change it to _r_
            if group == mirror_mapping.source_solver_syntax:
                group = mirror_mapping.target_solver_syntax
            # If the group matches the target, change the group to the source and swap the sides in the config
            elif group == mirror_mapping.target_solver_syntax:
                group = mirror_mapping.source_solver_syntax
                mirror_mapping.swap_sides()
            # Add the group name to generate the new name for the solver
            target_rbf_solver_name += group
        return target_rbf_solver_name

    def _get_mirrored_transforms(self, transforms, mirror_mapping, ignore_invalid_nodes=False):
        """
        Generate a list of transforms that mirror the list given
        :param transforms :type list: list of transforms to get the mirrored name for
        :param mirror_mapping :type pose_wrangler.model.mirror_mapping.MirrorMapping: mirror mapping ref
        :return :type list: list of mirrored transform names
        """
        # Generate empty list to store the newly mapped transforms
        new_transforms = []
        for transform in transforms:
            # Check if the transform matches the target transform expression
            match = re.match(mirror_mapping.transform_expression, transform)
            # If it doesn't, raise exception. Can't work with incorrectly named transforms
            if not match:
                raise exceptions.exceptions.InvalidMirrorMapping(
                    "Unable to mirror transform '{transform}'. The naming conventions do "
                    "not match the mirror mapping specified: {expression}".format(
                        transform=transform,
                        expression=mirror_mapping.transform_expression
                    )
                )
            # Generate the new pose transform name
            target_transform_name = ""
            # Iterate through the groups
            for group in match.groups():
                # If the the group matches the source transform syntax, change the group to be the target syntax.
                if group == mirror_mapping.source_transform_syntax:
                    group = mirror_mapping.target_transform_syntax
                elif group == mirror_mapping.target_transform_syntax:
                    group = mirror_mapping.source_transform_syntax
                # Add the group name to generate the new name for the transform
                target_transform_name += group
            # If the generated transform name doesn't exist, raise exception
            if not cmds.ls(target_transform_name) and not ignore_invalid_nodes:
                raise exceptions.exceptions.InvalidMirrorMapping(
                    "Unable to mirror transform '{transform}'. Target transform does not exist: '{target}'".format(
                        transform=transform,
                        target=target_transform_name
                    )
                )
            # Add the new transform to the list
            new_transforms.append(target_transform_name)
        return new_transforms
