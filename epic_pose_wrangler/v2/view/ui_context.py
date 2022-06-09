#  Copyright Epic Games, Inc. All Rights Reserved.
class PoseWranglerUIContext(object):
    def __init__(
            self, current_solvers, current_poses, current_drivers, current_driven, solvers, poses, drivers, driven
    ):
        self._current_solvers = current_solvers
        self._current_poses = current_poses
        self._current_drivers = current_drivers
        self._current_driven = current_driven
        self._solvers = solvers
        self._poses = poses
        self._drivers = drivers
        self._driven = driven

    @property
    def current_solvers(self):
        return self._current_solvers

    @property
    def current_poses(self):
        return self._current_poses

    @property
    def current_drivers(self):
        return self._current_drivers

    @property
    def current_driven(self):
        return self._current_driven

    @property
    def solvers(self):
        return self._solvers

    @property
    def poses(self):
        return self._poses

    @property
    def drivers(self):
        return self._drivers

    @property
    def driven(self):
        return self._driven
