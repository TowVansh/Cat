"""Miso's body.

The cat is pixel art: a handful of hand-authored frames per action
(miso/assets/pixel/<skin>/), swapped rather than smoothly deformed, the way
sprite-based desktop pets have always worked. Idle blinks, walking cycles a
4-frame bounce synced to the same step clock that drives the tail sway, and
sleep breathes slowly. Mood (curious/happy/lonely/bored) doesn't have its own
pose yet -- that's a later pass -- so it currently falls back to idle.

Each skin (SKINS) is the same frame set redrawn in a different palette --
cream tabby, orange tabby, gray mackerel, tuxedo -- picked via Cat.set_skin()
or the right-click menu. The frames themselves are generated, not hand-drawn
-- see tools/pixelcat/generate.py to rebuild or add one.
"""
from __future__ import annotations

import math
import random
import time
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QPainter, QPainterPath,
                           QPen, QPixmap, QPolygonF, QTransform)
from PySide6.QtWidgets import QLineEdit, QMenu, QWidget

ASSET_DIR = Path(__file__).resolve().parent / "assets" / "pixel"
SPRITE_TARGET_H = 128.0   # the cat's height on screen, paws to ear tip

WALK_FRAMES = ["walk_0", "walk_1", "walk_2", "walk_3"]
STEP_PER_FRAME = 0.6      # how much self._step advances between walk frames

MOOD_FRAMES = {
    "curious": "mood_curious", "happy": "mood_happy",
    "lonely": "mood_lonely", "bored": "mood_bored",
}
TALK_HZ = 4.5              # mouth-flap rate while a line is on screen --
                            # fixed-cadence, not real audio amplitude; see
                            # tools/pixelcat/generate.py's docstring

DEFAULT_SKIN = "cream_tabby"
SKINS = ["cream_tabby", "orange_tabby", "gray_mackerel", "tuxedo"]

_sprite_cache: dict[str, QPixmap] = {}


def _sprite(skin: str, name: str, flipped: bool) -> QPixmap:
    """Load once and cache; a QPixmap needs a QApplication to exist, so this
    is lazy rather than a module-level constant."""
    key = f"{skin}/{name}:{'L' if flipped else 'R'}"
    pm = _sprite_cache.get(key)
    if pm is None:
        pm = QPixmap(str(ASSET_DIR / skin / f"{name}.png"))
        if flipped:
            pm = pm.transformed(QTransform().scale(-1, 1))
        _sprite_cache[key] = pm
    return pm

# ----------------------------------------------------------------- palette

