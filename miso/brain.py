"""The local model. Stdlib only -- no client library, no key, no network past
localhost.
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request

HOST = "http://127.0.0.1:11434"
MODEL = "qwen3:8b"
KEEP_ALIVE = "30m"      # hold the weights in VRAM between ticks

# a separate, smaller model for glancing at the screen -- kept apart from
# MODEL/KEEP_ALIVE so the text model's own VRAM residency is disturbed as
# little as possible by a capability that fires at most a few times an hour
VISION_MODEL = "moondream"
VISION_KEEP_ALIVE = "5m"

OPTIONS = {
    "temperature": 0.85,      # a pet should not be repeatable
    "top_p": 0.92,
    "repeat_penalty": 1.12,
    "num_ctx": 8192,
    "num_predict": 320,
}


class BrainOffline(Exception):
    pass


def _post(path: str, payload: dict, timeout: int = 120) -> dict:
    req = urllib.request.Request(
        HOST + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise BrainOffline(f"cannot reach ollama at {HOST}: {exc}") from exc


def awake() -> bool:
    try:
        req = urllib.request.Request(HOST + "/api/tags")
        with urllib.request.urlopen(req, timeout=5):
            return True
    except (urllib.error.URLError, OSError):
        return False


def installed_models() -> list[str]:
    try:
        req = urllib.request.Request(HOST + "/api/tags")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return [m["name"] for m in data.get("models", [])]
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return []


def think(messages: list[dict], tools: list[dict] | None = None,
          options: dict | None = None, reason: bool | None = None) -> dict:
    """One turn. Returns the assistant message: {content, tool_calls?}.

    Qwen3 only calls tools reliably with its reasoning mode on, so reasoning
    defaults to on whenever tools are offered. Ollama returns that reasoning in
    a separate `thinking` field, so it never reaches the speech bubble.
    """
    if reason is None:
        reason = bool(tools)
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "keep_alive": KEEP_ALIVE,
        "options": {**OPTIONS, **(options or {})},
        "think": reason,
    }
    if tools:
        payload["tools"] = tools
    data = _post("/api/chat", payload)
    msg = data.get("message", {"role": "assistant", "content": ""})
    msg.pop("thinking", None)         # the working-out is not Miso's voice
    return msg


def small_think(prompt: str, system: str = "", max_tokens: int = 120) -> str:
    """One cheap shot with no tools -- used for naps, summaries, and talking.

    Reasoning is off here. It is only needed to make tool calls reliable, and
    it costs several seconds that a conversation cannot afford.
    """
    msgs = ([{"role": "system", "content": system}] if system else [])
    msgs.append({"role": "user", "content": prompt})
    msg = think(msgs, options={"num_predict": max_tokens}, reason=False)
    return (msg.get("content") or "").strip()


def see(image_png: bytes, prompt: str, max_tokens: int = 200) -> str:
    """Describe an image with the vision model. A separate, one-off call --
    not routed through think(), since it needs a different model, a shorter
    keep_alive, and never offers tools."""
    payload = {
        "model": VISION_MODEL,
        "messages": [{
            "role": "user",
            "content": prompt,
            "images": [base64.b64encode(image_png).decode("ascii")],
        }],
        "stream": False,
        "keep_alive": VISION_KEEP_ALIVE,
        "options": {"num_predict": max_tokens},
        "think": False,
    }
    data = _post("/api/chat", payload)
    msg = data.get("message", {"content": ""})
    return (msg.get("content") or "").strip()
