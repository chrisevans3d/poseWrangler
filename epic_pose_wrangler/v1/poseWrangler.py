#  Copyright Epic Games, Inc. All Rights Reserved.
import traceback
import math
import json
from PySide2 import QtWidgets
import maya.cmds as cmds
import maya.api.OpenMaya as api


class UE4PoseDriver(object):
    '''
    TODO:
        - add a transform to an existing pose driver
        - I was told that the Maya implementation only works with one driver,
            not multiple transforms, this reflects that
        - properly serialize the UI driving mode when opening the UI based on connections into the drivers
        - validate the node network on load, knowing that a driven has driven, etc.. (low prio)
    '''

    def __init__(self, existing_interpolator=None):

        self.name = None

        self.solver = None
        self.decompose_mx_list = []

        self.copied_trs_map = {}

        if existing_interpolator:
            if cmds.nodeType(existing_interpolator) == 'UE4RBFSolverNode':
                self.name = existing_interpolator
                self.solver = existing_interpolator
            else:
                print('Node', existing_interpolator, 'is not of type UE4RBFSolverNode.')
                return

    ## General utils pulled from utils lib
    #################################################################################
    def attrExists(self, attr):
        if '.' in attr:
            node, att = attr.split('.')
            return cmds.attributeQuery(att, node=node, ex=1)
        else:
            cmds.warning('attrExists: No attr passed in: ' + attr)
            return False

    def msgConnect(self, attribFrom, attribTo, debug=0):
        objFrom, attFrom = attribFrom.split('.')
        objTo, attTo = attribTo.split('.')
        objTo, attTo = attribTo.split('.')
        if debug: print('msgConnect>>> Locals:', locals())
        if not self.attrExists(attribFrom):
            cmds.addAttr(objFrom, longName=attFrom, attributeType='message')
        if not self.attrExists(attribTo):
            cmds.addAttr(objTo, longName=attTo, attributeType='message')
            # check that both atts, if existing are msg atts
        for a in (attribTo, attribFrom):
            if cmds.getAttr(a, type=1) != 'message':
                cmds.warning('msgConnect: Attr, ' + a + ' is not a message attribute. CONNECTION ABORTED.')
                return False
        try:
            return cmds.connectAttr(attribFrom, attribTo, f=True)
        except Exception as e:
            print(traceback.format_exc())
            return False

    def break_all_connections(self, node):
        destination_conns = cmds.listConnections(node, plugs=True, connections=True, source=False) or []
        for i in range(0, len(destination_conns), 2):
            cmds.disconnectAttr(destination_conns[i], destination_conns[i + 1])
        source_conns = cmds.listConnections(node, plugs=True, connections=True, destination=False) or []
        for i in range(0, len(source_conns), 2):
            # we have to flip these because the output is always node centric and not connection centric
            cmds.disconnectAttr(source_conns[i + 1], source_conns[i])

    def get_dag_dict(self, dagpose_node):
        dag_dict = {}
        if cmds.nodeType(dagpose_node) == 'dagPose':
            for idx in range(1, cmds.getAttr(dagpose_node + '.members', size=True)):
                conns = cmds.listConnections(dagpose_node + '.members[' + str(idx) + ']')
                if conns:
                    # because it's a message there could be more than one incoming, but Maya doesn't do that
                    # set the value for the name key to the int socket
                    # also this check for length is because of the garbage menber plugs for parents
                    if len(conns) == 1:
                        dag_dict[conns[0]] = idx
            return dag_dict
        else:
            cmds.error('Requires dagPose node.')
            return False

    def get_local_matrix(self, node, invertJointOrient=False):

        local_mx = cmds.xform(node, m=1, q=1)
        # ignore code below for now - that code will take joint orient into account
        return local_mx

        if invertJointOrient:
            # if it's a joint, lets remove the joint orient from the local matrix
            if cmds.nodeType(node) == "joint":
                selList = api.MGlobal.getSelectionListByName(node)
                dagPath = selList.getDagPath(0)

                parentMatrix = dagPath.exclusiveMatrix()
                worldMatrix = dagPath.inclusiveMatrix()

                jointOrient = cmds.getAttr(node + ".jointOrient")[0]
                x = math.radians(jointOrient[0])
                y = math.radians(jointOrient[1])
                z = math.radians(jointOrient[2])
                joEuler = api.MEulerRotation(x, y, z)
                joMatrix = joEuler.asMatrix()

                localMatrix = worldMatrix * parentMatrix.inverse()
                orientLocalMatrix = localMatrix * joMatrix.inverse()

                # combine the orient local matrix and the translation which shouldn't be changed based on the orientation
                for i in range(12):
                    localMatrix[i] = orientLocalMatrix[i]

                # set the local matrix to this
                local_mx = localMatrix

        return local_mx

    def create_matrix_node(self, node, mx_node_name, invertJointOrient=False):
        local_mx = self.get_local_matrix(node, invertJointOrient=invertJointOrient)
        world_mx = cmds.xform(node, m=1, ws=1, q=1)

        mx_node = cmds.createNode('network', name=mx_node_name)
        cmds.addAttr(mx_node, at='matrix', longName='outputLocalMatrix')
        cmds.addAttr(mx_node, at='matrix', longName='outputWorldMatrix')
        cmds.addAttr(mx_node, dt='string', longName='matrix_node_ver')

        self.msgConnect(node + '.mx_pose', mx_node + '.driven_transform')

        cmds.setAttr(mx_node + '.outputLocalMatrix', local_mx, type='matrix')
        cmds.setAttr(mx_node + '.outputWorldMatrix', world_mx, type='matrix')

        return mx_node

    ## Methods used by class
    #################################################################################
    def init_pose_driver_system(self, existing_solver_node):
        # check that it's a solver node
        if cmds.nodeType(existing_solver_node) == 'UE4RBFSolverNode':
            self.solver = existing_solver_node

    def create_pose_driver_system(self, name, input_xform, driven_xforms):
        solver = self.create_UE4RBFSolverNode(name, input_xform, driven_xforms)

    def create_UE4RBFSolverNode(self, name, input_xform, driven_xforms):
        try:
            cmds.undoInfo(openChunk=True, undoName='create pose interpolator')
            # create the interpolator (will be your API)
            self.solver = cmds.createNode('UE4RBFSolverNode', name=name + '_UE4RBFSolver')
            self.name = self.solver

            # Set the default values for the solver node
            cmds.setAttr("{}.radius".format(self.solver), 50)

            # connect the world matrix from the driving xform to the interp
            cmds.connectAttr(input_xform + '.matrix', self.solver + '.inputs[0]')

            # connect the default pose into the first target (Nate said to do this)
            default_mx_node = self.create_matrix_node(input_xform, input_xform + '_base_pose', invertJointOrient=True)
            cmds.connectAttr(default_mx_node + '.outputLocalMatrix', self.solver + '.targets[0].targetValues[0]')

            # connect the driver to the interp for the property to query
            self.msgConnect(input_xform + '.ue4_rbf_solver', self.solver + '.driver')

            # store the driven nodes for the property query
            for node in driven_xforms:
                self.msgConnect(self.solver + '.driven_transforms', node + '.ue4_rbf_solver')

            for node in driven_xforms:

                blender_node_name = node + '_ue4PoseBlender'
                if not cmds.objExists(blender_node_name):
                    print("node: " + blender_node_name + " didn't exist!")

                    # make matrix node
                    mx_node = self.create_matrix_node(node, node + '_base_pose', invertJointOrient=True)
                    print("mx node")
                    print(mx_node)
                    blender_node = cmds.createNode('UE4PoseBlenderNode', name=blender_node_name)

                    # connect the base pose, it doesn't make much sense copying the same mx into
                    # all three slots on this node (base_pose, in_matrix, pose) -but I was told to by the author
                    cmds.connectAttr(mx_node + '.outputLocalMatrix', blender_node + '.basePose')
                    cmds.connectAttr(mx_node + '.outputLocalMatrix', blender_node + '.inMatrix')

                    self.msgConnect(node + '.blenderNode', blender_node + '.drivenTransform')
                    cmds.connectAttr(mx_node + '.outputLocalMatrix', blender_node + '.poses[0]')

                    # connect ourtput, remember that this bone could already be driven
                    next_pose_weight_idx = cmds.getAttr(blender_node + '.weights', size=True)
                    cmds.connectAttr(
                        self.solver + '.outputs[0]',
                        blender_node + '.weights[' + str(next_pose_weight_idx) + ']'
                    )

                    # wire up the pose representation
                    self.msgConnect(self.solver + '.stored_pose_base_pose', mx_node + '.ue4_rbf_solver')


                else:
                    print("node: " + blender_node_name + " did exist!")
                    blender_node = node + '_ue4PoseBlender'
                    # TODO: check that this node is valid and has a base pose connected

                self.msgConnect(self.solver + '.pose_blenders', blender_node + '.ue4_rbf_solver')
                self.msgConnect(self.solver + '.stored_pose_base_pose', default_mx_node + '.ue4_rbf_solver')


        except Exception as e:
            print(traceback.format_exc())
            return False
        finally:
            cmds.undoInfo(closeChunk=True)

    def add_pose(self, pose_name, debug_mode=0):
        '''
        Because the user has selected what xforms are driven on creation of the solver, this function does
        not need to know anything but what we will call the pose, everything else is derived from metadata.
        '''
        try:
            cmds.undoInfo(openChunk=True, undoName='create pose')
            self.is_driving(False)
            if pose_name:
                if debug_mode:
                    # I was storing transforms as locators for testing
                    pose_loc = cmds.spaceLocator(name=pose_name)[0]
                    cmds.delete(cmds.parentConstraint(self.driving_transform, pose_loc))

                # wire up the world mx of the driver in it's current position to the solver
                mx_node_driver = self.create_matrix_node(
                    self.driving_transform,
                    self.driving_transform + '_' + pose_name + '_pose',
                    invertJointOrient=True
                )

                next_target_index = cmds.getAttr(self.solver + '.targets', size=True)
                cmds.connectAttr(
                    mx_node_driver + '.outputLocalMatrix',
                    self.solver + '.targets[' + str(next_target_index) + '].targetValues[0]'
                )

                # get the next output weight
                next_output = cmds.getAttr(self.solver + '.outputs', size=True)

                # hook that up to existing
                for node in self.driven_transforms:
                    # make matrix node
                    mx_node = self.create_matrix_node(node, pose_name + '_' + node + '_mx_pose', invertJointOrient=True)

                    blender_node = cmds.listConnections(node + '.blenderNode')[0]

                    next_pose_idx = cmds.getAttr(blender_node + '.poses', size=True)

                    cmds.connectAttr(
                        mx_node + '.outputLocalMatrix',
                        blender_node + '.poses[' + str(next_pose_idx) + ']'
                    )
                    # connect to weight
                    next_pose_weight_idx = cmds.getAttr(blender_node + '.weights', size=True)
                    cmds.connectAttr(
                        self.solver + '.outputs[' + str(next_output) + ']',
                        blender_node + '.weights[' + str(next_pose_weight_idx) + ']'
                    )

                    # wire up the pose representation
                    self.msgConnect(self.solver + '.stored_pose_' + pose_name, mx_node + '.ue4_rbf_solver')
                    driving_xform_mx = \
                        cmds.listConnections(self.solver + '.targets[' + str(next_target_index) + '].targetValues[0]')[
                            0]
                    self.msgConnect(self.solver + '.stored_pose_' + pose_name, driving_xform_mx + '.ue4_rbf_solver')
            self.is_driving(True)
        except Exception as e:
            print(traceback.format_exc())
        finally:
            cmds.undoInfo(closeChunk=True)

    def update_pose(self, pose_name):
        try:
            cmds.undoInfo(openChunk=True, undoName='enable pose ' + pose_name)
            if pose_name in self.pose_dict:
                for mx_node in self.pose_dict[pose_name]:
                    driven_xform = cmds.listConnections(mx_node + '.driven_transform')[0]
                    # local_mx = cmds.xform(driven_xform, m=1, q=1)
                    local_mx = self.get_local_matrix(driven_xform, invertJointOrient=True)
                    cmds.setAttr(mx_node + '.outputLocalMatrix', local_mx, type='matrix')
        except Exception as e:
            print(traceback.format_exc())
        finally:
            cmds.undoInfo(closeChunk=True)

    def delete_pose(self, pose_name):
        try:
            cmds.undoInfo(openChunk=True, undoName='enable pose ' + pose_name)
            if pose_name in self.pose_dict:
                for mx_node in self.pose_dict[pose_name]:

                    print("mx node")
                    print(mx_node)
                    # this will also remove the pose array instance which keeps the pose computing
                    conn = cmds.listConnections(mx_node + ".outputLocalMatrix", d=1, s=0, p=1)
                    print(conn)
                    if conn:
                        index = int(conn[0].split("[")[-1].split("]")[0])
                        # this means the conn is a poseBlender
                        if ".poses[" in conn[0]:
                            cmds.removeMultiInstance(conn[0], b=1)
                            poseBlender = conn[0].split(".")[0]
                            cmds.removeMultiInstance(poseBlender + ".weights[" + str(index) + "]", b=1)
                            print("pose blender:")
                            print(poseBlender)

                        print("solver")
                        print(self.solver)
                        cmds.removeMultiInstance(self.solver + ".outputs[" + str(index) + "]", b=1)
                        cmds.removeMultiInstance(self.solver + ".targets[" + str(index) + "]", b=1)
                        print("index:")
                        print(index)

                        # driven = cmds.listConnections(mx_node + ".driven_transform")[0]
                        # blender_node_name = driven + '_ue4PoseBlender'
                        # cmds.removeMultiInstance(blender_node_name + ".weights[" + str(index) + "]", b=1)
                    cmds.delete(mx_node)
                cmds.deleteAttr(self.name + '.stored_pose_' + pose_name)
        except Exception as e:
            print(traceback.format_exc())
        finally:
            cmds.undoInfo(closeChunk=True)

    def assume_pose(self, pose_name):
        try:
            cmds.undoInfo(openChunk=True, undoName='enable pose ' + pose_name)
            if pose_name in self.pose_dict:
                for mx in self.pose_dict[pose_name]:
                    driven_xform = cmds.listConnections(mx + '.driven_transform')[0]
                    mx = cmds.getAttr(mx + '.outputLocalMatrix')
                    """
                    matrix = api.MMatrix(mx)
                    matrixFn = api.MTransformationMatrix(matrix)
                    euler = matrixFn.rotation()
                    rotX = math.degrees(euler[0])
                    rotY = math.degrees(euler[1])
                    rotZ = math.degrees(euler[2])
                    translation = matrixFn.translation(api.MSpace.kWorld)
                    scale = matrixFn.scale(api.MSpace.kWorld)

                    try:
                        cmds.setAttr(driven_xform + ".translate", translation[0], translation[1], translation[2])
                    except:
                        pass
                    try:
                        cmds.setAttr(driven_xform + ".rotate", rotX, rotY, rotZ)
                    except:
                        pass
                    try:
                        cmds.setAttr(driven_xform + ".scale", scale[0], scale[1], scale[2])
                    except:
                        pass
                    """
                    # replace this to take joint orient into account
                    cmds.xform(driven_xform, m=mx)


        except Exception as e:
            print(traceback.format_exc())
        finally:
            cmds.undoInfo(closeChunk=True)

    def bake_poses_to_timeline(self, start_frame=0, suppress=False, anim_layer=None):
        """
        Bakes the poses to the timeline and sets the time range to the given animation.
        :param start_frame: start frame of he baked animation
        :param suppress: A bool to suppress the warning dialogue. Meant to be used outside of the UI
        :anim_layer: if given the animations will be baked on that layer.If the layer doesnt exist we will create one.
        """
        bake_bool = True
        pose_list = []
        if not anim_layer:
            anim_layer = "BaseAnimation"
        if not cmds.animLayer(anim_layer, query=True, exists=True):
            cmds.animLayer(anim_layer)
        try:
            cmds.autoKeyframe(e=1, st=0)
            if not suppress:
                ret = QtWidgets.QMessageBox.warning(
                    None, "WARNING: DESTRUCTIVE FUNCTION",
                    "This will bake the poses to the timeline, change your time range, and delete inputs on driving and driven transforms.\n" + \
                    "Do you want this to happen?",
                    QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel,
                    QtWidgets.QMessageBox.Cancel
                )
                if ret == QtWidgets.QMessageBox.StandardButton.Ok:
                    bake_bool = True
                    cmds.undoInfo(openChunk=True, undoName='Bake poses to timeline')
                else:
                    bake_bool = False

            if bake_bool:
                # begin printing UE4 pose list
                # print('<- UE4 Pose List ---------------------->')
                i = start_frame
                for p in self.pose_dict:
                    driven_xforms = []
                    for mx_node in self.pose_dict[p]:
                        driven_xforms.extend(cmds.listConnections(mx_node + '.driven_transform'))
                    # let's key it on the previous and next frames before we pose it
                    cmds.select(driven_xforms)
                    cmds.animLayer(anim_layer, addSelectedObjects=True, e=True)
                    cmds.setKeyframe(driven_xforms, t=[(i - 1), (i + 1)], animLayer=anim_layer)

                    # assume the pose
                    self.assume_pose(p)

                    cmds.setKeyframe(driven_xforms, t=[i], animLayer=anim_layer)

                    # print out to UE4 pose list
                    print(p)
                    pose_list.append(p)

                    # increment to next keyframe
                    i += 1
                # print('<- UE4 Pose List ---------------------->')

                # set the range to the number of keyframes
                cmds.playbackOptions(minTime=0, maxTime=i, animationStartTime=0, animationEndTime=i - 1)
                cmds.dgdirty(a=1)
                return pose_list
            cmds.dgdirty(a=1)
        except Exception as e:
            print(traceback.format_exc())
        finally:
            cmds.undoInfo(closeChunk=True)

    def is_driving(self, state):
        try:
            cmds.undoInfo(openChunk=True, undoName='Change driving state')
            # state is True or False
            if state:
                for node in self.pose_blenders:
                    # let's get the driven transform
                    driven_transform = cmds.listConnections(node + '.drivenTransform')[0]
                    # we have to decompose the out matrix in order to connect it to the driven transform
                    mx_decompose = cmds.createNode('decomposeMatrix', name=node + '_mx_decompose')
                    # we hookup the output mx of the pose driver to the input of the decompose
                    cmds.connectAttr(node + '.outMatrix', mx_decompose + '.inputMatrix')
                    # and the TRS out of the decompose back into the original driven xform
                    cmds.connectAttr(mx_decompose + '.outputTranslate', driven_transform + '.translate', f=True)
                    cmds.connectAttr(mx_decompose + '.outputRotate', driven_transform + '.rotate', f=True)
                    cmds.connectAttr(mx_decompose + '.outputScale', driven_transform + '.scale', f=True)

            else:
                for node in self.pose_blenders:
                    print("debugging:")
                    print(node)
                    mx_decompose_node = cmds.listConnections(node + '.outMatrix')
                    print(mx_decompose_node)
                    while (mx_decompose_node):
                        self.break_all_connections(mx_decompose_node[0])
                        cmds.delete(mx_decompose_node[0])
                        mx_decompose_node = cmds.listConnections(node + '.outMatrix')
        except Exception as e:
            print(traceback.format_exc())
        finally:
            cmds.undoInfo(closeChunk=True)

    def delete(self):
        """function that deletes the node"""

        for mx_nodes in self.pose_dict.values():
            for mx_node in mx_nodes:
                cmds.delete(mx_node)
        cmds.delete(self.pose_blenders)
        cmds.delete(self.solver)

    def add_driven(self, driven):

        try:
            cmds.undoInfo(openChunk=True, undoName='add driven')

            self.msgConnect(self.solver + '.driven_transforms', driven + '.ue4_rbf_solver')
            blender_node_name = driven + '_ue4PoseBlender'
            mx_node = self.create_matrix_node(driven, driven + '_base_pose', invertJointOrient=True)
            blender_node = cmds.createNode('UE4PoseBlenderNode', name=blender_node_name)

            cmds.connectAttr(mx_node + '.outputLocalMatrix', blender_node + '.basePose')
            cmds.connectAttr(mx_node + '.outputLocalMatrix', blender_node + '.inMatrix')

            self.msgConnect(driven + '.blenderNode', blender_node + '.drivenTransform')
            cmds.connectAttr(mx_node + '.outputLocalMatrix', blender_node + '.poses[0]')

            cmds.connectAttr(self.solver + '.outputs[0]', blender_node + '.weights[0]')

            self.msgConnect(self.solver + '.stored_pose_base_pose', mx_node + '.ue4_rbf_solver')
            self.msgConnect(self.solver + '.pose_blenders', blender_node + '.ue4_rbf_solver')

            output_size = cmds.getAttr(self.solver + '.outputs', size=True)
            for i in range(output_size):
                cmds.connectAttr(
                    self.solver + ".outputs[" + str(i) + "]", blender_node + ".weights[" + str(i) + "]",
                    f=1
                )

            for pose_name in self.pose_dict.keys():
                other_mx_node = self.pose_dict[pose_name][0]
                conns = cmds.listConnections(other_mx_node + ".outputLocalMatrix", d=1, s=0, p=1)
                index = None
                for conn in conns:
                    if "poses" in conn and "PoseBlender" in conn:
                        index = int(conn.split("[")[-1].split("]")[0])

                mx_node = self.create_matrix_node(driven, pose_name + '_' + driven + '_mx_pose', invertJointOrient=True)
                cmds.connectAttr(mx_node + '.outputLocalMatrix', blender_node + '.poses[' + str(index) + ']', f=1)

                self.msgConnect(self.solver + '.stored_pose_' + pose_name, mx_node + '.ue4_rbf_solver')


        except Exception as e:
            print(traceback.format_exc())
            return False
        finally:
            cmds.undoInfo(closeChunk=True)

    def copy_driven_trs(self):
        """copies the driven TRS so we can paste it across other poses"""

        for driven in self.driven_transforms:
            translate = cmds.getAttr(driven + ".translate")[0]
            rotate = cmds.getAttr(driven + ".rotate")[0]
            scale = cmds.getAttr(driven + ".scale")[0]
            self.copied_trs_map[driven] = {"translate": translate, "rotate": rotate, "scale": scale}

        print("Copied driven TRS successfully.")

    def paste_driven_trs(self, mult=1.0):
        """pastes the driven trs and multiplies it"""

        for driven, data in self.copied_trs_map.items():
            translate = data['translate']
            rotate = data['rotate']
            scale = list(data['scale'])

            scale[0] = ((scale[0] - 1.0) * mult) + 1.0
            scale[1] = ((scale[1] - 1.0) * mult) + 1.0
            scale[2] = ((scale[2] - 1.0) * mult) + 1.0

            try:
                cmds.setAttr(driven + ".translate", translate[0] * mult, translate[1] * mult, translate[2] * mult)
            except:
                traceback.print_exc()
            try:
                cmds.setAttr(driven + ".rotate", rotate[0] * mult, rotate[1] * mult, rotate[2] * mult)
            except:
                traceback.print_exc()
            try:
                cmds.setAttr(driven + ".scale", scale[0], scale[1], scale[2])
            except:
                traceback.print_exc()

        print("Pasted driven TRS successfully.")

    def zero_base_pose(self):
        """zero's out the base pose"""
        self.assume_pose("base_pose")
        self.is_driving(False)

        for d in self.driven_transforms:
            cmds.setAttr(d + ".translate", 0.0, 0.0, 0.0)
            cmds.setAttr(d + ".rotate", 0.0, 0.0, 0.0)
            cmds.setAttr(d + ".scale", 1.0, 1.0, 1.0)

        self.update_pose("base_pose")
        self.is_driving(True)

    ## Class properties
    #################################################################################
    @property
    def is_enabled(self):

        found_conns = False
        for node in self.pose_blenders:
            mx_decompose_node = cmds.listConnections(node + '.outMatrix')
            if mx_decompose_node:
                found_conns = True
        return found_conns

    @property
    def driven_transforms(self):
        """gets the driven transforms"""

        if cmds.attributeQuery("driven_transforms", n=self.solver, ex=1):
            xforms = cmds.listConnections(self.solver + '.driven_transforms')
            if xforms:
                return xforms

        return []

    @driven_transforms.setter
    def driven_transforms(self, xforms):
        pass

    @property
    def driving_transform(self):
        """gets the driving transform"""

        if cmds.attributeQuery("driver", n=self.solver, ex=1):
            transform = cmds.listConnections(self.solver + '.driver')[0]
            if transform:
                return transform
        return []

    @driving_transform.setter
    def driving_transform(self, transform):
        self.msgConnect(transform + '.ue4_rbf_solver', self.solver + '.driver')

    @property
    def base_dagPose(self):
        xforms = cmds.listConnections(self.solver + '.driven_transforms')
        if xforms:
            return xforms
        else:
            return []

    @base_dagPose.setter
    def base_dagPose(self, dp):
        pass

    @property
    def pose_blenders(self):

        if not cmds.attributeQuery("pose_blenders", ex=1, n=self.solver):
            return []

        xforms = cmds.listConnections(self.solver + '.pose_blenders')
        if xforms:
            return xforms
        else:
            return []

    @pose_blenders.setter
    def poses(self, pose_list):
        # nuke poses connections
        for item in pose_list:
            self.msgConnect(self.solver + '.pose_blenders', item + '.ue4_rbf_solver')

    @property
    def pose_dict(self):
        pose_dict = {}
        attrs = cmds.listAttr(self.solver, st='stored_pose_*')
        if attrs:
            for attr in attrs:
                pose_name = attr.replace('stored_pose_', '')
                pose_matrices = cmds.listConnections(self.solver + '.' + attr)
                pose_dict[pose_name] = pose_matrices
        return pose_dict


