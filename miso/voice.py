"""Miso's voice.

Two backends, picked at startup:
  kokoro  -- small neural TTS, warm and natural, needs two model files
  sapi    -- the voice already built into Windows, no download, robotic

Voice is optional everywhere. If it fails, Miso is simply quiet on speakers and
still talks in text.
"""
from __future__ import annotations

import queue
import subprocess
import threading
from pathlib import Path

from . import config

MODEL_DIR = config.CODE_DIR / "models" / "kokoro"
KOKORO_MODEL = MODEL_DIR / "kokoro-v1.0.onnx"
KOKORO_VOICES = MODEL_DIR / "voices-v1.0.bin"

# a small bright voice suits a kitten
KOKORO_VOICE = "af_sky"
KOKORO_SPEED = 1.05


class Voice:
    def __init__(self) -> None:
        self.backend = "none"
        self._kokoro = None
        self._sd = None
        self._q: queue.Queue[str] = queue.Queue()

        if KOKORO_MODEL.exists() and KOKORO_VOICES.exists():
            try:
                from kokoro_onnx import Kokoro
                import sounddevice as sd
                self._kokoro = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
                self._sd = sd
                self.backend = "kokoro"
            except Exception:
                self._kokoro = None

        if self.backend == "none":
            self.backend = "sapi"

        threading.Thread(target=self._pump, daemon=True).start()
        threading.Thread(target=self._warm, daemon=True).start()

    def _warm(self) -> None:
        """Run one silent synthesis so the first thing Miso says is not slow."""
        if self.backend != "kokoro":
            return
        try:
            self._kokoro.create("mm", voice=KOKORO_VOICE, speed=KOKORO_SPEED,
                                lang="en-us")
        except Exception:
            pass

    # ------------------------------------------------------------ speaking

    def say(self, text: str) -> None:
        """Queue a line. Never blocks the caller."""
        text = text.strip()
        if text:
            self._q.put(text[:400])

    def _pump(self) -> None:
        while True:
            text = self._q.get()
            try:
                if self.backend == "kokoro":
                    self._say_kokoro(text)
                else:
                    self._say_sapi(text)
            except Exception:
                pass          # a silent pet is better than a crashed one

    def _say_kokoro(self, text: str) -> None:
        samples, rate = self._kokoro.create(
            text, voice=KOKORO_VOICE, speed=KOKORO_SPEED, lang="en-us")
        self._sd.play(samples, rate)
        self._sd.wait()

    def _say_sapi(self, text: str) -> None:
        safe = text.replace("'", "''")
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$s.Rate = 1; $s.Volume = 90; "
            f"$s.Speak('{safe}')"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, timeout=60,
        )


def kokoro_ready() -> bool:
    return KOKORO_MODEL.exists() and KOKORO_VOICES.exists()
