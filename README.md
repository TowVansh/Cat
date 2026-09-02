# Miso

A cat that lives on this machine. Not an assistant and not a chatbot — she has
her own clock, her own drives and her own home, and she does things whether or
not anyone is talking to her.

She does not speak English. Everything she says is cat noise, with your reading
of it bracketed above:

```
(i wanna eat i am hungry)
mrrow mrow mrow mew
```

The text box is not a conversation. It is how you point at things in her world
— "miso food is there", "come here". She will often ignore you, and that is the
feature: a dog obeys, a cat considers the offer.

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
    mind.py               the voice her nightly diary is written in
    meow.py               how she talks: phrase bank + syllable synthesis
    commands.py           the text box; what she agrees to, and what she won't
    doings.py             what she does, decided in code rather than by a model
    watching.py           what you've been staring at, and when she minds
    body.py               the heartbeat
    voice.py              Kokoro TTS, falling back to the Windows voice
    ears.py               push-to-talk transcription
    face.py               the cat: drawn, not sprited, plus the speech bubble
    antics.py             how she moves: physics, chasing, pouncing, depth
    needs.py              hunger, thirst, and the bowls they come from
    home.py               her room, drawn; the bowls, bed, toys, shelf, sink
    house.py              the window that room lives in, and travelling to it
  pet.py                  start Miso with its body (this is the one you want)
  run.py                  start Miso in a plain console instead
  peek.py                 look in on its drives and memory without disturbing it
  test_jail.py            58 checks that the jail holds
  test_pet.py             78 checks that she stays a pet
  test_eyes.py            21 checks on screen vision
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

## She gets bored of what you're doing

If one window holds the foreground for hours **and** she is bored or lonely,
she minds — not on your behalf, she has no opinion about your screen time, but
because she wants to play and you are busy. She complains, then walks over and
sits squarely in front of it, then minimizes it.

**She can only ever minimize.** A minimized window is one click from being back
exactly as it was; a closed one can cost you unsaved work, and she has no way
of knowing what is unsaved. `test_pet.py` asserts the words `WM_CLOSE`,
`TerminateProcess`, `taskkill`, `DestroyWindow` and `ExitProcess` appear
nowhere in `watching.py`, and that `ShowWindow` is called exactly once.

She reads window *titles* only — never a screenshot for this. Password-manager
and banking titles are skipped, as is her own window. Every minimize is written
to the audit log. Tune `NAG_AFTER_MINUTES` in `watching.py`; it defaults to two
hours.

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

Speech went the same way. She used to compose replies through the model, which
took eight to thirteen seconds and, however fast it got, made the whole thing a
chat window with a cat drawn on it. Now every noise she makes is synthesised in
`meow.py` from what she wants — instantly, with no GPU — and the model is down
to one job.

## What the model is still for

Exactly one thing: at night she reads back everything that actually happened to
her that day and writes it up as though she understood it. That is what makes a
month-old Miso different from one born this morning, and it is the only place a
sentence of English is allowed to come from her. Nothing she says to you goes
near it.

```
ollama pull qwen3:8b       her diary
ollama pull moondream      the occasional glance at the screen (optional)
```

She runs without Ollama at all — she simply stops keeping a diary.

## Notes

- Most heartbeats cost nothing. The model is only woken when a drive is loud
  enough to want something, so the GPU stays idle when Miso is idle.
- Miso is meant to be left running. A month-old Miso is a different creature
  from a fresh one, because `who-i-am.md` and `map-of-the-world.md` are
  rewritten in its sleep from what actually happened.
- If you want Miso to reach more of the machine, add a mount to
  `config.MOUNTS`. Everything not mounted simply does not exist to it.
