"""Hunger, thirst, and the bowls they are filled from.

This is the part that makes Miso yours to look after rather than just to watch.
Bowls empty on their own whether or not the program is running, so coming back
after two days means coming back to a cat that needs something.

Deliberately gentle: hunger and thirst move slowly, and a neglected Miso gets
quiet and slow rather than ill. Nothing here can hurt her, and nothing here is
a punishment for having a life away from the computer.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field

from . import config

STATE_FILE = config.CODE_DIR / "state" / "needs.json"

# a full bowl lasts about this long
FOOD_HOURS = 30.0
WATER_HOURS = 22.0
MAX_AWAY_HOURS = 48.0     # a week away is not a week of hunger

EAT_PER_SECOND = 0.055    # how fast a bowl drains while she is eating
DRINK_PER_SECOND = 0.075


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass
class Needs:
    food_bowl: float = 1.0     # what is in the bowl
    water_bowl: float = 1.0
    hunger: float = 0.15       # what is in her
    thirst: float = 0.15
    last_tick: float = field(default_factory=time.time)
    meals: int = 0             # how many times you have fed her
    refills: int = 0

    # ---------------------------------------------------------------- time

    def tick(self) -> None:
        now = time.time()
        hours = min(MAX_AWAY_HOURS, max(0.0, (now - self.last_tick) / 3600))
        self.last_tick = now

        self.hunger = _clamp(self.hunger + hours / FOOD_HOURS)
        self.thirst = _clamp(self.thirst + hours / WATER_HOURS)

        # water left standing goes stale and slowly evaporates
        self.water_bowl = _clamp(self.water_bowl - hours * 0.006)

    # --------------------------------------------------------------- doing

    def eat(self, seconds: float) -> bool:
        """Returns True while there is anything left to eat."""
        if self.food_bowl <= 0.01:
            return False
        bite = min(self.food_bowl, EAT_PER_SECOND * seconds)
        self.food_bowl = _clamp(self.food_bowl - bite)
        self.hunger = _clamp(self.hunger - bite * 2.2)
        return True

    def drink(self, seconds: float) -> bool:
        if self.water_bowl <= 0.01:
            return False
        sip = min(self.water_bowl, DRINK_PER_SECOND * seconds)
        self.water_bowl = _clamp(self.water_bowl - sip)
        self.thirst = _clamp(self.thirst - sip * 2.4)
        return True

    def fill_food(self) -> None:
        self.food_bowl = 1.0
        self.meals += 1

    def fill_water(self) -> None:
        self.water_bowl = 1.0
        self.refills += 1

    # -------------------------------------------------------------- asking

    def wants(self) -> str | None:
        """The loudest need, if any is loud enough to act on."""
        if self.thirst > 0.55 and self.water_bowl > 0.02:
            return "drink"
        if self.hunger > 0.55 and self.food_bowl > 0.02:
            return "eat"
        return None

    def complaining(self) -> str | None:
        """The intent she would voice about an empty bowl, for `meow.say`.
        An intent rather than a sentence -- she has no English."""
        if self.thirst > 0.7 and self.water_bowl <= 0.02:
            return "thirsty"
        if self.hunger > 0.7 and self.food_bowl <= 0.02:
            return "bowl_empty"
        return None

    def feelings(self) -> str:
        bits = []
        if self.hunger > 0.7:
            bits.append("very hungry")
        elif self.hunger > 0.45:
            bits.append("hungry")
        if self.thirst > 0.7:
            bits.append("very thirsty")
        elif self.thirst > 0.45:
            bits.append("thirsty")
        if self.food_bowl <= 0.02:
            bits.append("your food bowl is empty")
        if self.water_bowl <= 0.02:
            bits.append("your water bowl is empty")
        return " and ".join(bits)

    # ------------------------------------------------------------ storage

    def save(self) -> None:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls) -> "Needs":
        if STATE_FILE.exists():
            try:
                return cls(**json.loads(STATE_FILE.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()
