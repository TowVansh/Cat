"""What Miso does before she thinks.

A pet does not compose a reply. It reacts, immediately, and the thought (if any)
catches up a second later. Everything here is pure code -- no model, no GPU, no
waiting. It fires in under a millisecond so that the moment you hit enter,
something happens.

The model still answers afterwards when it has something to add. This is the
flinch, not the conversation.
"""
from __future__ import annotations

import random
import re

# ------------------------------------------------------------ recognitions

GREETING = re.compile(r"\b(hi+|hey+|hello+|yo+|sup|hai|helo+|miso|meso)\b", re.I)
NAME_CALL = re.compile(r"\b(miso|meso|mesooo+|kitty|cat|kitten|puss)\b", re.I)
PRAISE = re.compile(r"\b(good|clever|cute|sweet|pretty|nice|love|adorable|best)\b", re.I)
SCOLD = re.compile(r"\b(bad|stupid|dumb|stop|no|shut ?up|annoying|ugly)\b", re.I)
QUESTION = re.compile(r"\?\s*$|^\s*(what|who|where|why|how|when|are|do|did|can|is)\b", re.I)
PLAY = re.compile(r"\b(play|game|fetch|chase|catch|toy|fun|dance|jump|spin)\b", re.I)
FOOD = re.compile(r"\b(food|eat|hungry|fish|treat|snack|milk|dinner)\b", re.I)
SLEEP = re.compile(r"\b(sleep|tired|bed|nap|night|goodnight|gn)\b", re.I)
BYE = re.compile(r"\b(bye|goodbye|later|cya|see you|leaving|going)\b", re.I)
SORRY = re.compile(r"\b(sorry|apolog|forgive)\b", re.I)
LOVE = re.compile(r"\b(love you|luv u|ily|miss you)\b", re.I)

# ---------------------------------------------------------------- reactions
# (lines, the antic it triggers, whether the model should still reply)

REACTIONS = [
    (LOVE,    ["!!", "oh", "mrrp", "..."],                       "spin",   True),
    (PLAY,    ["yes", "!!", "ok ok ok", "mrrp!"],                "zoomies", False),
    (FOOD,    ["where", "!!", "i want it", "is it for me"],      "pounce", True),
    (SLEEP,   ["mm", "ok", "...", "sleepy"],                     "settle", False),
    (BYE,     ["oh", "wait", "...", "hm"],                       "watch",  True),
    (SORRY,   ["ok", "mm", "it is fine"],                        "sit",    False),
    (PRAISE,  ["mrrp", "!", "i know", "hehe", "..."],            "wiggle", False),
    (SCOLD,   ["...", "hmph", "oh", "mm"],                       "shrink", False),
    (GREETING,["hi", "oh! hi", "mrrp", "hello", "you"],          "perk",   True),
    (NAME_CALL,["hm?", "yes?", "what", "mm?"],                   "perk",   True),
]

# said while the model is still thinking, when nothing else matched
FILLER = ["hm", "mm", "...", "oh", "?", "hm?", "mrr"]

# said when Miso is asked something and has not answered yet
THINKING_NOISE = ["hm", "...", "let me look", "mm", "wait"]


def react(heard: str) -> tuple[str, str, bool]:
    """Return (line, antic, let_the_model_speak_too) for something just said.

    Instant. Never touches the model.
    """
    text = heard.strip()

    for pattern, lines, antic, defer in REACTIONS:
        if pattern.search(text):
            return random.choice(lines), antic, defer

    if QUESTION.search(text):
        return random.choice(THINKING_NOISE), "perk", True

    if len(text) > 90:                     # a wall of words at a small creature
        return random.choice(["that is a lot", "mm", "..."]), "tilt", True

    return random.choice(FILLER), "perk", True


def idle_noise() -> str:
    """Something small to say for no reason at all."""
    return random.choice([
        "mrrp", "...", "hm", "*yawn*", "oh", "mm", "hup",
    ])
