"""The text box.

Not a conversation. It is how you point at things in her world -- "food is
there", "come here" -- the way you would actually talk to an animal that has
learned about six words. There is no model behind it and there should never be
one: the moment this starts parsing sentences it becomes a chat window again.

She is allowed to refuse. That is not a bug to be tuned out; it is the whole
difference between a pet and a command line. A dog obeys. A cat considers your
request, decides what is in it for her, and often does not bother.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass

# what she was told to do, and how hard it is to talk her into it
#   pull: how appetising the request is to her (0..1). Higher obeys more often.

FOOD = re.compile(r"\b(food|eat|dinner|treat|snack|fish|kibble|breakfast)\b", re.I)
WATER = re.compile(r"\b(water|drink|thirsty)\b", re.I)
COME = re.compile(r"\b(come|here|c'?mere|over here|to me)\b", re.I)
HOME = re.compile(r"\b(home|room|inside|go in)\b", re.I)
BED = re.compile(r"\b(sleep|bed|nap|rest|goodnight|gn)\b", re.I)
PLAY = re.compile(r"\b(play|toy|game|fetch|chase|ball|yarn)\b", re.I)
STOP = re.compile(r"\b(no|stop|bad|don'?t|quit|leave it|get off)\b", re.I)
NAME = re.compile(r"\b(miso|meso|mesooo+|kitty|kitten|puss|cat)\b", re.I)
PRAISE = re.compile(r"\b(good|clever|cute|pretty|sweet|love|adorable|best)\b", re.I)


@dataclass(frozen=True)
class Command:
    action: str        # what she would do
    intent: str        # what she says about it
    pull: float        # how much she wants to


# order matters: the first match wins, so the specific ones come first
TABLE: list[tuple[re.Pattern, Command]] = [
    (FOOD,   Command("go_eat", "hungry", 0.95)),
    (WATER,  Command("go_drink", "thirsty", 0.90)),
    (PLAY,   Command("play", "want_play", 0.85)),
    (BED,    Command("go_bed", "sleepy", 0.55)),
    (HOME,   Command("go_home", "going_home", 0.50)),
    (COME,   Command("come_here", "want_attention", 0.45)),
    (STOP,   Command("stop", "annoyed", 0.70)),
    (PRAISE, Command("preen", "pleased", 1.00)),
    (NAME,   Command("look_up", "greeting", 0.80)),
]


def understand(text: str) -> Command | None:
    """What she thinks you meant, or None if it meant nothing to her."""
    text = (text or "").strip()
    if not text:
        return None
    for pattern, command in TABLE:
        if pattern.search(text):
            return command
    return None


def will_she(command: Command, drives, busy: bool = False) -> bool:
    """Whether she can actually be bothered.

    Hunger beats mood -- a cat told about food comes for food. Otherwise a
    tired, sulky or thoroughly-given-up Miso is much harder to move, and one
    already mid-pounce will not break off for you.
    """
    if command.pull >= 0.9:
        return True

    chance = command.pull
    chance -= 0.35 * getattr(drives, "resignation", 0.0)
    chance -= 0.25 * (1.0 - getattr(drives, "energy", 1.0))
    chance += 0.15 * getattr(drives, "loneliness", 0.0)   # missed you: more biddable
    if busy:
        chance -= 0.40
    return random.random() < max(0.05, min(0.98, chance))
