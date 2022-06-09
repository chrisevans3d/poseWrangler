#  Copyright Epic Games, Inc. All Rights Reserved.

import logging

from PySide2 import QtWidgets, QtCore, QtGui


class LogWidget(logging.Handler):
    """
    Custom Log Handler with embedded QtWidgets.QDockWidget
    """

    def __init__(self):
        super(LogWidget, self).__init__()
        # Set default formatting
        self.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s', '%Y-%m-%d %H:%M:%S'))
        # Create dock
        self._log_dock = QtWidgets.QDockWidget()
        # Only allow it to be parented to the bottom
        self._log_dock.setAllowedAreas(QtCore.Qt.BottomDockWidgetArea)

        central_widget = QtWidgets.QWidget()
        central_widget.setContentsMargins(0, 0, 0, 0)
        self._log_dock.setWidget(central_widget)
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        central_widget.setLayout(main_layout)

        toolbar_layout = QtWidgets.QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addLayout(toolbar_layout)

        self._output_log = QtWidgets.QListWidget()
        self._output_log.setProperty("Log", True)
        self._output_log.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self._output_log.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self._output_log.customContextMenuRequested.connect(self._show_context_menu)
        main_layout.addWidget(self._output_log)

        icon_size_px = 25
        icon_size = QtCore.QSize(icon_size_px, icon_size_px)
        btn_size_px = 30
        btn_size = QtCore.QSize(btn_size_px, btn_size_px)

        self._debug_btn = QtWidgets.QPushButton()
        self._debug_btn.setIcon(QtGui.QIcon(QtGui.QPixmap("PoseWrangler:debug.png")))
        self._debug_btn.setIconSize(icon_size)
        self._debug_btn.setProperty("LogButton", True)
        self._debug_btn.setCheckable(True)
        self._debug_btn.setChecked(False)
        self._debug_btn.setFixedSize(btn_size)
        self._debug_btn.clicked.connect(self._refresh_log)
        toolbar_layout.addWidget(self._debug_btn)

        self._info_btn = QtWidgets.QPushButton()
        self._info_btn.setIcon(QtGui.QIcon(QtGui.QPixmap("PoseWrangler:info.png")))
        self._info_btn.setIconSize(icon_size)
        self._info_btn.setProperty("LogButton", True)
        self._info_btn.setCheckable(True)
        self._info_btn.setChecked(True)
        self._info_btn.setFixedSize(btn_size)
        self._info_btn.clicked.connect(self._refresh_log)
        toolbar_layout.addWidget(self._info_btn)

        self._warning_btn = QtWidgets.QPushButton()
        self._warning_btn.setIcon(QtGui.QIcon(QtGui.QPixmap("PoseWrangler:warning.png")))
        self._warning_btn.setIconSize(icon_size)
        self._warning_btn.setProperty("LogButton", True)
        self._warning_btn.setCheckable(True)
        self._warning_btn.setChecked(True)
        self._warning_btn.setFixedSize(btn_size)
        self._warning_btn.clicked.connect(self._refresh_log)
        toolbar_layout.addWidget(self._warning_btn)

        self._error_btn = QtWidgets.QPushButton()
        self._error_btn.setIcon(QtGui.QIcon(QtGui.QPixmap("PoseWrangler:error.png")))
        self._error_btn.setIconSize(icon_size)
        self._error_btn.setProperty("LogButton", True)
        self._error_btn.setCheckable(True)
        self._error_btn.setChecked(True)
        self._error_btn.setFixedSize(btn_size)
        self._error_btn.clicked.connect(self._refresh_log)
        toolbar_layout.addWidget(self._error_btn)
        toolbar_layout.addStretch(0)

        self._clear_log_btn = QtWidgets.QPushButton()
        self._clear_log_btn.setIcon(QtGui.QIcon(QtGui.QPixmap("PoseWrangler:clear.png")))
        self._clear_log_btn.setIconSize(icon_size)
        self._clear_log_btn.setProperty("LogButton", True)
        self._clear_log_btn.setFixedSize(btn_size)
        self._clear_log_btn.clicked.connect(self._output_log.clear)
        toolbar_layout.addWidget(self._clear_log_btn)

    @property
    def log_dock(self):
        return self._log_dock

    def emit(self, record):
        level_colour_map = {
            logging.DEBUG: QtGui.QColor(91, 192, 222),
            logging.INFO: QtGui.QColor(247, 247, 247),
            logging.WARNING: QtGui.QColor(240, 173, 78),
            logging.ERROR: QtGui.QColor(217, 83, 79)
        }
        msg = self.format(record)
        item = QtWidgets.QListWidgetItem(msg)
        item.setData(QtCore.Qt.UserRole, record.levelno)
        item.setForeground(QtGui.QBrush(level_colour_map[record.levelno]))
        self._output_log.addItem(item)
        self._refresh_log()

    def _refresh_log(self):
        level_btn_map = {
            logging.DEBUG: self._debug_btn,
            logging.INFO: self._info_btn,
            logging.WARNING: self._warning_btn,
            logging.ERROR: self._error_btn
        }
        for i in range(0, self._output_log.count()):
            item = self._output_log.item(i)
            data = item.data(QtCore.Qt.UserRole)
            item.setHidden(not level_btn_map[data].isChecked())

    def _copy_to_clipboard(self):
        clipboard_text = ""
        for item in self._output_log.selectedItems():
            text = item.text()
            clipboard_text += text
            if text:
                clipboard_text += "\n"
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(clipboard_text)

    def _show_context_menu(self, pos):
        if not self._output_log.selectedItems():
            return
        menu = QtWidgets.QMenu(parent=self._output_log)
        copy_action = menu.addAction("Copy")
        copy_action.triggered.connect(self._copy_to_clipboard)
        menu.exec_(QtGui.QCursor.pos())