poseWrangler
============

![alt tag](epic_pose_wrangler/docs/site/html/_images/v2.png)

Overview
---------------
PoseWrangler is a tool for interfacing with Epic’s MayaUERBFPlugin. The plugin is distributed by Epic Games and installed via Quixel Bridge. This is the same version distributed through Quixel Bridge with the Maya plugin (v6.9.2 or later)
 - Supports scenes created with the UERBFSolverNode
 - Multiple Driver Support
 - Initial blendshape support (WIP)
 - Supports Maya 2018-2022
 - Support for custom mirror mappings to allow for rigs with naming conventions that deviate from the default UE5 conventions
 - Fully automatable via Python and MayaPy
 - Serialization/deserialization to dictionary or JSON file
 - Support for custom extensions and context menu actions

__Contributors__
 - Chris Theodosius
 - Chris Evans
 - Judd Simantov
 - David Corral
 - Borna Berc

Opening the tool
---------------
To load the tool, you can call it like so:
```
from epic_pose_wrangler import main
pose_wrangler = main.PoseWrangler()
```
