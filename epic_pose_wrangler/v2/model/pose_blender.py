#  Copyright Epic Games, Inc. All Rights Reserved.

import copy

from maya import cmds
from maya.api import OpenMaya as om

from epic_pose_wrangler.log import LOG
from epic_pose_wrangler.v2.model import exceptions, utils


class UEPoseBlenderNode(object):
    """
    Class wrapper for UEPoseBlenderNode
    """
    node_type = 'UEPoseBlenderNode'

    @classmethod
    def create(cls, driven_transform=None):
        """
        Create Pose Blender Node
        >>> new_node = UEPoseBlenderNode.create()
        """
        name = driven_transform
        # If no name is specified, generate unique name
        if name is None:
            name = '{name}#'.format(name=cls.node_type)
        name += "_{class_name}".format(class_name=cls.__name__)
        # Create node
        node = cmds.createNode(cls.node_type, name=name)
        node_ref = cls(node)
        # If a driving transform is specified, connect it via a message attribute and set the base pose
        if driven_transform is not None:
            utils.message_connect(
                from_attribute="{node}.drivenTransform".format(node=node),
                to_attribute="{transform}.poseBlender".format(transform=driven_transform)
            )
            # Set the base pose
            node_ref.base_pose = cmds.xform(driven_transform, query=True, objectSpace=True, matrix=True)
        # Return the new UEPoseBlenderNode reference
        return node_ref

    @classmethod
    def find_all(cls):
        """
        Returns all PoseBlender nodes in scene
        """
        return [cls(node) for node in cmds.ls(type=cls.node_type)]

    @classmethod
    def find_by_name(cls, name):
        """
        Find a UEPoseBlenderNode class with the specified name
        :param name :type str: name of the node
        :return :type UEPoseBlenderNode or None:
        """
        if not name.endswith(cls.node_type):
            name += "_{node_type}".format(node_type=cls.node_type)
        match = cmds.ls(name, type=cls.node_type)
        return cls(match[0]) if match else None

    @classmethod
    def find_by_transform(cls, transform):
        """
        Finds a UEPoseBlenderNode class connected to the specified joint
        :param transform :type str: name of the transform
        :return :type UEPoseBlenderNode or None
        """
        if not cmds.attributeQuery('poseBlender', node=transform, exists=True):
            return
        connections = cmds.listConnections('{transform}.poseBlender'.format(transform=transform))
        if not connections:
            return
        return cls(connections[0])

    def __init__(self, node):
        # If the node doesn't exist, raise an exception
        if not cmds.objectType(node, isAType=self.node_type):
            raise exceptions.InvalidNodeType(
                'Invalid "{node_type}" node: "{node_name}"'.format(
                    node_type=self.node_type,
                    node_name=node
                )
            )
        # Store a reference ot the MObject in case the name of the node is changed whilst this class is still in use
        self._node = om.MFnDependencyNode(om.MGlobal.getSelectionListByName(node).getDependNode(0))

    def __repr__(self):
        """
        Returns class string representation
        """
        return '<{node_type}>: {object}'.format(node_type=self.node_type, object=self)

    def __str__(self):
        """
        Returns class as string
        """
        return str(self.node)

    def __eq__(self, other):
        """
        Returns if two objects are the same, allows for comparing two different UEPoseBlenderNode references that wrap
        the same MObject
        """
        return str(self) == str(other)

    def __enter__(self):
        """
        Override the __enter__ to allow for this class to be used as a context manager to toggle edit mode
        >>> pose_blender = UEPoseBlenderNode('TestPoseBlenderNode')
        >>> with pose_blender:
        >>>     # Edit mode enabled so changes can be made
        >>>     pass
        >>> # Edit mode is now disabled
        """
        self.edit = True

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        On exit, disable edit mode
        """
        self.edit = not self.edit

    @property
    def node(self):
        return self._node.name()

    @property
    def rbf_solver_attr(self):
        return '{node}.rbfSolver'.format(node=self.node)

    @property
    def base_pose_attr(self):
        return '{node}.basePose'.format(node=self.node)

    @property
    def envelope_attr(self):
        return '{node}.envelope'.format(node=self.node)

    @property
    def in_matrix_attr(self):
        return '{node}.inMatrix'.format(node=self.node)

    @property
    def out_matrix_attr(self):
        return '{node}.outMatrix'.format(node=self.node)

    @property
    def poses_attr(self):
        return '{node}.poses'.format(node=self.node)

    @property
    def weights_attr(self):
        return '{node}.weights'.format(node=self.node)

    @property
    def driven_transform(self):
        """
        Get the current driven transform
        :return :type str: transform node name
        """
        if cmds.attributeQuery('drivenTransform', node=self.node, exists=True):
            transforms = cmds.listConnections("{node}.drivenTransform".format(node=self.node))
            if transforms:
                return transforms[0]

    @property
    def edit(self):
        """
        :return :type bool: are the driven transforms connected to this node editable?
        """
        transform = self.driven_transform
        # If no transform, we can edit!
        if not transform:
            return True
        # False if we have any matrix connections, otherwise we have no connections and can edit
        return False if cmds.listConnections(self.out_matrix_attr) else True

    @edit.setter
    def edit(self, value):
        """
        Allow the driven transforms to be edited (or not)
        :param value :type bool: edit mode enabled True/False
        """
        # If we don't have a driven transform we can't do anything
        transform = self.driven_transform
        if not transform:
            return
        # If we are in edit mode, disable out connections
        if bool(value):
            self.out_matrix = None
        # Otherwise connect up the transform
        else:
            self.out_matrix = transform

    @property
    def rbf_solver(self):
        """
        :return:The connected rbf solver node if it exists
        """
        from epic_pose_wrangler.v2.model import api
        # Check the attr exists
        exists = cmds.attributeQuery(self.rbf_solver_attr.split('.')[-1], node=self.node, exists=True)
        # Query the connections
        connections = cmds.listConnections(self.rbf_solver_attr)
        # Return the node if the attr exists and a connection is found
        return api.RBFNode(connections[0]) if exists and connections else None

    @rbf_solver.setter
    def rbf_solver(self, rbf_solver_attr):
        """
        Connects up this node to an rbf solver node
        :param rbf_solver_attr: the attribute on the rbf solver to connect this to i.e my_rbf_solver.poseBlend_back_120
        """
        utils.message_connect(rbf_solver_attr, self.rbf_solver_attr)

    @property
    def base_pose(self):
        """
        :return :type list: matrix
        """
        return self.get_pose(index=0)

    @base_pose.setter
    def base_pose(self, matrix):
        """
        Set the base pose to a specific pose.PoseNode
        :param matrix :type list: Matrix to set as base pose
        """
        # Connect up the pose's outputLocalMatrix to the basePose plug
        utils.set_attr_or_connect(source_attr_name=self.base_pose_attr, value=matrix, attr_type='matrix')
        # Set the inMatrix to the basePose plug
        self.in_matrix = matrix
        # Set the first pose in the pose list to the new base pose
        self.set_pose(index=0, overwrite=True, matrix=matrix)

    @property
    def envelope(self):
        """
        Get the value of the envelope attr from this node
        """
        return utils.get_attr(self.envelope_attr, as_value=True)

    @envelope.setter
    def envelope(self, value):
        """
        Sets the envelope
        :param value: float, int or string (i.e node.attributeName). Float/Int will set the value, whilst
        passing an attribute will connect the plugs
        """
        if isinstance(value, float) or isinstance(value, int) and 0 > value > 1:
            value = min(max(0.0, value), 1.0)
        utils.set_attr_or_connect(source_attr_name=self.envelope_attr, value=value)

    @property
    def in_matrix(self):
        """
        Get the inMatrix value
        :return: matrix or attributeName
        """
        # Get the current value of the attribute
        return utils.get_attr(self.in_matrix_attr, as_value=True)

    @in_matrix.setter
    def in_matrix(self, value):
        """
        Sets the inMatrix attribute to a value or connects it to another matrix plug
        :param value: matrix (list) or string node.attributeName
        """
        utils.set_attr_or_connect(source_attr_name=self.in_matrix_attr, value=value, attr_type='matrix')

    @property
    def out_matrix(self):
        """
        :return:
        """
        return cmds.getAttr(self.out_matrix_attr)

    @out_matrix.setter
    def out_matrix(self, transform_name=None):
        """
        Connect the output matrix up to a given transform node
        :param transform_name: name of a transform node to connect to
        """
        # If a transform is specified, connect it
        current_selection = cmds.ls(selection=True)
        if transform_name:
            # Check that the node type is a transform
            if not cmds.ls(transform_name, type='transform'):
                # If its not a transform raise an error
                raise exceptions.InvalidNodeType(
                    "Invalid node type. Expected 'transform', received '{node_type}'".format(
                        node_type=cmds.objectType(transform_name)
                    )
                )
            # Create a new decomposeMatrix node to convert the outMatrix to T,R,S
            mx_decompose_node = cmds.createNode('decomposeMatrix', name="{node}_mx_decompose#".format(node=self.node))
            # Connect the outMatrix up to the decomposeMatrix's input
            cmds.connectAttr(self.out_matrix_attr, '{node}.inputMatrix'.format(node=mx_decompose_node))
            # Create an iterator with TRS attributes
            attributes = ('translate', 'rotate', 'scale')
            # Iterate through each attr and connect it
            for attr in attributes:
                out_attr = '{mx_decompose_node}.output{attr}'.format(
                    mx_decompose_node=mx_decompose_node,
                    attr=attr.capitalize()
                )
                in_attr = '{node_name}.{attr}'.format(node_name=transform_name, attr=attr)
                cmds.connectAttr(out_attr, in_attr, force=True)
        else:
            # No transform was specified, disconnect all existing connections
            connections = cmds.listConnections(self.out_matrix_attr, type='decomposeMatrix')
            current_matrix = cmds.xform(self.driven_transform, query=True, matrix=True, objectSpace=True)
            if connections:
                cmds.delete(connections)
            for connection in cmds.listConnections(self.out_matrix_attr, plugs=True) or []:
                cmds.disconnectAttr(self.out_matrix_attr, connection)
            cmds.xform(self.driven_transform, matrix=current_matrix, objectSpace=True)
        cmds.select(current_selection, replace=True)

    def get_pose(self, index=-1):
        """
        Get the pose at the specified index
        :param index :type int: index to query
        :return :type list matrix or None
        """
        # Get the value of the pose_attr at the specified index
        return utils.get_attr(
            '{poses_attr}[{index}]'.format(poses_attr=self.poses_attr, index=index),
            as_value=True
        )

    def get_poses(self):
        """
        :return :type list of matrices
        """
        # TODO update this when the weight + name get added
        return utils.get_attr_array(attr_name=self.poses_attr, as_value=True)

    def add_pose_from_current(self, pose_name, index=-1):
        """
        Add a pose from the current transforms positions
        :param pose_name :type str: name of the pose
        :param index :type int: target index for the pose
        """
        # Find the next index if no index is specified
        if index < 0:
            # If the index is less than 0 find the next available index
            index = len(cmds.getAttr(self.poses_attr, multiIndices=True) or [0]) - 1
        # Store driven transform in var to reduce number of cmds calls
        driven_transform = self.driven_transform
        if not driven_transform:
            raise exceptions.PoseBlenderPoseError(
                "No driven transform associated with this node, "
                "unable to get the current matrix"
            )
        # Get the local matrix for the driven transform
        local_matrix = cmds.xform(driven_transform, query=True, objectSpace=True, matrix=True)
        # Set the pose
        self.set_pose(index=index, pose_name=pose_name, matrix=local_matrix)

    def set_pose(self, index=-1, pose_name="", overwrite=True, matrix=None):
        """
        Set a pose for the specified index
        :param index: int value of the index to set
        :param pose_name: name of the pose as a string
        :param overwrite: should it overwrite any existing pose at the index or insert
        :param matrix: matrix value to set
        """
        # Find the next index if no index is specified
        if index < 0:
            if pose_name:
                LOG.warning("Set Pose has not been implemented to support a pose name. FIXME")
                return
            else:
                # If the index is less than 0 find the next available index
                index = len(cmds.getAttr(self.poses_attr, multiIndices=True) or [0]) - 1

        # If no matrix is specified, grab the matrix for the driven transform
        if matrix is None:
            matrix = cmds.xform(self.driven_transform, query=True, matrix=True, objectSpace=True)

        # TODO add in support for inserting into the pose list
        if not overwrite:
            pose_count = len(cmds.getAttr(self.poses_attr, multiIndices=True) or [])
            if pose_count - 1 > index:
                pass

        # Generate the source attribute (the attribute on this node) from the default attr and given index
        source_attr_name = '{poses_attr}[{index}]'.format(poses_attr=self.poses_attr, index=index)
        # Set the pose
        utils.set_attr_or_connect(source_attr_name=source_attr_name, value=matrix, attr_type='matrix')

    def go_to_pose(self, index=-1):
        """
        Move the driven transform to the matrix stored in the pose list at the specified index
        :param index :type index: index to go to
        """
        # Get the matrix at the specified index
        pose_matrix = self.get_pose(index=index)
        # Assume the position
        cmds.xform(self.driven_transform, matrix=pose_matrix)

    def delete_pose(self, index=-1, pose_name=""):
        """
        Delete a pose at the specified index or with the given name
        :param index :type int: index to delete or -1 to use pose_name
        :param pose_name :type str: pose name to delete
        """
        # TODO Delete pose will need to remember enabled state + reconnect up pose_name connection when the changes are
        #  made to the solver. Currently can't delete by pose name because there is nothing tying an index to a pose
        #  name
        # If no index and no pose name, raise exception
        if index < 0 and not pose_name:
            raise exceptions.InvalidPoseIndex("Unable to delete pose")

        # Copy a list of the poses
        poses = copy.deepcopy(self.get_poses())

        # Iterate through the existing poses in reverse
        for i in reversed(range(len(poses))):
            # Remove the pose from the list of targets
            cmds.removeMultiInstance('{blender}.poses[{index}]'.format(blender=self, index=i), b=True)

        # Remove the pose at the given index
        poses.pop(index)

        # Re-add all the deleted poses (minus the one we popped)
        for pose_index, matrix in enumerate(poses):
            self.set_pose(index=pose_index, matrix=matrix)

    def get_weight(self, index, as_float=True):
        """
        Get the current weight for the specified index
        :param index :type int
        :param as_float :type bool: return as float or as attribute name of the connected plug
        :return: float or plug
        """
        return utils.get_attr('{weights}[{index}]'.format(weights=self.weights_attr, index=index), as_value=as_float)

    def get_weights(self, as_float=True):
        """
        Get all the weights associated with this node
        :param as_float :type bool: as list of floats or list of plugs
        :return: list of floats or plugs
        """
        return utils.get_attr_array(attr_name=self.weights_attr, as_value=as_float)

    def set_weight(self, index=-1, in_float_attr="", float_value=0.0):
        """
        Set the weight at a given index either by connecting an attribute or specifying a float value
        :param index :type int: index to set
        :param in_float_attr :type str: node.attributeName to connect to this plug
        :param float_value :type float: float value to set
        """
        if index < 0:
            # If the index is less than 0 find the next available index
            index = len(cmds.getAttr(self.weights_attr, multiIndices=True) or [0]) - 1
        # Generate the correct source attr name for the index specified
        source_attr_name = '{weights}[{index}]'.format(weights=self.weights_attr, index=index)
        # Set the array element to either the attr or the float value
        utils.set_attr_or_connect(source_attr_name=source_attr_name, value=in_float_attr or float_value)

    def set_weights(self, in_float_array_attr="", floats=None):
        """
        Set multiple weights either by an attribute array string or a float list.Will overwrite existing values
        :param in_float_array_attr :type str: node.attributeName array attribute to connect all indices with
        :param floats :type list: list of float values to set for each corresponding index
        """
        # Prioritize plugs over setting floats
        if in_float_array_attr:
            # Iterate through all the indices in the array
            for i in range(len(cmds.getAttr(in_float_array_attr, multiIndices=True) or [0])):
                # Generate the source attr name
                in_float_attr = "{array_attr}[{index}]".format(array_attr=in_float_array_attr, index=i)
                # Set the weight for the current index
                self.set_weight(index=i, in_float_attr=in_float_attr)
        elif floats:
            # Iterate through the floats
            for index, float_value in enumerate(floats):
                # Set the weight for the current index
                self.set_weight(index=index, float_value=float_value)

    def delete(self):
        """
        Delete the node associated with this wrapper
        """
        # If we aren't in edit mode we still have connections made to decomposeMatrix nodes that we want to delete
        if not self.edit:
            # Enable edit mode to delete those decomposeMatrix nodes
            self.edit = True
        # Disconnect all attrs
        destination_conns = cmds.listConnections(self, plugs=True, connections=True, source=False) or []
        for i in range(0, len(destination_conns), 2):
            cmds.disconnectAttr(destination_conns[i], destination_conns[i + 1])
        source_conns = cmds.listConnections(self, plugs=True, connections=True, destination=False) or []

        for i in range(0, len(source_conns), 2):
            # we have to flip these because the output is always node centric and not connection centric
            cmds.disconnectAttr(source_conns[i + 1], source_conns[i])
        # Delete the node
        cmds.delete(self.node)
