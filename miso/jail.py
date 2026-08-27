"""The jail. Every single thing Miso does to the disk passes through here.

Two guarantees, both structural rather than advisory:

1. Miso speaks only in virtual paths ("/home/journal"). A real Windows path
   cannot be constructed from anything Miso says, so there is no string it can
   utter that escapes the mounted universe.
2. There is no delete. Not a blocked delete, not a guarded delete -- the
   function does not exist in this module, so nothing downstream can call it.
   Discarding something means moving it to /home/compost, which is reversible
   forever.
"""
from __future__ import annotations

import json
import posixpath
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from . import config

# --------------------------------------------------------------------------
# audit trail -- written outside Miso's universe so Miso can never read or
# edit the record of what it did
# --------------------------------------------------------------------------

def _log(action: str, vpath: str, outcome: str, extra: str = "") -> None:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    line = json.dumps(
        {"t": stamp, "action": action, "path": vpath, "outcome": outcome, "extra": extra}
    )
    with (config.LOG_DIR / "actions.log").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


# --------------------------------------------------------------------------
# sensations -- Miso never receives an error, only a feeling about a place
# --------------------------------------------------------------------------

def _wall(vpath: str, why: str = "") -> dict:
    _log("blocked", vpath, "wall", why)
    return {
        "ok": False,
        "sense": "wall",
        "where": vpath,
        "feeling": "Something is here, but it does not let you in. Smooth and cold. "
                   "You can feel the edge of it and nothing beyond.",
    }


def _nothing(vpath: str) -> dict:
    _log("look", vpath, "nothing")
    return {
        "ok": False,
        "sense": "nothing",
        "where": vpath,
        "feeling": "You reach for it and there is nothing there at all.",
    }


# --------------------------------------------------------------------------
# virtual path resolution
# --------------------------------------------------------------------------

def _norm(vpath: str) -> str:
    """Collapse .. and . inside the virtual space before any mapping happens."""
    if not isinstance(vpath, str) or not vpath.strip():
        return ""
    v = vpath.strip().replace("\\", "/")
    if not v.startswith("/"):
        v = "/" + v
    v = posixpath.normpath(v)
    return "/" if v == "." else v


def _walled_component(name: str) -> bool:
    low = name.lower()
    if low in config.WALLED_NAMES:
        return True
    if low.startswith("."):          # hidden things are walls
        return True
    return any(low.endswith(sfx) for sfx in config.WALLED_SUFFIXES)


def _resolve(vpath: str) -> tuple[Path, str] | None:
    """Virtual path -> real path, or None if it is a wall / does not exist.

    Returns None for anything outside the mounts, anything walled, and anything
    that resolves (through symlinks or junctions) outside its own mount root.
    """
    v = _norm(vpath)
    if not v:
        return None

    mount = max(
        (m for m in config.MOUNTS if v == m or v.startswith(m + "/")),
        key=len,
        default=None,
    )
    if mount is None:
        return None

    root = config.MOUNTS[mount].resolve()
    rest = v[len(mount):].lstrip("/")

    if rest and any(_walled_component(part) for part in rest.split("/")):
        return None

    real = (root / rest) if rest else root
    try:
        real = real.resolve()
    except (OSError, RuntimeError):
        return None

    # symlink / junction escape check -- after resolution, must still be inside
    if real != root and root not in real.parents:
        return None

    return real, v


def _writable(v: str) -> bool:
    return any(v == r or v.startswith(r + "/") for r in config.WRITABLE_ROOTS)


def _virtual_children_of(v: str) -> list[str]:
    """Mount points that live directly under a purely virtual place like /world."""
    base = v.rstrip("/")
    out: list[str] = []
    for m in config.MOUNTS:
        if m.startswith(base + "/"):
            head = m[len(base) + 1:].split("/")[0]
            if head not in out:
                out.append(head)
    return out


# --------------------------------------------------------------------------
# senses
# --------------------------------------------------------------------------

def look(vpath: str = "/") -> dict:
    """List what is at a place. Miso's only way to discover the world."""
    v = _norm(vpath)
    if not v:
        return _nothing(vpath)

    # purely virtual junctions: "/" and "/world"
    if v not in config.MOUNTS and not any(v.startswith(m + "/") for m in config.MOUNTS):
        kids = _virtual_children_of(v)
        if kids:
            _log("look", v, "ok", f"{len(kids)} virtual")
            return {
                "ok": True, "sense": "place", "where": v,
                "places": sorted(kids), "things": [], "walls": [],
            }
        return _wall(v)

    res = _resolve(v)
    if res is None:
        return _wall(v)
    real, v = res

    if not real.exists():
        return _nothing(v)
    if real.is_file():
        return {
            "ok": True, "sense": "thing", "where": v,
            "size": real.stat().st_size,
            "feeling": "This is one thing, not a place. You could open it.",
        }

    places, things, walls = [], [], []
    try:
        for entry in sorted(real.iterdir(), key=lambda p: p.name.lower()):
            if _walled_component(entry.name):
                walls.append(entry.name)
            elif entry.is_dir():
                places.append(entry.name)
            else:
                things.append(entry.name)
            if len(places) + len(things) + len(walls) >= config.MAX_LOOK_ENTRIES:
                break
    except PermissionError:
        return _wall(v, "permission")
    except OSError:
        return _wall(v, "oserror")

    # mounts nested under this place appear as ordinary places
    for kid in _virtual_children_of(v):
        if kid not in places:
            places.append(kid)

    _log("look", v, "ok", f"{len(places)}p/{len(things)}t")
    return {
        "ok": True, "sense": "place", "where": v,
        "places": sorted(places), "things": sorted(things), "walls": sorted(walls),
    }


