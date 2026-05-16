# -*- coding: utf-8 -*-
"""Qt-native system tray icon. Replaces the old pystray + plyer combo."""

import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from i18n import t


def _fallback_icon():
    """Load assets/icon.png if the caller didn't pass an icon."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.normpath(
        os.path.join(here, "..", "assets", "icon.png"))
    if os.path.exists(candidate):
        return QIcon(candidate)
    return QIcon()


class Tray(QObject):
    """Wrap QSystemTrayIcon. Emits show/exit signals; lets the App decide
    what to do with them."""

    show_requested = Signal()
    exit_requested = Signal()

    def __init__(self, icon: QIcon = None, parent=None):
        super().__init__(parent)
        if icon is None or icon.isNull():
            icon = _fallback_icon()
        self._icon_obj = QSystemTrayIcon(icon, parent)
        self._icon_obj.setToolTip(t("app_short"))

        self._menu = QMenu()
        self._act_show = QAction(t("tray_show"), self._menu)
        self._act_exit = QAction(t("tray_exit"), self._menu)
        self._act_show.triggered.connect(self.show_requested.emit)
        self._act_exit.triggered.connect(self.exit_requested.emit)
        self._menu.addAction(self._act_show)
        self._menu.addSeparator()
        self._menu.addAction(self._act_exit)
        self._icon_obj.setContextMenu(self._menu)

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

    # ------------------------------------------------------------------
    # Live language switch
    # ------------------------------------------------------------------
    def retranslate(self):
        try:
            self._icon_obj.setToolTip(t("app_short"))
            self._act_show.setText(t("tray_show"))
            self._act_exit.setText(t("tray_exit"))
        except Exception:
            pass
