"""Miso's body.

The cat is drawn, not loaded -- every part of it is vector shapes on a canvas.
That means no sprite sheet to fall out of sync, expressions that interpolate
instead of snapping between frames, and a pose that can be driven straight from
the drives: a bored Miso really does hold its ears differently from a curious
one.

Poses are not switched, they are eased toward. Every visible quantity (ear
angle, eye openness, tail speed, squash) is a number that chases a target, so
the cat is never caught in a hard cut.
"""
from __future__ import annotations

import math
import random
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetrics, QLinearGradient,
                           QPainter, QPainterPath, QPen, QPolygonF)
from PySide6.QtWidgets import QLineEdit, QMenu, QWidget

# ----------------------------------------------------------------- palette

CREAM = QColor("#F7E9D7")
CREAM_SHADE = QColor("#E8D5BC")
TAN = QColor("#D6A279")
TAN_DARK = QColor("#B9835B")
INK = QColor("#4A3A30")
PINK = QColor("#F0AFB4")
BLUSH = QColor(240, 150, 160, 90)
WHITE = QColor("#FFFFFF")

BUBBLE_BG = QColor(255, 253, 249, 246)
BUBBLE_LINE = QColor("#4A3A30")
BUBBLE_TEXT = QColor("#3B2E26")
THOUGHT_TEXT = QColor(90, 78, 70, 200)

W, H = 340, 360          # window
GROUND = H - 26          # where the cat sits
CX = W / 2

REVEAL_CPS = 42.0        # characters per second, game dialogue pace
HOLD_PER_CHAR = 0.055    # how long a finished line stays up
HOLD_MIN, HOLD_MAX = 2.6, 11.0


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


# -------------------------------------------------------------------- pose

POSES = {
    "idle":    dict(ear=0.00, eye=1.00, lid=0.00, tail=1.0, tailup=0.05,
                    squash=0.00, wide=0.00, blush=0.0, tilt=0.0, drop=0.0),
    "curious": dict(ear=1.00, eye=1.20, lid=0.00, tail=2.0, tailup=0.85,
                    squash=-0.06, wide=-0.03, blush=0.0, tilt=-9.0, drop=-5.0),
    "happy":   dict(ear=0.70, eye=0.00, lid=0.00, tail=3.0, tailup=0.70,
                    squash=0.04, wide=0.02, blush=1.0, tilt=0.0, drop=-2.0),
    "lonely":  dict(ear=-0.95, eye=1.05, lid=0.00, tail=0.4, tailup=-0.40,
                    squash=0.10, wide=0.04, blush=0.0, tilt=9.0, drop=7.0),
    "bored":   dict(ear=-0.60, eye=0.90, lid=0.75, tail=0.5, tailup=-0.25,
                    squash=0.13, wide=0.07, blush=0.0, tilt=6.0, drop=5.0),
    "sleep":   dict(ear=-1.00, eye=0.00, lid=1.00, tail=0.2, tailup=-0.55,
                    squash=0.30, wide=0.22, blush=0.0, tilt=4.0, drop=16.0),
    "walk":    dict(ear=0.35, eye=1.00, lid=0.00, tail=2.2, tailup=0.55,
                    squash=-0.04, wide=-0.02, blush=0.0, tilt=0.0, drop=0.0),
}