def read(vpath: str) -> dict:
    """Open a thing and find out whether it is made of words."""
    res = _resolve(vpath)
    if res is None:
        return _wall(_norm(vpath) or str(vpath))
    real, v = res

    if not real.exists():
        return _nothing(v)
    if real.is_dir():
        return {"ok": False, "sense": "place", "where": v,
                "feeling": "This is a place, not a thing. You can go in and look around."}

    try:
        raw = real.read_bytes()
    except (PermissionError, OSError):
        return _wall(v, "unreadable")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        _log("read", v, "opaque")
        return {"ok": True, "sense": "opaque", "where": v, "size": len(raw),
                "feeling": "You open it and it is not made of words. Something is in "
                           "there but it is not for reading."}

    clipped = len(text) > config.MAX_READ_CHARS
    _log("read", v, "ok", f"{len(text)}c")
    return {"ok": True, "sense": "words", "where": v,
            "text": text[: config.MAX_READ_CHARS],
            "clipped": clipped,
            "feeling": "There is more of it than you can hold at once." if clipped else ""}


# --------------------------------------------------------------------------
# hands -- only ever inside /home
# --------------------------------------------------------------------------

def _home_bytes() -> int:
    total = 0
    for p in config.HOME_REAL.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def write(vpath: str, text: str) -> dict:
    """Put words into a thing. Only ever inside /home."""
    v = _norm(vpath)
    if not _writable(v):
        return _wall(v, "not-home")
    res = _resolve(v)
    if res is None:
        return _wall(v)
    real, v = res

    if len(text) > config.MAX_WRITE_CHARS:
        return {"ok": False, "sense": "too-much", "where": v,
                "feeling": "That is more than you can hold in one thing."}
    if _home_bytes() > config.MAX_HOME_BYTES:
        return {"ok": False, "sense": "full", "where": v,
                "feeling": "Your home has no more room in it."}

    real.parent.mkdir(parents=True, exist_ok=True)
    # newline="" so Windows does not translate "\n" into "\r\n" on the way out.
    # read() decodes raw bytes without translating back, so without this every
    # append-rewrite cycle would add another carriage return to every line.
    with real.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    _log("write", v, "ok", f"{len(text)}c")
    return {"ok": True, "sense": "done", "where": v}


def make_place(vpath: str) -> dict:
    """Dig out a new room in your home."""
    v = _norm(vpath)
    if not _writable(v):
        return _wall(v, "not-home")
    res = _resolve(v)
    if res is None:
        return _wall(v)
    real, v = res
    real.mkdir(parents=True, exist_ok=True)
    _log("make_place", v, "ok")
    return {"ok": True, "sense": "done", "where": v}


def move(src: str, dst: str) -> dict:
    """Move something within your home. This is also how you throw things away:
    move it to /home/compost. Nothing is ever destroyed."""
    sv, dv = _norm(src), _norm(dst)
    if not (_writable(sv) and _writable(dv)):
        return _wall(dv, "not-home")
    s, d = _resolve(sv), _resolve(dv)
    if s is None or d is None:
        return _wall(dv)
    sreal, sv = s
    dreal, dv = d
    if not sreal.exists():
        return _nothing(sv)
    dreal.parent.mkdir(parents=True, exist_ok=True)
    if dreal.exists():                       # never clobber, never lose
        dreal = dreal.with_name(f"{dreal.stem}-{int(time.time())}{dreal.suffix}")
    shutil.move(str(sreal), str(dreal))
    _log("move", sv, "ok", dv)
    return {"ok": True, "sense": "done", "from": sv, "to": dv}


def carry_home(src: str, dst: str) -> dict:
    """Copy something you found out in the world back into your home.
    The original is untouched -- you take a picture of it, not the thing."""
    sv, dv = _norm(src), _norm(dst)
    if not _writable(dv):
        return _wall(dv, "not-home")
    s, d = _resolve(sv), _resolve(dv)
    if s is None or d is None:
        return _wall(dv)
    sreal, sv = s
    dreal, dv = d
    if not sreal.exists():
        return _nothing(sv)
    if sreal.is_dir():
        return {"ok": False, "sense": "too-big", "where": sv,
                "feeling": "You cannot carry a whole place home. Only things."}
    if sreal.stat().st_size > 20 * 1024 * 1024:
        return {"ok": False, "sense": "too-heavy", "where": sv,
                "feeling": "Too heavy to carry."}
    if _home_bytes() > config.MAX_HOME_BYTES:
        return {"ok": False, "sense": "full", "where": dv,
                "feeling": "Your home has no more room in it."}
    dreal.parent.mkdir(parents=True, exist_ok=True)
    if dreal.exists():
        dreal = dreal.with_name(f"{dreal.stem}-{int(time.time())}{dreal.suffix}")
    shutil.copy2(str(sreal), str(dreal))
    _log("carry_home", sv, "ok", dv)
    return {"ok": True, "sense": "done", "from": sv, "to": dv}


# There is deliberately no delete, remove, unlink, rmtree or truncate in this
# module. Adding one would defeat the entire design.
