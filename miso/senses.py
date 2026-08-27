"""What Miso can feel about the world outside its own head."""
from __future__ import annotations

import ctypes
import time

from . import config


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def idle_seconds() -> float:
    """How long since the human last touched the keyboard or mouse."""
    try:
        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        ticks = ctypes.windll.kernel32.GetTickCount()
        return max(0.0, (ticks - info.dwTime) / 1000.0)
    except (AttributeError, OSError):
        return 0.0


def someone_is_there() -> bool:
    """True if the human is at the machine right now."""
    return idle_seconds() < 120


def paused() -> bool:
    """Kill switch. Drop a file named PAUSE next to the code and Miso sleeps."""
    return (config.CODE_DIR / "PAUSE").exists()


def part_of_day() -> str:
    h = time.localtime().tm_hour
    if h < 5:
        return "night"
    if h < 9:
        return "early"
    if h < 17:
        return "day"
    if h < 22:
        return "evening"
    return "night"