def zero_all_base_poses():
    """zero's all driver bases poses"""

    nodes = cmds.ls(type='UE4RBFSolverNode')
    for node in nodes:
        driver_obj = UE4PoseDriver(existing_interpolator=node)
        driver_obj.zero_base_pose()


def export_drivers(drivers, file_path):
    output_data = {"drivers": {}}
    for driver in drivers:

        driver_data = {}
        driver_obj = UE4PoseDriver(existing_interpolator=driver)

        solver = driver_obj.solver
        driver_name = driver_obj.name.replace("_UE4RBFSolver", "")
        driver_data['name'] = driver_name
        driver_data['solver_settings'] = {}
        solver_attrs = cmds.listAttr(solver, k=1)
        for solver_attr in solver_attrs:
            try:
                value = cmds.getAttr(solver + "." + solver_attr)
            except:
                continue
            driver_data['solver_settings'][solver_attr] = value

        driver_data['driver_transform'] = driver_obj.driving_transform
        driver_data['driven_transforms'] = driver_obj.driven_transforms

        """
        driver_data['driven_off_transforms'] = []

        for transform in driver_obj.driven_transforms:
            parent = cmds.listRelatives(transform, p=1)
            if parent:
        """

        driver_data['pose_data'] = {}
        for pose, mx_list in driver_obj.pose_dict.items():
            pose_data = {
                "pose": pose, "local_matrix_map": {}, "world_matrix_map": {}, "driven_trs": {},
                "driving_trs": {}
            }
            driver_obj.assume_pose(pose)

            driving_transforn = driver_obj.driving_transform
            translate = cmds.getAttr(driving_transforn + ".translate")[0]
            rotate = cmds.getAttr(driving_transforn + ".rotate")[0]
            scale = cmds.getAttr(driving_transforn + ".scale")[0]
            pose_data["driving_trs"][driving_transforn] = {"translate": translate, "rotate": rotate, "scale": scale}

            for driven in driver_obj.driven_transforms:
                translate = cmds.getAttr(driven + ".translate")[0]
                rotate = cmds.getAttr(driven + ".rotate")[0]
                scale = cmds.getAttr(driven + ".scale")[0]
                pose_data["driven_trs"][driven] = {"translate": translate, "rotate": rotate, "scale": scale}

            for mx in mx_list:
                local_matrix = cmds.getAttr(mx + ".outputLocalMatrix")
                world_matrix = cmds.getAttr(mx + ".outputWorldMatrix")
                pose_data['local_matrix_map'][mx] = local_matrix
                pose_data['world_matrix_map'][mx] = world_matrix
            driver_data['pose_data'][pose] = pose_data
        output_data['drivers'][driver_name] = driver_data

        # zero the pose
        driver_obj.assume_pose("base_pose")

    with open(file_path, 'w') as outfile:

        json.dump(output_data, outfile, sort_keys=1, indent=4, separators=(",", ":"))

    print("Successfuly export pose data to : " + file_path)


