"""Build every pixel-cat frame, for every skin, into miso/assets/pixel/.

Run from anywhere:  python3 tools/pixelcat/generate.py

To add a skin: add a palette to PALETTES in gen.py -- nothing else changes,
every frame is regenerated from the same drawing code for every palette.
To add a frame: add an entry to SPECS below and re-run.

talk_0/talk_1 flap on a fixed timer (see Cat._frame_name in face.py), not
real audio amplitude -- Miso's actual TTS (miso/voice.py) isn't wired into
the pixel renderer yet. Real lip-sync would sample the live playback
amplitude each frame instead of a sine wave; this is the placeholder for
that until it's worth the audio-thread plumbing.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frames
from gen import render, PALETTES

OUT = Path(__file__).resolve().parent.parent.parent / "miso" / "assets" / "pixel"

SPECS = {
    # idle_0 has blank eye sockets -- the app composites eye_overlay() on
    # top of it live, gaze-offset, so she can track the cursor. Every other
    # frame bakes the iris in as before (no live tracking while walking/etc).
    "idle_0": dict(eyes="blank"),
    "idle_1": dict(eye_open=False),
    # every frame has an asymmetric leg pose -- no frame where both sides
    # sit neutral, or half the cycle shows no leg motion at all and she
    # reads as gliding instead of stepping
    "walk_0": dict(leg_lift=(3, 0), bob=0, tail_phase=0.0),
    "walk_1": dict(leg_lift=(1, 2), bob=1, tail_phase=1.6, ear_a=1),
    "walk_2": dict(leg_lift=(0, 3), bob=0, tail_phase=3.1),
    "walk_3": dict(leg_lift=(2, 1), bob=1, tail_phase=4.7, ear_a=1),
    # airborne (hop/pounce/mid-air) -- both legs tucked, ears perked. Used
    # to exist nowhere: mid-air fell through to the sitting idle frame,
    # which is why jumps used to look broken rather than like a jump.
    "jump_0": dict(leg_lift=(3, 3), ear_a=1),
    # mood poses -- tied to the real drives (curiosity/loneliness/boredom),
    # not a canned animation. Previously all four fell back to plain idle.
    "mood_curious": dict(ear_a=2, bob=-1),
    "mood_happy": dict(ear_a=1, eye_mode="happy", mouth_curve=1),
    "mood_lonely": dict(ear_a=-2, mouth_curve=-1, bob=1),
    "mood_bored": dict(ear_a=-1, eye_mode="heavy", bob=1),
    # talking: mouth flaps between these two while a speech line is on
    # screen, at a fixed cadence (no real-time audio amplitude wired up
    # yet -- see the module docstring)
    "talk_0": dict(),
    "talk_1": dict(mouth_open=True),
    # held: picked up. Legs actually dangle (negative leg_lift lengthens
    # them instead of tucking them), the tail hangs and swings instead of
    # curling, and the body sits higher in the frame (bob) to leave the
    # extra canvas room the longer legs need. Two frames, tail swung to
    # opposite sides, alternated slowly for a bit of independent tail sway
    # under the whole-body pendulum motion the app drives separately.
    "held_0": dict(leg_lift=(-3, -3), tail_mode="hang", tail_phase=math.pi / 2,
                   ear_a=-1, bob=4),
    "held_1": dict(leg_lift=(-3, -3), tail_mode="hang", tail_phase=-math.pi / 2,
                   ear_a=-1, bob=4),
}


# sleep is a genuinely different silhouette (curled, not sitting with the
# eyes shut) so it's drawn by its own function, not base_cat -- see
# frames.sleep_curl. breathe is the only thing that changes between frames.
SLEEP_SPECS = {
    "sleep_0": dict(breathe=-0.6),
    "sleep_1": dict(breathe=0.6),
}


def main() -> None:
    count = 0
    for skin, palette in PALETTES.items():
        skin_dir = OUT / skin
        skin_dir.mkdir(parents=True, exist_ok=True)
        for name, kw in SPECS.items():
            grid = frames.base_cat(palette=palette, **kw)
            render(grid).save(skin_dir / f"{name}.png")
            count += 1
        for name, kw in SLEEP_SPECS.items():
            grid = frames.sleep_curl(palette, **kw)
            render(grid).save(skin_dir / f"{name}.png")
            count += 1
        # the movable iris overlay for idle_0, centred (gaze offset applied
        # live by the app, not baked in)
        eyes_grid = frames.eye_overlay(palette)
        render(eyes_grid).save(skin_dir / "eyes.png")
        count += 1
    print(f"wrote {count} frames across {len(PALETTES)} skins -> {OUT}")


if __name__ == "__main__":
    main()
