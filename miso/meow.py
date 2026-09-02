"""How Miso talks.

She does not speak English. She never has. What comes out of her is cat noise,
and the bracketed line above it is your translation of what she probably meant
-- the way you decide what your own cat is on about. She is not choosing those
words; you are.

So the noise is synthesised from the meaning rather than stored beside it. A
long complaint makes a long noise, an urgent want makes a sharper one, and a
sleepy remark trails off. Same want twice in a row will not give you the same
string of syllables.

Nothing here touches the model. This is a phrase bank and a syllable
generator, which is all a pet's vocabulary has ever needed to be.
"""
from __future__ import annotations

import random

# --------------------------------------------------------------- her moods
# Each mood is a different set of noises and a different way of ending them.

VOICES = {
    "urgent":  dict(syl=["meow", "mrow", "meoow", "mrrow", "mew", "meow"],
                    end=["!", "!", "!!", ""], stretch=0.35),
    "sleepy":  dict(syl=["mrr", "mmm", "mrrr", "mew", "mrp", "mm"],
                    end=["...", "...", "", ".."], stretch=0.55),
    "pleased": dict(syl=["mrrp", "purr", "prrp", "mew", "nya", "mrrp"],
                    end=["", "!", "~", ""], stretch=0.25),
    "sulky":   dict(syl=["mrow", "mrf", "mm", "hmf", "mrr"],
                    end=[".", "...", "", "."], stretch=0.15),
    "curious": dict(syl=["mrrp", "mew", "mrr", "nya", "meo"],
                    end=["?", "?", "", "?!"], stretch=0.30),
    "plain":   dict(syl=["meow", "meo", "mew", "mrrp", "mrr", "mao"],
                    end=["", "", ".", "~"], stretch=0.30),
}

# every syllable any voice can produce -- the tests assert nothing outside this
# set ever reaches the spoken line
ALL_SYLLABLES = {s for v in VOICES.values() for s in v["syl"]}


# ------------------------------------------------------------- what she means
# intent -> (voice, [ways of putting it])

MEANINGS: dict[str, tuple[str, list[str]]] = {
    "hungry": ("urgent", [
        "i wanna eat i am hungry",
        "food. food now",
        "my stomach is empty and this is your problem",
        "i have not eaten in forever",
    ]),
    "thirsty": ("urgent", [
        "i want water",
        "the water. i need the water",
        "thirsty. very thirsty",
    ]),
    "bowl_empty": ("sulky", [
        "my bowl is empty and nobody has noticed",
        "there is nothing in the bowl",
        "the bowl. look at the bowl",
    ]),
    "want_play": ("urgent", [
        "i wanna play",
        "play with me. now",
        "come on. come on come on",
        "i am extremely bored and you are just sitting there",
    ]),
    "want_attention": ("plain", [
        "look at me",
        "i am here you know",
        "hello. i exist",
        "you have not looked at me in ages",
    ]),
    "bored": ("sulky", [
        "nothing here is interesting",
        "i have looked at everything already",
        "ugh",
        "there is nothing to do in this place",
    ]),
    "sleepy": ("sleepy", [
        "i am going to sleep now",
        "tired",
        "everything is warm and i am done",
        "mm. bed",
    ]),
    "annoyed": ("sulky", [
        "no",
        "do not",
        "i did not like that",
        "hmph",
    ]),
    "curious": ("curious", [
        "what is that",
        "hm. what is this",
        "there is something over here",
        "i have not seen this before",
    ]),
    "found_thing": ("pleased", [
        "look what i found",
        "i took this. it is mine now",
        "this was lying around so i have it now",
    ]),
    "going_home": ("plain", [
        "i am going home",
        "back soon. maybe",
        "going in",
    ]),
    "arrived_home": ("pleased", [
        "home",
        "ah. my room",
        "this is mine",
    ]),
    "held": ("urgent", [
        "put me down",
        "no no no no",
        "i did not agree to this",
        "down. down",
    ]),
    "put_down": ("sulky", [
        "finally",
        "never do that again",
        "hmph",
    ]),
    "ignored_you": ("sulky", [
        "no",
        "i heard you. i am not doing it",
        "make me",
        "later. maybe",
        "and why would i do that",
    ]),
    "get_off_that": ("urgent", [
        "you have been staring at that for hours",
        "stop looking at that and look at me",
        "enough. play with me",
        "that thing is not more interesting than me",
    ]),
    "pleased": ("pleased", [
        "good",
        "yes. this",
        "i like this",
        "mm",
    ]),
    "greeting": ("plain", [
        "oh. you",
        "hello",
        "there you are",
    ]),
    "fed": ("pleased", [
        "finally. thank you",
        "yes. this is what i wanted",
        "acceptable",
    ]),
}


# ------------------------------------------------------------ making a noise

def _noise(translation: str, voice_name: str, rng: random.Random) -> str:
    """Build the actual cat noise for a piece of meaning.

    Length follows the meaning: a four-word want is a short noise, a rambling
    complaint is a long one, so the two lines feel like the same utterance
    rather than a caption stuck onto a stock sound.
    """
    voice = VOICES.get(voice_name, VOICES["plain"])
    words = max(1, len(translation.split()))
    count = max(2, min(8, round(words * 0.7)))

    parts = []
    for i in range(count):
        syl = rng.choice(voice["syl"])
        # occasionally draw a vowel out, the way a real one does mid-sentence
        if rng.random() < voice["stretch"] and "e" in syl:
            syl = syl.replace("e", "ee", 1)
        parts.append(syl)

    return " ".join(parts) + rng.choice(voice["end"])


def say(intent: str, seed: int | None = None) -> tuple[str, str]:
    """(noise, translation) for something she wants to get across.

    An unknown intent is not an error -- she just says something non-committal,
    because a cat has no failure mode.
    """
    rng = random.Random(seed)
    voice, options = MEANINGS.get(intent, ("plain", ["hm"]))
    translation = rng.choice(options)
    return _noise(translation, voice, rng), translation


def just_noise(voice: str = "plain", seed: int | None = None) -> tuple[str, str]:
    """A small sound with no particular meaning behind it. The translation is
    empty, so nothing is put in her mouth that she did not mean."""
    rng = random.Random(seed)
    return _noise("mm mm", voice, rng), ""


def idle_noise() -> tuple[str, str]:
    """Something to say for no reason at all."""
    return just_noise(random.choice(["plain", "sleepy", "pleased"]))
