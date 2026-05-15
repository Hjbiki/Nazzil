# -*- coding: utf-8 -*-
"""Qt-native system tray icon. Replaces the old pystray + plyer combo."""

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from i18n import t


class Tray(QObject):
    """Wrap QSystemTrayIcon. Emits show/exit signals; lets the App decide
    what to do with them."""

    show_requested = Signal()
    exit_requested = Signal()

    def __init__(self, icon: QIcon, parent=None):
        super().__init__(parent)
        self._icon_obj = QSystemTrayIcon(icon, parent)
        self._icon_obj.setToolTip(t("app_short"))

        self._menu = QMenu()
        act_show = QAction(t("tray_show"), self._menu)
        act_exit = QAction(t("tray_exit"), self._menu)
        act_show.triggered.connect(self.show_requested.emit)
        act_exit.triggered.connect(self.exit_requested.emit)
        self._menu.addAction(act_show)
        self._menu.addSeparator()
        self._menu.addAction(act_exit)
        self._icon_obj.setContextMenu(self._menu)

        # Left-click / double-click on the tray icon → show window
        self._icon_obj.activated.connect(self._on_activated)

    def _on_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_requested.emit()

    def show(self):
        self._icon_obj.show()

    def hide(self):
        self._icon_obj.hide()

    def is_available(self):
        return QSystemTrayIcon.isSystemTrayAvailable()

    def notify(self, title, message, msec=6000):
        try:
            self._icon_obj.showMessage(
                title, message, QSystemTrayIcon.Information, msec)
        except Exception:
            pass