def import_drivers(file_path, driverFilter=None):
    """imports the drivers"""

    with open(file_path) as json_file:
        data = json.load(json_file)

    for driver, driver_data in data['drivers'].items():

        if driverFilter:
            if not driver in driverFilter:
                continue

        print("driver:")
        print(driver)

        driving_transform = driver_data['driver_transform']
        driven_transforms = driver_data['driven_transforms']

        print("driving: ")
        print(driving_transform)
        print("driven: ")
        print(driven_transforms)

        # if the driver exists, then just update it
        if (cmds.objExists(driver + "_UE4RBFSolver")):
            pose_driver_obj = UE4PoseDriver(existing_interpolator=driver + "_UE4RBFSolver")
        else:
            print("Solver NOT found!")
            pose_driver_obj = UE4PoseDriver()
            pose_driver_obj.create_pose_driver_system(driver, driving_transform, driven_transforms)

        # pose_driver_obj.is_driving(True)#delete this one
        pose_driver_obj.is_driving(False)

        for attr, value in driver_data['solver_settings'].items():
            cmds.setAttr(pose_driver_obj.solver + "." + attr, value)

        for pose, pose_data in driver_data['pose_data'].items():

            if pose == "base_pose":
                continue

            if not pose in pose_driver_obj.pose_dict.keys():
                pose_driver_obj.add_pose(pose.replace("_pose", ""))

            local_matrix_map = pose_data['local_matrix_map']
            world_matrix_map = pose_data['local_matrix_map']
            for mx_node, local_matrix in local_matrix_map.items():
                if mx_node.startswith(driving_transform):
                    translate = cmds.getAttr(driving_transform + ".translate")[0]
                    local_matrix[12] = translate[0]
                    local_matrix[13] = translate[1]
                    local_matrix[14] = translate[2]
                cmds.setAttr(mx_node + ".outputLocalMatrix", local_matrix, type="matrix")

            for mx_node, world_matrix in world_matrix_map.items():
                if mx_node.startswith(driving_transform):
                    translate = cmds.getAttr(driving_transform + ".translate")[0]
                    world_matrix[12] = translate[0]
                    world_matrix[13] = translate[1]
                    world_matrix[14] = translate[2]
                cmds.setAttr(mx_node + ".outputWorldMatrix", world_matrix, type="matrix")

        pose_driver_obj.is_driving(True)


