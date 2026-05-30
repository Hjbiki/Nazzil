# -*- coding: utf-8 -*-
"""Single-instance guard via a QLocalServer named pipe.

Launching Nazzil a second time shouldn't spawn another window — instead the
already-running instance is brought to the front. The first process owns a
local server; later processes connect to it, send a "show" ping, and exit.
"""

import getpass

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


def _server_name() -> str:
    # Per-user so two different Windows accounts can each run their own copy.
    try:
        who = getpass.getuser()
    except Exception:
        who = "user"
    return f"Nazzil-singleton-{who}"


class SingleInstance(QObject):
    """Usage:
        si = SingleInstance()
        if si.is_running():
            si.ping_primary()      # tell the running copy to show itself
            return                 # this process exits
        si.start_server()          # we are the primary
        si.activated.connect(window._tray_show)
    """

    activated = Signal()           # emitted in the primary when a ping arrives

    def __init__(self, parent=None):
        super().__init__(parent)
        self._name = _server_name()
        self._server = None

    def is_running(self) -> bool:
        sock = QLocalSocket()
        sock.connectToServer(self._name)
        ok = sock.waitForConnected(300)
        if ok:
            sock.disconnectFromServer()
        return ok

    def ping_primary(self) -> bool:
        """Connect to the primary and ask it to surface its window."""
        sock = QLocalSocket()
        sock.connectToServer(self._name)
        if not sock.waitForConnected(500):
            return False
        try:
            sock.write(b"show")
            sock.flush()
            sock.waitForBytesWritten(500)
            sock.disconnectFromServer()
        except Exception:
            return False
        return True

    def start_server(self):
        # Clear any stale socket left behind by a crash, then listen.
        QLocalServer.removeServer(self._name)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_new_connection)
        self._server.listen(self._name)

    def _on_new_connection(self):
        conn = self._server.nextPendingConnection()
        if conn is not None:
            try:
                conn.readAll()
            except Exception:
                pass
            self.activated.emit()
