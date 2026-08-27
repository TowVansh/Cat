"""The heartbeat.

This is the difference between a pet and a chatbot: the loop runs whether or
not anyone is talking. Most beats cost nothing -- the model is only woken when
a drive is actually loud enough to want something.
"""
from __future__ import annotations

import queue
import threading
import time
from datetime import date

from . import brain, config, drives as drives_mod, memory, mind, reflex, senses

TICK_SECONDS = 30
MIN_GAP_BETWEEN_ACTS = 150      # seconds of quiet between unprompted moments
MAX_TURNS_PER_HOUR = 24         # hard ceiling, cannot spiral

OCCASIONS = {
    "explore": "nobody is about. you want to go and look at something. pick a "
               "direction and actually go -- look, and if you find a thing, open it. "
               "if you learn something worth keeping, put it in your map.",
    "potter": "you are in your home with nothing to do. tidy something, make "
              "something, write something down, or move an old thing to compost.",
    "find_you": "they are here. you want them to notice you. say something small. "
                "do not ask them if they need anything.",
    "rest": "you are tired. settle somewhere. maybe say one sleepy thing, maybe not.",
    "sleep": "you are asleep.",
    "idle": "nothing in particular. you are just here.",
}


class Miso:
    def __init__(self, on_speak=None, on_act=None, on_note=None, on_antic=None):
        self.drives = drives_mod.Drives.load()
        self.inbox: queue.Queue[str] = queue.Queue()
        self.on_speak = on_speak or (lambda s: None)
        self.on_act = on_act or (lambda a: None)
        self.on_note = on_note or (lambda n: None)
        self.on_antic = on_antic or (lambda a: None)
        self._stop = threading.Event()
        self._last_act = 0.0
        self._turn_times: list[float] = []
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

    # ---------------------------------------------------------------- life

    def _answer(self, heard: str) -> None:
        """Someone spoke. React now, think after.

        The reflex is instant and free. The spoken reply comes from the fast,
        tool-free path, which lands in well under a second. Miso is allowed to
        be wrong; she is not allowed to be slow.
        """
        self.drives.saw_you()
        self.drives.tick()
        self._asleep_until = 0.0             # being spoken to wakes a cat

        line, antic, wants_words = reflex.react(heard)
        self.on_antic(antic)
        if line:
            self.on_speak(line)
        memory.remember("heard", heard)

        if wants_words:
            reply = mind.chat(self.drives, heard)
            if reply:
                self.on_speak(reply)
                memory.remember("said", reply)
        self.drives.satisfy(loneliness=-0.25, boredom=-0.15)
        self._spend_turn()

    def _act(self, occasion_key: str, heard: str | None = None) -> None:
        occasion = OCCASIONS.get(occasion_key, OCCASIONS["idle"])
        # whatever Miso is doing on its own stops the moment you say something
        stop_for_you = None if heard else (lambda: not self.inbox.empty())
        try:
            out = mind.turn(self.drives, occasion, heard, interrupted=stop_for_you)
        except brain.BrainOffline as exc:
            self.on_note(f"(brain unreachable: {exc})")
            time.sleep(20)
            return

        for line in out["speech"]:
            self.on_speak(line)
        for act in out["acts"]:
            self.on_act(act)
        if out["napped"]:
            self._asleep_until = time.time() + out["napped"] * 60
            self.on_note(f"(curled up for {out['napped']} minutes)")
        self._spend_turn()

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
            if urge in ("idle", "rest") or not quiet_enough or not self._rate_ok():
                self.drives.save()
                self._stop.wait(TICK_SECONDS)
                continue

            # do not go hunting for someone who is not there
            if urge == "find_you" and not senses.someone_is_there():
                urge = "explore" if self.drives.curiosity > self.drives.boredom else "potter"

            self._act(urge)
            self.drives.save()
            self._stop.wait(TICK_SECONDS)