def mirror_all_drivers():
    nodes = cmds.ls(type='UE4RBFSolverNode')
    for node in nodes:
        if "_l_" not in node:
            continue

        mirror_pose_driver(node)
        print("-----------------------------------------------------------")
        print("--------successfuly mirrored node: " + node + "-------")
        print("-------------------------------------------------------------")


def mirror_pose_driver(source_pose_driver, pose=None):
    source_syntax = "_l_"
    target_syntax = "_r_"
    target_pose_driver = None
    if "_r_" in source_pose_driver:
        source_syntax = "_r_"
        target_syntax = "_l_"

    target_pose_driver = source_pose_driver.replace(source_syntax, target_syntax)
    source_driver_obj = UE4PoseDriver(existing_interpolator=source_pose_driver)
    poses = source_driver_obj.pose_dict.keys()
    driven = source_driver_obj.driven_transforms
    driving = source_driver_obj.driving_transform
    target_driving = driving.replace(source_syntax, target_syntax)
    target_driver_obj = None
    if not cmds.objExists(target_pose_driver):
        target_driven = []
        for d in driven:
            target_driven.append(d.replace(source_syntax, target_syntax))

        target_driver_obj = UE4PoseDriver()
        target_driver_obj.create_pose_driver_system(
            target_pose_driver.replace("_UE4RBFSolver", ""), target_driving,
            target_driven
        )
    else:
        target_driver_obj = UE4PoseDriver(existing_interpolator=target_pose_driver)

    # make sure the solver settings match
    solver_attrs = cmds.listAttr(source_driver_obj.solver, k=1)
    for solver_attr in solver_attrs:
        try:
            value = cmds.getAttr(source_driver_obj.solver + "." + solver_attr)
        except:
            continue
        cmds.setAttr(target_driver_obj.solver + "." + solver_attr, value)

    for p in poses:

        if pose and not pose == p:
            continue

        # don't mirror the base pose
        if "base_pose" in p:
            continue

        target_pose = p.replace(source_syntax, target_syntax)
        source_driver_obj.assume_pose(p)
        target_driver_obj.is_driving(False)

        # if the pose doesn't exist, lets add it
        if target_pose not in target_driver_obj.pose_dict.keys():
            print("didn't find pose: " + target_pose)
            # mirror_transforms([driving], rotation=True, position=False)
            rotate = cmds.getAttr(driving + ".rotate")[0]
            cmds.setAttr(target_driving + ".rotate", rotate[0], rotate[1], rotate[2])
            mirror_transforms(driven)
            target_driver_obj.add_pose(target_pose)
        else:
            target_driver_obj.assume_pose(target_pose)
            mirror_transforms(driven)
            target_driver_obj.update_pose(target_pose)

        target_driver_obj.is_driving(True)

        print("Successfully mirrored pose: " + p + " to " + target_pose)

    # if no pose was specified, then lets default back to base at the end
    if not pose:
        source_driver_obj.assume_pose("base_pose")
        target_driver_obj.assume_pose("base_pose")


