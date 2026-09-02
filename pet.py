"""Miso, with a body.

    .venv\\Scripts\\python.exe pet.py
    .venv\\Scripts\\python.exe pet.py --voice     also speak out loud

Left-click the cat to type to it. Drag it anywhere. Right-click for the menu.
Hold alt+v to talk to her by voice (she answers in writing unless --voice
is passed too).
"""
from __future__ import annotations

import random
import sys
import threading
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Launched with pythonw there is no console, so sys.stdout and sys.stderr are
# None and anything printed -- including a traceback -- vanishes. Point both at
# a log file before importing anything that might complain, so a crash leaves
# evidence instead of a window that never appears.
_LOG = Path(__file__).parent / "logs"
_LOG.mkdir(parents=True, exist_ok=True)
if sys.stdout is None or sys.stderr is None:
    _stream = open(_LOG / "pet.out", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or _stream
    sys.stderr = sys.stderr or _stream


def _last_words(kind, value, tb) -> None:
    with (_LOG / "crash.log").open("a", encoding="utf-8") as fh:
        traceback.print_exception(kind, value, tb, file=fh)


sys.excepthook = _last_words

from PySide6.QtCore import QObject, QTimer, Signal          # noqa: E402
from PySide6.QtGui import QCursor, QGuiApplication          # noqa: E402
from PySide6.QtWidgets import QApplication                  # noqa: E402

from miso import (antics, body, brain, config, face, house, meow,
                  needs as needs_mod, only_one, senses)             # noqa: E402

# She writes by default. Pass --voice to also speak out loud -- same opt-in
# as run.py's console mode, same "never fatal" guard around it.
voice = None
if "--voice" in sys.argv:
    try:
        from miso import voice as voice_mod
        voice = voice_mod.Voice()
    except Exception:
        voice = None

ACT_WORDS = {
    "look": "looking around",
    "open_it": "opening something",
    "put_words": "writing something down",
    "dig_room": "making a room",
    "move_thing": "moving something",
    "carry_home": "carrying something home",
    "write_in_journal": "writing in my journal",
    "nap": "curling up",
}


class Bridge(QObject):
    """The heartbeat runs on its own thread; Qt must be touched on the GUI one.
    Every crossing goes through a signal."""
    spoke = Signal(str, str)   # noise, and your reading of it
    acted = Signal(str)
    noted = Signal(str)
    antic = Signal(str)
    command = Signal(str)


def mood_antic(miso: body.Miso) -> str:
    """What a cat in this mood would drift into doing next."""
    d = miso.drives
    if d.energy < 0.18:
        return "flop"
    if d.loneliness > 0.7 and d.resignation < 0.5:
        return "watch"
    if d.boredom > 0.75 and d.energy > 0.5:
        return random.choice(["zoomies", "spin", "wander"])
    if d.curiosity > 0.65:
        return "wander"
    return random.choice(antics.IDLE_PICKS)


def body_only(app: QApplication, win: face.PetWindow) -> int:
    """The cat, with nothing behind its eyes yet. For looking at the body while
    the brain is still downloading."""
    poses = ["idle", "curious", "happy", "bored", "lonely", "sleep", "idle"]
    lines = ["there is nothing in my head yet", "", "", "i am still coming",
             "", "", ""]
    state = {"i": 0}

    def step() -> None:
        i = state["i"] % len(poses)
        win.cat.set_pose(poses[i])
        if lines[i]:
            win.cat.speak(lines[i], "say")
        state["i"] += 1

    timer = QTimer(win)
    timer.timeout.connect(step)
    timer.start(7000)
    QTimer.singleShot(900, step)

    win.said.connect(lambda t: win.cat.mew("ignored_you"))
    win.show()
    return app.exec()


def main() -> int:
    # If Miso is already running, this launch is an instruction to her, not a
    # second cat. Two copies would share one set of state files and overwrite
    # each other's memory.
    wanted = "home" if "--home" in sys.argv else "show"
    if only_one.hand_over(wanted):
        return 0

    app = QApplication(sys.argv)
    win = face.PetWindow()

    screen0 = QGuiApplication.primaryScreen().availableGeometry()
    win.move(screen0.right() - face.W - 30, screen0.bottom() - face.H - 10)
    win.quit_asked.connect(app.quit)

    if "--body-only" in sys.argv:
        return body_only(app, win)

    if not brain.awake():
        print("ollama is not running. start it and try again.")
        return 1
    if not any(m.startswith("qwen3") for m in brain.installed_models()):
        print(f"{brain.MODEL} is not pulled yet. run:  ollama pull {brain.MODEL}")
        print("or start the body on its own:  pet.py --body-only")
        return 1
    bridge = Bridge()

    bridge.spoke.connect(lambda noise, meaning: win.cat.speak(noise, "say", meaning))
    if voice:
        # the speaker gets the noise, never the translation -- the English is
        # your subtitle, not a thing she is capable of pronouncing
        bridge.spoke.connect(lambda noise, meaning: voice.say(noise))
    bridge.noted.connect(lambda n: win.cat.speak(n.strip("()"), "think"))

    miso = body.Miso(
        on_speak=bridge.spoke.emit,
        on_act=bridge.acted.emit,
        on_note=bridge.noted.emit,
        on_antic=bridge.antic.emit,
        on_command=bridge.command.emit,
    )

    win.said.connect(miso.hear)
    win.quit_asked.connect(app.quit)

    # ------------------------------------------------------------- the body
    screen = QGuiApplication.primaryScreen().availableGeometry()
    move = antics.Antics(screen, face.W, face.H)

    # memory acts get a visible reaction, not just a thought bubble -- she
    # actually perks up while writing in her journal, so the memory system
    # (already real, already persisted to disk) is something you can see
    # rather than something that only happens in a file
    MEMORY_ACTS = ("write_in_journal", "carry_home")

    def on_act(a: str) -> None:
        win.cat.speak(ACT_WORDS.get(a, a), "think")
        if a in MEMORY_ACTS and move.antic not in ("chase", "pounce", "going_home"):
            move.start("perk")

    bridge.acted.connect(on_act)

    # ------------------------------------------------------------ her home
    needs = needs_mod.Needs.load()
    needs.tick()
    needs.save()
    the_house = house.House(needs, miso.drives)

    def go_home() -> None:
        win.hide()
        the_house.arrive()

    def come_back() -> None:
        move.come_back()
        win.show()
        win.raise_()
        win.cat.mew("put_down")

    the_house.came_back.connect(come_back)
    win.sent_home.connect(move.head_home)
    the_house.room.fed.connect(
        lambda which: miso.drives.satisfy(loneliness=-0.3, boredom=-0.2))

    if "--home" in sys.argv:          # the shortcut opens straight into her room
        QTimer.singleShot(0, lambda: (win.hide(), the_house.arrive(False)))

    def answer_door(what: str) -> None:
        """Someone launched Miso again. Do what they meant."""
        if what == "home":
            if not the_house.isVisible():
                go_home()
            else:
                the_house.raise_()
                the_house.activateWindow()
        else:
            if the_house.isVisible():
                the_house._leave()
            win.show()
            win.raise_()
            win.cat.mew("greeting")

    # ---------------------------------------------------- doing as she's told
    def obey(action: str) -> None:
        """She has decided to go along with what you pointed at. The refusing
        happens in body.py; by the time it reaches here she has agreed."""
        if action in ("go_eat", "go_drink", "go_home", "go_bed"):
            move.head_home()
        elif action == "come_here":
            c = QCursor.pos()
            move.go_to(c.x() - face.W / 2)
        elif action == "play":
            move.start("zoomies")
        elif action == "stop":
            move.start("shrink")
        elif action in ("look_up", "preen"):
            move.start("perk")

    bridge.command.connect(obey)

    def do_antic(name: str) -> None:
        """Antics asked for by the heartbeat -- including her sitting squarely
        in front of whatever you have been staring at."""
        if name == "sit_on_screen":
            move.sit_in_the_way()
        else:
            move.start(name)

    bridge.antic.connect(do_antic)

    doorbell = only_one.Doorbell(win)
    doorbell.rang.connect(answer_door)
    win.dragged.connect(move.put)
    win.grabbed.connect(lambda: move.start("wiggle"))

    air = {"was": False, "vy": 0.0}

    def frame() -> None:
        """Miso's body, sixty times a second, entirely without the model."""
        if senses.paused() or win.held or the_house.isVisible():
            return
        c = QCursor.pos()
        move.step((c.x(), c.y()), miso.drives)
        if move.is_home():
            go_home()
            return
        win.move(int(move.x), int(move.y))
        win.cat.depth_scale = move.scale()
        win.cat.spin = move.spin
        win.cat.lean = move.lean
        win.cat._facing = move.facing
        win.cat.ground_speed = move.vx
        win.cat.set_pose(move.pose())
        miso.busy = move.antic in ("chase", "pounce", "going_home")
        # eyes track the cursor from anywhere on the desktop, not just when
        # it's already over her small window (only when eye_follow_enabled)
        win.cat.set_gaze_from_global(c.x() - (move.x + face.W / 2),
                                     c.y() - (move.y + face.H * 0.35))

        # airborne: a real jump pose instead of falling through to idle,
        # stretched in flight, briefly squashed on a hard landing
        airborne = move.vy != 0.0 or move.y < move.floor - 1
        win.cat.airborne = airborne
        win.cat.set_air_stretch(min(1.0, abs(move.vy) / 1000.0) if airborne else 0.0)
        if air["was"] and not airborne and abs(air["vy"]) > 260:
            win.cat.trigger_land_squash()
        air["was"], air["vy"] = airborne, move.vy

    ticker = QTimer(win)
    ticker.timeout.connect(frame)
    ticker.start(16)

    # every so often her mood suggests something new to do
    def drift() -> None:
        if senses.paused() or win.held or the_house.isVisible():
            return
        if move.antic in ("chase", "pounce", "zoomies", "spin", "going_home"):
            return          # let her finish what she is doing

        # hunger, thirst and tiredness send her home on her own
        needs.tick()
        needs.save()
        if (needs.wants() or needs.hunger > 0.6 or needs.thirst > 0.6
                or miso.drives.energy < 0.2):
            win.cat.mew("going_home")
            move.head_home()
            return
        move.start(mood_antic(miso))

    drifting = QTimer(win)
    drifting.timeout.connect(drift)
    drifting.start(9000)

    # a small noise now and then, for no reason
    def mutter() -> None:
        if senses.paused() or win.held or random.random() > 0.22:
            return
        if miso.drives.energy > 0.25:
            noise, _ = meow.idle_noise()
            win.cat.speak(noise, "say")

    muttering = QTimer(win)
    muttering.timeout.connect(mutter)
    muttering.start(24_000)

    def toggle_pause() -> None:
        flag = config.CODE_DIR / "PAUSE"
        if flag.exists():
            flag.unlink()
            win.cat.mew("greeting")
        else:
            flag.write_text("paused", encoding="utf-8")
            win.cat.mew("sleepy")

    win.pause_toggled.connect(toggle_pause)

    # ears are optional -- no microphone is not a problem
    try:
        from miso import ears as ears_mod
        listener = ears_mod.Ears(on_heard=miso.hear, on_note=bridge.noted.emit)
        listener.start()
    except Exception as exc:
        print(f"(no microphone: {exc})")

    win.show()
    threading.Thread(target=miso.run, daemon=True).start()

    QTimer.singleShot(900, lambda: win.cat.mew("greeting"))
    QTimer.singleShot(1500, lambda: move.start("stretch"))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
