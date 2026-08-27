"""Miso's home.

A room she actually lives in, rather than a menu about a room. It fills the
screen, and everything in it does something:

  the bed        she sleeps here when she is tired
  the bowls      they empty on their own; you refill them
  the sink       drag from the tap to the water bowl
  the food sack  drag from the sack to the food bowl
  the toy basket she drags things out of it when she is bored
  the shelf      her real journal and the real things she carried home
  the bin        her compost -- nothing is ever thrown away, only put here
  the door       she walks out of it, back onto your desktop

The shelf is the part worth pointing at: it is not decoration. It reads her
actual memory files off the disk through the same jail everything else uses,
so a Miso who has lived a month has a fuller shelf than one born this morning.
"""
from __future__ import annotations

import math
import random
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPolygonF, QRadialGradient)
from PySide6.QtWidgets import QWidget

from . import face, jail, memory

# ------------------------------------------------------------------ colours

WALL_TOP = QColor("#F0DFC8")
WALL_BOT = QColor("#E3CDB0")
FLOOR_NEAR = QColor("#C98F5F")
FLOOR_FAR = QColor("#B0764A")
PLANK = QColor(120, 80, 50, 70)
SKIRTING = QColor("#F7EEE2")
INK = QColor("#4A3A30")

WOOD = QColor("#A9764B")
WOOD_DARK = QColor("#8A5E39")
CUSHION = QColor("#E9A9A9")
CUSHION_DARK = QColor("#D98C8C")
METAL = QColor("#CFD6DC")
METAL_DARK = QColor("#A7B2BB")
WATER = QColor("#8FD3E8")
KIBBLE = QColor("#B5763F")
PAPER = QColor("#FBF3E6")
LEAF = QColor("#94B87A")

NIGHT = QColor("#2B3550")
DAY = QColor("#9FD3EE")
DUSK = QColor("#E8A87C")


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def mix(c1: QColor, c2: QColor, t: float) -> QColor:
    return QColor(int(lerp(c1.red(), c2.red(), t)),
                  int(lerp(c1.green(), c2.green(), t)),
                  int(lerp(c1.blue(), c2.blue(), t)))


