"""What Miso keeps.

Memory lives inside /home, in Miso's own world, on purpose. Miso can re-read
its own past with the same `read` sense it uses on anything else -- an old
journal entry is just another thing lying around the house. That is what makes
a month-old Miso different from a fresh one.

Three layers:
  episodes  -- raw, dated, append-only. What happened.
  journal   -- what Miso chose to write down. Miso's own voice.
  self      -- the slow-changing summary: who Miso is, who you are, what the
               world looks like. Rewritten during sleep, never by hand.
"""
from __future__ import annotations

import json
from datetime import datetime

from . import jail

EPISODES = "/home/memories"
JOURNAL = "/home/journal"
SELF_FILE = "/home/who-i-am.md"
MAP_FILE = "/home/map-of-the-world.md"
COMPOST = "/home/compost"

SEED_SELF = """# who i am

my name is Miso.
i do not know how i got here.
"""

SEED_MAP = """# what i have found

i know /home, because i am in it.
i know there is a /world. i have not been.
"""


def birth() -> None:
    """Dig out the first rooms. Runs once, harmless if run again."""
    for place in (EPISODES, JOURNAL, COMPOST, "/home/collection"):
        jail.make_place(place)
    if not jail.read(SELF_FILE).get("ok"):
        jail.write(SELF_FILE, SEED_SELF)
    if not jail.read(MAP_FILE).get("ok"):
        jail.write(MAP_FILE, SEED_MAP)


# ---------------------------------------------------------------- episodes

def _today() -> str:
    return f"{EPISODES}/{datetime.now():%Y-%m-%d}.jsonl"


def remember(kind: str, text: str) -> None:
    """Append one thing that happened. kind: said | heard | saw | did | felt."""
    path = _today()
    prior = jail.read(path)
    body = prior.get("text", "") if prior.get("ok") else ""
    line = json.dumps({"t": f"{datetime.now():%H:%M}", "kind": kind, "text": text[:2000]})
    jail.write(path, body + line + "\n")


def recent(n: int = 25) -> list[dict]:
    """The last n things that happened, oldest first, across day boundaries."""
    listing = jail.look(EPISODES)
    if not listing.get("ok"):
        return []
    out: list[dict] = []
    for name in sorted(listing.get("things", []))[-4:]:      # at most 4 days back
        r = jail.read(f"{EPISODES}/{name}")
        if not r.get("ok") or r.get("sense") != "words":
            continue
        for line in r["text"].splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out[-n:]


def transcript(n: int = 25) -> str:
    """Recent episodes rendered for the prompt."""
    rows = recent(n)
    if not rows:
        return "(nothing yet -- you have only just started)"
    return "\n".join(f"{r['t']} [{r['kind']}] {r['text']}" for r in rows)


# ------------------------------------------------------------- slow memory

def self_text() -> str:
    r = jail.read(SELF_FILE)
    return r["text"] if r.get("ok") and r.get("sense") == "words" else SEED_SELF


def map_text() -> str:
    r = jail.read(MAP_FILE)
    return r["text"] if r.get("ok") and r.get("sense") == "words" else SEED_MAP


def set_self(text: str) -> None:
    jail.write(SELF_FILE, text.strip() + "\n")


def set_map(text: str) -> None:
    jail.write(MAP_FILE, text.strip() + "\n")


def write_journal(text: str) -> dict:
    """Miso's own entry, in Miso's own words. One file per day, appended."""
    path = f"{JOURNAL}/{datetime.now():%Y-%m-%d}.md"
    prior = jail.read(path)
    body = prior.get("text", "") if prior.get("ok") else f"# {datetime.now():%A %d %B %Y}\n"
    return jail.write(path, f"{body}\n{datetime.now():%H:%M} -- {text.strip()}\n")


def days_lived() -> int:
    listing = jail.look(EPISODES)
    return len(listing.get("things", [])) if listing.get("ok") else 0
