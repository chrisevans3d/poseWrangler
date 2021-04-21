import xml.etree.ElementTree as xml
from cStringIO import StringIO

import maya.OpenMayaUI as omui

from PySide2.QtCore import * 
from PySide2.QtGui import * 
from PySide2.QtWidgets import *
from PySide2 import __version__
from shiboken2 import wrapInstance
import pyside2uic as pysideuic    
   

def load_ui(uiFile):
    parsed = xml.parse(uiFile)
    widget_class = parsed.find('widget').get('class')
    form_class = parsed.find('class').text

    with open(uiFile, 'r') as f:
        o = StringIO()
        frame = {}

        pysideuic.compileUi(f, o, indent=0)
        pyc = compile(o.getvalue(), '<string>', 'exec')
        exec pyc in frame

        #Fetch the base_class and form class based on their type in the xml from designer
        form_class = frame['Ui_%s'%form_class]
        base_class = eval('%s'%widget_class)
    return form_class, base_class

def maya_window():
    """Get the Maya main window as a QmainWindow instance"""
    parentWindow = omui.MQtUtil.mainWindow()
    return wrapInstance(long(parentWindow), QWidget)



