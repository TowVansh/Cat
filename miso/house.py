"""The window her room lives in, and the business of travelling between the
desktop and home.

Windows has no supported way to drive its virtual desktops -- there is no
public API, only undocumented COM interfaces that change between builds -- so
her home is a full-screen window of its own instead. It behaves the way the
idea wanted: she leaves the right-hand edge of your desktop, and she is home;
she walks out of the door, and she is back.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget, QVBoxLayout

from . import home


class House(QWidget):
    """Full-screen window holding the room."""

    came_back = Signal()

    def __init__(self, needs, drives) -> None:
        super().__init__()
        self.setWindowTitle("Miso's home")
        self.setWindowFlags(Qt.Window)

        self.room = home.Room(needs, drives, self)
        self.room.left_home.connect(self._leave)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.room)

        screen = QGuiApplication.primaryScreen().geometry()
        self.resize(screen.width(), screen.height())

    # ------------------------------------------------------------ arriving

    def arrive(self, from_door: bool = True) -> None:
        """She comes home. Put her at the door and let her wander in."""
        self.room.cx = 0.09 if from_door else 0.5
        self.room.cy = 0.66
        self.room.target = None
        self.room.busy_with = None
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self.room.cat.speak("home", "say")

    def _leave(self) -> None:
        self.hide()
        self.came_back.emit()

    def keyPressEvent(self, ev) -> None:
        if ev.key() == Qt.Key_Escape:
            self._leave()
        else:
            super().keyPressEvent(ev)

    def closeEvent(self, ev) -> None:
        ev.ignore()          # closing the room only sends her back outside
        self._leave()
