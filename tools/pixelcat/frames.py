"""Miso's pixel-cat frame builder: a 34x42 grid for enough room for fur/eye/
toe detail. Shading is simple top-light/bottom-shadow banding, not a
directional-light gradient -- an earlier version tried that and the boxy
per-cell bands read as stray dark patches on the cheeks, not volume.

Run generate.py in this directory to (re)build the PNGs under
miso/assets/pixel/. Nothing here is imported by the running app -- it's a
build step, not a runtime dependency.
"""
import math
from gen import *


def blob_mask(cx, cy, rx, ry):
    cells = set()
    for y in range(GH):
        for x in range(GW):
            if ((x - cx + 0.5) / rx) ** 2 + ((y - cy + 0.5) / ry) ** 2 <= 1.0:
                cells.add((x, y))
    return cells

def blob_banded(g, cx, cy, rx, ry, hi, base, lo, lo_from=0.15):
    """Fill an ellipse: top ~55% = hi, next band = base, bottom = lo. Plain
    vertical banding reads cleanly as pixel-art shading at any resolution."""
    for (x, y) in blob_mask(cx, cy, rx, ry):
        ny = (y - cy + 0.5) / ry     # -1 (top) .. 1 (bottom)
        color = lo if ny > lo_from else (hi if ny < -0.25 else base)
        px(g, x, y, color)

def stripe(g, x, y, h, color, w=1):
    rect(g, x, y, w, h, color)


def eye_anchors(cx=17.0, hy=13.0):
    """Where each eye's white/iris sits, shared by base_cat (blank or full)
    and eye_overlay so they can never drift out of alignment."""
    ey = int(hy - 0.5)
    return ey, [(-1, int(cx - 4.6)), (1, int(cx + 2.6))]


def eye_overlay(palette, gaze=(0.0, 0.0), cx=17.0, hy=13.0):
    """Just the iris/pupil/highlight, transparent everywhere else, offset by
    a live gaze vector -- drawn on top of a base_cat(eyes='blank') frame so
    the eyes can track the cursor without redrawing the whole sprite."""
    BLUE, BLUE_HI = palette["BLUE"], palette["BLUE_HI"]
    g = new_grid()
    ey, sides = eye_anchors(cx, hy)
    gx, gy = round(gaze[0]), round(gaze[1])
    for side, ex in sides:
        iris_x = ex + (2 if side < 0 else 1) + gx
        iy = ey - 1 + gy
        rect(g, iris_x, iy, 2, 2, BLUE)
        px(g, iris_x, iy, BLUE_HI)
        px(g, iris_x + (0 if side < 0 else 1), iy + 1, INK)
    return g


