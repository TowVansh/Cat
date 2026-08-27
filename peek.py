"""Look in on Miso without disturbing it.

    py -3.12 peek.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from miso import config, drives as drives_mod, memory   # noqa: E402

BAR = 24


def bar(x: float) -> str:
    filled = int(round(x * BAR))
    return "[" + "#" * filled + "." * (BAR - filled) + f"] {x:.2f}"


def main() -> int:
    d = drives_mod.Drives.load()
    print(f"\n{config.PET_NAME} -- {d.age_days:.1f} days old, {d.ticks} heartbeats\n")
    for name in ("curiosity", "boredom", "loneliness", "energy", "resignation"):
        print(f"  {name:<12} {bar(getattr(d, name))}")
    print(f"\n  wants to     {d.urge()}")
    print(f"  last saw you {d.hours_since_you:.1f} hours ago")
    print(f"\n  {d.feelings()}\n")

    print("-- who it thinks it is " + "-" * 40)
    print(memory.self_text().strip())
    print("\n-- what it has found " + "-" * 42)
    print(memory.map_text().strip())

    print("\n-- lately " + "-" * 53)
    print(memory.transcript(15))

    log = config.LOG_DIR / "actions.log"
    if log.exists():
        lines = log.read_text(encoding="utf-8").splitlines()[-8:]
        print("\n-- last things it touched " + "-" * 37)
        for line in lines:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            when = r["t"][11:16]
            print(f"  {when}  {r['action']:<10} {r['outcome']:<8} {r['path']}")

    walls = 0
    if log.exists():
        walls = sum(1 for line in log.read_text(encoding="utf-8").splitlines()
                    if '"outcome": "wall"' in line)
    print(f"\n  walls it has bumped into: {walls}")
    print(f"  home: {config.HOME_REAL}")
    print(f"  today: {datetime.now():%A %d %B}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