class Cat(QWidget):
    """The whole pet: body, face, speech bubble, and a place to type."""

    said = Signal(str)          # user pressed enter in the input box

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(W, H)
        self.setMouseTracking(True)
        # the window behind this is translucent; the cat must not paint a
        # rectangle of its own over it
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)

        # animation clock
        self._t0 = time.time()
        self._pose_name = "idle"
        self._p = dict(POSES["idle"])           # current, eased
        self._target = dict(POSES["idle"])

        # blinking and twitching
        self._blink_at = time.time() + random.uniform(2, 5)
        self._blink = 0.0
        self._twitch = 0.0
        self._twitch_at = time.time() + random.uniform(4, 12)

        # where the eyes are looking (follows the cursor, gently)
        self._gaze = QPointF(0, 0)
        self._gaze_target = QPointF(0, 0)

        # walking, and where in the room she is standing
        self._step = 0.0
        self._walking = False
        self._facing = 1
        self.depth_scale = 1.0      # perspective, driven by Antics
        self.spin = 0.0             # tail-chasing
        self.lean = 0.0             # body lean into a movement

        # speech
        self._line = ""
        self._kind = "say"          # say | think
        self._queue: list[tuple[str, str]] = []
        self._shown = 0.0
        self._said_at = 0.0
        self._bubble_w = 0.0
        self._bubble_h = 0.0
        self._bubble_a = 0.0        # alpha, eased

        # typing
        self.entry = QLineEdit(self)
        self.entry.setPlaceholderText("say something to miso...")
        self.entry.setStyleSheet("""
            QLineEdit {
                background: rgba(255,253,249,242);
                border: 2px solid #4A3A30;
                border-radius: 13px;
                padding: 5px 11px;
                color: #3B2E26;
                font-family: 'Segoe UI'; font-size: 12px;
            }""")
        self.entry.setGeometry(int(CX - 128), H - 24, 256, 26)
        self.entry.hide()
        self.entry.returnPressed.connect(self._entered)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._frame)
        self._timer.start(1000 // 60)

    # ------------------------------------------------------------- driving

    def set_pose(self, name: str) -> None:
        if name in POSES and name != self._pose_name:
            self._pose_name = name
            self._target = dict(POSES[name])
            self._walking = name == "walk"

    def speak(self, text: str, kind: str = "say") -> None:
        """Queue a line. Lines wait their turn instead of replacing each other --
        a reply followed immediately by 'looking around' would otherwise wipe the
        reply in the same frame, and it would look like Miso never answered."""
        text = text.strip()
        if not text:
            return
        if kind == "say":
            # something Miso actually says outranks a thought it was mid-way
            # through; drop pending thoughts so the reply is next
            self._queue = [q for q in self._queue if q[1] == "say"]
            if self._line and self._kind == "think":
                self._line = ""
        self._queue.append((text, kind))
        if not self._line:
            self._next_line()

    def _next_line(self) -> None:
        if not self._queue:
            return
        text, kind = self._queue.pop(0)
        self._line = text
        self._kind = kind
        self._shown = 0.0
        self._said_at = time.time()

    def open_entry(self) -> None:
        self.entry.show()
        self.entry.setFocus()

    def _entered(self) -> None:
        text = self.entry.text().strip()
        self.entry.clear()
        self.entry.hide()
        if text:
            self.said.emit(text)

    # --------------------------------------------------------------- frame

    def _frame(self) -> None:
        now = time.time()
        ease = 0.10

        for key, target in self._target.items():
            self._p[key] = lerp(self._p[key], target, ease)

        # blink
        if now > self._blink_at:
            self._blink = 1.0
            self._blink_at = now + random.uniform(2.2, 6.5)
        self._blink = max(0.0, self._blink - 0.16)

        # ear twitch
        if now > self._twitch_at:
            self._twitch = 1.0
            self._twitch_at = now + random.uniform(5, 15)
        self._twitch = max(0.0, self._twitch - 0.09)

        # gaze drifts toward wherever it was last looking
        self._gaze.setX(lerp(self._gaze.x(), self._gaze_target.x(), 0.12))
        self._gaze.setY(lerp(self._gaze.y(), self._gaze_target.y(), 0.12))

        if self._walking:
            self._step += 0.18

        # reveal speech one character at a time
        if self._line:
            self._shown = min(len(self._line), self._shown + REVEAL_CPS / 60.0)
            done = self._shown >= len(self._line)
            hold = min(HOLD_MAX, max(HOLD_MIN, len(self._line) * HOLD_PER_CHAR))
            if done and now - self._said_at > hold + len(self._line) / REVEAL_CPS:
                self._line = ""
                self._shown = 0.0
                self._next_line()      # whatever was waiting gets its turn

        # the bubble chases the size of the text revealed so far, so it grows
        # as the words arrive. this is animation state, so it belongs here and
        # not in the paint pass.
        tw, th = self._measure(self._line[: int(self._shown)])
        self._bubble_w = lerp(self._bubble_w, tw + 30, 0.28)
        self._bubble_h = lerp(self._bubble_h, th + 22, 0.28)
        self._bubble_a = lerp(self._bubble_a, 1.0 if self._line else 0.0, 0.18)
        self.update()

    def _measure(self, shown: str) -> tuple[float, float]:
        font = QFont("Segoe UI", 11)
        font.setItalic(self._kind == "think")
        fm = QFontMetrics(font)
        rect = fm.boundingRect(QRectF(0, 0, W - 54, 400).toRect(),
                               int(Qt.TextWordWrap), shown or " ")
        return rect.width(), rect.height()

    def settle(self, frames: int = 40) -> None:
        """Run the easing forward without waiting -- used when rendering stills."""
        for _ in range(frames):
            self._frame()

    # ------------------------------------------------------------- pointer

    def mouseMoveEvent(self, ev) -> None:
        # eyes follow the cursor within a small range
        dx = (ev.position().x() - CX) / (W / 2)
        dy = (ev.position().y() - (GROUND - 96)) / (H / 2)
        self._gaze_target = QPointF(max(-1, min(1, dx)) * 3.4,
                                    max(-1, min(1, dy)) * 2.6)
        super().mouseMoveEvent(ev)

    def leaveEvent(self, ev) -> None:
        self._gaze_target = QPointF(0, 0)
        super().leaveEvent(ev)

    # ------------------------------------------------------------ painting

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        t = time.time() - self._t0

        # perspective: further back in the room means smaller, drawn about the
        # spot where she meets the floor so she never appears to float
        p.save()
        p.translate(CX, GROUND)
        p.scale(self.depth_scale, self.depth_scale)
        if abs(self.spin) > 0.5:
            p.rotate(self.spin)
        if abs(self.lean) > 0.2:
            p.rotate(self.lean)
        p.translate(-CX, -GROUND)

        self._draw_shadow(p, t)
        self._draw_cat(p, t)
        p.restore()

        if self._pose_name == "sleep":
            self._draw_zzz(p, t)
        if self._bubble_a > 0.02:
            self._draw_bubble(p)

    # ---- shadow

    def _draw_shadow(self, p: QPainter, t: float) -> None:
        breathe = math.sin(t * 1.7) * 0.02
        w = 116 * (1 + breathe)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(60, 45, 38, 46))
        p.drawEllipse(QRectF(CX - w / 2, GROUND - 9, w, 18))

    # ---- the cat itself

    def _draw_cat(self, p: QPainter, t: float) -> None:
        pr = self._p
        breathe = math.sin(t * 1.7) * 0.022
        squash = pr["squash"]
        bob = math.sin(self._step * 2) * 3.0 if self._walking else 0.0

        p.save()
        p.translate(CX, GROUND + bob)

        body_h = 84 * (1 - squash + breathe)
        body_w = 98 * (1 + pr["wide"] + squash * 0.35)
        head_y = -(body_h + 44) + 16 + pr["drop"]

        self._draw_tail(p, t, body_h)
        if self._walking:
            self._draw_legs(p)

        # body
        outline = QPen(INK, 3.2)
        outline.setJoinStyle(Qt.RoundJoin)
        grad = QLinearGradient(0, -body_h, 0, 0)
        grad.setColorAt(0.0, CREAM)
        grad.setColorAt(1.0, CREAM_SHADE)
        p.setPen(outline)
        p.setBrush(QBrush(grad))
        body = QRectF(-body_w / 2, -body_h, body_w, body_h * 1.06)
        path = QPainterPath()
        path.addRoundedRect(body, body_w * 0.5, body_h * 0.62)
        p.drawPath(path)

        # front paws
        p.setBrush(TAN)
        for sx in (-1, 1):
            p.drawEllipse(QRectF(sx * 9 - 15, -15, 30, 15))

        # chest patch
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 70))
        p.drawEllipse(QRectF(-17, -body_h * 0.62, 34, body_h * 0.44))

        self._draw_head(p, t, head_y)
        p.restore()

    def _draw_legs(self, p: QPainter) -> None:
        p.setPen(QPen(INK, 3.0))
        p.setBrush(TAN)
        for i, sx in enumerate((-1, 1)):
            swing = math.sin(self._step + i * math.pi) * 7
            p.drawEllipse(QRectF(sx * 26 - 12 + swing, -14, 24, 14))

    def _draw_tail(self, p: QPainter, t: float, body_h: float) -> None:
        pr = self._p
        sway = math.sin(t * 1.6 * max(0.2, pr["tail"])) * (9 + 7 * pr["tail"])
        up = pr["tailup"]
        f = self._facing

        # a long S from behind the hip, curling up beside the body
        start = QPointF(f * 30, -body_h * 0.20)
        c1 = QPointF(f * (72 + sway * 0.3), -body_h * (0.16 + 0.10 * up))
        c2 = QPointF(f * (98 + sway * 0.9), -body_h * (0.78 + 0.62 * up))
        end = QPointF(f * (70 + sway * 1.3), -body_h * (1.18 + 0.86 * up))

        path = QPainterPath(start)
        path.cubicTo(c1, c2, end)

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(INK, 15, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(path)
        p.setPen(QPen(CREAM, 9.5, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(path)

        # tan tip, drawn as the last stretch of the same curve
        tip = QPainterPath(path.pointAtPercent(0.70))
        tip.quadTo(path.pointAtPercent(0.86), end)
        p.setPen(QPen(INK, 15, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(tip)
        p.setPen(QPen(TAN, 9.5, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(tip)

    def _draw_head(self, p: QPainter, t: float, head_y: float) -> None:
        pr = self._p
        p.save()
        p.translate(0, head_y)
        p.rotate(pr["tilt"] + math.sin(t * 0.8) * 1.2)

        r = 47.0
        self._draw_ears(p, r)

        p.setPen(QPen(INK, 3.2))
        grad = QLinearGradient(0, -r, 0, r)
        grad.setColorAt(0.0, CREAM)
        grad.setColorAt(1.0, CREAM_SHADE)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QRectF(-r, -r * 0.94, r * 2, r * 1.88))

        # blush
        if pr["blush"] > 0.05:
            p.setPen(Qt.NoPen)
            c = QColor(BLUSH)
            c.setAlpha(int(90 * pr["blush"]))
            p.setBrush(c)
            for sx in (-1, 1):
                p.drawEllipse(QRectF(sx * 30 - 11, 4, 22, 13))

        self._draw_eyes(p)
        self._draw_muzzle(p)
        p.restore()

    def _draw_ears(self, p: QPainter, r: float) -> None:
        pr = self._p
        p.setPen(QPen(INK, 3.2))
        for sx in (-1, 1):
            p.save()
            p.translate(sx * r * 0.62, -r * 0.62)
            twitch = self._twitch * 10 * (1 if sx > 0 else -1)
            p.rotate(sx * (26 - pr["ear"] * 22) + twitch)
            outer = QPolygonF([QPointF(-19, 6), QPointF(0, -34), QPointF(19, 6)])
            p.setBrush(CREAM)
            p.drawPolygon(outer)
            p.setPen(Qt.NoPen)
            p.setBrush(PINK)
            p.drawPolygon(QPolygonF([QPointF(-9, 2), QPointF(0, -21), QPointF(9, 2)]))
            p.setPen(QPen(INK, 3.2))
            p.restore()

    def _draw_eyes(self, p: QPainter) -> None:
        pr = self._p
        open_amt = max(0.0, pr["eye"] * (1.0 - self._blink))
        gx, gy = self._gaze.x(), self._gaze.y()

        for sx in (-1, 1):
            ex = sx * 18.5
            ey = -2.0
            if open_amt < 0.14:
                # closed: a contented arc
                p.setPen(QPen(INK, 3.4, Qt.SolidLine, Qt.RoundCap))
                p.setBrush(Qt.NoBrush)
                path = QPainterPath(QPointF(ex - 10, ey + 1))
                path.quadTo(QPointF(ex, ey - 8), QPointF(ex + 10, ey + 1))
                p.drawPath(path)
                continue

            lid = pr["lid"]
            h = 22 * min(1.25, open_amt) * (1.0 - 0.52 * lid)
            w = 17.0
            top = ey - h / 2 + 5.5 * lid

            p.setPen(QPen(INK, 2.6))
            p.setBrush(WHITE)
            p.drawEllipse(QRectF(ex - w / 2, top, w, h))

            p.setPen(Qt.NoPen)
            p.setBrush(INK)
            pr_ = 6.4 * (1.0 - 0.25 * lid)
            p.drawEllipse(QRectF(ex - pr_ + gx, top + h / 2 - pr_ + gy * (1 - lid),
                                 pr_ * 2, pr_ * 2))
            p.setBrush(WHITE)
            p.drawEllipse(QRectF(ex - 1.6 + gx + 2.2, top + h / 2 - 5.4 + gy, 4.4, 4.4))

            if lid > 0.08:       # a heavy upper lid reads as sleepy at a glance
                p.setPen(QPen(INK, 3.0, Qt.SolidLine, Qt.RoundCap))
                p.setBrush(Qt.NoBrush)
                p.drawLine(QPointF(ex - w / 2 - 1, top), QPointF(ex + w / 2 + 1, top))

    def _draw_muzzle(self, p: QPainter) -> None:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 120))
        p.drawEllipse(QRectF(-17, 10, 34, 20))

        # nose
        p.setPen(QPen(INK, 2.2))
        p.setBrush(PINK)
        nose = QPolygonF([QPointF(-5, 13), QPointF(5, 13), QPointF(0, 19)])
        p.drawPolygon(nose)

        # mouth
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(INK, 2.4, Qt.SolidLine, Qt.RoundCap))
        m = QPainterPath(QPointF(0, 19))
        m.quadTo(QPointF(-6, 26), QPointF(-11, 21))
        p.drawPath(m)
        m2 = QPainterPath(QPointF(0, 19))
        m2.quadTo(QPointF(6, 26), QPointF(11, 21))
        p.drawPath(m2)

        # whiskers
        p.setPen(QPen(QColor(120, 100, 88, 190), 1.9, Qt.SolidLine, Qt.RoundCap))
        for sx in (-1, 1):
            for i, dy in enumerate((-3.0, 2.0, 7.0)):
                x0 = sx * 20
                p.drawLine(QPointF(x0, 12 + dy * 0.5),
                           QPointF(x0 + sx * 30, 8 + dy * 1.5))

    def _draw_zzz(self, p: QPainter, t: float) -> None:
        p.setPen(Qt.NoPen)
        f = QFont("Segoe UI", 13, QFont.Bold)
        for i in range(3):
            phase = (t * 0.5 + i * 0.33) % 1.0
            alpha = int(190 * (1 - phase))
            if alpha <= 6:
                continue
            size = 11 + i * 3
            f.setPointSize(int(size))
            p.setFont(f)
            p.setPen(QColor(120, 105, 95, alpha))
            x = CX + 42 + phase * 26
            y = GROUND - 150 - phase * 46
            p.drawText(QPointF(x, y), "z")

    # ---- the speech bubble

    def _draw_bubble(self, p: QPainter) -> None:
        shown = self._line[: int(self._shown)] or " "

        font = QFont("Segoe UI", 11)
        font.setItalic(self._kind == "think")
        p.setFont(font)

        bw, bh = self._bubble_w, self._bubble_h
        if bw < 8 or bh < 8:
            return

        bx = CX - bw / 2
        by = GROUND - 214 - bh
        by = max(6.0, by)

        a = self._bubble_a
        p.save()
        p.setOpacity(a)

        # tail pointing down at the cat
        tail = QPolygonF([QPointF(CX - 11, by + bh - 2), QPointF(CX + 11, by + bh - 2),
                          QPointF(CX + 2, by + bh + 15)])
        body = QPainterPath()
        body.addRoundedRect(QRectF(bx, by, bw, bh), 15, 15)
        body.addPolygon(tail)

        p.setPen(QPen(BUBBLE_LINE, 2.6))
        p.setBrush(BUBBLE_BG if self._kind == "say"
                   else QColor(250, 248, 244, 214))
        p.drawPath(body.simplified())

        p.setPen(BUBBLE_TEXT if self._kind == "say" else THOUGHT_TEXT)
        p.drawText(QRectF(bx + 15, by + 11, bw - 30, bh - 22),
                   int(Qt.TextWordWrap), shown)
        p.restore()


class PetWindow(QWidget):
    """Frameless, transparent, always on top. Drag it anywhere."""

    said = Signal(str)
    quit_asked = Signal()
    pause_toggled = Signal()
    dragged = Signal(float, float)     # where you put her down
    grabbed = Signal()                 # you picked her up
    sent_home = Signal()               # you told her to go home

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Miso")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(W, H)

        self.cat = Cat(self)
        self.cat.said.connect(self.said)

        self._drag = None
        self._moved_while_held = False
        self.held = False          # while true the physics leaves her alone

    # ---- mouse

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.LeftButton:
            self._drag = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._moved_while_held = False
            self.held = True
            self.grabbed.emit()
        elif ev.button() == Qt.RightButton:
            self._menu(ev.globalPosition().toPoint())

    def mouseMoveEvent(self, ev) -> None:
        if self._drag and ev.buttons() & Qt.LeftButton:
            self.move(ev.globalPosition().toPoint() - self._drag)
            self._moved_while_held = True

    def mouseReleaseEvent(self, _ev) -> None:
        self._drag = None
        self.held = False
        # hand her real position back to the physics, or the next frame would
        # teleport her to wherever it still thought she was
        self.dragged.emit(float(self.x()), float(self.y()))
        if not self._moved_while_held:
            self.cat.open_entry()          # a click, not a drag: you want to talk

    def _menu(self, at) -> None:
        m = QMenu(self)
        m.addAction("go home", self.sent_home.emit)
        m.addAction("say something", self.cat.open_entry)
        m.addSeparator()
        m.addAction("pause / wake", self.pause_toggled.emit)
        m.addAction("let miso go", self.quit_asked.emit)
        m.exec(at)
