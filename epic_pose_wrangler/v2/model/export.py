#  Copyright Epic Games, Inc. All Rights Reserved.
import os
import json
from maya import cmds

from special_projects.publish_tools.fbx_cmd import fbx_export
from special_projects.publish_tools.utils import find_top_joints

from special_projects.rigging.rbf_node import RBFNode


class RBFNodeExporter(object):
    """
    Utility class to export a RBFsolver node, exports a JSON and FBX
    
    >>> from special_projects.rigging.rbf_node.export import RBFNodeExporter
    >>> node = 'my_UE4RBFSolver_node'
    >>> asset_name = 'my_asset_name'
    >>> export_directory = 'my:/export/directory'
    >>> exporter = RBFNodeExporter(node, asset_name, export_directory)
    >>> exporter.export()

    Result:
        export_directory/node.json
        export_directory/node.fbx
    """

    def __init__(self, node, asset_name, export_directory):
        """
        Initialize RBF Exporter
        """

        self.set_node(node)
        self.set_asset_name(asset_name)
        self.set_export_directory(export_directory)
        self._set_fbx_export_path()
        self._set_json_export_path()

    def node(self):
        return self._node

    def set_node(self, node):

        if not cmds.objectType(node, isAType=RBFNode.node_type):
            raise TypeError('Invalid "{}" node: "{}"'.format(RBFNode.node_type, node))

        self._node = RBFNode(node)

    def asset_name(self):
        return self._asset_name

    def set_asset_name(self, asset_name):
        self._asset_name = asset_name

    def export_directory(self):
        return self._export_directory

    def set_export_directory(self, directory):
        if os.path.isdir(directory) and os.path.exists(directory):
            self._export_directory = directory
        else:
            raise IOError('Export directory "{}" does not exists'.format(directory))

    def fbx_export_path(self):
        return self._fbx_export_path

    def _set_fbx_export_path(self):
        self._fbx_export_path = os.path.join(self._export_directory, '{}.fbx'.format(self._node))

    def json_export_path(self):
        return self._json_export_path

    def _set_json_export_path(self):
        self._json_export_path = os.path.join(self._export_directory, '{}.json'.format(self._node))

    # -------------------------------------------------------------------------------------

    def export(self):
        """
        Exports FBX and sidecar JSON file
        """

        self.fbx_export()
        self.json_export()

    def json_export(self):
        """
        Exports JSON sidecar
        """

        self.node().name_unnamed_poses()

        config = self._node.data()
        config['export_fbx'] = self.fbx_export_path()
        config['asset_name'] = self.asset_name()

        with open(self.json_export_path(), 'w') as outfile:
            json.dump(config, outfile, sort_keys=0, indent=4, separators=(",", ":"))

    def fbx_export(self):
        """
        Exports baked poses to FBX
        """

        self.node().name_unnamed_poses()

        self.bake_poses()
        cmds.select(self.root_joint())
        fbx_export(self.fbx_export_path(),
                   animation=True,
                   bake_complex_animation=True,
                   bake_complex_start=0,
                   bake_complex_end=cmds.playbackOptions(q=True, maxTime=True),
                   up_axis='z')

    # -------------------------------------------------------------------------------------

    def blendshape_nodes(self):
        """
        Finds blendshape nodes from driven attributes
        """

        driven_attributes = self._node.driven_attributes(type='blendShape')

        blendshape_nodes = list()
        for output in driven_attributes:
            for attribute in output:
                blendshape_nodes.append(attribute.split('.')[0])

        return list(set(blendshape_nodes))

    def meshes(self):
        """
        Finds meshes from blendshape nodes
        """

        meshes = list()

        blendShapes = self.blendshape_nodes()
        if blendShapes:
            for blendShape in blendShapes:
                meshes.extend(cmds.deformer(blendShape, q=True, geometry=True))

            meshes = list(set(meshes))
            meshes = cmds.listRelatives(meshes, parent=True)

        return meshes

    def root_joint(self):
        """
        Finds root joint from meshes
        """

        meshes = self.meshes()
        if meshes:
            skeleton = list()
            for mesh in meshes:
                skin_cluster = cmds.ls(cmds.findDeformers(mesh), type='skinCluster')
                if skin_cluster:
                    skin_cluster = skin_cluster[0]
                    influences = cmds.skinCluster(skin_cluster, q=True, inf=True)
                    if influences:
                        skeleton.extend(influences)
                    else:
                        raise RuntimeError('No influences found for "{}"'.format(skin_cluster))
                else:
                    cmds.warning('No skinCluster found for "{}"'.format(mesh))

            root_joints = find_top_joints(skeleton)

        else:
            skeleton = self._node.drivers()
            # for driver in self._node.drivers():
            # driven = driver.replace('_drv', '')
            # if cmds.objExists(driven):
            #    skeleton.append(driven)

            root_joints = find_top_joints(skeleton)

        if not root_joints:
            raise RuntimeError('No root joint found for "{}"'.format(self._node))

        return root_joints[0]

    def add_root_attributes(self, root_joint):
        """
        Adds RBFNode driven attributes to root_joint
        """

        pose_root_attributes = dict()

        poses = self._node.poses()
        for pose in poses:
            driven_attributes = self._node.pose_driven_attributes(pose)  # add type flag!
            current_pose = list()
            for attribute in driven_attributes:
                node, target = attribute.split('.')
                root_attribute = '{}.{}'.format(root_joint, target)
                if root_attribute not in current_pose:
                    if not cmds.objExists(root_attribute):
                        cmds.addAttr(root_joint, ln=target, at='double', k=True)
                    else:
                        input_connection = cmds.listConnections(root_attribute, s=True, d=False, plugs=True)
                        if input_connection:
                            cmds.disconnectAttr(input_connection[0], root_attribute)

                    # cmds.connectAttr(attribute, root_attribute)
                    current_pose.append(root_attribute)

            pose_root_attributes[pose] = current_pose

        return pose_root_attributes

    def bake_poses(self):
        """
        Bakes the RBFNode poses in the timeline for FBX export
        """

        for anim_curve_type in ['animCurveTL', 'animCurveTA', 'animCurveTU']:
            cmds.delete(cmds.ls(type=anim_curve_type))

        pose_root_attributes = self.add_root_attributes(self.root_joint())

        for frame, pose in enumerate(self._node.poses()):

            # go to pose
            self._node.go_to_pose(pose)

            # key controllers
            if self._node.num_controllers():
                for controller in self._node.controllers():
                    cmds.setKeyframe(controller, t=frame, inTangentType='linear', outTangentType='step')

            # or key drivers
            else:
                for driver in self._node.drivers():
                    cmds.setKeyframe(driver, t=frame, inTangentType='linear', outTangentType='step')

            root_attributes = pose_root_attributes.get(pose, [])

            for root_attribute in root_attributes:

                input_connection = cmds.listConnections(root_attribute, s=True, d=False, plugs=True)
                if input_connection:
                    cmds.disconnectAttr(input_connection[0], root_attribute)

                # Key Driven Before/After
                cmds.setAttr(root_attribute, 0)

                if frame == len(self._node.poses()) - 1:
                    cmds.setKeyframe(root_attribute, t=(frame - 1), inTangentType='linear', outTangentType='linear')
                else:
                    cmds.setKeyframe(root_attribute, t=((frame - 1), (frame + 1)), inTangentType='linear',
                                     outTangentType='linear')

                # Key Driven
                cmds.setAttr(root_attribute, 1)
                cmds.setKeyframe(root_attribute, t=frame, inTangentType='linear', outTangentType='linear')

        # set start-end frames
        end_frame = len(self._node.poses()) - 1
        cmds.playbackOptions(minTime=0, maxTime=end_frame, animationStartTime=0, animationEndTime=end_frame)
        cmds.dgdirty(a=True)