class Room(QWidget):
    """The whole home, drawn to fit whatever screen it is given."""

    left_home = Signal()             # she walked out of the door
    fed = Signal(str)                # "food" or "water"
    poked = Signal(str)              # something was clicked

    def __init__(self, needs, drives, parent=None) -> None:
        super().__init__(parent)
        self.needs = needs
        self.drives = drives
        self.setMouseTracking(True)

        self.cat = face.Cat(self)
        self.cat.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        # where she is standing in the room, in fractions of the floor
        self.cx = 0.55
        self.cy = 0.62
        self.vx = 0.0
        self.target: tuple[float, float] | None = None
        self.doing = "wander"
        self.until = time.time() + 3
        self.busy_with: str | None = None

        self._t0 = time.time()
        self._last = time.time()
        self._hover: str | None = None
        self._dragging: str | None = None
        self._drag_at = QPointF(0, 0)
        self._splash: list[list[float]] = []
        self._toy_out: str | None = None
        self._toy_pos = QPointF(0, 0)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._frame)
        self._timer.start(16)

    # ------------------------------------------------------------ geometry
    # everything is placed in fractions so the room fits any screen

    @property
    def floor_y(self) -> float:
        return self.height() * 0.52

    def spot(self, name: str) -> QRectF:
        w, h = self.width(), self.height()
        f = self.floor_y
        below = h - f
        return {
            "door":    QRectF(w * 0.02, f - below * 0.62, w * 0.075, below * 0.72),
            "bed":     QRectF(w * 0.72, f + below * 0.34, w * 0.20, below * 0.30),
            "food":    QRectF(w * 0.33, f + below * 0.50, w * 0.075, below * 0.15),
            "water":   QRectF(w * 0.42, f + below * 0.50, w * 0.075, below * 0.15),
            "counter": QRectF(w * 0.13, f - below * 0.10, w * 0.20, below * 0.62),
            "sink":    QRectF(w * 0.155, f - below * 0.08, w * 0.105, below * 0.16),
            "sack":    QRectF(w * 0.275, f - below * 0.02, w * 0.055, below * 0.20),
            "basket":  QRectF(w * 0.55, f + below * 0.46, w * 0.095, below * 0.22),
            "shelf":   QRectF(w * 0.62, f - below * 0.52, w * 0.26, below * 0.30),
            "bin":     QRectF(w * 0.93, f + below * 0.30, w * 0.05, below * 0.26),
            "window":  QRectF(w * 0.40, f - below * 0.68, w * 0.17, below * 0.42),
        }[name]

    def _at(self, pos: QPointF) -> str | None:
        for name in ("sink", "sack", "food", "water", "basket", "shelf",
                     "bed", "bin", "door"):
            if self.spot(name).adjusted(-6, -6, 6, 6).contains(pos):
                return name
        return None

    # --------------------------------------------------------------- frame

    def _frame(self) -> None:
        now = time.time()
        dt = min(0.05, now - self._last)
        self._last = now

        self.needs.tick()
        self._live(now, dt)

        # splashes from the tap
        for s in self._splash:
            s[1] += s[3] * dt
            s[3] += 1400 * dt
            s[4] -= dt
        self._splash = [s for s in self._splash if s[4] > 0]

        # put her body where the room says she is
        cw, ch = self.cat.width(), self.cat.height()
        self.cat.move(int(self.cx * self.width() - cw / 2),
                      int(self.cy * self.height() - ch + ch * 0.07))
        self.cat.depth_scale = 0.85 + 0.45 * ((self.cy - 0.52) / 0.46)
        self.update()

    def _live(self, now: float, dt: float) -> None:
        """What she does in here. Needs come first, then boredom, then rest."""
        if self.busy_with == "eat":
            if not self.needs.eat(dt) or self.needs.hunger < 0.08:
                self._done_with("that was good" if self.needs.hunger < 0.2 else None)
            return
        if self.busy_with == "drink":
            if not self.needs.drink(dt) or self.needs.thirst < 0.08:
                self._done_with(None)
            return

        if self.target is not None:
            tx, ty = self.target
            dx, dy = tx - self.cx, ty - self.cy
            dist = math.hypot(dx, dy)
            if dist < 0.012:
                self.target = None
                self._arrive()
            else:
                speed = 0.30 * dt
                self.cx += dx / dist * speed
                self.cy += dy / dist * speed
                self.cat._facing = 1 if dx > 0 else -1
                self.cat.set_pose("walk")
            return

        if now < self.until:
            return

        want = self.needs.wants()
        if want == "drink":
            self._go_to("water", "drink")
        elif want == "eat":
            self._go_to("food", "eat")
        elif self.drives.energy < 0.3:
            self._go_to("bed", "sleep")
        elif self.drives.boredom > 0.5 and random.random() < 0.6:
            self._go_to("basket", "play")
        else:
            complaint = self.needs.complaining()
            if complaint and random.random() < 0.35:
                self.cat.speak(complaint, "say")
            self.cx = min(0.9, max(0.12, self.cx + random.uniform(-0.16, 0.16)))
            self.cy = min(0.95, max(0.56, self.cy + random.uniform(-0.05, 0.05)))
            self.until = now + random.uniform(2.5, 6.0)
            self.cat.set_pose(random.choice(["idle", "curious", "idle"]))

    def _go_to(self, place: str, then: str) -> None:
        r = self.spot(place)
        self.target = (r.center().x() / self.width(),
                       min(0.95, (r.bottom() + 6) / self.height()))
        self._next = then

    def _arrive(self) -> None:
        what = getattr(self, "_next", None)
        if what == "eat":
            self.busy_with = "eat"
            self.cat.set_pose("idle")
        elif what == "drink":
            self.busy_with = "drink"
            self.cat.set_pose("idle")
        elif what == "sleep":
            self.cat.set_pose("sleep")
            self.until = time.time() + random.uniform(20, 60)
        elif what == "play":
            self._toy_out = random.choice(["yarn", "mouse", "feather"])
            self._toy_pos = QPointF(self.cx * self.width() + random.uniform(-90, 90),
                                    self.cy * self.height() - 10)
            self.cat.set_pose("happy")
            self.drives.satisfy(boredom=-0.4)
            self.until = time.time() + random.uniform(5, 12)
            self.cat.speak(random.choice(["!", "mrrp", "got it", "hup"]), "say")
        else:
            self.until = time.time() + 2

    def _done_with(self, line: str | None) -> None:
        self.busy_with = None
        self.until = time.time() + random.uniform(2, 5)
        self.needs.save()
        if line:
            self.cat.speak(line, "say")

    # --------------------------------------------------------------- mouse

    def mouseMoveEvent(self, ev) -> None:
        self._hover = self._at(ev.position())
        if self._dragging:
            self._drag_at = ev.position()
        self.setCursor(Qt.PointingHandCursor if self._hover else Qt.ArrowCursor)

    def mousePressEvent(self, ev) -> None:
        where = self._at(ev.position())
        if where in ("sink", "sack"):
            self._dragging = where
            self._drag_at = ev.position()
        elif where == "door":
            self.left_home.emit()
        elif where == "basket":
            self._go_to("basket", "play")
        elif where == "bed":
            self._go_to("bed", "sleep")
        elif where in ("food", "water"):
            # a click on a bowl is the impatient way to fill it
            self._fill(where)
        elif where in ("shelf", "bin"):
            self.poked.emit(where)

    def mouseReleaseEvent(self, ev) -> None:
        if not self._dragging:
            return
        over = self._at(ev.position())
        if self._dragging == "sink" and over == "water":
            self._fill("water")
        elif self._dragging == "sack" and over == "food":
            self._fill("food")
        self._dragging = None

    def _fill(self, which: str) -> None:
        if which == "water":
            self.needs.fill_water()
            r = self.spot("water")
            for _ in range(16):
                self._splash.append([r.center().x() + random.uniform(-14, 14),
                                     r.top(), 0.0, random.uniform(-260, -60),
                                     random.uniform(0.25, 0.6)])
        else:
            self.needs.fill_food()
        self.needs.save()
        self.fed.emit(which)
        self.cat.speak(random.choice(["!!", "oh!", "mrrp", "yes"]), "say")
        self._go_to(which, "drink" if which == "water" else "eat")

    # ------------------------------------------------------------ painting

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        t = time.time() - self._t0

        self._draw_room(p)
        self._draw_window(p, t)
        self._draw_counter(p)
        self._draw_shelf(p)
        self._draw_bed(p)
        self._draw_basket(p)
        self._draw_bin(p)
        self._draw_bowls(p)
        self._draw_door(p)
        if self._toy_out:
            self._draw_toy(p, self._toy_out, self._toy_pos, t)
        self._draw_splash(p)
        if self._dragging:
            self._draw_carried(p)
        self._draw_labels(p)

    # ---- shell

    def _draw_room(self, p: QPainter) -> None:
        w, h, f = self.width(), self.height(), self.floor_y

        wall = QLinearGradient(0, 0, 0, f)
        wall.setColorAt(0, WALL_TOP)
        wall.setColorAt(1, WALL_BOT)
        p.fillRect(QRectF(0, 0, w, f), QBrush(wall))

        floor = QLinearGradient(0, f, 0, h)
        floor.setColorAt(0, FLOOR_FAR)
        floor.setColorAt(1, FLOOR_NEAR)
        p.fillRect(QRectF(0, f, w, h - f), QBrush(floor))

        # boards fanning out in perspective
        p.setPen(QPen(PLANK, 1.6))
        for i in range(-14, 30):
            x_far = w * 0.5 + (i - 8) * w * 0.031
            x_near = w * 0.5 + (i - 8) * w * 0.085
            p.drawLine(QPointF(x_far, f), QPointF(x_near, h))
        for k in range(1, 7):
            y = f + (h - f) * (k / 6.5) ** 1.7
            p.setPen(QPen(PLANK, 1.2))
            p.drawLine(QPointF(0, y), QPointF(w, y))

        p.setPen(Qt.NoPen)
        p.setBrush(SKIRTING)
        p.drawRect(QRectF(0, f - h * 0.022, w, h * 0.022))
        p.setPen(QPen(QColor(0, 0, 0, 40), 1.4))
        p.drawLine(QPointF(0, f), QPointF(w, f))

        # warm pool of light from the window
        glow = QRadialGradient(w * 0.48, f * 0.7, w * 0.42)
        glow.setColorAt(0.0, QColor(255, 240, 200, 46))
        glow.setColorAt(1.0, QColor(255, 240, 200, 0))
        p.setBrush(QBrush(glow))
        p.setPen(Qt.NoPen)
        p.drawRect(self.rect())

    def _draw_window(self, p: QPainter, t: float) -> None:
        r = self.spot("window")
        hour = time.localtime().tm_hour + time.localtime().tm_min / 60
        day = max(0.0, math.sin((hour - 6) / 24 * 2 * math.pi * 1.0))
        sky = mix(NIGHT, DAY, day)
        if 5 < hour < 8 or 17 < hour < 20:
            sky = mix(sky, DUSK, 0.45)

        p.setPen(QPen(INK, 3))
        p.setBrush(sky)
        p.drawRoundedRect(r, 6, 6)

        p.setPen(Qt.NoPen)
        if day < 0.25:                                    # stars
            random.seed(7)
            for _ in range(14):
                sx = r.left() + random.random() * r.width()
                sy = r.top() + random.random() * r.height() * 0.7
                a = 120 + 100 * math.sin(t * 1.4 + sx)
                p.setBrush(QColor(255, 255, 255, int(max(40, a))))
                p.drawEllipse(QPointF(sx, sy), 1.6, 1.6)
            random.seed()
            p.setBrush(QColor(250, 248, 230))
            p.drawEllipse(QPointF(r.center().x() + r.width() * 0.22,
                                  r.top() + r.height() * 0.26), 13, 13)
            p.setBrush(sky)
            p.drawEllipse(QPointF(r.center().x() + r.width() * 0.28,
                                  r.top() + r.height() * 0.22), 12, 12)
        else:
            p.setBrush(QColor(255, 236, 170))
            p.drawEllipse(QPointF(r.center().x() - r.width() * 0.2,
                                  r.top() + r.height() * 0.24), 16, 16)
            p.setBrush(QColor(255, 255, 255, 150))
            for i in range(3):
                cx = r.left() + (0.2 + 0.3 * i) * r.width() + math.sin(t * 0.2 + i) * 8
                cy = r.top() + r.height() * (0.4 + 0.13 * i)
                p.drawEllipse(QRectF(cx, cy, r.width() * 0.34, r.height() * 0.11))

        p.setPen(QPen(INK, 3))
        p.drawLine(QPointF(r.center().x(), r.top()), QPointF(r.center().x(), r.bottom()))
        p.drawLine(QPointF(r.left(), r.center().y()), QPointF(r.right(), r.center().y()))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, 6, 6)

    # ---- furniture

    def _draw_counter(self, p: QPainter) -> None:
        r = self.spot("counter")
        top_h = r.height() * 0.16

        # the splashback behind, so the tap has something to come out of
        p.setPen(QPen(INK, 3))
        p.setBrush(QColor("#EAD9BE"))
        p.drawRoundedRect(QRectF(r.left(), r.top() - r.height() * 0.42,
                                 r.width(), r.height() * 0.46), 5, 5)

        # cupboard body, then the worktop laid across it
        p.setBrush(WOOD)
        p.drawRoundedRect(QRectF(r.left(), r.top() + top_h * 0.6,
                                 r.width(), r.height() - top_h * 0.6), 8, 8)
        p.setBrush(QColor("#C69A6B"))
        p.drawRoundedRect(QRectF(r.left() - 6, r.top(), r.width() + 12, top_h), 5, 5)

        # cupboard doors
        p.setPen(QPen(QColor(120, 82, 50, 150), 2))
        p.setBrush(Qt.NoBrush)
        for i in (0, 1):
            p.drawRoundedRect(QRectF(r.left() + 10 + i * (r.width() / 2 - 4),
                                     r.top() + top_h + 12,
                                     r.width() / 2 - 16, r.height() * 0.48), 4, 4)

        # the sink, sunk into the worktop
        sink = self.spot("sink")
        p.setPen(QPen(INK, 3))
        p.setBrush(METAL_DARK)
        p.drawRoundedRect(sink, 8, 8)
        p.setBrush(METAL)
        p.drawRoundedRect(sink.adjusted(5, 4, -5, -6), 6, 6)
        p.setPen(QPen(METAL_DARK, 2))
        p.drawEllipse(QPointF(sink.center().x(), sink.center().y() + 2), 5, 3)

        # the tap, rising from the splashback and curving over the basin
        p.setPen(QPen(QColor("#8E9AA5"), 7, Qt.SolidLine, Qt.RoundCap))
        base_y = sink.top() - 2
        top_y = sink.top() - sink.height() * 1.35
        tap = QPainterPath(QPointF(sink.left() + 14, base_y))
        tap.lineTo(QPointF(sink.left() + 14, top_y))
        tap.quadTo(QPointF(sink.left() + 14, top_y - 14),
                   QPointF(sink.center().x() + 2, top_y - 10))
        tap.lineTo(QPointF(sink.center().x() + 6, top_y + 2))
        p.drawPath(tap)
        p.setPen(QPen(QColor("#6F7B86"), 4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(sink.left() + 14, top_y - 2),
                   QPointF(sink.left() + 30, top_y - 8))

        sack = self.spot("sack")
        p.setPen(QPen(INK, 3))
        p.setBrush(QColor("#D9C39A"))
        p.drawRoundedRect(sack, 6, 6)
        p.setBrush(KIBBLE)
        p.drawEllipse(QRectF(sack.left() + 4, sack.top() - 3,
                             sack.width() - 8, sack.height() * 0.20))
        p.setPen(QPen(INK, 2))
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.drawText(sack.adjusted(0, sack.height() * 0.35, 0, 0),
                   int(Qt.AlignHCenter | Qt.AlignTop), "food")

    def _draw_bowls(self, p: QPainter) -> None:
        for name, level, colour in (("food", self.needs.food_bowl, KIBBLE),
                                    ("water", self.needs.water_bowl, WATER)):
            r = self.spot(name)
            p.setPen(QPen(INK, 3))
            p.setBrush(QColor("#EFE2D2") if name == "food" else QColor("#DCEAF2"))
            p.drawEllipse(QRectF(r.left(), r.top(), r.width(), r.height() * 1.05))
            inner = r.adjusted(r.width() * 0.16, r.height() * 0.22,
                               -r.width() * 0.16, -r.height() * 0.02)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 30))
            p.drawEllipse(inner)
            if level > 0.02:
                fill = QRectF(inner)
                fill.setHeight(inner.height() * max(0.22, level))
                fill.moveBottom(inner.bottom())
                p.setBrush(colour)
                p.drawEllipse(fill)
                if name == "food":
                    p.setBrush(QColor("#9B6234"))
                    random.seed(int(level * 40))
                    for _ in range(5):
                        p.drawEllipse(QPointF(
                            fill.center().x() + random.uniform(-fill.width() * 0.3,
                                                               fill.width() * 0.3),
                            fill.center().y() + random.uniform(-3, 3)), 3, 2.2)
                    random.seed()

    def _draw_bed(self, p: QPainter) -> None:
        """A basket with a raised back, not a plate on the floor."""
        r = self.spot("bed")
        rim = r.height() * 0.24

        # the back wall of the basket, rising behind where she lies
        p.setPen(QPen(INK, 3))
        p.setBrush(CUSHION_DARK)
        back = QPainterPath()
        back.moveTo(r.left(), r.center().y())
        back.quadTo(QPointF(r.center().x(), r.top() - rim),
                    QPointF(r.right(), r.center().y()))
        back.lineTo(r.right(), r.center().y() + 4)
        back.quadTo(QPointF(r.center().x(), r.top() - rim * 0.55),
                    QPointF(r.left(), r.center().y() + 4))
        back.closeSubpath()
        p.drawPath(back)

        # the cushion she actually sits on
        p.setBrush(CUSHION)
        p.drawEllipse(QRectF(r.left(), r.center().y() - r.height() * 0.16,
                             r.width(), r.height() * 0.72))
        p.setPen(QPen(QColor(255, 255, 255, 100), 2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(r.left() + r.width() * 0.14,
                             r.center().y() - r.height() * 0.04,
                             r.width() * 0.72, r.height() * 0.44))
        # a soft dent in the middle from being slept in
        p.setPen(QPen(QColor(190, 120, 130, 90), 2))
        p.drawArc(QRectF(r.left() + r.width() * 0.26,
                         r.center().y() + r.height() * 0.06,
                         r.width() * 0.48, r.height() * 0.28), 0, 180 * 16)

    def _draw_basket(self, p: QPainter) -> None:
        r = self.spot("basket")
        p.setPen(QPen(INK, 3))
        p.setBrush(QColor("#D8A96B"))
        path = QPainterPath()
        path.moveTo(r.left() + r.width() * 0.10, r.top())
        path.lineTo(r.right() - r.width() * 0.10, r.top())
        path.lineTo(r.right(), r.bottom())
        path.lineTo(r.left(), r.bottom())
        path.closeSubpath()
        p.drawPath(path)
        p.setPen(QPen(QColor(150, 105, 60, 130), 1.6))
        for i in range(1, 4):
            y = r.top() + r.height() * i / 4
            p.drawLine(QPointF(r.left() + 3, y), QPointF(r.right() - 3, y))
        # toys poking out
        p.setPen(QPen(INK, 2.4))
        p.setBrush(QColor("#E4728F"))
        p.drawEllipse(QPointF(r.center().x() - r.width() * 0.16, r.top() + 2), 11, 11)
        p.setBrush(QColor("#9AC6E8"))
        p.drawEllipse(QPointF(r.center().x() + r.width() * 0.18, r.top() - 1), 9, 9)

    def _draw_bin(self, p: QPainter) -> None:
        r = self.spot("bin")
        p.setPen(QPen(INK, 3))
        p.setBrush(QColor("#B9C3A8"))
        p.drawRoundedRect(r, 5, 5)
        p.setBrush(LEAF)
        p.drawRoundedRect(QRectF(r.left() - 3, r.top() - 7, r.width() + 6, 10), 4, 4)

    def _draw_shelf(self, p: QPainter) -> None:
        """Her real memory, on a wall."""
        r = self.spot("shelf")
        p.setPen(QPen(INK, 3))
        p.setBrush(WOOD)
        p.drawRoundedRect(QRectF(r.left(), r.bottom() - 9, r.width(), 11), 3, 3)

        listing = jail.look("/home/collection")
        things = listing.get("things", []) if listing.get("ok") else []
        days = memory.days_lived()

        # her journal: one book per day she has lived, up to a shelf-full
        x = r.left() + 12
        p.setPen(QPen(INK, 2))
        for i in range(min(9, max(3, days))):
            bh = 30 + (i * 7) % 16
            p.setBrush([QColor("#C98B8B"), QColor("#8FB4C9"), QColor("#C9B98F"),
                        QColor("#A8C99B")][i % 4])
            p.drawRoundedRect(QRectF(x, r.bottom() - 9 - bh, 13, bh), 2, 2)
            x += 16

        # things she carried home
        x = max(x + 14, r.center().x())
        for i, _name in enumerate(things[:6]):
            p.setBrush(PAPER)
            p.drawRoundedRect(QRectF(x, r.bottom() - 9 - 22, 17, 22), 3, 3)
            p.setPen(QPen(QColor(150, 130, 110), 1.4))
            for k in range(3):
                p.drawLine(QPointF(x + 3, r.bottom() - 26 + k * 5),
                           QPointF(x + 14, r.bottom() - 26 + k * 5))
            p.setPen(QPen(INK, 2))
            x += 21

        # a plant on the end, because a shelf with one book on it looks sad
        px = r.right() - 26
        p.setPen(QPen(INK, 2))
        p.setBrush(QColor("#C98B6B"))
        p.drawRoundedRect(QRectF(px, r.bottom() - 9 - 16, 20, 16), 3, 3)
        p.setBrush(LEAF)
        for dx, dy, rad in ((-1, -9, 9), (8, -13, 7), (-8, -14, 6)):
            p.drawEllipse(QPointF(px + 10 + dx, r.bottom() - 25 + dy), rad, rad * 0.8)

        p.setPen(QColor(120, 100, 85, 170))
        p.setFont(QFont("Segoe UI", 9))
        label = f"{days} day{'s' if days != 1 else ''} of journal"
        if things:
            label += f"  ·  {len(things)} thing{'s' if len(things) != 1 else ''} carried home"
        p.drawText(QRectF(r.left(), r.bottom() + 6, r.width(), 20),
                   int(Qt.AlignHCenter), label)

    def _draw_door(self, p: QPainter) -> None:
        r = self.spot("door")
        p.setPen(QPen(INK, 3))
        p.setBrush(WOOD_DARK)
        p.drawRoundedRect(r, 6, 6)
        p.setBrush(QColor("#E8C88A"))
        p.drawEllipse(QPointF(r.right() - 12, r.center().y()), 5, 5)
        p.setPen(QColor(255, 255, 255, 190))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(r, int(Qt.AlignHCenter | Qt.AlignTop), "\nout")

    # ---- bits and pieces

    def _draw_toy(self, p: QPainter, kind: str, at: QPointF, t: float) -> None:
        wobble = math.sin(t * 7) * 4
        p.setPen(QPen(INK, 2.4))
        if kind == "yarn":
            p.setBrush(QColor("#E4728F"))
            p.drawEllipse(at + QPointF(wobble, 0), 13, 13)
            p.setPen(QPen(QColor(200, 90, 120), 1.6))
            for i in range(3):
                p.drawArc(QRectF(at.x() - 11 + wobble, at.y() - 11, 22, 22),
                          i * 1800, 1400)
        elif kind == "mouse":
            p.setBrush(QColor("#C9C2B8"))
            p.drawEllipse(QRectF(at.x() - 12 + wobble, at.y() - 7, 24, 14))
            p.setPen(QPen(QColor(160, 150, 140), 2.4, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(at + QPointF(12 + wobble, 0), at + QPointF(26 + wobble, -6))
        else:
            p.setBrush(QColor("#9AC6E8"))
            feather = QPolygonF([at + QPointF(wobble, -14), at + QPointF(8 + wobble, 4),
                                 at + QPointF(wobble, 12), at + QPointF(-8 + wobble, 4)])
            p.drawPolygon(feather)

    def _draw_splash(self, p: QPainter) -> None:
        p.setPen(Qt.NoPen)
        for x, y, _vx, _vy, life in self._splash:
            p.setBrush(QColor(140, 210, 235, int(220 * min(1.0, life * 2))))
            p.drawEllipse(QPointF(x, y), 3.2, 3.6)

    def _draw_carried(self, p: QPainter) -> None:
        """What you are holding, following the cursor."""
        at = self._drag_at
        p.setPen(QPen(INK, 2.4))
        if self._dragging == "sink":
            p.setBrush(WATER)
            p.drawEllipse(at, 13, 15)
            p.setBrush(QColor(255, 255, 255, 120))
            p.drawEllipse(at + QPointF(-4, -5), 4, 4)
        else:
            p.setBrush(KIBBLE)
            for dx, dy in ((0, 0), (9, 4), (-8, 5), (3, -8)):
                p.drawEllipse(at + QPointF(dx, dy), 5, 4)

    def _draw_labels(self, p: QPainter) -> None:
        if not self._hover:
            return
        words = {
            "sink": "drag water to her bowl",
            "sack": "drag food to her bowl",
            "food": "her food bowl",
            "water": "her water bowl",
            "basket": "her toys",
            "bed": "her bed",
            "shelf": "her journal, and what she carried home",
            "bin": "her compost. nothing is ever thrown away",
            "door": "let her out onto your desktop",
        }[self._hover]
        r = self.spot(self._hover)
        p.setFont(QFont("Segoe UI", 10))
        box = QRectF(r.center().x() - 130, r.top() - 34, 260, 26)
        p.setPen(QPen(INK, 2))
        p.setBrush(QColor(255, 253, 249, 240))
        p.drawRoundedRect(box, 12, 12)
        p.setPen(QColor("#3B2E26"))
        p.drawText(box, int(Qt.AlignCenter), words)
