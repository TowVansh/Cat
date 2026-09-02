# AGENTS.md — for whichever AI agent picks this repo up next

This file exists so a fresh agent (any model, any tool) can get oriented without
re-deriving everything from scratch. It explains what Miso is, how the modules
fit together, what changed in the most recent working session, and what's
honestly still missing. Read `README.md` first for the human-facing pitch and
the Safety section — this file is the engineering map underneath it.

## What Miso is

A desktop pet (Windows, PySide6) driven by a local LLM (Ollama, `qwen3:8b`),
not a chatbot skin. She has drives that persist and decay over real time, a
memory system that writes a daily journal and rewrites her own self-summary
while "asleep," and a filesystem sandbox (`jail.py`) that is the only way
anything in the app touches disk. The core design principle, stated in the
README and worth re-reading before changing anything: **safety rules here are
structural, not advisory** — they're properties of the code, not wording in a
prompt.

## Module map

| Module | Owns |
|---|---|
| `jail.py` | Every disk access. Virtual paths only (`/home`, `/world/...`). No delete function exists anywhere in the file — discarding means moving to `/home/compost`. Audits every access (`_log()`) to `logs/actions.log`, outside Miso's own reach. 57 tests in `test_jail.py`. |
| `config.py` | The world map: `MOUNTS` (virtual → real path), `WALLED_NAMES`/`WALLED_SUFFIXES` (credential-shaped things), `WALLED_WINDOW_KEYWORDS` (same idea for window titles, see `eyes.py`), size caps. |
| `drives.py` | `Drives` dataclass — curiosity, boredom, loneliness, energy, resignation. Ticks based on real elapsed time, asymptotic approach to ceiling, persists to `state/drives.json`. Plain, standalone, no LLM dependency. |
| `needs.py` | Same pattern as `drives.py`, for hunger/thirst — drives her home when unmet. |
| `memory.py` | `remember(kind, text)` — `kind` is `said | heard | saw | did | felt`. Appends JSONL to `/home/memories/`, journal to `/home/journal/`, rewrites `/home/who-i-am.md` and `/home/map-of-the-world.md` only during the nightly dream. Everything here routes through `jail.*`. |
| `mind.py` | The turn loop. `turn(drives, occasion, heard, interrupted)` builds a prompt (`system_prompt()`), calls the model with tools, dispatches tool calls via `_perform()`, returns `{"speech": [...], "acts": [...], "napped": int}`. `occasion` is a plain opaque string — the general-purpose hook for injecting situational context into a turn (see eyes.py's usage). `chat()` is a separate, faster, tool-free path for instant replies. |
| `brain.py` | Stdlib-only Ollama client. `think()`/`small_think()` for the text model (`MODEL = "qwen3:8b"`), `see()` for the vision model (`VISION_MODEL = "moondream"`, added this session). No client library, no network past localhost. |
| `reflex.py` | Instant, model-free pattern-matched reactions to what's heard (`<1ms`). Fires before any model call. |
| `body.py` | The heartbeat (`Miso.run()`, its own thread). Ticks drives, computes an `urge`, rate-limits and dispatches turns via `_act()`. `OCCASIONS` dict maps urge → prompt string. This is where new autonomous behaviors get wired in (see `_glance()`/`look_at_screen` for the pattern). |
| `senses.py` | Idle time, "is someone there," the `PAUSE` kill-switch, time of day. All Windows-specific calls wrapped in `try/except (AttributeError, OSError): return <safe default>` — the template every other OS-specific module follows. |
| `eyes.py` | **New this session.** Screen vision — see "Screen vision" below. |
| `ears.py` | Push-to-talk transcription (optional, mic). |
| `voice.py` | TTS (Kokoro if models are present, else Windows SAPI). Optional everywhere. |
| `antics.py` | Pure-code 60fps physics/movement — position, velocity, gravity, which "antic" she's doing (sit/wander/chase/pounce/spin/hop/...) and what pose that maps to. Never touches the model. |
| `face.py` | The rendered widget (`Cat`, `PetWindow`). Picks a pixel-art frame per tick based on pose/walking/blink/mood/held/airborne state, composites it, applies transforms (stretch, squash, wobble, sway). See "Pixel art" below. |
| `house.py` / `home.py` | Her room — a separate full-screen window, not a real virtual desktop (Windows offers no supported API for those). |
| `pet.py` | Entry point that wires all of the above together with Qt. `run.py` is the console-only alternative (no body/physics, text or `--voice`). |

## Safety model (do not weaken without explicit user sign-off)

- **Delete does not exist** in `jail.py`. Not blocked — absent.
- **Virtual paths only.** Miso cannot construct a real path from anything she says.
- **World is read-only** outside `/home` (`WRITABLE_ROOTS = ("/home",)`).
- **Walls**: credential-shaped file names/suffixes, and now credential-shaped
  *window titles* (`config.WALLED_WINDOW_KEYWORDS`, checked by
  `eyes.is_walled_title()`) return a wall, not an error.
- **Caps**: read/write/listing sizes, home quota, turns-per-hour
  (`MAX_TURNS_PER_HOUR = 24` in `body.py`), and now a separate, tighter
  vision cap (`MAX_VISION_PER_HOUR = 3`, `MIN_GAP_BETWEEN_VISION = 1200`).
- **Audit**: every jail access, and now every vision glance, logged to
  `logs/actions.log` via a private `_log()` — `eyes._log()` is a deliberate
  duplicate of `jail._log()`, not a shared export, so `jail.py`'s audited
  surface stays exactly what it was.
- **Kill switch**: a `PAUSE` file next to the code.

If you're asked to extend what Miso can perceive or do, follow this shape:
new sense/capability → its own module (not jammed into `jail.py`) → its own
rate limit → its own audit-log call → explicit, narrow, and mentioned in this
file.

## What changed in the most recent session (chronological, so the "why" is traceable)

Started as: realistic-illustrated-cat rendering (a cutout of a user-supplied
reference photo). Pivoted hard to **pixel art** after the user referenced a
specific style (a published app called "Comnyang") — the realistic-image
version was discarded entirely; nothing from that phase remains.

1. **Pixel-art rendering pipeline** — `tools/pixelcat/` (see below). Original
   scope: idle/walk/sleep frames, hand-authored via a coarse-grid generator
   since no image-gen tool was available in that session.
2. **4 skins** — cream tabby, orange tabby, gray mackerel, tuxedo. Same
   frame set, different palette (`gen.py:PALETTES`).
3. **Core physics** — eye-follow (opt-in, off by default —
   `Cat.eye_follow_enabled`), mochi-drag-turned-realistic-hold (see below),
   shake-wobble, mouse-hunt (this one already existed in `antics.py` before
   any of this session's work — verified, not built).
4. **Behavior fixes** — the walk cycle used to have two "dead" frames with
   zero leg asymmetry (read as gliding); jump had no anticipation and used
   the sitting-idle sprite mid-air (no `jump_0` frame existed); `spin`
   rotated the whole sprite at 900°/s (looked like a spinning coin, not a
   cat); `hop` was over-selected (in both the main playful pool and the
   bored+energetic mood branch). All fixed in `antics.py`/`face.py` — see
   the inline comments at each site, they explain the specific bug.
5. **Mood frames + talk-sync + memory-visibility** — curious/happy/lonely/
   bored now have real distinct frames tied to `_pose_name` (previously all
   four fell back to plain idle). Talking flaps the mouth on a **fixed
   timer**, not real audio amplitude — `voice.py`'s Kokoro backend has the
   raw samples available before playback, so true amplitude-driven lip-sync
   is possible, but needs new cross-thread plumbing that was never built or
   tested. Memory acts (`write_in_journal`, `carry_home`) now trigger a
   visible `perk` antic via `pet.py`'s `on_act`, not just a thought bubble.
6. **Screen vision** (`eyes.py`, `brain.see()`, `body.py._glance()`) — see
   below, planned via a written plan file
   (`.claude/plans/peppy-sniffing-book.md`) before implementation, since it's
   the one capability in this session that's a genuine departure from "she
   only sees a few mounted folders."
7. **Realism pass** — held pose (legs actually dangle, tail hangs and swings
   instead of curling, rotation pivots near the shoulders like an actually-
   gripped cat, not the paws), curled sleep silhouette (`sleep_curl()`, a
   genuinely different function from the sitting-pose rig — real cats don't
   sleep sitting-up-with-eyes-shut), jump crouch anticipation, reduced jump
   frequency.

### Explicitly not done — don't assume these exist

- **Real audio-amplitude lip sync.** Currently a fixed-cadence sine wave.
- **Walk vs. run as distinct gaits.** Ground speed currently only changes
  the cycle *rate* of the same 4 walk frames, not the silhouette.
- **A drinking-water animation.** Never built.
- **A path to the `bored` mood pose.** The frame and `_pose_name` handling
  exist (`mood_bored.png`, `MOOD_FRAMES` in `face.py`), but nothing in
  `antics.py`'s `mood_antic()`/`POSE_FOR` ever selects it — flagged to the
  user as a personality-tuning decision, not silently wired up, since
  `mood_antic()`'s existing thresholds read as deliberate.
- **Keyboard-reactive features** (kneading, "overheat" on fast typing),
  petting/purring, reminders/timers, Pomodoro, name personalization. Scoped
  out of every pass so far as a separate, larger batch (needs a global
  keyboard hook + OS permission grant, which nothing in this repo does yet).
- **Multi-window enumeration, browser-tab-level tracking, dedicated OCR** —
  see eyes.py's non-goals below.

## Pixel art pipeline (`tools/pixelcat/`)

Not a runtime dependency — a **build step**. Run to regenerate or extend:

```
python3 tools/pixelcat/generate.py
```

- `gen.py` — grid primitives (`new_grid`, `rect`, `px`, `render`) and
  `PALETTES` (the skins). `PX = 3` (block size), `GW, GH = 34, 42` (grid
  size) — chosen after an earlier, lower-resolution pass (`20x24`) proved too
  coarse for the requested detail level.
- `frames.py` — the actual drawing code. `base_cat(...)` is the sitting/
  standing rig (idle, walk, jump, held, moods, talk — everything except
  sleep). `sleep_curl(...)` is a separate function for the curled sleeping
  silhouette. `eye_overlay(...)` renders just the movable iris for the live
  eye-follow composite. Shading is flat top/bottom banding
  (`blob_banded()`), not a directional-light gradient — an earlier attempt
  at that produced boxy per-cell artifacts that read as dirt, not volume;
  documented in the file's own docstring so nobody re-tries it blind.
- `generate.py` — `SPECS` (base_cat frames) + `SLEEP_SPECS` (sleep_curl
  frames), one dict entry per frame per skin. Add a frame here and re-run;
  add a skin by adding one palette to `gen.py:PALETTES` and everything
  regenerates for it automatically.

Output lands in `miso/assets/pixel/<skin>/<frame>.png` — those PNGs *are*
committed (they're small, ~1-2KB each, ~300KB total for all 4 skins); the
generator is the source of truth if you need to change how they look.

`face.py`'s `_frame_name(t)` is the single place that decides which frame
name is current, in priority order: held → airborne → sleep → walking →
talking → mood → idle. If you add a new frame/state, it plugs in there.

## Screen vision (`eyes.py`)

Added deliberately narrow, after explicitly telling the user this is a
different category of capability from everything else (window/screen
content is far more sensitive than file access) and getting an explicit,
informed choice on scope. Full plan is preserved at
`.claude/plans/peppy-sniffing-book.md` if you need the reasoning, not just
the result.

- **Foreground window only**, once every 20+ minutes, max 3/hour
  (`MIN_GAP_BETWEEN_VISION`, `MAX_VISION_PER_HOUR` in `body.py`). Not a
  model-invokable tool — decided externally by `body.py`, like `find_you`,
  specifically so the model can't fire it repeatedly in one turn.
- Captured via Win32 `PrintWindow`/`GetDIBits` + Pillow. **The single
  highest-risk unverified detail in this whole session**: this was never
  run on real Windows (no Windows machine in the building session). DIB row
  order and BGRA-vs-RGB channel order are classic GDI mistakes — before
  trusting `brain.see()`'s output on a real machine, save one captured PNG
  to disk and look at it.
- `WALLED_WINDOW_KEYWORDS` in `config.py` — a recommended-not-imposed wall
  for password managers/banks/wallets. One line to empty for zero
  restriction; the user was told exactly that tradeoff.
- Feeds into `mind.turn()` via the existing `occasion` string mechanism —
  zero changes to `mind.py`'s function signatures — and into memory via
  `memory.remember("saw", ...)`, a `kind` that was already anticipated in
  `memory.py`'s own docstring but unused before this.
- **Non-goals, explicit**: multi-window enumeration, browser-extension tab
  tracking (a focused Chrome window's screenshot + its window title already
  covers "what site" without new integration surface), dedicated OCR,
  continuous/always-on capture, DRM/fullscreen capture (known `PrintWindow`
  limitation, not worked around).
- `pet.py` now wires `voice.py` behind `--voice` (it never did before, at
  all — found while checking whether vision-triggered speech would actually
  be audible; unrelated to vision itself but was a real, silent gap).

## Testing

```
python3 test_jail.py    # 57 checks, the safety sandbox
python3 test_mind.py    # 10 checks, the turn loop with a scripted fake model
python3 test_eyes.py    # 21 checks, vision — wall heuristic, brain.see()'s
                         # payload shape, rate limiting, _glance() end to end,
                         # everything faked (no Windows/Ollama needed)
```

All three run and pass on macOS with no Ollama and no display — they're
designed to, following `test_jail.py`'s original pattern of a plain
`check(label, cond)` counter and monkeypatched fakes rather than a test
framework or a mocking library.

**What can't be verified without the user's real Windows machine + Ollama +
a pulled vision model**: actual screen-capture pixel correctness, real
vision-model description quality/latency, model-swap behavior when Ollama
juggles `qwen3:8b` and the vision model, and whether the full app (`pet.py`)
actually runs end to end — this whole session worked from a macOS sandbox
with no Ollama installed, verifying everything else (rendering, physics,
turn-loop logic, safety) through direct widget rendering, `py_compile`, and
the test suites above.

## Platform notes

The app targets **Windows** (`winreg`, `ctypes.windll`, `.bat` launchers).
Every Windows-only call is wrapped in the `try/except (AttributeError,
OSError): return <safe default>` pattern established in `senses.py` — this
is why the whole thing imports and runs cleanly on macOS/Linux for
development, even though it doesn't *do* anything platform-specific there.
There's still no `requirements.txt`/`pyproject.toml` in this repo — every
dependency (PySide6, keyboard, numpy, sounddevice, faster_whisper,
kokoro_onnx, Pillow) is an unlisted import. Adding one more is normal
practice here, not a new category of change, but a real gap worth closing
eventually.
