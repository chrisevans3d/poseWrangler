#  Copyright Epic Games, Inc. All Rights Reserved.
import math
import traceback

from maya import OpenMaya, cmds

from epic_pose_wrangler.log import LOG
from epic_pose_wrangler.v2.model import exceptions

# NOTE: MTransformationMatrix & MEulerRotation have different values for the same axis.
XFORM_ROTATION_ORDER = {
    'xyz': OpenMaya.MTransformationMatrix.kXYZ,
    'yzx': OpenMaya.MTransformationMatrix.kYZX,
    'zxy': OpenMaya.MTransformationMatrix.kZXY,
    'xzy': OpenMaya.MTransformationMatrix.kXZY,
    'yxz': OpenMaya.MTransformationMatrix.kYXZ,
    'zyx': OpenMaya.MTransformationMatrix.kZYX
}

EULER_ROTATION_ORDER = {
    'xyz': OpenMaya.MEulerRotation.kXYZ,
    'yzx': OpenMaya.MEulerRotation.kYZX,
    'zxy': OpenMaya.MEulerRotation.kZXY,
    'xzy': OpenMaya.MEulerRotation.kXZY,
    'yxz': OpenMaya.MEulerRotation.kYXZ,
    'zyx': OpenMaya.MEulerRotation.kZYX
}


def compose_matrix(position, rotation, rotation_order='xyz'):
    """
    Compose a 4x4 matrix with given transformation.

    >>> compose_matrix((0.0, 0.0, 0.0), (90.0, 0.0, 0.0))
    [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
    """

    # create rotation ptr
    rot_script_util = OpenMaya.MScriptUtil()
    rot_script_util.createFromDouble(*[deg * math.pi / 180.0 for deg in rotation])
    rot_double_ptr = rot_script_util.asDoublePtr()

    # construct transformation matrix
    xform_matrix = OpenMaya.MTransformationMatrix()
    xform_matrix.setTranslation(OpenMaya.MVector(*position), OpenMaya.MSpace.kTransform)
    xform_matrix.setRotation(rot_double_ptr, XFORM_ROTATION_ORDER[rotation_order], OpenMaya.MSpace.kTransform)

    matrix = xform_matrix.asMatrix()
    return [matrix(m, n) for m in range(4) for n in range(4)]


def decompose_matrix(matrix, rotation_order='xyz'):
    """
    Decomposes a 4x4 matrix into translation and rotation.

    >>> decompose_matrix([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0])
    ((0.0, 0.0, 0.0), (90.0, 0.0, 0.0))
    """

    mmatrix = OpenMaya.MMatrix()
    OpenMaya.MScriptUtil.createMatrixFromList(matrix, mmatrix)

    # create transformation matrix
    xform_matrix = OpenMaya.MTransformationMatrix(mmatrix)

    # get translation
    translation = xform_matrix.getTranslation(OpenMaya.MSpace.kTransform)

    # get rotation
    # @ref: https://github.com/LumaPictures/pymel/blob/master/pymel/core/datatypes.py
    # The apicls getRotation needs a "RotationOrder &" object, which is impossible to make in python...
    euler_rotation = xform_matrix.eulerRotation()
    euler_rotation.reorderIt(EULER_ROTATION_ORDER[rotation_order])
    rotation = euler_rotation.asVector()

    return (
        (translation.x, translation.y, translation.z),
        (rotation.x * 180.0 / math.pi, rotation.y * 180.0 / math.pi, rotation.z * 180.0 / math.pi)
    )


def euler_to_quaternion(rotation, rotation_order='xyz'):
    """
    Returns Euler Rotation as Quaternion

    >>> euler_to_quaternion((90, 0, 0))
    (0.7071, 0.0, 0.0, 0.70710))
    """
    euler_rotation = OpenMaya.MEulerRotation(
        rotation[0] * math.pi / 180.0,
        rotation[1] * math.pi / 180.0,
        rotation[2] * math.pi / 180.0
    )
    euler_rotation.reorderIt(EULER_ROTATION_ORDER[rotation_order])

    quat = euler_rotation.asQuaternion()
    return quat.x, quat.y, quat.z, quat.w


def quaternion_to_euler(rotation, rotation_order='xyz'):
    """
    Returns Quaternion Rotation as Euler

    quaternion_to_euler((0.7071, 0.0, 0.0, 0.70710))
    (90, 0, 0)
    """
    quat = OpenMaya.MQuaternion(*rotation)
    euler_rotation = quat.asEulerRotation()
    euler_rotation.reorderIt(EULER_ROTATION_ORDER[rotation_order])

    return euler_rotation.x * 180.0 / math.pi, euler_rotation.y * 180.0 / math.pi, euler_rotation.z * 180.0 / math.pi


def is_connected_to_array(attribute, array_attr):
    """
    Check if the attribute is connected to the specified array
    :param attribute :type str: attribute
    :param array_attr :type str array attribute
    :return :type int or None: int of index in the array or None
    """
    try:
        indices = cmds.getAttr(array_attr, multiIndices=True) or []
    except ValueError:
        return None
    for i in indices:
        attr = '{from_attr}[{index}]'.format(from_attr=array_attr, index=i)
        if attribute in (cmds.listConnections(attr, plugs=True) or []):
            return i
    return None


def get_next_available_index_in_array(attribute):
    # Get the next available index
    indices = cmds.getAttr(attribute, multiIndices=True) or []
    i = 0
    for index in indices:
        if index != i and i not in indices:
            indices.append(i)
        i += 1
    indices.sort()
    attrs = ['{from_attr}[{index}]'.format(from_attr=attribute, index=i) for i in indices]
    connections = [cmds.listConnections(attr, plugs=True) or [] for attr in attrs]
    target_index = len(indices)
    for index, conn in enumerate(connections):
        if not conn:
            target_index = index
            break
    return target_index


