from __future__ import annotations

from collections.abc import Callable

from PySide6.QtNetwork import QLocalServer, QLocalSocket

SERVER_NAME = "quotabubble"


class SingleInstance:
    def __init__(self, on_activate: Callable[[], None], name: str = SERVER_NAME) -> None:
        self._on_activate = on_activate
        self._name = name
        self._server: QLocalServer | None = None

    def acquire(self) -> bool:
        if self._notify_existing():
            return False
        self._server = QLocalServer()
        self._server.newConnection.connect(self._handle)
        if self._server.listen(self._name):
            return True
        if self._notify_existing():
            self._server = None
            return False
        QLocalServer.removeServer(self._name)
        if self._server.listen(self._name):
            return True
        self._server = None
        return False

    def close(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None

    def _notify_existing(self) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(self._name)
        if not socket.waitForConnected(200):
            return False
        socket.write(b"activate")
        socket.flush()
        socket.waitForBytesWritten(200)
        socket.disconnectFromServer()
        return True

    def _handle(self) -> None:
        if self._server is None:
            return
        while self._server.hasPendingConnections():
            connection = self._server.nextPendingConnection()
            connection.readAll()
            connection.disconnectFromServer()
        self._on_activate()
