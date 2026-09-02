"""She notices what you have been doing, and eventually does something about it.

Not out of concern. She has no opinion about your screen time. What happens is
that she gets bored, and you have been motionless in front of the same window
for hours, and she would like that to stop being true.

Two deliberate limits:

* **Titles only.** The foreground window's title already says "YouTube". That
  is enough to know you have been on one thing for hours, and it costs nothing
  -- no screenshot, no vision model, nothing leaving the machine. `eyes.py`
  exists for looking at pixels and is separately gated; this never calls it.
* **She minimizes, never closes.** A minimized window is one click from being
  back exactly as it was. A closed one can cost you unsaved work, and she has
  no way of knowing what is unsaved. She is not allowed to make that mistake
  on your behalf.
"""
from __future__ import annotations

import ctypes
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from . import config, eyes

STATE_FILE = config.CODE_DIR / "state" / "watching.json"

NAG_AFTER_MINUTES = 120.0     # how long on one thing before she minds
NAG_COOLDOWN = 900.0          # 15 min between naggings, however cross she is
STEP_PATIENCE = 45.0          # how long she waits at each step to be noticed
FORGET_AFTER = 600.0          # a real break resets the clock
SW_MINIMIZE = 6

# she nags about things you sit and stare at, not about her own windows
OWN_TITLES = ("miso", "miso's home")


def _log(action: str, subject: str, outcome: str, extra: str = "") -> None:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps({
        "t": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "action": action, "path": subject[:120], "outcome": outcome, "extra": extra,
    })
    with (config.LOG_DIR / "actions.log").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _app_of(title: str) -> str:
    """A rough name for what you are looking at.

    Window titles are usually "<document> - <app>", so the last dash-separated
    piece is the app. Good enough to tell one long sitting from another, and
    it never needs to be exactly right.
    """
    tail = title.rsplit(" - ", 1)[-1].strip().lower()
    return tail[:60] or title[:60].lower()


def minimize(hwnd: int) -> bool:
    """Put a window away. Reversible, and the only thing she can do to one."""
    try:
        return bool(ctypes.windll.user32.ShowWindow(hwnd, SW_MINIMIZE))
    except (AttributeError, OSError):
        return False


@dataclass
class Watcher:
    """How long you have been on one thing, and how far she has escalated."""

    app: str = ""
    seconds: float = 0.0
    last_seen: float = field(default_factory=time.time)
    last_nag: float = 0.0
    step: int = 0                 # 0 nothing, 1 complained, 2 sat on it
    step_at: float = 0.0

    # ------------------------------------------------------------- watching

    def tick(self) -> None:
        """Called every few seconds. Keeps the tally, nothing more."""
        now = time.time()
        gap = now - self.last_seen
        self.last_seen = now

        fg = eyes.foreground_window()
        if fg is None:
            return
        _hwnd, title = fg

        if eyes.is_walled_title(title) or any(o in title.lower() for o in OWN_TITLES):
            return

        app = _app_of(title)
        if app != self.app or gap > FORGET_AFTER:
            self.app = app
            self.seconds = 0.0
            self.reset_escalation()
            return
        self.seconds += min(gap, 30.0)

    def reset_escalation(self) -> None:
        self.step = 0
        self.step_at = 0.0

    # ------------------------------------------------------------- wanting

    def fed_up(self, drives) -> bool:
        """Whether she currently minds. Her mood is half of this: the same two
        hours on the same window is fine by her if she is tired or has given up
        on you for the day."""
        if self.seconds < NAG_AFTER_MINUTES * 60:
            return False
        if time.time() - self.last_nag < NAG_COOLDOWN:
            return False
        if drives.energy < 0.3 or drives.resignation > 0.6:
            return False
        return drives.boredom > 0.6 or drives.loneliness > 0.65

    def next_step(self) -> str | None:
        """Advance the escalation, once she has waited to be noticed.

        Returns 'complain', 'sit_on_it', 'minimize', or None while she is still
        giving you the chance to look up.
        """
        now = time.time()
        if self.step and now - self.step_at < STEP_PATIENCE:
            return None

        self.step += 1
        self.step_at = now
        if self.step == 1:
            return "complain"
        if self.step == 2:
            return "sit_on_it"

        self.last_nag = now
        self.seconds = 0.0
        self.reset_escalation()
        return "minimize"

    def put_it_away(self) -> bool:
        """The last step. Minimize whatever is in front, if it is still the
        thing she was cross about."""
        fg = eyes.foreground_window()
        if fg is None:
            return False
        hwnd, title = fg
        if eyes.is_walled_title(title) or any(o in title.lower() for o in OWN_TITLES):
            return False
        if _app_of(title) != self.app:
            return False           # you moved on by yourself; leave it alone

        ok = minimize(hwnd)
        _log("minimized", title, "ok" if ok else "failed", f"{self.seconds / 60:.0f} min")
        return ok

    # ------------------------------------------------------------- storage

    def save(self) -> None:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls) -> "Watcher":
        if STATE_FILE.exists():
            try:
                return cls(**json.loads(STATE_FILE.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()
