#  Copyright Epic Games, Inc. All Rights Reserved.
from PySide2 import QtCore, QtGui, QtWidgets


class CategoryWidget(QtWidgets.QWidget):
    def __init__(self, name):
        super(CategoryWidget, self).__init__()

        self.setContentsMargins(0, 0, 0, 0)
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)

        self._category_button = QtWidgets.QPushButton(name)
        font = self._category_button.font()
        font.setBold(True)
        font.setPointSize(10)
        self._category_button.setFont(font)
        self._category_button.setIcon(QtGui.QIcon(QtGui.QPixmap("PoseWrangler:frame_open.png")))
        self._category_button.setIconSize(QtCore.QSize(16, 16))
        self._category_button.clicked.connect(self._toggle_category_visibility)
        self._category_button.setCheckable(True)
        self._category_button.setChecked(True)
        self._category_button.setProperty("Category", True)
        main_layout.addWidget(self._category_button)

        self._category_container = QtWidgets.QWidget()
        self._category_container.setContentsMargins(0, 0, 0, 0)
        self._category_layout = QtWidgets.QVBoxLayout()
        self._category_layout.setContentsMargins(0, 0, 0, 0)
        self._category_layout.setSpacing(0)
        self._category_container.setLayout(self._category_layout)
        main_layout.addWidget(self._category_container)

    def _toggle_category_visibility(self):
        self._category_container.setVisible(self._category_button.isChecked())
        self._category_button.setIcon(
            QtGui.QIcon(QtGui.QPixmap("PoseWrangler:frame_open.png"))
            if self._category_button.isChecked() else QtGui.QIcon(
                QtGui.QPixmap("PoseWrangler:frame_closed.png")
            )
        )

    def add_extension(self, widget):
        self._category_layout.addWidget(widget)
