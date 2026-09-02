"""Hand-authored pixel-art cat, drawn on a coarse grid so it reads as pixel
art after nearest-neighbor upscale. No AI image gen available here, so this
builds the sprite directly out of colored grid cells."""
from PIL import Image, ImageDraw

PX = 3                      # size of one "pixel" block in the final image
GW, GH = 34, 42             # grid size in blocks -- finer than v1 for detail

INK       = (54, 40, 33, 255)
WHISKER   = (200, 180, 160, 190)

# Each skin is a full role->color set. base_cat() unpacks one of these into
# locals shadowing these names, so the drawing code below never mentions a
# skin by name -- it just draws "CREAM" etc. and the palette decides what
# that means.
PALETTES = {
    "cream_tabby": dict(
        CREAM_LI=(250, 235, 210, 255), CREAM=(240, 216, 182, 255), CREAM_SH=(219, 188, 148, 255),
        TABBY=(168, 126, 87, 255), TABBY_DK=(128, 91, 60, 255),
        WHITE=(255, 252, 246, 255), WHITE_SH=(232, 222, 206, 255),
        PINK=(235, 165, 173, 255), PINK_DK=(214, 130, 140, 255),
        BLUE=(68, 122, 190, 255), BLUE_DK=(44, 84, 138, 255), BLUE_HI=(215, 232, 248, 255),
        NOSE=(214, 128, 138, 255),
    ),
    "orange_tabby": dict(
        CREAM_LI=(255, 210, 150, 255), CREAM=(240, 166, 92, 255), CREAM_SH=(206, 130, 62, 255),
        TABBY=(196, 110, 50, 255), TABBY_DK=(150, 78, 32, 255),
        WHITE=(255, 250, 240, 255), WHITE_SH=(235, 220, 198, 255),
        PINK=(240, 172, 150, 255), PINK_DK=(216, 132, 108, 255),
        BLUE=(140, 190, 90, 255), BLUE_DK=(92, 138, 56, 255), BLUE_HI=(224, 240, 200, 255),
        NOSE=(222, 130, 100, 255),
    ),
    "gray_mackerel": dict(
        CREAM_LI=(218, 218, 210, 255), CREAM=(184, 184, 174, 255), CREAM_SH=(146, 146, 136, 255),
        TABBY=(118, 116, 106, 255), TABBY_DK=(76, 74, 66, 255),
        WHITE=(255, 252, 248, 255), WHITE_SH=(230, 228, 222, 255),
        PINK=(214, 182, 184, 255), PINK_DK=(188, 150, 152, 255),
        BLUE=(120, 168, 110, 255), BLUE_DK=(70, 112, 64, 255), BLUE_HI=(220, 238, 210, 255),
        NOSE=(184, 140, 142, 255),
    ),
    "tuxedo": dict(
        # dark base instead of cream, and TABBY == CREAM_SH so the stripe
        # overlay disappears -- tuxedos are solid, not striped
        CREAM_LI=(74, 70, 68, 255), CREAM=(46, 44, 42, 255), CREAM_SH=(30, 28, 27, 255),
        TABBY=(30, 28, 27, 255), TABBY_DK=(20, 19, 18, 255),
        WHITE=(255, 252, 246, 255), WHITE_SH=(228, 222, 214, 255),
        PINK=(224, 160, 168, 255), PINK_DK=(200, 126, 136, 255),
        BLUE=(150, 196, 90, 255), BLUE_DK=(98, 144, 56, 255), BLUE_HI=(228, 240, 200, 255),
        NOSE=(210, 140, 145, 255),
    ),
}

def new_grid():
    return [[None] * GW for _ in range(GH)]

def rect(g, x, y, w, h, color):
    for j in range(y, y + h):
        for i in range(x, x + w):
            if 0 <= j < GH and 0 <= i < GW:
                g[j][i] = color

def px(g, x, y, color):
    if 0 <= y < GH and 0 <= x < GW:
        g[y][x] = color

def render(g):
    img = Image.new("RGBA", (GW * PX, GH * PX), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for y in range(GH):
        for x in range(GW):
            c = g[y][x]
            if c is None:
                continue
            d.rectangle([x * PX, y * PX, x * PX + PX - 1, y * PX + PX - 1], fill=c)
    return img
