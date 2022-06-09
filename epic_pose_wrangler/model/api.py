#  Copyright Epic Games, Inc. All Rights Reserved.
class RBFAPI(object):
    """
    Base class for creating RBF API classes
    """
    UPGRADE_AVAILABLE = False
    VERSION = "0.0.0"

    def __init__(self, view=False, parent=None, file_path=None):
        super(RBFAPI, self).__init__()
        self._view = view
        self._parent = parent
        self._file_path = file_path
