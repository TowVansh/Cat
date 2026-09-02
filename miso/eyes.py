"""What Miso can see, when she glances at the screen.

A different kind of sense from jail.py's: not path-addressed, not writable,
no compost -- just a rare, cooldown-gated look at whatever window has focus.
Follows senses.py's pattern for anything Windows-only: wrapped in a broad
try/except that returns a safe default (None) rather than raising, so this
degrades cleanly off Windows and on any capture failure alike.

Audited the same way jail.py audits everything, through its own private
_log() -- deliberately not exposing jail._log() publicly, so jail.py's
audited surface (filesystem access) stays exactly what it already is.
"""
from __future__ import annotations

import ctypes
import io
import json
from datetime import datetime, timezone

from . import config

try:
    from PIL import Image
except ImportError:                      # Pillow not installed
    Image = None


def _log(action: str, subject: str, outcome: str, extra: str = "") -> None:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    line = json.dumps(
        {"t": stamp, "action": action, "path": subject, "outcome": outcome, "extra": extra}
    )
    with (config.LOG_DIR / "actions.log").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def is_walled_title(title: str) -> bool:
    """A window whose title suggests something credential-shaped -- a
    password manager, a bank, a wallet. Pure string check, no OS call, so
    it's testable everywhere. Empty config.WALLED_WINDOW_KEYWORDS for no
    restriction at all."""
    low = title.lower()
    return any(kw in low for kw in config.WALLED_WINDOW_KEYWORDS)


def foreground_window() -> tuple[int, str] | None:
    """(hwnd, title) of whatever window currently has focus, or None on any
    failure -- including simply not being on Windows."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return hwnd, buf.value
    except (AttributeError, OSError):
        return None


def capture_foreground() -> bytes | None:
    """PNG bytes of the foreground window, or None if there's nothing to
    capture, the window is walled, or the capture itself fails for any
    reason (closed mid-shot, access denied, a renderer PrintWindow can't
    read -- all treated the same way: silently give up, nothing to see)."""
    fg = foreground_window()
    if fg is None:
        return None
    hwnd, title = fg

    if is_walled_title(title):
        _log("blocked", title, "wall", "window title")
        return None

    if Image is None:
        _log("look", title, "nothing", "Pillow not installed")
        return None

    try:
        png = _grab_window(hwnd)
    except Exception as exc:                       # noqa: BLE001 -- a failed
        _log("look", title, "nothing", str(exc)[:200])   # glance is not a crash
        return None

    if png is None:
        _log("look", title, "nothing", "blank capture")
        return None

    _log("look", title, "ok", f"{len(png)}b")
    return png


def _grab_window(hwnd: int) -> bytes | None:
    """The actual Win32 GDI capture: PrintWindow into a compatible bitmap,
    read it back with GetDIBits, hand the raw pixels to Pillow. PW_RENDER-
    FULLCONTENT (2) is needed for GetDIBits to see anything from GPU-
    composited windows (most modern apps, including Chrome) rather than a
    blank/black rectangle."""
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    if w <= 0 or h <= 0:
        return None

    hwnd_dc = user32.GetWindowDC(hwnd)
    mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
    gdi32.SelectObject(mem_dc, bitmap)

    PW_RENDERFULLCONTENT = 2
    ok = user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)

    buf = None
    if ok:
        bmi = _bitmapinfo(w, h)
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(mem_dc, bitmap, 0, h, buf, ctypes.byref(bmi), 0)

    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(hwnd, hwnd_dc)

    if not ok or buf is None:
        return None

    img = Image.frombuffer("RGBA", (w, h), buf.raw, "raw", "BGRA", 0, 1).convert("RGB")
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _bitmapinfo(w: int, h: int):
    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
            ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
            ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
            ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
            ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
            ("biClrImportant", ctypes.c_uint32),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", ctypes.c_uint32 * 3)]

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h        # negative: top-down row order
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0    # BI_RGB
    return bmi
