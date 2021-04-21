
class UIWidget(object):
    """class that will be inherited to do things like showUI"""

    ui_name  = "widget" #the name that will be used to find the UI in __main__

    def cleanupOnClose(self):
        """implement any cleaup code here"""

    @classmethod
    def showUI(cls, *args, **kwargs):
        """creates and instance then shows the UI"""

        ui = cls.createInstance(*args, **kwargs)
        ui.show()
        return ui

    @classmethod
    def createInstance(cls, *args, **kwargs):
        """create an instance of the UI - kills any existing instances"""

        import __main__
        windows = __main__.__dict__.setdefault("qt_windows", {})

        #get the ui name and if it's open, close it before re-instantiating
        ui = windows.get(cls.ui_name)
        if ui:
            ui.close()
        windows[cls.ui_name] = cls(*args, **kwargs)

        return windows[cls.ui_name]