def mirror_transforms(transforms, position=True, rotation=True, scale=True):
    """mirrors the transform"""

    for transform in transforms:
        source_transform = transform

        source_syntax = "_l_"
        target_syntax = "_r_"
        if "_r_" in source_transform:
            source_syntax = "_r_"
            target_syntax = "_l_"

        target_transform = source_transform.replace(source_syntax, target_syntax)
        source_parent_mat = api.MMatrix()
        values = cmds.getAttr(source_transform + ".parentMatrix")
        index = 0
        for i in range(4):
            for j in range(4):
                source_parent_mat.setElement(i, j, values[index])
                index += 1
        target_parent_mat = api.MMatrix()
        values = cmds.getAttr(target_transform + ".parentMatrix")
        index = 0
        for i in range(4):
            for j in range(4):
                target_parent_mat.setElement(i, j, values[index])
                index += 1

        if position:
            pos = cmds.getAttr(source_transform + ".translate")[0]
            pos = api.MVector(pos[0], pos[1], pos[2])
            pos = _mirror_position(parent_matrix=source_parent_mat, m_parent_matrix=target_parent_mat, pos=pos)
            try:
                cmds.setAttr(target_transform + ".translate", pos[0], pos[1], pos[2])
            except:
                pass
        if rotation:
            rot = cmds.getAttr(source_transform + ".rotate")[0]
            rot = api.MVector(rot[0], rot[1], rot[2])
            rot = _mirror_rotation(parent_matrix=source_parent_mat, m_parent_matrix=target_parent_mat, rot=rot)
            try:
                cmds.setAttr(target_transform + ".rotate", rot[0], rot[1], rot[2])
            except:
                pass

        # scale we assume the axis correlate and mirror
        if scale:
            scale = cmds.getAttr(source_transform + ".scale")[0]
            cmds.setAttr(target_transform + ".scale", scale[0], scale[1], scale[2])


