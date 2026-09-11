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
        socket = QLocalSocket()
        socket.connectToServer(self._name)
        if socket.waitForConnected(200):
            socket.write(b"activate")
            socket.flush()
            socket.waitForBytesWritten(200)
            socket.disconnectFromServer()
            return False
        QLocalServer.removeServer(self._name)
        self._server = QLocalServer()
        self._server.newConnection.connect(self._handle)
        return self._server.listen(self._name)

    def close(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None

    def _handle(self) -> None:
        if self._server is None:
            return
        while self._server.hasPendingConnections():
            connection = self._server.nextPendingConnection()
            connection.readAll()
            connection.disconnectFromServer()
        self._on_activate()
