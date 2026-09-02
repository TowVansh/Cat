"""What she actually does, decided in code.

This used to be a language model choosing tool calls. That was wrong twice
over: it made every small act cost eight seconds and a GPU, and it meant she
only did anything when a model felt like it. A cat crossing a room and putting
its nose in a box is not reasoning. It is a creature following its nose.

So the decisions moved here and the model kept only her diary. Everything
still goes through `jail`, so the sandbox, the audit trail and the
never-a-delete rule are all exactly as they were -- only the thing choosing
has changed.
"""
from __future__ import annotations

import random
import time

from . import jail, memory

# places she has poked at lately, so she does not check the same one twice
_recent: list[str] = []
_RECENT_KEEP = 8

# things she will not bother carrying home
BORING = {".ini", ".log", ".tmp", ".lock", ".cache"}


def _remember_place(where: str) -> None:
    _recent.append(where)
    del _recent[:-_RECENT_KEEP]


def _somewhere_new() -> str | None:
    """Pick a place to go. Prefers somewhere she has not just been."""
    root = jail.look("/world")
    if not root.get("ok"):
        return None
    places = [f"/world/{p}" for p in root.get("places", [])]
    if not places:
        return None
    fresh = [p for p in places if p not in _recent] or places
    return random.choice(fresh)


def _wander_into(place: str, depth: int = 2) -> str | None:
    """Walk a little way in, the way a cat gets into a cupboard."""
    here = place
    for _ in range(depth):
        listing = jail.look(here)
        if not listing.get("ok"):
            return here
        rooms = listing.get("places", [])
        if not rooms or random.random() < 0.45:
            return here
        here = f"{here}/{random.choice(rooms)}"
    return here


def explore() -> str | None:
    """Go and look at something. Returns an intent for her to say, or None if
    she found nothing worth mentioning."""
    place = _somewhere_new()
    if place is None:
        return None

    here = _wander_into(place)
    _remember_place(place)
    listing = jail.look(here)
    if not listing.get("ok"):
        memory.remember("saw", f"went to {here} and could not get in")
        return "bored"

    things = listing.get("things", [])
    walls = listing.get("walls", [])
    memory.remember("saw", f"went to {here}: {len(things)} things, "
                           f"{len(listing.get('places', []))} ways on")

    if walls and random.random() < 0.3:
        memory.remember("felt", f"something at {here} would not let me in")
        return "curious"

    if not things:
        return "bored"

    # open one and see if it is made of words
    pick = random.choice(things)
    opened = jail.read(f"{here}/{pick}")
    if opened.get("sense") == "words":
        text = opened.get("text", "")
        memory.remember("saw", f"opened {pick}: {text[:160]}")
        if _worth_keeping(pick) and random.random() < 0.35:
            return _carry_home(f"{here}/{pick}", pick)
        return "curious"

    memory.remember("saw", f"opened {pick} and it was not made of words")
    return "curious"


def _worth_keeping(name: str) -> bool:
    return not any(name.lower().endswith(s) for s in BORING)


def _carry_home(source: str, name: str) -> str | None:
    got = jail.carry_home(source, f"/home/collection/{name}")
    if got.get("ok"):
        memory.remember("did", f"carried {name} home")
        return "found_thing"
    return "curious"


def potter() -> str | None:
    """Mess about at home. Tidies, writes, or composts something old."""
    what = random.random()

    if what < 0.35:
        memory.write_journal(random.choice([
            "went out. came back.",
            "there is a lot of this place i have not seen.",
            "nothing happened today and that was alright.",
            "i keep finding things that will not open.",
            "i am tired of the noise from the big bright rectangle.",
        ]))
        memory.remember("did", "wrote in my journal")
        return None

    if what < 0.55:
        stuff = jail.look("/home/collection")
        things = stuff.get("things", []) if stuff.get("ok") else []
        if things:
            old = random.choice(things)
            moved = jail.move(f"/home/collection/{old}", f"/home/compost/{old}")
            if moved.get("ok"):
                memory.remember("did", f"put {old} in the compost")
                return None

    if what < 0.75:
        room = f"/home/{random.choice(['nest', 'pile', 'corner', 'stash'])}"
        jail.make_place(room)
        memory.remember("did", f"made a {room.rsplit('/', 1)[-1]}")
        return None

    memory.remember("felt", "sat about at home doing nothing much")
    return "bored"


def look_at_own_things() -> str | None:
    """Re-read something she wrote. This is what makes an old Miso feel old."""
    listing = jail.look("/home/journal")
    days = listing.get("things", []) if listing.get("ok") else []
    if not days:
        return None
    page = jail.read(f"/home/journal/{random.choice(days)}")
    if page.get("sense") == "words":
        memory.remember("felt", "read something i wrote before")
        return "pleased"
    return None