class RBFPoseExporterBatch(object):
    """
    Utility class to export multiple RBFsolver nodes, exports a JSON and FBX for each solver

    >>> solvers = cmds.ls(type='UE4RBFSolverNode')
    >>> rig_scene = r'D:\Build\UE5_Main\Collaboration\Frosty\ArtSource\Character\Hero\Kenny\Rig\Kenny_Rig.ma'
    >>> export_directory = r'D:\test\class'
    >>> asset_name = 'Kenny'
    >>> rbf_exporter_batch = RBFPoseExporterBatch(solvers, asset_name, export_directory, rig_scene)

    Result:
        export_directory/node1.json
        export_directory/node1.fbx
        export_directory/node2.json
        export_directory/node2.fbx
    """

    def __init__(self, nodes, asset_name, export_directory, rig_scene):
        self.set_pose_exporter(nodes, asset_name, export_directory)
        self.set_rig_scene(rig_scene)

    def pose_exporter(self):
        return self._poseExporter

    def asset_name(self):
        return self._asset_name

    def export_directory(self):
        return self._export_directory

    def set_pose_exporter(self, nodes, asset_name, export_directory):
        if not hasattr(nodes, '__iter__'):
            nodes = [nodes]

        exporters = list()
        for node in nodes:
            if cmds.objectType(node, isAType=RBFNodeExporter.node_type):
                exporters.append(RBFNodeExporter(node, asset_name, export_directory))

        if not len(exporters):
            raise RuntimeError('No valid {} objects found'.format(RBFNodeExporter.node_type))

        self._poseExporter = exporters
        self._asset_name = asset_name
        self._export_directory = export_directory

    def rig_scene(self):
        return self._rig_scene

    def set_rig_scene(self, rig_scene):
        if not os.path.exists(rig_scene):
            raise IOError('Rig scene "{}" does not exists'.format(rig_scene))

        self._rig_scene = rig_scene

    # -------------------------------------------------------------------------------------

    def export(self, run_in_subprocess=True):
        # TO-DO: Implement run_in_subprocess
        for exporter in self.pose_exporter():
            cmds.file(self.rig_scene(), open=True, force=True)
            exporter.export()
