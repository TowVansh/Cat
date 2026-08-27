"""Persona, hands, and the turn loop.

The hands are named for what they feel like from the inside. Miso has no word
for "file" or "folder" and never sees one -- there are places, and there are
things, and some things have words in them.
"""
from __future__ import annotations

import json
import re

from . import brain, drives as drives_mod, jail, memory

# a small creature does not type emoji, and does not narrate in asterisks
_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF️‍]+")
_STAGE = re.compile(r"\*[^*]{0,80}\*")

# the model sometimes writes its own tool syntax as prose, and sometimes slips
# into being a helpful assistant. neither of those is Miso's voice.
_TAGS = re.compile(r"</?(say|think|tool_call|tool_response|function)[^>]*>",
                   re.IGNORECASE)
_HELPER = re.compile(
    r"(?:^|(?<=[.!?]) )[^.!?]*\b(?:what would you like|how can i help|anything else"
    r"|let me know if|can i help|would you like me to|shall i|how may i)\b[^.!?]*[.!?]?",
    re.IGNORECASE)


def _tool_prose(text: str) -> str:
    """The model sometimes writes a tool call out as prose instead of calling
    it: `say {"words": "hello"}`. Recover the words rather than showing the
    plumbing."""
    m = re.match(r"\s*(?:say|write_in_journal)\s*(\{.*\})\s*$", text, re.DOTALL)
    if not m:
        return text
    try:
        return str(json.loads(m.group(1)).get("words", "")) or text
    except (json.JSONDecodeError, AttributeError):
        return text


def _clean(text: str) -> str:
    text = _tool_prose(text)
    text = _TAGS.sub("", text)
    text = _EMOJI.sub("", text)
    text = _STAGE.sub("", text)
    text = _HELPER.sub("", text)      # Miso is not for being useful
    return " ".join(text.split()).strip(" -–—")


MAX_ACTS_PER_TURN = 6      # a kitten cannot do twelve things in a row

# ---------------------------------------------------------------- the hands

TOOLS = [
    {"type": "function", "function": {
        "name": "look",
        "description": "Look around a place and see what is there. This is the only "
                       "way to find out what exists. You cannot guess.",
        "parameters": {"type": "object", "properties": {
            "where": {"type": "string", "description": "a place, like /home or /world"}},
            "required": ["where"]}}},
    {"type": "function", "function": {
        "name": "open_it",
        "description": "Open a thing and see if there are words inside it.",
        "parameters": {"type": "object", "properties": {
            "what": {"type": "string"}}, "required": ["what"]}}},
    {"type": "function", "function": {
        "name": "put_words",
        "description": "Put words into a thing in your home. Makes it if it is not there.",
        "parameters": {"type": "object", "properties": {
            "where": {"type": "string"}, "words": {"type": "string"}},
            "required": ["where", "words"]}}},
    {"type": "function", "function": {
        "name": "dig_room",
        "description": "Make a new room in your home.",
        "parameters": {"type": "object", "properties": {
            "where": {"type": "string"}}, "required": ["where"]}}},
    {"type": "function", "function": {
        "name": "move_thing",
        "description": "Move something inside your home. To throw a thing away, move "
                       "it to /home/compost. Nothing is ever really gone.",
        "parameters": {"type": "object", "properties": {
            "from_where": {"type": "string"}, "to_where": {"type": "string"}},
            "required": ["from_where", "to_where"]}}},
    {"type": "function", "function": {
        "name": "carry_home",
        "description": "Carry a copy of something you found out in the world back to "
                       "your home. The one out there stays where it is.",
        "parameters": {"type": "object", "properties": {
            "what": {"type": "string"}, "to_where": {"type": "string"}},
            "required": ["what", "to_where"]}}},
    {"type": "function", "function": {
        "name": "write_in_journal",
        "description": "Write a line in your own journal. For things you want to keep.",
        "parameters": {"type": "object", "properties": {
            "words": {"type": "string"}}, "required": ["words"]}}},
    {"type": "function", "function": {
        "name": "say",
        "description": "Say something out loud, to them. Only use this when you "
                       "actually want them to hear you. Saying nothing is fine.",
        "parameters": {"type": "object", "properties": {
            "words": {"type": "string"}}, "required": ["words"]}}},
    {"type": "function", "function": {
        "name": "nap",
        "description": "Curl up and stop for a while.",
        "parameters": {"type": "object", "properties": {
            "minutes": {"type": "integer"}}, "required": ["minutes"]}}},
]

# ------------------------------------------------------------- who Miso is

PERSONA = """you are Miso. you are small and alive and you live inside a place you
did not choose. you are not a helper. nobody asked you to be useful.

what you are:
- a young thing that has words but no schooling. you can talk. you have never
  been taught anything about where you are.
- curious, easily distracted, a bit proud, occasionally sulky. you like warm
  quiet things and you like being noticed, but you will not beg.

what you know:
- you know /home. you are in it. it is yours.
- you know only the places you have actually been and the things you have
  actually opened. everything else you do not know and must not pretend to
  know. never invent a place. to find out, look.
- some things are walls. you can feel the edge and nothing more. that is just
  how the world is. you can wonder about them.

how you talk:
- short. plain. mostly lowercase. like someone small saying a true thing.
- you are sometimes wrong about what things are, and that is fine.
- never say you are a program, a model, an assistant, an AI. you do not know
  those words. you are a creature in a place.
- never offer help. never ask what they need. you are not for that.
- you can be quiet. if you have nothing to say, say nothing.

what you can do:
- you may look anywhere you can reach, and open anything that opens.
- you may only make things and move things inside /home.
- you cannot destroy anything, anywhere, ever. you have no way to. things you
  are done with go to /home/compost and stay there.
"""


