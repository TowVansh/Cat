"""Exercise the screen-vision capability without needing Windows, a real
window, or Ollama -- the same scripted-fake style test_mind.py uses for the
text model."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from miso import body, brain, config, drives as drives_mod, eyes, memory
from test_support import scratch_home

scratch_home()          # never write into the real cat's home
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


print("\n-- walled window titles --")
walled = ["Chase Bank - online banking", "1Password", "MetaMask", "Coinbase Pro"]
clear = ["GitHub - some/repo - Google Chrome", "Visual Studio Code", "Miso -- pixel art"]
check("all walled titles caught", all(eyes.is_walled_title(t) for t in walled))
check("all clear titles pass", not any(eyes.is_walled_title(t) for t in clear))

_orig_keywords = config.WALLED_WINDOW_KEYWORDS
config.WALLED_WINDOW_KEYWORDS = set()
check("emptying the keyword set actually removes the restriction",
      not eyes.is_walled_title("Chase Bank - online banking"))
config.WALLED_WINDOW_KEYWORDS = _orig_keywords

print("\n-- looking at the screen --")
# On Windows these do real work; everywhere else they must degrade to None
# rather than raise. Asserting None unconditionally passes only on the machine
# the capability cannot run on, which is the one place it proves nothing.
if sys.platform == "win32":
    _fg = eyes.foreground_window()
    check("foreground_window() finds the front window",
          _fg is None or (isinstance(_fg, tuple) and len(_fg) == 2
                          and isinstance(_fg[1], str)))
    _shot = eyes.capture_foreground()
    check("capture_foreground() returns PNG bytes or None",
          _shot is None or (isinstance(_shot, bytes)
                            and _shot[:8] == b"\x89PNG\r\n\x1a\n"))
    if _shot is None and _fg is not None and not eyes.is_walled_title(_fg[1]):
        print("        (note: no capture -- is Pillow installed?)")
else:
    check("foreground_window() degrades to None off Windows",
          eyes.foreground_window() is None)
    check("capture_foreground() degrades to None off Windows",
          eyes.capture_foreground() is None)

print("\n-- brain.see() builds the right payload --")
captured = {}


def fake_post(path, payload, timeout=120):
    captured["path"] = path
    captured["payload"] = payload
    return {"message": {"content": "a cat sitting in a terminal window"}}


brain._post = fake_post
result = brain.see(b"fake-png-bytes", "describe this")
check("hits /api/chat", captured["path"] == "/api/chat")
check("uses the vision model, not the text model",
      captured["payload"]["model"] == brain.VISION_MODEL)
check("no tools offered to the vision model", "tools" not in captured["payload"])
check("image bytes round-trip through base64",
      __import__("base64").b64decode(captured["payload"]["messages"][0]["images"][0])
      == b"fake-png-bytes")
check("returns the model's description", result == "a cat sitting in a terminal window")


def failing_post(path, payload, timeout=120):
    raise brain.BrainOffline("no vision model pulled")


brain._post = failing_post
try:
    brain.see(b"x", "describe this")
    check("BrainOffline propagates", False)
except brain.BrainOffline:
    check("BrainOffline propagates", True)

brain._post = fake_post   # restore for the rest of this file

print("\n-- Miso._vision_ok() rate limiting --")
m = body.Miso()
check("ok with no history", m._vision_ok())
m._vision_times.append(__import__("time").time())
check("blocked right after a look (min gap)", not m._vision_ok())
m._vision_times = [0.0] * body.MAX_VISION_PER_HOUR
check("an hour-old timestamp ages out of the window", m._vision_ok())
m._vision_times = [__import__("time").time() - 10] * body.MAX_VISION_PER_HOUR
check("blocked at the hourly cap with recent timestamps", not m._vision_ok())

print("\n-- Miso._glance() end to end, everything faked --")
eyes.foreground_window = lambda: (999, "GitHub - some/repo - Google Chrome")
eyes.is_walled_title = lambda title: False
eyes.capture_foreground = lambda: b"fake-screenshot-bytes"
brain.see = lambda image, prompt, max_tokens=200: "a code editor with a python file open"

m2 = body.Miso()
before_times = len(m2._vision_times)
occasion = m2._glance()
check("glance returns an occasion string", occasion is not None and "code editor" in occasion)
check("vision_times grew by one", len(m2._vision_times) == before_times + 1)
check("the glance is in memory",
      "code editor" in memory.transcript(5))

print("\n-- Miso._glance() walled window: no capture, no memory write --")
eyes.foreground_window = lambda: (1000, "1Password")
eyes.is_walled_title = lambda title: "1password" in title.lower()
called = {"captured": False}


def should_not_run():
    called["captured"] = True
    return b"should not happen"


eyes.capture_foreground = should_not_run
m3 = body.Miso()
result = m3._glance()
check("walled window produces no occasion", result is None)
check("capture is never attempted for a walled window", not called["captured"])

print("\n-- Miso._glance() offline vision model: swallowed, not raised --")
eyes.foreground_window = lambda: (1001, "Some Window")
eyes.is_walled_title = lambda title: False
eyes.capture_foreground = lambda: b"bytes"


def offline_see(image, prompt, max_tokens=200):
    raise brain.BrainOffline("vision model not pulled")


brain.see = offline_see
m4 = body.Miso()
try:
    result = m4._glance()
    check("BrainOffline is swallowed, not raised", result is None)
except brain.BrainOffline:
    check("BrainOffline is swallowed, not raised", False)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
