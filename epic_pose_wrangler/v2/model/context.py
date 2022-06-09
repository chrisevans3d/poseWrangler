#  Copyright Epic Games, Inc. All Rights Reserved.
class PoseWranglerContext(object):
    def __init__(self, current_solver, solvers):
        self._current_solver = current_solver
        self._solvers = solvers

    @property
    def current_solver(self):
        return self._current_solver

    @property
    def solvers(self):
        return self._solvers