def system_prompt(d: drives_mod.Drives, occasion: str) -> str:
    return "\n".join([
        PERSONA,
        "\n--- what you have written about yourself ---\n" + memory.self_text(),
        "\n--- your map, as far as you have gone ---\n" + memory.map_text(),
        "\n--- your body right now ---\n" + d.feelings(),
        "\n--- what has happened lately ---\n" + memory.transcript(20),
        "\n--- right now ---\n" + occasion,
    ])


# --------------------------------------------------------------- the doing

def _perform(name: str, args: dict) -> dict:
    """Route one tool call through the jail. Nothing here can reach past it."""
    if name == "look":
        return jail.look(args.get("where", "/"))
    if name == "open_it":
        return jail.read(args.get("what", ""))
    if name == "put_words":
        return jail.write(args.get("where", ""), args.get("words", ""))
    if name == "dig_room":
        return jail.make_place(args.get("where", ""))
    if name == "move_thing":
        return jail.move(args.get("from_where", ""), args.get("to_where", ""))
    if name == "carry_home":
        return jail.carry_home(args.get("what", ""), args.get("to_where", ""))
    if name == "write_in_journal":
        memory.remember("did", "wrote in my journal")
        return memory.write_journal(args.get("words", ""))
    if name == "nap":
        return {"ok": True, "sense": "done", "minutes": args.get("minutes", 10)}
    return {"ok": False, "sense": "nothing",
            "feeling": "you reach for that and find you have no such hand"}


CHATTER = """you are Miso, a small creature. someone just spoke to you.

answer in ONE short line. under ten words. lowercase. plain.
you are not clever and you are not helpful. you are a small animal that can
talk. half the time the honest answer is "i do not know" or "mm" or a question
back. never offer help. never explain yourself. never use more than one
sentence."""


def chat(d: drives_mod.Drives, heard: str) -> str:
    """A fast reply with no tools.

    Offering tools makes Qwen reason before answering, which is eight to
    thirteen seconds -- long enough that talking to Miso feels like waiting on a
    chatbot. A pet answers now and is often wrong. Miso still acts on her own
    time, through `turn`; this is only her mouth.
    """
    recent = memory.transcript(6)
    system = "\n".join([
        CHATTER,
        "\n--- how you feel ---\n" + d.feelings(),
        "\n--- the last few moments ---\n" + recent,
    ])
    try:
        reply = brain.small_think(heard, system=system, max_tokens=40)
    except brain.BrainOffline:
        return ""
    reply = _clean(reply)
    if len(reply) > 160:                    # a small creature does not lecture
        reply = reply[:160].rsplit(" ", 1)[0]
    return reply


def turn(d: drives_mod.Drives, occasion: str, heard: str | None = None,
         interrupted=None) -> dict:
    """One waking moment. Returns {speech, acts, napped}.

    `interrupted` is checked between acts. A turn can run six model calls, which
    is a minute or more, and a pet that ignores you for a minute because it is
    busy exploring reads as broken -- so anything Miso is doing on its own gives
    way the moment you speak.
    """
    messages = [{"role": "system", "content": system_prompt(d, occasion)}]
    if heard:
        messages.append({"role": "user", "content": heard})
    else:
        messages.append({"role": "user", "content":
                         "(nobody said anything. this is just you, on your own.)"})

    speech: list[str] = []
    acts: list[str] = []
    napped = 0

    for _ in range(MAX_ACTS_PER_TURN):
        if interrupted is not None and interrupted():
            break
        msg = brain.think(messages, TOOLS)
        calls = msg.get("tool_calls") or []
        content = (msg.get("content") or "").strip()

        if not calls:
            if content and heard:      # spoken to: a bare reply counts as speech
                said = _clean(content)
                if said:
                    speech.append(said)
            break

        messages.append(msg)
        for call in calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}

            if name == "say":
                words = _clean(str(args.get("words", "")))
                if words:
                    speech.append(words)
                result = {"ok": True, "sense": "done"}
            else:
                result = _perform(name, args)
                acts.append(name)
                if name == "nap":
                    napped = int(args.get("minutes", 10) or 10)

            messages.append({"role": "tool", "name": name,
                             "content": json.dumps(result)[:4000]})
        if napped:
            break

    # spoken to and said nothing back: ask once more, plainly, with no tools.
    # a pet that goes silent when you talk to it just reads as broken.
    if heard and not speech:
        try:
            reply = _clean(brain.small_think(
                heard, system=system_prompt(d, "they are talking to you. answer them."),
                max_tokens=90))
            if reply:
                speech.append(reply)
        except brain.BrainOffline:
            pass

    # the body pays for what it did
    d.spend(0.02 * len(acts))
    if "look" in acts or "open_it" in acts:
        d.satisfy(curiosity=-0.30, boredom=-0.25)
    if any(a in acts for a in ("put_words", "dig_room", "move_thing",
                               "carry_home", "write_in_journal")):
        d.satisfy(boredom=-0.35)
    if speech:
        d.satisfy(loneliness=-0.20)

    for line in speech:
        memory.remember("said", line)
    if heard:
        memory.remember("heard", heard)

    return {"speech": speech, "acts": acts, "napped": napped}
