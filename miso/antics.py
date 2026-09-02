"""How Miso moves about.

None of this touches the model. A cat spends almost all of its time doing
things that require no thought at all -- crossing the room, sitting down,
noticing a moving thing, running at it, losing interest halfway -- and if those
only happened when a language model decided they should, the pet would be still
and dead most of the time.

So movement is its own loop, running at 60fps on pure code, driven by the same
drives as everything else. The model handles what Miso *says*. This handles
what Miso *is doing*, which is most of what you actually see.

Depth: the desktop is treated as a room seen in perspective. Higher up the
screen is further away, so Miso is drawn smaller there and moves more slowly.
"""
from __future__ import annotations

import math
import random
import time

# --------------------------------------------------------------- the world

GRAVITY = 2600.0          # pixels per second squared
FLOOR_BOUNCE = 0.22
NEAR_SCALE = 1.00         # at the bottom of the screen
FAR_SCALE = 0.55          # at the back of the room
CHASE_SPEED = 430.0
WANDER_SPEED = 120.0
POUNCE_CROUCH = 0.45      # seconds spent wiggling before a leap
HOP_CROUCH = 0.16         # a hop is smaller than a pounce, so the wind-up is
                          # shorter -- but a jump with zero anticipation at
                          # all reads as a teleport, not a leap

# how long each antic lasts before Miso gets bored of it
DURATIONS = {
    "sit": (2.5, 6.0), "groom": (3.0, 6.0), "stretch": (1.4, 2.2),
    "spin": (1.1, 1.9), "zoomies": (2.4, 5.0), "pounce": (0.9, 1.6),
    "wander": (2.5, 7.0), "watch": (1.5, 4.0), "perk": (1.0, 2.0),
    "wiggle": (0.9, 1.6), "shrink": (1.5, 3.0), "settle": (3.0, 8.0),
    "tilt": (1.2, 2.2), "chase": (1.5, 5.0), "flop": (4.0, 9.0),
    "hop": (0.5, 0.9),
}

# what each antic looks like on the body
POSE_FOR = {
    "sit": "idle", "groom": "idle", "stretch": "idle", "spin": "happy",
    "zoomies": "walk", "pounce": "curious", "wander": "walk", "watch": "curious",
    "perk": "curious", "wiggle": "happy", "shrink": "lonely", "settle": "sleep",
    "tilt": "curious", "chase": "walk", "flop": "sleep", "hop": "happy",
}

IDLE_PICKS = ["sit", "groom", "wander", "stretch", "wander", "watch", "flop"]
# "hop" used to be in here, which made her jump constantly -- it's a real but
# rare bit of body language now, not a coin-flip filler between other antics
PLAYFUL_PICKS = ["zoomies", "spin", "pounce", "wander", "chase"]

DURATIONS["going_home"] = (6.0, 14.0)
POSE_FOR["going_home"] = "walk"

# planting herself in the middle of the screen, in front of whatever you are
# doing. Long, because being ignored is the entire point of it.
DURATIONS["sit_on_screen"] = (20.0, 40.0)
POSE_FOR["sit_on_screen"] = "bored"


