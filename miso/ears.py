"""Push-to-talk. Hold the key, say something, let go.

Note on the key: a bare "v" cannot be the hotkey while you are also typing to
Miso in the same window -- every "v" you typed would start recording. The
default is alt+v. Change PTT_KEY in config.py to whatever you like
("right shift" and "right ctrl" both work well as bare keys).
"""
from __future__ import annotations

import threading
import time

PTT_KEY = "alt+v"
SAMPLE_RATE = 16000
MIN_SECONDS = 0.35
MAX_SECONDS = 30.0
WHISPER_SIZE = "base.en"


class Ears:
    def __init__(self, on_heard, on_note=None) -> None:
        self.on_heard = on_heard
        self.on_note = on_note or (lambda s: None)
        self._model = None
        self._stop = threading.Event()

        import sounddevice as sd            # noqa: F401  (fail fast if missing)
        import keyboard                     # noqa: F401
        self._sd = sd
        self._kb = keyboard

    # ------------------------------------------------------------- loading

    def _model_ready(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            try:
                self._model = WhisperModel(WHISPER_SIZE, device="cuda",
                                           compute_type="float16")
            except Exception:
                self._model = WhisperModel(WHISPER_SIZE, device="cpu",
                                           compute_type="int8")
        return self._model

    # ------------------------------------------------------------ the loop

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        import numpy as np
        while not self._stop.is_set():
            if not self._kb.is_pressed(PTT_KEY):
                time.sleep(0.03)
                continue

            frames: list = []
            started = time.time()
            with self._sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                                      dtype="float32") as stream:
                while self._kb.is_pressed(PTT_KEY):
                    if time.time() - started > MAX_SECONDS:
                        break
                    block, _ = stream.read(1024)
                    frames.append(block.copy())

            held = time.time() - started
            if held < MIN_SECONDS or not frames:
                continue

            audio = np.concatenate(frames, axis=0).flatten()
            self.on_note("(listening...)")
            try:
                model = self._model_ready()
                segments, _info = model.transcribe(
                    audio, language="en", beam_size=1, vad_filter=True)
                text = " ".join(s.text for s in segments).strip()
            except Exception as exc:
                self.on_note(f"(could not hear: {exc})")
                continue

            if text:
                self.on_heard(text)
