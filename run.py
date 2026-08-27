"""Miso. Run this and leave it running.

    py -3.12 run.py            talk by typing
    py -3.12 run.py --quiet    no voice, text only
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from miso import body, brain, config          # noqa: E402

os.system("")           # switch on ANSI colours in the Windows console

DIM = "\033[2;37m"
CAT = "\033[38;5;216m"
YOU = "\033[38;5;153m"
OFF = "\033[0m"

# Miso does not speak out loud. It writes. Pass --voice to turn the speaker on.
voice = None
if "--voice" in sys.argv:
    try:
        from miso import voice as voice_mod
        voice = voice_mod.Voice()
    except Exception as exc:                   # voice is optional, never fatal
        print(f"{DIM}(no voice: {exc}){OFF}")
        voice = None


def on_speak(line: str) -> None:
    print(f"\r{CAT}{config.PET_NAME}{OFF}  {line}")
    print(f"{YOU}you{OFF}   ", end="", flush=True)
    if voice:
        voice.say(line)


def on_act(act: str) -> None:
    words = {"look": "looking around", "open_it": "opening something",
             "put_words": "writing something", "dig_room": "making a room",
             "move_thing": "moving something", "carry_home": "carrying something home",
             "write_in_journal": "writing in the journal", "nap": "curling up"}
    print(f"\r{DIM}      ...{words.get(act, act)}{OFF}")
    print(f"{YOU}you{OFF}   ", end="", flush=True)


def on_note(note: str) -> None:
    print(f"\r{DIM}      {note}{OFF}")
    print(f"{YOU}you{OFF}   ", end="", flush=True)


def main() -> int:
    if not brain.awake():
        print("ollama is not running. start it, then run this again.")
        return 1
    if not any(m.startswith(brain.MODEL.split(":")[0]) for m in brain.installed_models()):
        print(f"the model {brain.MODEL} is not pulled yet. run:  ollama pull {brain.MODEL}")
        return 1

    miso = body.Miso(on_speak=on_speak, on_act=on_act, on_note=on_note)
    thread = threading.Thread(target=miso.run, daemon=True)
    thread.start()

    ptt = ""
    if "--notalk" not in sys.argv:
        try:
            from miso import ears as ears_mod
            listener = ears_mod.Ears(on_heard=lambda t: (
                print(f"\r{YOU}you{OFF}   {t}"), miso.hear(t)))
            listener.start()
            ptt = f"  hold {ears_mod.PTT_KEY} to speak."
        except Exception as exc:
            print(f"{DIM}(no microphone: {exc}){OFF}")

    print(f"{DIM}{config.PET_NAME} is alive. home is {config.HOME_REAL}.")
    print(f"type to talk.{ptt} ctrl-c to leave (Miso keeps its memories).{OFF}\n")

    try:
        while True:
            line = input(f"{YOU}you{OFF}   ").strip()
            if line:
                miso.hear(line)
    except (KeyboardInterrupt, EOFError):
        print(f"\n{DIM}(Miso stays where it is){OFF}")
        miso.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