class Antics:
    """Miso's body in space. Owns her position, velocity, and current antic."""

    def __init__(self, screen, w: int, h: int) -> None:
        self.screen = screen
        self.w, self.h = w, h

        self.x = float(screen.right() - w - 30)
        self.y = float(screen.bottom() - h - 10)
        self.vx = 0.0
        self.vy = 0.0

        self.antic = "sit"
        self.until = time.time() + 2.0
        self.target: tuple[float, float] | None = None
        self.spin = 0.0            # degrees, for tail-chasing
        self.lean = 0.0            # body lean into movement
        self.crouch_until = 0.0

        self.facing = 1
        self.playfulness = 0.5     # nudged by the drives
        self.attention = 0.0       # how interested in the cursor, 0..1

        self._last = time.time()
        self._cursor_still_since = time.time()
        self._last_cursor = (0.0, 0.0)

    # ------------------------------------------------------------ geometry

    @property
    def floor(self) -> float:
        return float(self.screen.bottom() - self.h - 10)

    @property
    def back(self) -> float:
        return float(self.screen.top() + 40)

    def depth(self) -> float:
        """0 at the back of the room, 1 at the front."""
        span = max(1.0, self.floor - self.back)
        return max(0.0, min(1.0, (self.y - self.back) / span))

    def scale(self) -> float:
        return FAR_SCALE + (NEAR_SCALE - FAR_SCALE) * self.depth()

    # -------------------------------------------------------------- choosing

    def start(self, antic: str, target=None) -> None:
        self.antic = antic
        lo, hi = DURATIONS.get(antic, (1.5, 3.0))
        self.until = time.time() + random.uniform(lo, hi)
        self.target = target
        if antic == "pounce":
            self.crouch_until = time.time() + POUNCE_CROUCH
        if antic == "hop":
            self.crouch_until = time.time() + HOP_CROUCH
        if antic == "spin":
            self.spin = 0.0
        if antic in ("wander", "zoomies") and target is None:
            self.target = (random.uniform(self.screen.left() + 10,
                                          self.screen.right() - self.w - 10),
                           random.uniform(self.back, self.floor))

    def pick_next(self) -> None:
        pool = PLAYFUL_PICKS if random.random() < self.playfulness else IDLE_PICKS
        self.start(random.choice(pool))

    # ---------------------------------------------------------------- update

    def step(self, cursor: tuple[int, int], drives) -> None:
        now = time.time()
        dt = min(0.05, now - self._last)      # a stall must not fling her away
        self._last = now

        self.playfulness = max(0.05, min(0.95,
                               0.25 + drives.energy * 0.5 + drives.boredom * 0.35
                               - drives.resignation * 0.4))

        self._notice_cursor(cursor, now)
        self._run_antic(cursor, dt, now)
        self._integrate(dt)

        if now > self.until and self.vy == 0.0:
            self.pick_next()

    # ---- the cursor is the most interesting thing on the desktop

    def _notice_cursor(self, cursor, now: float) -> None:
        cx, cy = cursor
        moved = math.dist((cx, cy), self._last_cursor)
        self._last_cursor = (cx, cy)

        if moved > 2.0:      # a mouse rarely travels far in a single frame
            self._cursor_still_since = now
            near = math.dist((cx, cy), self._centre()) < 420
            # a fast-moving thing nearby is very hard for a cat to ignore
            gain = 0.05 + min(0.35, moved / 90.0) * (1.6 if near else 0.5)
            self.attention = min(1.0, self.attention + gain * self.playfulness)
        else:
            self.attention = max(0.0, self.attention - 0.012)

        # only a chase, a pounce or a spin is worth more than a moving cursor;
        # aimless running about is not, or she would never notice you at all
        busy = self.antic in ("chase", "pounce", "spin")
        if not busy and self.attention > 0.55 and random.random() < 0.10:
            self.attention = 0.2
            self.start("chase" if random.random() < 0.7 else "pounce",
                       target=(cx - self.w / 2, cy - self.h * 0.6))

    def _centre(self) -> tuple[float, float]:
        return self.x + self.w / 2, self.y + self.h * 0.7

    # ---- what each antic actually does to the body

    def _run_antic(self, cursor, dt: float, now: float) -> None:
        a = self.antic
        cx, cy = cursor

        if a == "chase":
            self._steer_to(cx - self.w / 2, cy - self.h * 0.6, CHASE_SPEED, dt)
            if math.dist(self._centre(), (cx, cy)) < 70:
                self.start("wiggle")

        elif a == "pounce":
            if now < self.crouch_until:
                self.vx *= 0.80                      # wiggle, gather, aim
                self.lean = math.sin(now * 26) * 5
            elif self.vy == 0.0:
                tx = (self.target or (cx, cy))[0]
                self.vx = max(-620, min(620, (tx - self.x) * 2.6))
                self.vy = -1150.0
                self.facing = 1 if self.vx >= 0 else -1

        elif a == "zoomies":
            if self.target is None or math.dist((self.x, self.y), self.target) < 40:
                self.target = (random.uniform(self.screen.left() + 10,
                                              self.screen.right() - self.w - 10),
                               random.uniform(self.back, self.floor))
            self._steer_to(*self.target, CHASE_SPEED * 1.15, dt)
            if self.vy == 0.0 and random.random() < 0.012:
                self.vy = -520.0                     # little skips as she runs

        elif a == "going_home":
            self._steer_to(*(self.target or (self.screen.right(), self.floor)),
                           WANDER_SPEED * 1.5, dt)

        elif a == "sit_on_screen":
            self.vx = self.vy = 0.0           # she is not going anywhere

        elif a == "wander":
            if self.target is None or math.dist((self.x, self.y), self.target) < 25:
                self.start("sit")
            else:
                self._steer_to(*self.target, WANDER_SPEED, dt)

        elif a == "spin":
            # a happy shimmy, not a coin spinning on a table -- real cats
            # don't rotate their whole body through 360 degrees, and a flat
            # sprite doing that at 900deg/s is exactly what read as fake
            self.spin = math.sin(now * 8) * 25
            self.vx *= 0.85

        elif a == "hop":
            if now < self.crouch_until:
                self.vx *= 0.7                       # a beat to gather first
                self.lean = math.sin(now * 30) * 4
            elif self.vy == 0.0:
                self.vy = -720.0

        elif a in ("sit", "groom", "flop", "settle", "watch", "perk",
                   "tilt", "shrink", "wiggle", "stretch"):
            self.vx *= 0.86
            if a == "wiggle":
                self.lean = math.sin(now * 22) * 7
            elif a == "watch":
                self.facing = 1 if cx > self._centre()[0] else -1

        if a != "spin":
            self.spin *= 0.86
        if a not in ("wiggle", "pounce", "hop"):
            self.lean *= 0.88

    def _steer_to(self, tx: float, ty: float, speed: float, dt: float) -> None:
        dx, dy = tx - self.x, ty - self.y
        dist = max(1.0, math.hypot(dx, dy))
        # further away in the room means slower across the glass, like perspective
        s = speed * (0.55 + 0.45 * self.depth())
        self.vx += (dx / dist) * s * dt * 6.0
        self.vy += (dy / dist) * s * dt * 3.0 if self.vy == 0.0 else 0.0
        self.vx = max(-speed, min(speed, self.vx))
        if abs(self.vx) > 8:
            self.facing = 1 if self.vx > 0 else -1

    # ---- position

    def _integrate(self, dt: float) -> None:
        if self.antic == "sit_on_screen":
            return                          # she stays exactly where she sat
        in_air = self.vy != 0.0 or self.y < self.floor - 0.5

        if in_air:
            self.vy += GRAVITY * dt
        self.x += self.vx * dt
        self.y += self.vy * dt

        left = self.screen.left()
        right = self.screen.right() - self.w
        if self.x < left:
            self.x, self.vx = float(left), abs(self.vx) * 0.5
        elif self.x > right and self.antic != "going_home":
            self.x, self.vx = float(right), -abs(self.vx) * 0.5

        if self.y > self.floor:
            self.y = self.floor
            if abs(self.vy) > 260:
                self.vy = -abs(self.vy) * FLOOR_BOUNCE   # a small landing bounce
            else:
                self.vy = 0.0
        elif self.y < self.back:
            self.y, self.vy = self.back, abs(self.vy) * 0.3

        if not in_air:
            self.vx *= 0.90                              # friction on the floor
            if abs(self.vx) < 4:
                self.vx = 0.0

    def put(self, x: float, y: float) -> None:
        """You picked her up and set her down somewhere."""
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.start("wiggle" if self.y >= self.floor - 2 else "hop")

    # ------------------------------------------------------------ reporting

    def go_to(self, x: float, y: float | None = None) -> None:
        """Walk somewhere specific, because you told her to."""
        self.start("wander")
        self.target = (max(float(self.screen.left()),
                           min(float(self.screen.right() - self.w), x)),
                       self.floor if y is None else
                       max(self.back, min(self.floor, y)))

    def sit_in_the_way(self) -> None:
        """Park in the middle of the screen where you cannot miss her."""
        self.start("sit_on_screen")
        self.target = None
        mid = self.screen.left() + (self.screen.width() - self.w) / 2
        self.x = float(mid)
        self.y = float(self.screen.top() + (self.screen.height() - self.h) * 0.35)
        self.vx = self.vy = 0.0

    def head_home(self) -> None:
        """Set off for the right-hand edge of the screen."""
        self.start("going_home")
        self.target = (float(self.screen.right() + self.w * 0.6), self.floor)

    def is_home(self) -> bool:
        """True once she has walked far enough off the edge to be gone."""
        return (self.antic == "going_home"
                and self.x > self.screen.right() - self.w * 0.25)

    def come_back(self) -> None:
        """Step back onto the desktop from the right-hand edge."""
        self.x = float(self.screen.right() - self.w)
        self.y = self.floor
        self.vx = self.vy = 0.0
        self.start("stretch")

    def pose(self) -> str:
        # sitting in the way is the one time she is deliberately off the floor
        # without having jumped there, so it must not read as mid-air
        if self.antic != "sit_on_screen" and (self.vy != 0.0
                                              or self.y < self.floor - 1):
            return "happy"                               # mid-air
        return POSE_FOR.get(self.antic, "idle")