def base_cat(leg_lift=(0, 0), tail_phase=0.0, eye_open=True, ear_a=0, bob=0.0,
             palette=None, eyes="full", eye_mode="open", mouth_curve=0,
             mouth_open=False, tail_mode="curl"):
    pal = palette or PALETTES["cream_tabby"]
    # shadow the module-level color names with this skin's colors for the
    # rest of this call, so the drawing code below stays skin-agnostic
    CREAM_LI, CREAM, CREAM_SH = pal["CREAM_LI"], pal["CREAM"], pal["CREAM_SH"]
    TABBY, TABBY_DK = pal["TABBY"], pal["TABBY_DK"]
    WHITE, WHITE_SH = pal["WHITE"], pal["WHITE_SH"]
    PINK, PINK_DK = pal["PINK"], pal["PINK_DK"]
    BLUE, BLUE_DK, BLUE_HI = pal["BLUE"], pal["BLUE_DK"], pal["BLUE_HI"]
    NOSE = pal["NOSE"]

    g = new_grid()
    b = bob * 1.6
    cx = 17.0
    hy = 13.0 - b
    by = 27.0 - b

    # ================= body =================
    body_r = (9.6, 8.4)
    body = blob_mask(cx, by, *body_r)
    blob_banded(g, cx, by, *body_r, CREAM_LI, CREAM, CREAM_SH)

    chest = blob_mask(cx, by + 3.6, 4.4, 5.2)
    for (x, y) in chest:
        px(g, x, y, WHITE if y < by + 7 else WHITE_SH)

    for (dx, top_dy, h) in [(-6, -6, 5), (-4.5, -8, 6), (4.5, -8, 6), (6, -6, 5),
                             (-2, -8.5, 4), (2, -8.5, 4)]:
        x, y = int(cx + dx), int(by + top_dy)
        if (x, y) in body:
            stripe(g, x, y, h, TABBY_DK, w=1)

    # ================= neck bridge =================
    rect(g, int(cx - 4), int(hy + 5), 8, 4, CREAM)

    # ================= tail =================
    if tail_mode == "hang":
        # held from above: the tail just hangs and swings, it doesn't curl
        offsets = [(0, i) for i in range(0, 13)]
        sway = math.sin(tail_phase) * 3.0
        hip = (int(cx + 2.5), int(by + 6))
    else:
        offsets = [(0, 0), (1, 0), (2, 0), (3, -1), (4, -2), (5, -3), (5, -4),
                   (5, -5), (4, -6), (4, -7), (3, -8), (3, -9), (2, -10), (2, -11)]
        sway = math.sin(tail_phase) * 2.2
        hip = (int(cx + 7.5), int(by - 1))
    prev = None
    for i, (dx, dy) in enumerate(offsets):
        s = sway * (i / (len(offsets) - 1)) ** 2
        x, y = hip[0] + dx + round(s), hip[1] + dy
        if prev is not None and abs(x - prev[0]) > 1:
            x = prev[0] + (1 if x > prev[0] else -1)
        band = TABBY_DK if i % 3 == 1 else (CREAM if i % 2 else CREAM_SH)
        rect(g, x, y, 3, 2, band)
        prev = (x, y)

    # ================= legs / paws =================
    def paw(x, y, lift, color, toes):
        h = max(1, 4 - lift)
        rect(g, x, y - lift, 3, h, color)
        if lift < 2:
            px(g, x, y - lift, toes); px(g, x + 2, y - lift, toes)

    paw(int(cx - 8), int(by + 6), leg_lift[0], CREAM_SH, WHITE_SH)
    paw(int(cx + 6), int(by + 6), leg_lift[1], CREAM_SH, WHITE_SH)
    paw(int(cx - 4), int(by + 8), leg_lift[0], WHITE_SH, WHITE)
    paw(int(cx + 2), int(by + 8), leg_lift[1], WHITE_SH, WHITE)

    # ================= head =================
    head_r = (7.6, 6.6)
    head = blob_mask(cx, hy, *head_r)
    blob_banded(g, cx, hy, *head_r, CREAM_LI, CREAM, CREAM_SH, lo_from=0.5)

    muzzle = blob_mask(cx, hy + 3.4, 3.6, 2.6)
    for (x, y) in muzzle:
        if (x, y) in head:
            px(g, x, y, WHITE if y > hy + 2 else CREAM_LI)

    # forehead tabby streaks
    for dx in (-1, 0, 1):
        x = int(cx + dx * 1.6)
        if (x, int(hy - 5)) in head:
            stripe(g, x, int(hy - 5), 3, TABBY_DK, w=1)

    # ================= ears: solid triangle, tip -> base, one column of
    # code shared between the outer shape and the inner-pink placement so
    # they can never drift apart. =================
    ea = ear_a
    for side, ex in ((-1, int(cx - 6.2)), (1, int(cx + 3.2))):
        base_row = int(hy - 2)      # stop above eye height, or it reads as
        tip_row = int(hy - 9 - ea)  # a stray patch beside the cheek instead
        col_h = max(2, base_row - tip_row + 1)

        def col_at(i):
            width = 1 + round(3 * i / (col_h - 1))     # 1 at tip, 4 at base
            left = ex + (4 - width if side < 0 else 0)
            return left, width

        for i, y in enumerate(range(tip_row, base_row + 1)):
            left, width = col_at(i)
            rect(g, left, y, width, 1, CREAM)

        inner_i0 = col_h // 2
        for i in range(inner_i0, col_h):
            left, width = col_at(i)
            y = tip_row + i
            iw = max(1, width - 2)
            ix = left + (width - iw) // 2
            rect(g, ix, y, iw, 1, PINK)

    # ================= eyes: "full" bakes the iris in (used by every frame
    # except the trackable idle one); "blank" leaves just the white + lid,
    # for eye_overlay() to composite a gaze-offset iris on top of. eye_mode
    # covers the two expression shapes that aren't just "open vs. shut":
    # "happy" (a contented closed arc, not the flat blink bar) and "heavy"
    # (open but half-lidded, for boredom). =================
    ey, eye_sides = eye_anchors(cx, hy)
    for side, ex in eye_sides:
        if eye_mode == "happy" and eye_open:
            # a curved ^ arc reads as a contented squint, not a blink
            px(g, ex, ey, INK); px(g, ex + 1, ey - 1, INK)
            px(g, ex + 2, ey - 1, INK); px(g, ex + 3, ey, INK)
            continue
        if not eye_open:
            rect(g, ex, ey, 4, 1, INK)
            px(g, ex, ey + 1, INK); px(g, ex + 3, ey + 1, INK)
            continue
        rect(g, ex, ey - 1, 4, 3, WHITE)
        rect(g, ex, ey - 2, 4, 1, INK)          # thin lid line
        if eye_mode == "heavy":
            rect(g, ex, ey - 1, 4, 1, INK)      # a second, heavier lid line
        if eyes == "full":
            iris_x = ex + (2 if side < 0 else 1)
            rect(g, iris_x, ey - 1, 2, 2, BLUE)
            px(g, iris_x, ey - 1, BLUE_HI)
            px(g, iris_x + (0 if side < 0 else 1), ey, INK)

    # ================= nose + mouth: mouth_curve tilts the two corners up
    # (smile) or down (frown); mouth_open swaps in an open oval for talking
    # =================
    nx = int(cx)
    ny = int(hy + 4)
    px(g, nx - 1, ny, NOSE); px(g, nx, ny, NOSE)
    if mouth_open:
        rect(g, nx - 1, ny + 1, 2, 2, INK)
    else:
        px(g, nx - 1, ny + 1, INK); px(g, nx, ny + 1, INK)
        c = mouth_curve
        px(g, nx - 2, ny + 2 - c, INK); px(g, nx + 1, ny + 2 - c, INK)

    # whiskers -- three separate thin strands per side, with real gaps
    # between rows (adjacent rows here previously merged into a solid block)
    for side in (-1, 1):
        bx = nx + side * 5
        for dy in (-2, 0, 2):
            length = 3
            for k in range(length):
                px(g, bx + side * k, ny + dy, WHISKER)

    return g


