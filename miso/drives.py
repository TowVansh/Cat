"""Miso's insides.

These numbers are why Miso is a pet and not a chatbot. A chatbot is a function
of your input. Miso is a function of time -- the drives move whether or not you
are at the keyboard, and whatever is loudest when a tick fires is what Miso
wants to do next.

Two rules keep this from going flat:
  * drives approach their ceiling asymptotically, so nothing ever pins at 1.0
    and stays there
  * a drive that goes unmet long enough turns into resignation -- a cat that
    has waited all day stops waiting and goes to sleep in the warm spot

Miso never sees the numbers. Miso gets sentences.
"""
from __future__ import annotations

import json
import math
import random
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime

from . import config

STATE_FILE = config.CODE_DIR / "state" / "drives.json"

# per-hour approach rate toward the ceiling when nothing intervenes
DRIFT = {
    "curiosity": 0.30,
    "boredom": 0.40,
    "loneliness": 0.25,
}

MAX_TICK_HOURS = 12.0     # a three-week shutdown is not three weeks of boredom


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass
class Drives:
    curiosity: float = 0.5
    boredom: float = 0.3
    loneliness: float = 0.2
    energy: float = 0.8
    resignation: float = 0.0
    born_at: float = field(default_factory=time.time)
    last_tick: float = field(default_factory=time.time)
    last_saw_you: float = field(default_factory=time.time)
    ticks: int = 0

    # ---------------------------------------------------------------- time

    @property
    def age_days(self) -> float:
        return (time.time() - self.born_at) / 86400

    @property
    def hours_since_you(self) -> float:
        return (time.time() - self.last_saw_you) / 3600

    def circadian(self) -> float:
        """0 around 4am, 1 around 4pm. Miso is a little nocturnal, like a cat."""
        h = datetime.now().hour + datetime.now().minute / 60
        return 0.5 + 0.5 * math.sin((h - 10) / 24 * 2 * math.pi)

    # ---------------------------------------------------------------- tick

    def tick(self) -> None:
        now = time.time()
        hours = min(max(0.0, (now - self.last_tick) / 3600), MAX_TICK_HOURS)
        self.last_tick = now
        self.ticks += 1

        for name, rate in DRIFT.items():
            cur = getattr(self, name)
            jitter = random.uniform(0.75, 1.25)
            # asymptotic approach: fast when low, crawling near the top
            setattr(self, name, _clamp(cur + rate * hours * jitter * (1.0 - cur)))

        # waiting turns into giving up
        alone = self.hours_since_you
        if alone > 6:
            fade = min(1.0, (alone - 6) / 6)
            self.loneliness = _clamp(self.loneliness - 0.14 * hours * fade)
            self.resignation = _clamp(self.resignation + 0.10 * hours * fade)
        else:
            self.resignation = _clamp(self.resignation - 0.35 * hours)

        # energy tracks the clock rather than only climbing
        target = 0.30 + 0.60 * self.circadian()
        self.energy = _clamp(self.energy + (target - self.energy) * min(1.0, 0.55 * hours))

    # ------------------------------------------------------------- effects

    def spend(self, cost: float) -> None:
        self.energy = _clamp(self.energy - cost)

    def satisfy(self, **deltas: float) -> None:
        for name, d in deltas.items():
            if hasattr(self, name):
                setattr(self, name, _clamp(getattr(self, name) + d))

    def saw_you(self) -> None:
        self.last_saw_you = time.time()
        self.satisfy(loneliness=-0.55, boredom=-0.35, resignation=-0.60)

    # ---------------------------------------------------------------- urge

    def urge(self) -> str:
        """What Miso most wants right now. Pure code, no model call.

        Sampled rather than argmaxed so the same mood does not produce the same
        act every single time.
        """
        if self.energy < 0.15:
            return "sleep"

        wants = {
            "find_you": self.loneliness * (1.0 - 0.75 * self.resignation),
            "explore": self.curiosity * self.energy,
            "potter": self.boredom * 0.85,
            "rest": (1.0 - self.energy) * 0.9,
        }
        live = [(k, v) for k, v in wants.items() if v > 0.20]
        if not live:
            return "idle"

        total = sum(v ** 3 for _, v in live)      # sharpen, keep some variety
        r = random.random() * total
        acc = 0.0
        for name, v in live:
            acc += v ** 3
            if r <= acc:
                return name
        return live[-1][0]

    # ------------------------------------------------------------ language

    @staticmethod
    def _band(x: float, low: str, mid: str, high: str) -> str | None:
        if x > 0.7:
            return high
        if x > 0.4:
            return mid
        return low if x > 0.15 else None

    def feelings(self) -> str:
        """The only form these numbers ever reach the model in."""
        bits = [
            self._band(self.curiosity, "mildly curious",
                       "curious about something", "itching to go and look at something"),
            self._band(self.boredom, "a little bored",
                       "bored", "very bored, nothing here is interesting any more"),
            self._band(self.loneliness, "aware they are somewhere",
                       "missing them a bit", "lonely, they have been gone a while"),
            self._band(1 - self.energy, "fresh", "getting tired", "heavy and sleepy"),
        ]
        if self.resignation > 0.5:
            bits.append("past expecting them back today")
        felt = [b for b in bits if b]

        hour = datetime.now().hour
        part = ("the middle of the night" if hour < 5 else "early morning" if hour < 9
                else "the middle of the day" if hour < 17 else "evening" if hour < 22
                else "late at night")
        alone = (f"You have not seen them for about {self.hours_since_you:.1f} hours."
                 if self.hours_since_you > 1 else "They were here recently.")
        return (f"It is {part}. You are {', and '.join(felt) if felt else 'calm'}. "
                f"{alone} You have been alive {self.age_days:.1f} days.")

    # ------------------------------------------------------------ storage

    def save(self) -> None:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls) -> "Drives":
        if STATE_FILE.exists():
            try:
                return cls(**json.loads(STATE_FILE.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()          # first breath
