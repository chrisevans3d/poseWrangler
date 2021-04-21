from PySide2 import QtWidgets

import ui_widget

class UIWindow( QtWidgets.QMainWindow, ui_widget.UIWidget ):

    #UI name that to find the UI instance - used in showUI()
    ui_name = "window"

    def __init__(self, parent=None):
        super(UIWindow, self).__init__(parent)


    def setupUi(self, window):
        super(UIWindow, self).setupUi(window)


    def show(self):
        super(UIWindow, self).show()

    def showEvent(self, event):
        """show event"""
        super(UIWindow, self).showEvent(event)

    def closeEvent(self, event):
        """called when the UI is closed"""

        #gets called on cleanup
        self.cleanupOnClose()        

    def cleanupOnClose(self):
        """implement any cleaup code here"""
        print("cleaning up on close")