def sleep_curl(palette, breathe=0.0):
    """A curled, sleeping cat -- a genuinely different silhouette from
    base_cat, not the sitting pose with the eyes shut. Real cats sleep as a
    low, wide loaf with the head tucked down and the tail wrapped around the
    body, legs tucked away entirely. breathe (a small +/- value) is the only
    thing that changes between the two sleep frames, for a slow rise-and-fall
    instead of a hard cut."""
    CREAM_LI, CREAM, CREAM_SH = palette["CREAM_LI"], palette["CREAM"], palette["CREAM_SH"]
    TABBY_DK = palette["TABBY_DK"]
    WHITE = palette["WHITE"]
    PINK = palette["PINK"]

    g = new_grid()
    cx = 17.0
    by = 30.0 - breathe          # the loaf rises and falls as she breathes
    body_r = (11.2, 6.6 + breathe * 0.5)

    body = blob_mask(cx, by, *body_r)
    blob_banded(g, cx, by, *body_r, CREAM_LI, CREAM, CREAM_SH, lo_from=0.35)

    # belly patch, low and wide rather than the sitting pose's chest oval
    belly = blob_mask(cx + 1, by + 2.4, 5.4, 3.4)
    for (x, y) in belly:
        if (x, y) in body:
            px(g, x, y, WHITE)

    for (dx, top_dy, h) in [(-7, -3, 3), (-3, -4.5, 3), (2, -4.5, 3), (6, -3, 3)]:
        x, y = int(cx + dx), int(by + top_dy)
        if (x, y) in body:
            stripe(g, x, y, h, TABBY_DK, w=1)

    # tail, wrapped along the body's own edge rather than sticking out --
    # a run of cells just outside the body silhouette, following its curve
    tail_cells = []
    for deg in range(40, 172, 6):
        rad = math.radians(deg)
        tx = cx + (body_r[0] + 1.6) * math.cos(rad)
        ty = by + (body_r[1] + 1.6) * math.sin(rad)
        tail_cells.append((int(tx), int(ty)))
    for i, (x, y) in enumerate(tail_cells):
        rect(g, x, y, 2, 2, TABBY_DK if i % 3 == 1 else CREAM_SH)

    # head, tucked low and forward -- resting on/against the body, not
    # held up the way the sitting pose's head is
    hx, hy = cx - 5.5, by - 5.0 + breathe * 0.3
    head_r = (5.6, 4.8)
    head = blob_mask(hx, hy, *head_r)
    blob_banded(g, hx, hy, *head_r, CREAM_LI, CREAM, CREAM_SH, lo_from=0.4)

    muzzle = blob_mask(hx - 0.5, hy + 2.2, 2.6, 1.9)
    for (x, y) in muzzle:
        if (x, y) in head:
            px(g, x, y, WHITE if y > hy + 1.5 else CREAM_LI)

    # ears -- small and relaxed, no perk, using the same tip->base column
    # shape as base_cat's ears but shorter
    for side, ex in ((-1, int(hx - 4.4)), (1, int(hx + 2.6))):
        base_row = int(hy - 1)
        tip_row = int(hy - 5)
        col_h = max(2, base_row - tip_row + 1)
        for i, y in enumerate(range(tip_row, base_row + 1)):
            width = 1 + round(2 * i / (col_h - 1))
            left = ex + (3 - width if side < 0 else 0)
            rect(g, left, y, width, 1, CREAM)
        px(g, ex + (1 if side < 0 else 1), base_row - 1, PINK)

    # closed eyes -- a simple contented downward arc, no blink/open state;
    # she's asleep in every frame this function ever draws
    ey = int(hy - 0.5)
    for side, ex in ((-1, int(hx - 3.2)), (1, int(hx + 1.2))):
        px(g, ex, ey, INK); px(g, ex + 1, ey + 1, INK)

    # nose
    px(g, int(hx - 0.5), int(hy + 2.4), palette["NOSE"])

    return g