def message_connect(from_attribute, to_attribute, in_array=False, out_array=False):
    """
    Create and connect a message attribute between two nodes
    """
    # Generate the object and attr names
    from_object, from_attribute_name = from_attribute.split('.', 1)
    to_object, to_attribute_name = to_attribute.split('.', 1)

    # If the attributes don't exist, create them
    if not cmds.attributeQuery(from_attribute_name, node=from_object, exists=True):
        cmds.addAttr(from_object, longName=from_attribute_name, attributeType='message', multi=in_array)
    if not cmds.attributeQuery(to_attribute_name, node=to_object, exists=True):
        cmds.addAttr(to_object, longName=to_attribute_name, attributeType='message', multi=out_array)
    # Check that both attributes, if existing are message attributes
    for a in (from_attribute, to_attribute):
        if cmds.getAttr(a, type=1) != 'message':
            raise exceptions.MessageConnectionError(
                'Message Connect: Attribute {attr} is not a message attribute. CONNECTION ABORTED.'.format(
                    attr=a
                )
            )
    # Connect up the attributes
    try:
        if in_array:
            from_attribute = "{from_attribute}[{index}]".format(
                from_attribute=from_attribute,
                index=get_next_available_index_in_array(from_attribute)
            )

        if out_array:
            to_attribute = "{to_attribute}[{index}]".format(
                to_attribute=to_attribute,
                index=get_next_available_index_in_array(to_attribute)
            )

        return cmds.connectAttr(from_attribute, to_attribute, force=True)
    except Exception as e:
        LOG.error(traceback.format_exc())
        return False


def connect_attr(from_attr, to_attr):
    if not cmds.isConnected(from_attr, to_attr):
        cmds.connectAttr(from_attr, to_attr)


def get_attr(attr_name, as_value=True):
    """
    Get the specified attribute
    :param attr_name :type str: attribute name i.e node.translate
    :param as_value :type bool: return as value or connected plug name
    :return :type list or any: either returns a list of connections or the value of the attribute
    """
    # Check if the attribute is connected
    connections = cmds.listConnections(attr_name, plugs=True)
    if connections and not as_value:
        # If the attribute is connected and we don't want the value, return the connections
        return connections
    elif as_value:
        # Return the value
        return cmds.getAttr(attr_name)


def get_attr_array(attr_name, as_value=True):
    """
    Get the specified array attr
    :param attr_name :type str: attribute name i.e node.translate
    :param as_value :type bool: return as value or connected plug name
    :return :type list or any: either returns a list of connections or the value of the attribute
    """
    # Get the number of indices in the array
    indices = cmds.getAttr(attr_name, multiIndices=True) or []
    # Empty list to store the connected plugs
    connected_plugs = []
    # Empty list to store values
    values = []
    # Iterate through the indices
    for i in indices:
        # Get all the connected plugs for this index
        connections = cmds.listConnections('{attr_name}[{index}]'.format(attr_name=attr_name, index=i), plugs=True)
        # If we want the plugs and not values, store connections
        if connections and not as_value:
            connected_plugs.extend(connections)
        # If we want values, get the value at the index
        elif as_value:
            values.append(cmds.getAttr('{attr_name}[{index}]'.format(attr_name=attr_name, index=i)))
    # Return plugs or values, depending on which one has data
    return connected_plugs or values


def set_attr_or_connect(source_attr_name, value=None, attr_type=None, output=False):
    """
    Set an attribute or connect it to another attribute
    :param source_attr_name :type str: attribute name
    :param value : type any: value to set the attribute to
    :param attr_type :type str: name of the attribute type i.e matrix
    :param output :type bool: is this plug an output (True) or input (False)
    """
    # Type conversion from maya: python
    attr_types = {
        'matrix': list
    }
    # Check if we have a matching type
    matching_type = attr_types.get(attr_type, None)
    # If we have a matching type and the value matches that type, set the attr
    if matching_type is not None and isinstance(value, matching_type):
        cmds.setAttr(source_attr_name, value, type=attr_type)
    # If the value is a string and no type is matched, we want to connect the attributes
    elif isinstance(value, str):
        try:
            # Connect from left->right depending on if the source is output or input
            if output:
                if not cmds.isConnected(source_attr_name, value):
                    cmds.connectAttr(source_attr_name, value)
            else:
                if not cmds.isConnected(value, source_attr_name):
                    cmds.connectAttr(value, source_attr_name)
        except Exception as e:
            raise exceptions.PoseWranglerAttributeError(
                "Unable to {direction} {input} to '{output}'".format(
                    direction="connect" if value else "disconnect",
                    input=source_attr_name if output else value,
                    output=value if output else source_attr_name
                )
            )
    else:
        cmds.setAttr(source_attr_name, value)


def disconnect_attr(attr_name, array=False):
    """
    Disconnect the specified attribute
    :param attr_name :type str: attribute name to disconnect
    :param array :type bool: is this attribute an array?
    """
    attrs = []
    # If we are disconnecting an array, get the names of all the attributes
    if array:
        attrs.extend(cmds.getAttr(attr_name, multiIndices=True) or [])
    # Otherwise append the attr name specified
    else:
        attrs.append(attr_name)
    # Iterate through all the attrs listed
    for attr in attrs:
        # Find their connections and disconnect them
        for plug in cmds.listConnections(attr, plugs=True) or []:
            cmds.disconnectAttr(attr, plug)


def get_selection(_type=""):
    """
    Returns the current selection
    """
    return cmds.ls(selection=True, type=_type)


def set_selection(selection_list):
    """
    Sets the active selection
    """
    cmds.select(selection_list, replace=True)
