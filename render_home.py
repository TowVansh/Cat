"""Render the room to a picture so the art can be checked without opening it."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtCore import QPoint
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from miso import drives, home, needs

app = QApplication(sys.argv)

n = needs.Needs(food_bowl=0.55, water_bowl=0.85, hunger=0.4, thirst=0.3)
d = drives.Drives()

room = home.Room(n, d)
room.resize(1600, 900)
room._toy_out = "yarn"
from PySide6.QtCore import QPointF
room._toy_pos = QPointF(820, 640)
room._hover = "sink"
room.cat._p = dict(room.cat._p)
for _ in range(30):
    room._frame()

img = QImage(1600, 900, QImage.Format_ARGB32)
room.render(img, QPoint(0, 0))
out = Path(__file__).parent / "_setup" / "home_preview.png"
img.save(str(out))
print("wrote", out)
