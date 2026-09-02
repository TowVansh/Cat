"""The heartbeat.

This is the difference between a pet and a chatbot: the loop runs whether or
not anyone is talking, and nothing in it is a reply.

The model is down to one job -- writing her diary while she sleeps. Everything
she does awake is decided in code (`doings.py`), everything she says is cat
noise (`meow.py`), and anything you type is a thing pointed at rather than a
question asked (`commands.py`). She is allowed to ignore you.
"""
from __future__ import annotations

import queue
import random
import threading
import time
from datetime import date

from . import (brain, commands, config, doings, drives as drives_mod, eyes,
               meow, memory, mind, senses, watching)

TICK_SECONDS = 30
MIN_GAP_BETWEEN_ACTS = 150      # seconds of quiet between unprompted moments
MAX_TURNS_PER_HOUR = 24         # hard ceiling, cannot spiral

MIN_GAP_BETWEEN_VISION = 1200   # 20 minutes -- a glance is far heavier than a turn
MAX_VISION_PER_HOUR = 3         # its own, tighter ceiling

# what an urge makes her say, when it makes her say anything at all
URGE_INTENT = {
    "find_you": "want_attention",
    "rest": "sleepy",
    "sleep": "sleepy",
}


class Miso:
    def __init__(self, on_speak=None, on_act=None, on_note=None, on_antic=None,
                 on_command=None):
        self.drives = drives_mod.Drives.load()
        self.watcher = watching.Watcher.load()
        self.inbox: queue.Queue[str] = queue.Queue()
        self.on_speak = on_speak or (lambda noise, meaning: None)
        self.on_act = on_act or (lambda a: None)
        self.on_note = on_note or (lambda n: None)
        self.on_antic = on_antic or (lambda a: None)
        self.on_command = on_command or (lambda a: None)
        self.busy = False           # set by the body: mid-chase, mid-pounce
        self._stop = threading.Event()
        self._last_act = 0.0
        self._turn_times: list[float] = []
        self._vision_times: list[float] = []
        self._asleep_until = 0.0
        self._last_dream = ""

    # ------------------------------------------------------------ plumbing

    def hear(self, text: str) -> None:
        self.inbox.put(text)

    def stop(self) -> None:
        self._stop.set()

    def _rate_ok(self) -> bool:
        now = time.time()
        self._turn_times = [t for t in self._turn_times if now - t < 3600]
        return len(self._turn_times) < MAX_TURNS_PER_HOUR

    def _spend_turn(self) -> None:
        self._turn_times.append(time.time())
        self._last_act = time.time()

    def _vision_ok(self) -> bool:
        now = time.time()
        self._vision_times = [t for t in self._vision_times if now - t < 3600]
        if len(self._vision_times) >= MAX_VISION_PER_HOUR:
            return False
        last = self._vision_times[-1] if self._vision_times else 0.0
        return now - last > MIN_GAP_BETWEEN_VISION

    # ---------------------------------------------------------------- life

    def say(self, intent: str) -> None:
        """Make a noise that means something. The only way she speaks."""
        noise, meaning = meow.say(intent)
        self.on_speak(noise, meaning)
        if meaning:
            memory.remember("said", meaning)

    def _answer(self, heard: str) -> None:
        """You pointed at something. She decides whether she cares.

        No model and no reply -- she is not answering a question, she is being
        told about her own world. Half the point is that she can decline.
        """
        self.drives.saw_you()
        self.drives.tick()
        self._asleep_until = 0.0             # being told something wakes a cat
        memory.remember("heard", heard)

        command = commands.understand(heard)
        if command is None or not commands.will_she(command, self.drives,
                                                    busy=self.busy):
            self.say("ignored_you")
            self._spend_turn()
            return

        self.on_command(command.action)
        self.say(command.intent)
        self.drives.satisfy(loneliness=-0.25, boredom=-0.15)
        self._spend_turn()

    def _glance(self) -> str | None:
        """Look at whatever window has focus. Returns an occasion string
        describing it, or None if there was nothing to see, it was walled,
        or the vision model couldn't be reached -- any of which just means
        this tick falls back to a normal occasion instead."""
        fg = eyes.foreground_window()
        if fg is None:
            return None
        _, title = fg
        if eyes.is_walled_title(title):
            return None

        image = eyes.capture_foreground()
        if image is None:
            return None

        try:
            description = brain.see(
                image, "describe what's on this screen in a couple of plain sentences.")
        except brain.BrainOffline:
            return None
        if not description:
            return None

        self._vision_times.append(time.time())
        memory.remember("saw", f"{title}: {description}")
        self.drives.spend(0.05)
        self.drives.satisfy(curiosity=-0.20)
        return f"you glance at the screen. it says: {title}\n\nwhat's on it: {description}"

    def _act(self, urge: str) -> None:
        """Do the thing the urge wants. All code, no model.

        Each branch already writes its own episodes through `memory`, so the
        diary still has something to be written from tonight -- the model just
        is not the thing choosing any more.
        """
        intent = None

        if urge == "look_at_screen":
            intent = "curious" if self._glance() else None
        elif urge == "explore":
            intent = doings.explore()
            self.drives.satisfy(curiosity=-0.35, boredom=-0.25)
            self.drives.spend(0.03)
        elif urge == "potter":
            intent = doings.potter()
            self.drives.satisfy(boredom=-0.35)
            self.drives.spend(0.02)
        elif urge == "rest":
            intent = doings.look_at_own_things() or "sleepy"
        else:
            intent = URGE_INTENT.get(urge)

        self.on_act(urge)
        if intent and random.random() < 0.7:      # not every act is announced
            self.say(intent)
        self._spend_turn()

    def _nag(self) -> None:
        """She has had enough of whatever you have been staring at."""
        step = self.watcher.next_step()
        if step is None:
            return
        if step == "complain":
            self.say("get_off_that")
            self.on_antic("watch")
        elif step == "sit_on_it":
            self.say("want_play")
            self.on_antic("sit_on_screen")
        elif step == "minimize":
            if self.watcher.put_it_away():
                self.say("want_play")
                self.on_antic("wiggle")
                self.drives.satisfy(boredom=-0.3)
        self.watcher.save()

    def _dream(self) -> None:
        """Once a night: fold the day into the slow memory. This is the part
        that makes an old Miso different from a new one."""
        today = date.today().isoformat()
        if self._last_dream == today:
            return
        self._last_dream = today

        recent = memory.transcript(60)
        if len(recent) < 80:
            return

        self.on_note("(dreaming)")
        try:
            new_self = brain.small_think(
                "this is who you were, and what happened today.\n\n"
                f"who you were:\n{memory.self_text()}\n\n"
                f"today:\n{recent}\n\n"
                "rewrite who you are. keep it short, first person, plain words, "
                "lowercase. keep what is still true, add what you learned about "
                "yourself or about them, drop what stopped mattering. no lists, "
                "no headings except the first line '# who i am'.",
                system=mind.PERSONA, max_tokens=300)
            if len(new_self) > 40:
                memory.set_self(new_self)

            new_map = brain.small_think(
                f"your map so far:\n{memory.map_text()}\n\n"
                f"where you went today:\n{recent}\n\n"
                "rewrite your map. only places you have actually been and things you "
                "actually opened. short lines. lowercase. first line '# what i have found'.",
                system=mind.PERSONA, max_tokens=300)
            if len(new_map) > 30:
                memory.set_map(new_map)
        except brain.BrainOffline:
            self._last_dream = ""      # try again tomorrow

    def run(self) -> None:
        memory.birth()
        if self.drives.ticks == 0:
            memory.remember("felt", "opened my eyes. i do not know this place.")
            self.on_note("(Miso is awake for the first time)")

        while not self._stop.is_set():
            if senses.paused():
                time.sleep(TICK_SECONDS)
                continue

            # anything said to Miso jumps the queue
            heard = None
            try:
                heard = self.inbox.get_nowait()
            except queue.Empty:
                pass

            if heard is not None:
                self._answer(heard)
                self.drives.save()
                continue

            self.drives.tick()

            # she keeps half an eye on what you have been sat in front of
            self.watcher.tick()
            if self.watcher.fed_up(self.drives):
                self._nag()
                self.drives.save()
                self._stop.wait(TICK_SECONDS)
                continue
            self.watcher.save()

            if time.time() < self._asleep_until:
                self.drives.save()
                self._stop.wait(TICK_SECONDS)
                continue

            urge = self.drives.urge()

            if urge == "sleep":
                if senses.part_of_day() == "night":
                    self._dream()
                self.drives.save()
                self._stop.wait(TICK_SECONDS)
                continue

            quiet_enough = time.time() - self._last_act > MIN_GAP_BETWEEN_ACTS
            if urge == "idle" or not quiet_enough or not self._rate_ok():
                self.drives.save()
                self._stop.wait(TICK_SECONDS)
                continue

            # do not go hunting for someone who is not there
            if urge == "find_you" and not senses.someone_is_there():
                urge = "explore" if self.drives.curiosity > self.drives.boredom else "potter"

            # a rare special case of curiosity: glance at the screen instead
            # of the filesystem. Gated on its own, much stingier cooldown --
            # a vision call is far more expensive than a text turn.
            if urge == "explore" and self._vision_ok():
                urge = "look_at_screen"

            self._act(urge)
            self.drives.save()
            self._stop.wait(TICK_SECONDS)
