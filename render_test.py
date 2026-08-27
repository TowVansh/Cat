"""Render the cat in every pose to a sheet so the art can be checked."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

from miso import face

app = QApplication(sys.argv)

POSES = ["idle", "curious", "happy", "lonely", "bored", "sleep", "walk"]
LINES = {
    "idle": "",
    "curious": "there is a door here that will not open",
    "happy": "mrrp",
    "lonely": "you were gone a long time",
    "bored": "",
    "sleep": "",
    "walk": "",
}

cols = len(POSES)
sheet = QImage(face.W * cols, face.H + 30, QImage.Format_ARGB32)
sheet.fill(QColor("#2B2B33"))

p = QPainter(sheet)
p.setRenderHint(QPainter.Antialiasing, True)

for i, pose in enumerate(POSES):
    cat = face.Cat()
    cat._pose_name = pose
    cat._p = dict(face.POSES[pose])
    cat._target = dict(face.POSES[pose])
    cat._walking = pose == "walk"
    cat._step = 1.2
    line = LINES.get(pose, "")
    if line:
        cat.speak(line)
        cat._shown = len(line)
        cat._bubble_a = 1.0
        cat._bubble_w = 0
        cat._bubble_h = 0
        cat.settle(50)
    pix = cat.grab()
    p.drawPixmap(int(i * face.W), 30, pix)

    p.setPen(QColor("#C9C3BC"))
    p.setFont(QFont("Segoe UI", 11))
    p.drawText(QRectF(i * face.W, 4, face.W, 22), int(Qt.AlignCenter), pose)

p.end()
out = Path(__file__).parent / "_setup" / "pose_sheet.png"
sheet.save(str(out))
print("wrote", out)
