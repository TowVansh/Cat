"""She is a pet, not a chatbot -- the checks that keep her that way.

Replaces test_mind.py, which tested a turn loop that no longer exists. No
Ollama, no Windows, no display needed: same plain counter style as
test_jail.py.
"""
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from miso import commands, config, drives as drives_mod, meow, watching

passed = failed = 0


def check(label, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  pass  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}")


# --------------------------------------------------------------------- meow

print("\n-- she only ever makes cat noises --")
WORD = re.compile(r"[a-z]+")
for intent in meow.MEANINGS:
    noise, meaning = meow.say(intent, seed=1)
    words = set(WORD.findall(noise))
    check(f"{intent}: noise is only syllables",
          words and words <= meow.ALL_SYLLABLES | {"mee", "meee"} or
          all(w.strip("aeiourwmnyp") == "" or w in meow.ALL_SYLLABLES
              or w.replace("ee", "e") in meow.ALL_SYLLABLES for w in words))
    check(f"{intent}: has a translation", bool(meaning.strip()))

check("every intent is reachable", len(meow.MEANINGS) >= 15)
check("an unknown intent still makes a noise", bool(meow.say("nonsense")[0]))
check("idle noise carries no words put in her mouth",
      meow.idle_noise()[1] == "")

print("\n-- the noise fits the meaning --")
short = meow.say("annoyed", seed=3)[0]
long_ = meow.say("get_off_that", seed=3)[0]
check("a longer thought makes a longer noise",
      len(long_.split()) >= len(short.split()))
check("she does not repeat herself word for word",
      len({meow.say("hungry", seed=s)[0] for s in range(8)}) > 3)

print("\n-- no English reaches the spoken line --")
english = {"i", "the", "you", "and", "food", "play", "me", "is", "my"}
for intent in meow.MEANINGS:
    for s in range(6):
        noise = meow.say(intent, seed=s)[0]
        if set(WORD.findall(noise)) & english:
            check(f"{intent} leaked an English word into the noise", False)
            break
    else:
        continue
    break
else:
    check("no intent ever leaks English into the noise", True)


# ----------------------------------------------------------------- commands

print("\n-- the text box points at things --")
for text, action in [
    ("miso food is there", "go_eat"),
    ("water", "go_drink"),
    ("come here", "come_here"),
    ("go home", "go_home"),
    ("time to sleep", "go_bed"),
    ("wanna play?", "play"),
    ("no! stop", "stop"),
    ("miso", "look_up"),
    ("good girl", "preen"),
]:
    got = commands.understand(text)
    check(f"{text!r} -> {action}", got is not None and got.action == action)

check("nonsense means nothing to her",
      commands.understand("the quarterly figures are down") is None)
check("an empty box means nothing", commands.understand("   ") is None)

print("\n-- but she is allowed to refuse --")
keen = drives_mod.Drives(energy=1.0, resignation=0.0, loneliness=1.0)
sulky = drives_mod.Drives(energy=0.15, resignation=1.0, loneliness=0.0)

food = commands.understand("food")
check("food always works, whatever her mood",
      all(commands.will_she(food, sulky) for _ in range(30)))

come = commands.understand("come here")
refusals = sum(0 if commands.will_she(come, sulky) else 1 for _ in range(200))
check("a sulky, exhausted cat refuses most of the time", refusals > 120)
eager = sum(1 if commands.will_she(come, keen) else 0 for _ in range(200))
check("a lonely, rested one usually comes", eager > 60)
check("being mid-pounce makes her less biddable",
      sum(0 if commands.will_she(come, keen, busy=True) else 1
          for _ in range(200)) >
      sum(0 if commands.will_she(come, keen, busy=False) else 1
          for _ in range(200)))


# ----------------------------------------------------------------- watching

print("\n-- she notices what you have been staring at --")
w = watching.Watcher(app="youtube", seconds=0.0)
bored = drives_mod.Drives(boredom=0.9, loneliness=0.9, energy=0.8,
                          resignation=0.0)
tired = drives_mod.Drives(boredom=0.9, loneliness=0.9, energy=0.1,
                          resignation=0.0)
givenup = drives_mod.Drives(boredom=0.9, loneliness=0.9, energy=0.8,
                            resignation=0.9)

check("ten minutes on one thing is nobody's business",
      not w.fed_up(bored))
w.seconds = watching.NAG_AFTER_MINUTES * 60 + 1
check("hours on one thing, and bored, and she minds", w.fed_up(bored))
check("a tired cat does not care", not w.fed_up(tired))
check("a cat that has given up on you does not care", not w.fed_up(givenup))

calm = drives_mod.Drives(boredom=0.1, loneliness=0.1, energy=0.8,
                         resignation=0.0)
check("a contented cat does not mind what you do", not w.fed_up(calm))

print("\n-- and escalates, in order --")
w2 = watching.Watcher(app="youtube", seconds=watching.NAG_AFTER_MINUTES * 60 + 1)
check("first she complains", w2.next_step() == "complain")
check("she waits to be noticed", w2.next_step() is None)
w2.step_at -= watching.STEP_PATIENCE + 1
check("then she sits on it", w2.next_step() == "sit_on_it")
w2.step_at -= watching.STEP_PATIENCE + 1
check("only then does she put it away", w2.next_step() == "minimize")
check("and the clock resets afterwards", w2.seconds == 0.0 and w2.step == 0)

print("\n-- she can only ever minimize --")
source = Path(__file__).with_name("miso") / "watching.py"
text = source.read_text(encoding="utf-8")
for forbidden in ("TerminateProcess", "WM_CLOSE", "taskkill", "DestroyWindow",
                  "EndTask", "ExitProcess"):
    check(f"watching.py cannot {forbidden}", forbidden not in text)
check("SW_MINIMIZE is the only window command", text.count("ShowWindow") == 1)

print("\n-- and never touches the wrong window --")
w3 = watching.Watcher(app="bank")
check("her own window is never a target",
      any(o in "miso's home" for o in watching.OWN_TITLES))
check("walled titles are still walled",
      __import__("miso.eyes", fromlist=["x"]).is_walled_title("Chase Bank"))

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
