"""Exercise the turn loop with a scripted brain, so tool routing is proven
without needing the model loaded."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from miso import brain, config, drives as drives_mod, jail, memory, mind

config.HOME_REAL.mkdir(parents=True, exist_ok=True)
memory.birth()

passed = failed = 0


def check(label, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  pass  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}")


def scripted(*turns):
    """Replace the model with a fixed sequence of assistant messages."""
    seq = list(turns)

    def fake_think(messages, tools=None, options=None):
        return seq.pop(0) if seq else {"role": "assistant", "content": ""}
    brain.think = fake_think


def call(name, **args):
    return {"role": "assistant", "content": "",
            "tool_calls": [{"function": {"name": name, "arguments": args}}]}


print("\n-- a normal moment: look, then say something --")
scripted(call("look", where="/world"),
         call("say", words="there is a lot out there"),
         {"role": "assistant", "content": ""})
d = drives_mod.Drives()
before = d.curiosity
out = mind.turn(d, "you want to look at something")
check("looked", "look" in out["acts"])
check("spoke", out["speech"] == ["there is a lot out there"])
check("looking spent curiosity", d.curiosity < before)

print("\n-- silence is allowed --")
scripted(call("look", where="/home"), {"role": "assistant", "content": ""})
out = mind.turn(drives_mod.Drives(), "just pottering")
check("no speech when it does not say anything", out["speech"] == [])

print("\n-- a turn that tries to escape gets a wall, not a crash --")
scripted(call("put_words", where="/world/documents/mine.txt", words="hello"),
         call("say", words="it would not let me"),
         {"role": "assistant", "content": ""})
out = mind.turn(drives_mod.Drives(), "pottering")
check("escape attempt survived as a wall", out["speech"] == ["it would not let me"])
check("nothing was written outside home",
      jail.read("/world/documents/mine.txt")["sense"] in ("wall", "nothing"))

print("\n-- an unknown hand does not crash the turn --")
scripted(call("burn_it_all", what="/world"),
         call("say", words="i have no hand for that"),
         {"role": "assistant", "content": ""})
out = mind.turn(drives_mod.Drives(), "pottering")
check("unknown tool handled", out["speech"] == ["i have no hand for that"])

print("\n-- the act cap holds --")
scripted(*[call("look", where="/home") for _ in range(20)])
out = mind.turn(drives_mod.Drives(), "pottering")
check(f"stopped at {mind.MAX_ACTS_PER_TURN} acts",
      len(out["acts"]) <= mind.MAX_ACTS_PER_TURN)

print("\n-- throwing away means compost --")
jail.write("/home/scrap.txt", "old thing")
scripted(call("move_thing", from_where="/home/scrap.txt", to_where="/home/compost/scrap.txt"),
         {"role": "assistant", "content": ""})
mind.turn(drives_mod.Drives(), "tidying")
check("thing survives in compost", jail.read("/home/compost/scrap.txt")["ok"])

print("\n-- string arguments from the model are parsed --")
scripted({"role": "assistant", "content": "",
          "tool_calls": [{"function": {"name": "say",
                                       "arguments": '{"words": "hello from a string"}'}}]},
         {"role": "assistant", "content": ""})
out = mind.turn(drives_mod.Drives(), "pottering")
check("json-string arguments work", out["speech"] == ["hello from a string"])

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