def _mirror_position(parent_matrix, m_parent_matrix, pos):
    """this mirrors the position"""

    driver_mat_fn = api.MTransformationMatrix(api.MMatrix.kIdentity)
    driver_mat_fn.setTranslation(pos, api.MSpace.kWorld)
    driver_mat = driver_mat_fn.asMatrix()

    scale_matrix_fn = api.MTransformationMatrix(api.MMatrix.kIdentity)
    scale_matrix_fn.setScale([-1.0, 1.0, 1.0], api.MSpace.kWorld)
    scale_matrix = scale_matrix_fn.asMatrix()

    pos_matrix = driver_mat * parent_matrix
    pos_matrix = pos_matrix * scale_matrix
    pos_matrix = pos_matrix * m_parent_matrix.inverse()
    mat_fn = api.MTransformationMatrix(pos_matrix)
    m_pos = mat_fn.translation(api.MSpace.kWorld)

    return m_pos


def _mirror_rotation(parent_matrix, m_parent_matrix, rot):
    """this mirrors the rotation"""

    driver_mat_fn = api.MTransformationMatrix(api.MMatrix.kIdentity)

    # set the values to radians
    rot[0] = math.radians(rot[0])
    rot[1] = math.radians(rot[1])
    rot[2] = math.radians(rot[2])

    euler = api.MEulerRotation(rot[0], rot[1], rot[2])

    driver_mat_fn.setRotation(euler)
    driver_matrix = driver_mat_fn.asMatrix()

    world_matrix = driver_matrix * parent_matrix
    rot_matrix = parent_matrix.inverse() * world_matrix
    rot_matrix_fn = api.MTransformationMatrix(rot_matrix)
    rot = rot_matrix_fn.rotation(asQuaternion=True)
    rot.x = rot.x * -1.0
    rot.w = rot.w * -1.0
    rot_matrix = rot.asMatrix()
    final_rot_matrix = m_parent_matrix * rot_matrix * m_parent_matrix.inverse()

    rot_matrix_fn = api.MTransformationMatrix(final_rot_matrix)
    rot = rot_matrix_fn.rotation(asQuaternion=False)
    m_rot = api.MVector()
    m_rot[0] = math.degrees(rot[0])
    m_rot[1] = math.degrees(rot[1])
    m_rot[2] = math.degrees(rot[2])

    return m_rot