TAN_DARK = QColor("#B9835B")

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
        self.skin = DEFAULT_SKIN
        self.ground_speed = 0.0     # px/s, driven by Antics -- how fast the
                                     # walk-frame cycle advances, so a chase
                                     # visibly runs and a wander just walks
        self.depth_scale = 1.0      # perspective, driven by Antics
        self.spin = 0.0             # tail-chasing
        self.lean = 0.0             # body lean into a movement

        # held: picked up. Legs dangle (the held_0/held_1 frames), and she
        # swings like an actually-lifted cat -- a pendulum lag behind your
        # hand's motion, not a rubber-band stretch. Shaking still wobbles.
        self.held = False
        self.hold_sway = 0.0
        self._hold_sway_target = 0.0
        self._wobble_until = 0.0

        # jumping: stretched while flying, briefly squashed on landing --
        # same idea as the drag stretch, driven by Antics instead
        self.airborne = False
        self.air_stretch = 0.0
        self._air_stretch_target = 0.0
        self._land_squash_until = 0.0

        # off by default: she only watches the cursor once you ask her to
        self.eye_follow_enabled = False

        # speech
        self._line = ""
        self._kind = "say"          # say | think
        self._meaning = ""          # the bracketed reading of the noise
        self._queue: list[tuple[str, str, str]] = []
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

    def set_skin(self, name: str) -> None:
        if name in SKINS and name != self.skin:
            self.skin = name
            self.update()

    def set_held(self, held: bool) -> None:
        self.held = held
        if not held:
            self._hold_sway_target = 0.0

    def set_hold_sway(self, degrees: float) -> None:
        """A pendulum lag angle while held, reported fresh every mouse move
        and eased here -- same shape as set_air_stretch, different cause."""
        self._hold_sway_target = max(-30.0, min(30.0, degrees))

    def trigger_wobble(self) -> None:
        """Shaken while held: a short side-to-side wobble, decaying on its
        own rather than needing anyone to turn it back off."""
        self._wobble_until = time.time() + 0.9

    def set_gaze_from_global(self, dx: float, dy: float, radius: float = 260.0) -> None:
        """dx, dy: cursor position minus roughly where her head is on
        screen. A local hover alone isn't enough for a desktop pet -- she
        should track the cursor from anywhere, not just when it's already
        over her tiny window. No-op unless eye_follow_enabled -- off by
        default, since watching the cursor everywhere is a thing you opt
        into, not something she just does at you."""
        if not self.eye_follow_enabled:
            return
        nx = max(-1.0, min(1.0, dx / radius))
        ny = max(-1.0, min(1.0, dy / radius))
        self._gaze_target = QPointF(nx * 3.4, ny * 2.6)

    def set_eye_follow(self, enabled: bool) -> None:
        self.eye_follow_enabled = enabled
        if not enabled:
            self._gaze_target = QPointF(0, 0)

    def set_air_stretch(self, v: float) -> None:
        """0 = normal, 1 = fully stretched -- eased in _frame, driven by how
        fast she's moving vertically while airborne."""
        self._air_stretch_target = max(0.0, min(1.0, v))

    def trigger_land_squash(self) -> None:
        """A hard landing: brief squash, decaying on its own."""
        self._land_squash_until = time.time() + 0.22

    def speak(self, text: str, kind: str = "say", meaning: str = "") -> None:
        """Queue a line. Lines wait their turn instead of replacing each other --
        a reply followed immediately by 'looking around' would otherwise wipe the
        reply in the same frame, and it would look like Miso never answered.

        `text` is what she actually makes: cat noise. `meaning` is your reading
        of it, drawn smaller and bracketed above. She is not saying the English;
        you are supplying it.
        """
        text = text.strip()
        if not text:
            return
        if kind == "say":
            # something Miso actually says outranks a thought it was mid-way
            # through; drop pending thoughts so the reply is next
            self._queue = [q for q in self._queue if q[1] == "say"]
            if self._line and self._kind == "think":
                self._line = ""
        self._queue.append((text, kind, meaning.strip()))
        if not self._line:
            self._next_line()

    def _next_line(self) -> None:
        if not self._queue:
            return
        text, kind, meaning = self._queue.pop(0)
        self._line = text
        self._kind = kind
        self._meaning = meaning
        self._shown = 0.0
        self._said_at = time.time()

    def mew(self, intent: str) -> None:
        """Say something as a cat. The only speech path any caller should use --
        anything else risks putting English in her mouth."""
        from . import meow
        noise, meaning = meow.say(intent)
        self.speak(noise, "say", meaning)

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

        # both chase their target the same way; released, the target drops
        # to 0 and she settles back to normal on her own
        self.hold_sway = lerp(self.hold_sway, self._hold_sway_target, 0.16)
        self.air_stretch = lerp(self.air_stretch, self._air_stretch_target, 0.25)

        if self._walking:
            # tied to actual ground speed, not a fixed rate -- otherwise a
            # 430px/s chase and a 120px/s wander cycle their legs identically
            # and she reads as sliding rather than running or walking
            self._step += max(0.035, abs(self.ground_speed) * 0.00075)

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
        w, h = rect.width(), rect.height()

        # the bracketed meaning sits above the noise, so it is part of the box
        if self._meaning:
            small = QFont("Segoe UI", 9)
            small.setItalic(True)
            srect = QFontMetrics(small).boundingRect(
                QRectF(0, 0, W - 54, 400).toRect(),
                int(Qt.TextWordWrap), f"({self._meaning})")
            w = max(w, srect.width())
            h += srect.height() + 5
        return w, h

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

        self._draw_cat(p, t)
        p.restore()

        if self._pose_name == "sleep":
            self._draw_zzz(p, t)
        if self._bubble_a > 0.02:
            self._draw_bubble(p)

    # ---- the cat itself

    def _frame_name(self, t: float) -> str:
        """Which pixel frame is current -- driven by the same step/blink
        clocks _frame() already advances, so it needs no animation state of
        its own."""
        if self.held:
            return "held_0" if math.sin(t * 2.2) > 0 else "held_1"
        if self.airborne:
            return "jump_0"
        if self._pose_name == "sleep":
            return "sleep_0" if math.sin(t * 0.6) > 0 else "sleep_1"
        if self._walking:
            i = int(self._step / STEP_PER_FRAME) % len(WALK_FRAMES)
            return WALK_FRAMES[i]
        if self._line:
            # mouth flaps while there's an actual line on screen -- tied to
            # her real speaking state, just not real audio amplitude yet
            return "talk_1" if math.sin(t * TALK_HZ * 2 * math.pi) > 0 else "talk_0"
        if self._pose_name in MOOD_FRAMES:
            return MOOD_FRAMES[self._pose_name]
        return "idle_1" if self._blink > 0.4 else "idle_0"

    def _draw_cat(self, p: QPainter, t: float) -> None:
        frame_name = self._frame_name(t)
        flipped = self._facing < 0
        sprite = _sprite(self.skin, frame_name, flipped=flipped)
        if sprite.isNull():
            return

        # pixel art wants nearest-neighbor scaling, not the smooth filter
        # used everywhere else, or the crisp block edges turn to mush
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.setRenderHint(QPainter.Antialiasing, False)

        s = SPRITE_TARGET_H / sprite.height()
        w, h = sprite.width() * s, sprite.height() * s

        now = time.time()
        wobble, jitter_sway = 0.0, 0.0
        remaining = self._wobble_until - now
        if remaining > 0:
            # eased decay (not linear) so it settles instead of cutting off
            # abruptly, and slow enough to read as a wobble, not a buzz
            decay = (remaining / 0.9) ** 1.6
            wobble = math.sin(now * 9.5) * 16 * decay
            jitter_sway = math.sin(now * 9.5 + 1.2) * 5 * decay

        # a shake-wobble and the steady hold-sway are different things (a
        # brief startled shake vs. a continuous pendulum lag) but both are
        # just a rotation, so they add rather than needing separate states
        rotation = wobble + self.hold_sway

        # normally she pivots at her paws (standing on the ground). Held,
        # that would swing her like an upside-down pendulum -- wrong end.
        # She should hang and swing from about where a hand would actually
        # grip her, near the shoulders, so the pivot moves up near the top
        # of the sprite and the body dangles below it.
        pivot_y = -h * 0.72 if self.held else 0.0

        p.save()
        p.translate(CX + jitter_sway, GROUND + pivot_y)
        if abs(rotation) > 0.05:
            p.rotate(rotation)

        # the mid-air stretch is anchored at the paws so she stretches up
        # rather than out; landing briefly overrides it with a squash
        # instead, the classic cartoon-physics pair. Not applied while held
        # -- the pivot has already moved, and dangling has its own frame.
        stretch = 0.0 if self.held else self.air_stretch
        land = 0.0
        land_remaining = self._land_squash_until - now
        if land_remaining > 0 and not self.held:
            land = land_remaining / 0.22
        scale_x = 1.0 - stretch * 0.28 + land * 0.32
        scale_y = 1.0 + stretch * 0.55 - land * 0.42
        if abs(scale_x - 1.0) > 0.001 or abs(scale_y - 1.0) > 0.001:
            p.scale(scale_x, scale_y)

        top = -h - pivot_y
        p.drawPixmap(QRectF(-w / 2, top, w, h), sprite, QRectF(sprite.rect()))

        # idle_0 has blank eye sockets; composite the iris on top, offset
        # by the live gaze, so she can track the cursor
        if frame_name == "idle_0":
            eyes = _sprite(self.skin, "eyes", flipped=flipped)
            if not eyes.isNull():
                gx = max(-1.4, min(1.4, self._gaze.x() / 2.4)) * s
                gy = max(-1.0, min(1.0, self._gaze.y() / 2.0)) * s
                p.drawPixmap(QRectF(-w / 2 + gx, top + gy, w, h), eyes, QRectF(eyes.rect()))

        p.restore()

        p.setRenderHint(QPainter.Antialiasing, True)

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

        text_y = by + 11
        if self._meaning:
            # your reading of the noise, above it and quieter -- it is a
            # subtitle, not something she said
            small = QFont("Segoe UI", 9)
            small.setItalic(True)
            p.setFont(small)
            sh = QFontMetrics(small).boundingRect(
                QRectF(0, 0, bw - 30, 400).toRect(),
                int(Qt.TextWordWrap), f"({self._meaning})").height()
            p.setPen(QColor(120, 106, 96, 210))
            p.drawText(QRectF(bx + 15, text_y, bw - 30, sh),
                       int(Qt.TextWordWrap), f"({self._meaning})")
            text_y += sh + 5
            p.setFont(font)

        p.setPen(BUBBLE_TEXT if self._kind == "say" else THOUGHT_TEXT)
        p.drawText(QRectF(bx + 15, text_y, bw - 30, by + bh - 11 - text_y),
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

        # mochi drag / shake, tracked purely from consecutive drag positions
        self._drag_last_pos = None
        self._drag_last_time = 0.0
        self._shake_flips: list[float] = []
        self._shake_sign = 0

    # ---- mouse

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.LeftButton:
            self._drag = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._moved_while_held = False
            self.held = True
            self.cat.set_held(True)
            self._drag_last_pos = ev.globalPosition().toPoint()
            self._drag_last_time = time.time()
            self._shake_flips = []
            self._shake_sign = 0
            self.grabbed.emit()
        elif ev.button() == Qt.RightButton:
            self._menu(ev.globalPosition().toPoint())

    def mouseMoveEvent(self, ev) -> None:
        if self._drag and ev.buttons() & Qt.LeftButton:
            pos = ev.globalPosition().toPoint()
            self.move(pos - self._drag)
            self._moved_while_held = True
            self._track_drag_physics(pos)

    def _track_drag_physics(self, pos) -> None:
        """A held cat swings like a pendulum lagging behind your hand, and
        wobbles if you shake her -- both read straight off consecutive drag
        positions, no separate physics loop needed."""
        now = time.time()
        dt = max(1e-3, now - self._drag_last_time)
        if self._drag_last_pos is not None:
            dx = pos.x() - self._drag_last_pos.x()
            # she lags behind the direction you're moving her -- the same
            # sign convention as a pendulum bob trailing its pivot
            vx = dx / dt
            self.cat.set_hold_sway(max(-30.0, min(30.0, -vx / 45.0)))

            if abs(dx) > 3:
                sign = 1 if dx > 0 else -1
                if self._shake_sign and sign != self._shake_sign:
                    self._shake_flips.append(now)
                self._shake_sign = sign
            self._shake_flips = [ts for ts in self._shake_flips if now - ts < 0.6]
            if len(self._shake_flips) >= 4:
                self.cat.trigger_wobble()
                self._shake_flips.clear()
        self._drag_last_pos = pos
        self._drag_last_time = now

    def mouseReleaseEvent(self, _ev) -> None:
        self._drag = None
        self.held = False
        self.cat.set_held(False)
        self._drag_last_pos = None
        # hand her real position back to the physics, or the next frame would
        # teleport her to wherever it still thought she was
        self.dragged.emit(float(self.x()), float(self.y()))
        if not self._moved_while_held:
            self.cat.open_entry()          # a click, not a drag: you want to talk

    def _menu(self, at) -> None:
        m = QMenu(self)
        m.addAction("go home", self.sent_home.emit)
        m.addAction("say something", self.cat.open_entry)
        skins = m.addMenu("skin")
        for name in SKINS:
            label = name.replace("_", " ")
            action = skins.addAction(label, lambda n=name: self.cat.set_skin(n))
            action.setCheckable(True)
            action.setChecked(name == self.cat.skin)
        follow = m.addAction("follow cursor with eyes", self.cat.set_eye_follow)
        follow.setCheckable(True)
        follow.setChecked(self.cat.eye_follow_enabled)
        m.addSeparator()
        m.addAction("pause / wake", self.pause_toggled.emit)
        m.addAction("let miso go", self.quit_asked.emit)
        m.exec(at)
