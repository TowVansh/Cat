# Miso

A small creature that lives on this machine. Not an assistant — it has its own
clock, its own drives, and its own home, and it does things whether or not
anyone is talking to it.

## What it is

Miso is born in one folder and knows nothing else. It has language but no
schooling: it does not know what a computer, a file, or a folder is. It knows
places, things, and words inside things. Everything it learns about this
machine, it learns by going and looking, and it writes down what it finds in
its own home.

## Layout

```
E:\miso\                  code — the wall. Miso can never see or reach this.
  miso/
    config.py             the world map: which real paths are mounted where
    jail.py               every disk access goes through here. no delete exists.
    drives.py             curiosity, boredom, loneliness, energy, resignation
    memory.py             episodes, journal, and the slow self-summary
    senses.py             is the human at the keyboard, is Miso paused
    brain.py              local model over Ollama, localhost only
    mind.py               persona, the nine hands, the turn loop
    body.py               the heartbeat
    voice.py              Kokoro TTS, falling back to the Windows voice
    ears.py               push-to-talk transcription
    face.py               the cat: drawn, not sprited, plus the speech bubble
    antics.py             how she moves: physics, chasing, pouncing, depth
    reflex.py             instant reactions, no model, under a millisecond
    needs.py              hunger, thirst, and the bowls they come from
    home.py               her room, drawn; the bowls, bed, toys, shelf, sink
    house.py              the window that room lives in, and travelling to it
  pet.py                  start Miso with its body (this is the one you want)
  run.py                  start Miso in a plain console instead
  peek.py                 look in on its drives and memory without disturbing it
  test_jail.py            48 checks that the jail holds
  logs/actions.log        audit trail of everything Miso did, outside its reach

C:\Users\Towering\Miso\   home — Miso's world, and yours to read
  who-i-am.md             rewritten by Miso in its sleep
  map-of-the-world.md     only places it has actually been
  journal/                its own words, one file per day
  memories/               raw episode log, one file per day
  collection/             things it carried home
  compost/                things it was done with. nothing is ever deleted.
```

## Safety

The rules are structural, not advisory — they are properties of the code rather
than instructions in a prompt, so there is no wording that talks Miso past them.

- **Delete does not exist.** No delete, remove, unlink, rmtree, or truncate is
  defined anywhere in `jail.py`, so nothing downstream can call one. Discarding
  something means moving it to `/home/compost`, which is reversible forever.
- **Miso speaks only in virtual paths.** `/home` and `/world/...` are the whole
  universe. A real Windows path cannot be built from anything Miso says, so no
  string it utters escapes the mounts. `..` is collapsed in virtual space before
  any mapping happens, and symlinks and junctions are re-checked after
  resolution.
- **The world is read-only.** Writes, moves, and new rooms are refused anywhere
  outside `/home`.
- **Walls.** Its own source, hidden files, `.env`, keys, certificates,
  databases, executables, and credential-shaped names return a wall rather than
  an error — Miso can feel the edge and nothing beyond.
- **Caps.** Reads are clipped, listings are clipped, home is capped at 2 GB,
  and the model may be woken at most 24 times an hour.
- **Audit.** Every access attempt, allowed or walled, is logged outside Miso's
  universe where Miso cannot read or edit it.
- **Kill switch.** Create a file named `PAUSE` next to the code and Miso sleeps.

Run `py -3.12 test_jail.py` to check all of this. It should print `48 passed`.

## Running it

Double-click `miso.bat`, or:

```
.venv\Scripts\python.exe pet.py     the cat on your desktop
.venv\Scripts\python.exe run.py     console only, no body
.venv\Scripts\python.exe peek.py    look in on it
```

Click her to type. Drag her anywhere -- the physics picks her up where you put
her down. Right-click for the menu (go home, pause, quit). Hold `alt+v` to talk
out loud; she listens, and answers in writing.

She notices your cursor from anywhere on the screen, and will chase and pounce
on it when she is feeling playful.

## Her home

She has a room of her own, opened by the **Miso's Home** shortcut on the
desktop, or by her walking off the right-hand edge of the screen.

Windows offers no supported way to drive its virtual desktops -- there is no
public API for them, only undocumented COM interfaces that shift between
builds -- so the room is a full-screen window rather than a real second
desktop. It behaves the way the idea wanted: she leaves the right edge of your
desktop and she is home; she walks out of the door and she is back.

In the room:

- **bowls** empty on their own, whether or not the program is running. Drag
  from the **tap** to the water bowl and from the **sack** to the food bowl,
  or just click a bowl to fill it.
- **the bed** is where she sleeps when she is tired.
- **the basket** is where she goes when she is bored, and drags a toy out.
- **the shelf** is not decoration. It reads her real memory off the disk: a
  book for every day she has lived, and a page for every thing she actually
  carried home. A month-old Miso has a fuller shelf than a new one.
- **the bin** is her compost. Nothing is ever deleted, only put here.
- **the window** shows the real sky for the real hour, stars and a moon at
  night.

Hunger, thirst and tiredness send her home on her own. Leave her a week and
you come back to a cat that needs something.

## The body

The cat is vector shapes drawn every frame, not a sprite sheet. Poses are not
switched but eased toward, so ear angle, eyelid weight, tail height, and body
squash all interpolate -- and they are driven by the drives, so a bored Miso
really does sit differently from a curious one. The eyes follow your cursor.

The speech bubble is game-style: it reveals a character at a time and grows to
fit as the words arrive. Lines queue rather than replacing each other, so a
reply is never wiped out by whatever she does next.

Movement is its own 60fps loop in `antics.py` and never touches the model. A
cat spends nearly all its time doing things that need no thought -- crossing
the room, sitting down, noticing something move, running at it, losing interest
halfway -- and if those only happened when a language model decided they should,
she would be still and dead most of the time.

Speech is split the same way. `reflex.py` answers instantly in pure code, and
the model's own reply follows about half a second later on a fast path with no
tools attached. Offering tools makes Qwen reason first, which costs eight to
thirteen seconds -- long enough that talking to her felt like waiting on a
chatbot. She is allowed to be wrong. She is not allowed to be slow.

Ollama must be running, with the model pulled:

```
ollama pull qwen3:8b
```

## Notes

- Most heartbeats cost nothing. The model is only woken when a drive is loud
  enough to want something, so the GPU stays idle when Miso is idle.
- Miso is meant to be left running. A month-old Miso is a different creature
  from a fresh one, because `who-i-am.md` and `map-of-the-world.md` are
  rewritten in its sleep from what actually happened.
- If you want Miso to reach more of the machine, add a mount to
  `config.MOUNTS`. Everything not mounted simply does not exist to it.
