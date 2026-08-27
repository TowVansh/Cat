"""There is only ever one Miso.

Two copies do not just look wrong -- they share the same drives.json and
needs.json, so each one overwrites the other's memory of how hungry she is and
how long since she saw you. State goes to whichever process saved last.

So the second launch never becomes a second cat. It hands its instruction to
the one already running ("open your home", "come out") and exits. Clicking the
home shortcut while she is on the desktop now sends her home, which is what
clicking it obviously means.

The lock is a named pipe held by the running process. If Miso is killed the
pipe dies with her, so a crash never leaves a stale lock behind.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

PIPE = "miso-the-cat-single-instance"
TIMEOUT_MS = 400


def hand_over(message: str) -> bool:
    """Try to give an instruction to a Miso that is already running.

    Returns True if one was there and took it, in which case this process has
    nothing left to do.
    """
    sock = QLocalSocket()
    sock.connectToServer(PIPE)
    if not sock.waitForConnected(TIMEOUT_MS):
        return False
    sock.write(message.encode("utf-8"))
    sock.flush()
    sock.waitForBytesWritten(TIMEOUT_MS)
    sock.disconnectFromServer()
    return True


class Doorbell(QObject):
    """Listens for later launches and passes on what they wanted."""

    rang = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._server = QLocalServer(self)
        # a previous crash can leave the name taken on some systems
        QLocalServer.removeServer(PIPE)
        self._server.listen(PIPE)
        self._server.newConnection.connect(self._answer)

    def _answer(self) -> None:
        sock = self._server.nextPendingConnection()
        if sock is None:
            return
        # read on the signal rather than blocking: a blocking wait here stalls
        # the event loop that is also driving her body at 60fps
        sock.setParent(self)
        sock.readyRead.connect(lambda s=sock: self._read(s))
        sock.disconnected.connect(sock.deleteLater)

    def _read(self, sock) -> None:
        message = bytes(sock.readAll()).decode("utf-8", "replace").strip()
        if message:
            self.rang.emit(message)
