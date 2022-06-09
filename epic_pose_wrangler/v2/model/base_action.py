#  Copyright Epic Games, Inc. All Rights Reserved.
import abc


class BaseAction(object):
    __display_name__ = "BaseAction"
    __tooltip__ = ""
    __category__ = ""

    @classmethod
    @abc.abstractmethod
    def validate(cls, ui_context):
        raise NotImplementedError

    @abc.abstractmethod
    def execute(self, ui_context=None, **kwargs):
        raise NotImplementedError

    def __init__(self, api=None):
        self._api = api

    @property
    def api(self):
        return self._api
