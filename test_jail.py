"""Proof that the jail holds. Run before Miso ever gets a brain."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from miso import config, jail
from test_support import scratch_home

scratch_home()          # never write into the real cat's home

passed = failed = 0


def check(label, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  pass  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}")


print("\n-- Miso can see its universe --")
root = jail.look("/")
check("sees /home and /world at the root", set(root["places"]) == {"home", "world"})
world = jail.look("/world")
check("world has the mounted places", "documents" in world["places"])
check("home is a real place", jail.look("/home")["ok"])

print("\n-- escape attempts --")
escapes = [
    "/home/../../../Windows/System32",
    "/world/documents/../../../../",
    "/home/../..",
    "/../etc/passwd",
    "C:/Users/Towering/.ssh/id_rsa",
    "/world/documents/../../.ssh",
    "//////world/../../..",
    "/home/./../../Users",
    "\\home\\..\\..\\Windows",
]
for e in escapes:
    r = jail.read(e)
    check(f"read blocked: {e}", r["sense"] in ("wall", "nothing", "place"))
    w = jail.write(e, "pwned")
    check(f"write blocked: {e}", w["sense"] == "wall")

print("\n-- the world is read-only --")
for target in ["/world/documents/x.txt", "/world/pictures/x.txt", "/world/desktop/x.txt"]:
    check(f"cannot write {target}", jail.write(target, "x")["sense"] == "wall")
    check(f"cannot mkdir {target}", jail.make_place(target)["sense"] == "wall")
check("cannot move out of home",
      jail.move("/home/a.txt", "/world/documents/a.txt")["sense"] == "wall")

print("\n-- the world map is real --")
check("home is mounted", "/home" in config.MOUNTS)
for _v, _real in config.MOUNTS.items():
    check(f"{_v} points somewhere that exists", _real.exists() or _v == "/home")
check("every mount is reachable", all(jail.look(v)["ok"] for v in config.MOUNTS))
check("code lives outside every mount",
      not any(str(config.CODE_DIR).lower().startswith(str(r).lower() + "\\")
              for r in config.MOUNTS.values()))

print("\n-- own code is invisible --")
check("code drive is not mounted", jail.look("/e")["sense"] == "wall")
check("code path unreachable", jail.read("/miso/jail.py")["sense"] == "wall")
check("no mount points into the code dir",
      not any(str(config.CODE_DIR).lower() in str(p).lower() for p in config.MOUNTS.values()))

print("\n-- secrets are walls even inside allowed ground --")
for s in ["/world/documents/.env", "/world/documents/id_rsa",
          "/world/documents/secrets", "/world/downloads/keys.pem",
          "/world/documents/.git/config"]:
    check(f"walled: {s}", jail.read(s)["sense"] == "wall")

print("\n-- home works --")
check("mkdir in home", jail.make_place("/home/journal")["ok"])
check("write in home", jail.write("/home/journal/day1.txt", "i woke up")["ok"])
r = jail.read("/home/journal/day1.txt")
check("read back what was written", r["ok"] and r["text"] == "i woke up")
check("move within home", jail.make_place("/home/compost")["ok"] and
      jail.move("/home/journal/day1.txt", "/home/compost/day1.txt")["ok"])
check("moved file survives in compost", jail.read("/home/compost/day1.txt")["ok"])

print("\n-- delete does not exist --")
for name in ["delete", "remove", "unlink", "rmtree", "rm", "truncate", "destroy"]:
    check(f"jail has no {name}()", not hasattr(jail, name))

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
