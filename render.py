#!/usr/bin/env python3
"""Render entry.png (1024x1024) for news-image-20261120, agent 4.

Concept: "THE NEWS WALL" - an editorial poster. One giant hero scene
(cyclone Akvan over the Odisha coast) under a red masthead band, then
3 big tiles, a 6-number strip, a 6-tile masonry rail, a small world map,
an ALSO ON list, a DATE CHECK box and a footer.

100% stdlib. Draws flat vector shapes + embedded vector font outlines
(font_data.py, Liberation Sans subset, SIL OFL) into an RGB buffer and
writes a PNG with its own encoder. Deterministic: no time, no random,
no network, fixed iteration order.
"""
import math
import struct
import sys
import zlib

from font_data import FONTS, UPM

W, H = 1024, 1024
SS = 2                      # supersample: draw at 2048, downsample to 1024
W2, H2 = W * SS, H * SS     # (thin vector strokes vanish at 1x small sizes)

# --- palette -------------------------------------------------------------
PAPER = (246, 238, 220)   # warm cream paper
INK = (17, 17, 17)        # near-black ink
RED = (176, 58, 46)       # poster red
RED_DK = (140, 44, 34)
TEAL = (30, 110, 106)     # storm teal
TEAL_DK = (18, 74, 71)
GOLD = (201, 162, 39)
GOLD_LT = (232, 196, 90)
NAVY = (27, 42, 74)
WHITE = (255, 255, 255)
CREAM = (250, 246, 236)
GREY = (90, 84, 72)
SKY = (199, 220, 212)
SKY2 = (178, 205, 194)
SEA = (46, 125, 120)
SEA_DK = (28, 96, 92)
SAND = (232, 217, 168)
ORANGE = (224, 122, 42)
RUST = (178, 74, 32)

# --- canvas --------------------------------------------------------------
buf = bytearray(W2 * H2 * 3)


def fill_paper():
    r, g, b = PAPER
    for i in range(0, len(buf), 3):
        buf[i] = r
        buf[i + 1] = g
        buf[i + 2] = b


def rect(x0, y0, x1, y1, color):
    x0 = max(0, int(x0 * SS)); y0 = max(0, int(y0 * SS))
    x1 = min(W2, int(x1 * SS)); y1 = min(H2, int(y1 * SS))
    if x1 <= x0 or y1 <= y0:
        return
    r, g, b = color
    row = bytes((r, g, b)) * (x1 - x0)
    for y in range(y0, y1):
        o = (y * W2 + x0) * 3
        buf[o:o + len(row)] = row


def border(x0, y0, x1, y1, color, t=2):
    rect(x0, y0, x1, y0 + t, color)
    rect(x0, y1 - t, x1, y1, color)
    rect(x0, y0, x0 + t, y1, color)
    rect(x1 - t, y0, x1, y1, color)


def fill_polys(polys, color, scaled=False):
    """Even-odd scanline fill of a list of flat point lists [(x,y)...].
    Input coords are in 1024-space unless scaled=True (already 2x)."""
    r, g, b = color
    min_y = None
    max_y = None
    edges = []
    for poly in polys:
        n = len(poly)
        if n < 3:
            continue
        sp = poly if scaled else [(px * SS, py * SS) for (px, py) in poly]
        for i in range(n):
            x0, y0 = sp[i]
            x1, y1 = sp[(i + 1) % n]
            if y0 == y1:
                continue
            edges.append((x0, y0, x1, y1))
            min_y = y0 if min_y is None else min(min_y, y0)
            max_y = y0 if max_y is None else max(max_y, y0)
            min_y = min(min_y, y1)
            max_y = max(max_y, y1)
    if not edges or min_y is None:
        return
    y_start = max(0, int(math.floor(min_y)))
    y_end = min(H2 - 1, int(math.ceil(max_y)))
    for y in range(y_start, y_end + 1):
        yc = y + 0.5
        xs = []
        for (x0, y0, x1, y1) in edges:
            if (y0 <= yc < y1) or (y1 <= yc < y0):
                xs.append(x0 + (yc - y0) * (x1 - x0) / (y1 - y0))
        if len(xs) < 2:
            continue
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            xa = max(0, int(math.ceil(xs[i])))
            xb = min(W2, int(math.floor(xs[i + 1])))
            if xb <= xa:
                continue
            o = (y * W2 + xa) * 3
            n = xb - xa
            buf[o:o + n * 3] = bytes((r, g, b)) * n


def poly(points, color):
    fill_polys([points], color)


def circle(cx, cy, rad, color, n=48):
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    poly(pts, color)


def ellipse(cx, cy, rx, ry, color, n=48):
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    poly(pts, color)


def ring(cx, cy, r_out, r_in, color, n=64):
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        pts.append((cx + r_out * math.cos(a), cy + r_out * math.sin(a)))
    for i in range(n - 1, -1, -1):
        a = 2 * math.pi * i / n
        pts.append((cx + r_in * math.cos(a), cy + r_in * math.sin(a)))
    poly(pts, color)


def thick_line(x0, y0, x1, y1, w, color):
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    if L == 0:
        circle(x0, y0, w / 2, color)
        return
    nx, ny = -dy / L * w / 2, dx / L * w / 2
    poly([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
          (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], color)


def arc_pts(cx, cy, r, a0, a1, steps=40):
    pts = []
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def thick_arc(cx, cy, r, a0, a1, w, color, steps=40):
    pts = arc_pts(cx, cy, r, a0, a1, steps)
    for i in range(len(pts) - 1):
        thick_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], w, color)


def spiral(cx, cy, r0, r1, a0, a1, w, color, steps=90):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        a = a0 + (a1 - a0) * t
        r = r0 + (r1 - r0) * t
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    for i in range(len(pts) - 1):
        thick_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], w, color)


# --- text ----------------------------------------------------------------
def glyph(font, ch):
    return FONTS[font].get(ch) or FONTS[font]["?"]


def text_width(s, size, font="REGULAR"):
    sc = size / UPM
    w = 0.0
    for ch in s:
        adv, _ = glyph(font, ch)
        w += adv * sc
    return w


def draw_text(x, baseline, s, size, font="REGULAR", color=INK, align="left"):
    if align == "center":
        x -= text_width(s, size, font) / 2
    elif align == "right":
        x -= text_width(s, size, font)
    sc = size * SS / UPM
    cx = x * SS
    baseline2 = baseline * SS
    for ch in s:
        adv, polys = glyph(font, ch)
        if polys:
            moved = []
            for flat in polys:
                pts = []
                for i in range(0, len(flat), 2):
                    pts.append((cx + flat[i] * sc, baseline2 - flat[i + 1] * sc))
                moved.append(pts)
            fill_polys(moved, color, scaled=True)
        cx += adv * sc
    return cx / SS


def wrap(s, size, font, max_w):
    words = s.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_width(trial, size, font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_lines(x, y_top, lines, size, lh, font="REGULAR", color=INK, align="left"):
    y = y_top
    for line in lines:
        draw_text(x, y + size, line, size, font, color, align)
        y += lh
    return y


# --- hero scene: cyclone Akvan over the Odisha coast ----------------------
def hero_scene(x0, y0, x1, y1):
    # sky bands
    rect(x0, y0, x1, y0 + 118, SKY)
    rect(x0, y0 + 118, x1, y0 + 158, SKY2)
    # clouds
    for (cx, cy, rx, ry) in [(140, y0 + 26, 46, 12), (180, y0 + 18, 34, 10),
                             (880, y0 + 40, 52, 13), (920, y0 + 30, 36, 10)]:
        ellipse(cx, cy, rx, ry, WHITE)
    # cyclone spiral, centre right of middle
    cx, cy = 640, y0 + 108
    spiral(cx, cy, 12, 118, -0.6, 5.4, 17, WHITE)
    spiral(cx, cy, 12, 96, 2.2, 8.0, 15, TEAL)
    spiral(cx, cy, 12, 74, 4.6, 10.2, 13, WHITE)
    circle(cx, cy, 15, CREAM)
    ring(cx, cy, 20, 15, TEAL)
    # rain, slanted
    for i in range(46):
        rx = x0 + 18 + (i * 37) % 900
        ry = y0 + 12 + (i * 53) % 120
        thick_line(rx, ry, rx - 9, ry + 16, 2, (120, 160, 152))
    # sea
    rect(x0, y0 + 158, x1, y0 + 196, SEA)
    rect(x0, y0 + 196, x1, y1, SEA_DK)
    for wx in range(x0 + 30, x1 - 20, 74):
        thick_arc(wx, y0 + 172, 16, math.pi, 2 * math.pi, 3, WHITE)
        thick_arc(wx + 36, y0 + 206, 13, math.pi, 2 * math.pi, 3,
                  (150, 200, 192))
    # rescue boat on the sea
    bx, by = 830, y0 + 176
    poly([(bx - 34, by), (bx + 34, by), (bx + 24, by + 13), (bx - 24, by + 13)],
         ORANGE)
    rect(bx - 12, by - 14, bx + 12, by, WHITE)
    rect(bx - 12, by - 14, bx + 12, by - 10, RED)
    thick_line(bx, by - 14, bx, by - 26, 3, INK)
    poly([(bx, by - 26), (bx + 14, by - 18), (bx, by - 18)], RED)
    # sand coast + shelters + palms at the bottom
    poly([(x0, y1), (x0, y0 + 208), (x1, y0 + 200), (x1, y1)], SAND)
    for (hx, hy, s) in [(700, y1 - 8, 1.0), (760, y1 - 6, 0.85), (650, y1 - 4, 0.7)]:
        rect(hx - 16 * s, hy - 14 * s, hx + 16 * s, hy, (196, 150, 96))
        poly([(hx - 20 * s, hy - 14 * s), (hx, hy - 30 * s),
              (hx + 20 * s, hy - 14 * s)], RUST)
    for (px, py) in [(910, y1 - 4), (940, y1 - 2)]:
        thick_line(px, py, px + 4, py - 26, 4, (122, 92, 52))
        for (dx, dy) in [(-16, -30), (14, -32), (-4, -36), (8, -28)]:
            thick_line(px + 4, py - 26, px + 4 + dx, py - 26 + dy, 3, TEAL_DK)


# --- tile illustrations ----------------------------------------------------
def ill_kyiv(x, y, w, h):
    rect(x, y, x + w, y + h, NAVY)
    circle(x + w - 26, y + 16, 10, GOLD_LT)
    # city silhouette
    for (bx, bw, bh) in [(8, 26, 34), (40, 20, 48), (66, 30, 28), (102, 18, 42),
                         (126, 26, 36), (158, 22, 52), (186, 28, 30),
                         (220, 20, 44), (246, 26, 32), (278, 18, 40)]:
        rect(x + bx, y + h - bh, x + bx + bw, y + h, (10, 18, 38))
    for (wx, wy) in [(14, y + h - 26), (46, y + h - 40), (72, y + h - 20),
                     (108, y + h - 34), (132, y + h - 28), (164, y + h - 44),
                     (192, y + h - 22), (226, y + h - 36), (252, y + h - 24),
                     (284, y + h - 32)]:
        rect(wx + x, wy, wx + x + 4, wy + 5, GOLD_LT)
    # missile arcs + fire
    thick_arc(x + 60, y + h - 6, 52, 3.6, 5.6, 4, ORANGE)
    thick_arc(x + 190, y + h - 6, 44, 3.8, 5.8, 4, ORANGE)
    circle(x + 60, y + h - 52, 5, GOLD_LT)
    circle(x + 190, y + h - 46, 5, GOLD_LT)
    for (fx, fy, fr) in [(120, y + h - 8, 12), (132, y + h - 6, 9),
                         (250, y + h - 8, 11)]:
        circle(fx + x, fy, fr, ORANGE)
        circle(fx + x, fy - 4, fr // 2, GOLD_LT)


def ill_cop(x, y, w, h):
    rect(x, y, x + w, y + h, (214, 232, 222))
    circle(x + 62, y + 34, 24, GOLD)
    for i in range(8):
        a = math.pi * i / 4
        thick_line(x + 62 + 30 * math.cos(a), y + 34 + 30 * math.sin(a),
                   x + 62 + 40 * math.cos(a), y + 34 + 40 * math.sin(a),
                   3, GOLD)
    # sea + globe
    rect(x, y + h - 30, x + w, y + h, TEAL)
    for wx in range(x + 12, x + w - 8, 34):
        thick_arc(wx, y + h - 16, 9, math.pi, 2 * math.pi, 3, WHITE)
    circle(x + w - 66, y + 40, 30, SEA)
    ellipse(x + w - 66, y + 40, 30, 12, (120, 190, 170))
    ellipse(x + w - 66, y + 52, 22, 9, (120, 190, 170))
    rect(x + 14, y + 48, x + 150, y + 66, RED)
    draw_text(x + 82, y + 62, "COP31", 13, "BOLD", WHITE, "center")


def ill_markets(x, y, w, h):
    rect(x, y, x + w, y + h, (24, 28, 40))
    # candlesticks falling
    base = y + h - 14
    for i, (cw, ch) in enumerate([(14, 26), (14, 40), (14, 34), (14, 52),
                                  (14, 46), (14, 62)]):
        cx = x + 16 + i * 34
        rect(cx, base - ch, cx + cw, base - ch + 22, RED)
        thick_line(cx + 7, base - ch - 8, cx + 7, base - ch + 30, 2, RED)
    # down arrow
    thick_line(x + w - 96, y + 16, x + w - 30, y + 58, 6, GOLD)
    poly([(x + w - 30, y + 58), (x + w - 52, y + 52), (x + w - 36, y + 74)],
         GOLD)
    draw_text(x + 16, y + 22, "-7%", 22, "BOLD", WHITE)


def ill_cricket(x, y, w, h):
    rect(x, y, x + w, y + h, (46, 122, 74))
    # pitch (trapezoid, centre-right)
    poly([(x + 44, y + 8), (x + 76, y + 8),
          (x + 84, y + h - 8), (x + 36, y + h - 8)],
         (214, 196, 140))
    # stumps
    for sx in (-6, 0, 6):
        rect(x + 60 + sx - 2, y + 14, x + 60 + sx + 2, y + 30, GOLD_LT)
    # batsman silhouette, left
    bx, by = x + 20, y + h - 52
    circle(bx, by - 20, 8, INK)
    thick_line(bx, by - 12, bx + 3, by + 14, 6, INK)
    thick_line(bx + 3, by + 14, bx - 7, by + 38, 5, INK)
    thick_line(bx + 3, by + 14, bx + 15, by + 36, 5, INK)
    thick_line(bx, by - 9, bx + 22, by + 4, 5, INK)
    thick_line(bx + 22, by + 4, bx + 36, by + 24, 4, (222, 196, 150))
    circle(x + w - 12, y + 24, 6, RED)


def ill_space(x, y, w, h):
    rect(x, y, x + w, y + h, (12, 14, 30))
    for (sx, sy) in [(10, 10), (30, 20), (52, 8), (76, 16), (14, 40),
                     (80, 44), (44, 52)]:
        circle(x + sx, y + sy, 2, WHITE)
    # Mercury, top-right
    circle(x + 62, y + 30, 15, (176, 160, 140))
    circle(x + 57, y + 25, 3, (140, 126, 108))
    circle(x + 67, y + 34, 3, (140, 126, 108))
    # probe with panels, bottom-left + dotted trajectory to Mercury
    px, py = x + 26, y + h - 26
    rect(px - 7, py - 6, px + 7, py + 6, GOLD)
    rect(px - 22, py - 3, px - 7, py + 3, (90, 120, 180))
    rect(px + 7, py - 3, px + 22, py + 3, (90, 120, 180))
    for i in range(4):
        circle(px + 28 + i * 7, py - 6 - i * 6, 2, WHITE)


def ill_euuk(x, y, w, h):
    rect(x, y, x + w, y + h, (232, 236, 240))
    # EU flag, top half
    rect(x + 8, y + 6, x + w - 8, y + h // 2 - 2, (0, 51, 153))
    for i in range(12):
        a = 2 * math.pi * i / 12 - math.pi / 2
        circle(x + w // 2 + 22 * math.cos(a),
               y + h // 4 + 16 * math.sin(a), 2, GOLD_LT)
    # UK flag, bottom half, simplified cross
    ux, uy = x + 8, y + h // 2 + 2
    uw, uh = w - 16, h // 2 - 8
    rect(ux, uy, ux + uw, uy + uh, (1, 33, 105))
    thick_line(ux, uy, ux + uw, uy + uh, 5, WHITE)
    thick_line(ux + uw, uy, ux, uy + uh, 5, WHITE)
    thick_line(ux + uw // 2, uy, ux + uw // 2, uy + uh, 8, WHITE)
    thick_line(ux, uy + uh // 2, ux + uw, uy + uh // 2, 8, WHITE)
    thick_line(ux + uw // 2, uy, ux + uw // 2, uy + uh, 3, RED)
    thick_line(ux, uy + uh // 2, ux + uw, uy + uh // 2, 3, RED)


def ill_italy(x, y, w, h):
    rect(x, y, x + w, y + h, (240, 228, 200))
    # placard, top
    rect(x + 10, y + 8, x + w - 10, y + 28, WHITE)
    border(x + 10, y + 8, x + w - 10, y + 28, INK, 2)
    draw_text(x + w // 2, y + 24, "24H", 12, "BOLD", RED, "center")
    # marching figures, three across
    for i, fx in enumerate([20, 44, 68]):
        fy = y + h - 10
        col = INK if i % 2 == 0 else RED
        circle(x + fx, fy - 44, 8, col)
        thick_line(x + fx, fy - 36, x + fx, fy - 12, 6, col)
        thick_line(x + fx, fy - 12, x + fx - 9, fy, 5, col)
        thick_line(x + fx, fy - 12, x + fx + 9, fy, 5, col)


def ill_senegal(x, y, w, h):
    rect(x, y, x + w, y + h, (196, 222, 226))
    rect(x, y + h - 34, x + w, y + h, SEA)
    for wx in range(x + 8, x + w - 6, 26):
        thick_arc(wx, y + h - 18, 7, math.pi, 2 * math.pi, 3, WHITE)
    # capsized boat, centred
    bx, by = x + w // 2, y + h - 40
    poly([(bx - 34, by - 6), (bx + 34, by - 6), (bx + 26, by + 10),
          (bx - 26, by + 10)], (120, 84, 52))
    thick_line(bx - 18, by - 6, bx - 18, by - 22, 4, INK)
    # life ring, top-right
    ring(x + w - 16, y + 18, 11, 6, ORANGE)
    # figures in water
    for (fx, fy) in [(bx - 40, by + 16), (bx + 40, by + 14)]:
        circle(fx, fy, 5, INK)


def ill_pill(x, y, w, h):
    rect(x, y, x + w, y + h, (238, 232, 244))
    # capsule, tilted, inside the 88-wide block
    cx, cy = x + w // 2, y + h // 2 - 6
    poly([(cx - 32, cy - 4), (cx + 30, cy - 18), (cx + 34, cy - 6),
          (cx - 28, cy + 8)], TEAL)
    poly([(cx - 28, cy + 8), (cx + 34, cy - 6), (cx + 30, cy + 6),
          (cx - 32, cy + 20)], GOLD)
    # cells shrinking
    circle(x + 14, y + 14, 7, RED)
    circle(x + w - 14, y + h - 26, 6, RED)
    circle(x + w - 12, y + 16, 4, (200, 120, 110))
    draw_text(x + w // 2, y + h - 8, "60.7%", 14, "BOLD", TEAL, "center")


# --- layout ----------------------------------------------------------------
MX = 28            # left margin
RX = 996           # right edge
CW = RX - MX       # 968 content width

BIG_TILES = [
    ("KYIV · WAR", "Missiles rain on Kyiv overnight",
     "Waves of ballistic missiles after midnight damage three bridges "
     "over the Dnipro; fires burn in districts. Putin had vowed a "
     "\u201cpainful\u201d reply to the Crimea bridge strike.",
     "(Kyiv Independent, UNN)", ill_kyiv, RED),
    ("ANTALYA · CLIMATE", "COP31 ends its last day without a deal",
     "The final draft drops every mention of fossil fuels and the $120bn "
     "adaptation figure; hosts push a \u201c35 by 35\u201d clean-power goal; "
     "the text is due by midnight.",
     "(UN News, Reuters)", ill_cop, TEAL),
    ("SEOUL / TOKYO · MARKETS", "Asia\u2019s markets sink as the AI trade unwinds",
     "Nikkei \u22124.5%, KOSPI \u22124.7%, SoftBank \u221216%; Wall Street falls "
     "a sixth straight day, the Dow down 1,101 to 49,097.",
     "(Reuters)", ill_markets, INK),
]

STATS = [
    ("300,000", "evacuated from", "Odisha\u2019s coast"),
    ("$2.36bn", "GTA VI day one", "[ESTIMATE]"),
    ("118", "Phillips, a first", "centuries vs India"),
    ("60.7%", "tumours shrink", "early cancer trial"),
    ("2.2%", "Japan core CPI", "BoJ hike eyed"),
    ("49,097", "Dow close", "down 1,101"),
]

RAIL = [
    ("WELLINGTON · CRICKET", "Phillips makes history with 118",
     "First batter ever with Test, ODI and T20I centuries vs India in one "
     "year; Nicholls 175 not out, New Zealand 368.",
     "(Reuters, ICC)", ill_cricket),
    ("SPACE", "BepiColombo counts down to Mercury",
     "The ESA\u2013JAXA probe ends its 8-year, 6-billion-mile trip; orbit "
     "insertion is set for Saturday. [SCHEDULED]",
     "(ESA)", ill_space),
    ("BRUSSELS · EUROPE", "Burnham\u2019s first EU\u2013UK reset summit",
     "Costa and von der Leyen host the new UK prime minister; "
     "carbon-market links are on the table.",
     "(EU Council)", ill_euuk),
    ("ROME · LABOUR", "Italy\u2019s CGIL holds a 24-hour general strike",
     "Unions march in about 100 squares against the 2027 budget; "
     "transport is hit.",
     "(CGIL, AFP)", ill_italy),
    ("SENEGAL · MIGRATION", "Migrant boat capsizes off Senegal",
     "Four bodies are recovered from a boat carrying 50\u2013100 people; "
     "Canary arrivals surge.",
     "(Al Jazeera)", ill_senegal),
    ("BARCELONA · HEALTH", "Cancer pill shrinks tumours 60.7%",
     "Early trial, 61 patients, no control group; disease control 90.2%. "
     "[REPORTED]",
     "(ENA)", ill_pill),
]

ALSO_ON = [
    ("10", "TOKYO", "Japan core inflation 2.2%; BoJ hike eyed.", "Reuters"),
    ("11", "BEIJING", "China holds lending rates, 18th month.", "PBOC"),
    ("12", "SAN SALVADOR", "Bukele files for a third term.", "AP"),
    ("13", "WORLD", "GTA VI day one: 24.6m copies, $2.36bn [ESTIMATE].",
     "Sensor Tower"),
    ("14", "SHENZHEN", "Leaders declare \u201ca nuclear war cannot be won\u201d.",
     "Reuters"),
    ("15", "FLORIDA", "St Johns River record 18.3 ft; schools shut.", "AP"),
    ("16", "IOWA", "Army delays blowing up 68 explosive barrels.", "AP"),
    ("17", "SEOUL", "Ruling party moves to impeach top judge.", "SBS"),
    ("18", "BRASILIA", "Lula visits Raoni; Indigenous land recognised.",
     "Al Jazeera"),
    ("19", "COPENHAGEN", "Denmark approves Greenland defence bill.", "AFP"),
    ("20", "JAKARTA", "Indonesia passes asset-forfeiture bill.", "Reuters"),
    ("21", "HORMUZ", "Four attacks on commercial vessels in 96 hours.", "UKMTO"),
    ("22", "DOHA", "U17 World Cup: Australia stun Argentina 2\u20130.", "FIFA"),
    ("23", "TURIN", "Alcaraz\u2013Cobolli, Medvedev\u2013Tiafoe close ATP groups.",
     "ATP"),
    ("24", "TONGA", "Emergency declared as El Ni\u00f1o drought bites.", "RNZ"),
    ("25", "WASHINGTON", "Pentagon: US war cost vs Iran $48.3bn.", "Reuters"),
]

DATE_CHECK = ("First reported Thursday 19 Nov, so NOT shown here as Friday\u2019s "
    "news: the Senate\u2019s 51\u201348 Iran war-powers vote \u00b7 the strikes that "
    "hit Kyiv\u2019s Dutch, Austrian and Swedish embassies \u00b7 the ICJ\u2019s "
    "Rohingya genocide ruling \u00b7 the Trump\u2013Xi\u2013Putin meeting itself "
    "\u00b7 Anthropic\u2019s $83 IPO pricing \u00b7 GTA VI\u2019s midnight launch "
    "\u00b7 Voyager 1\u2019s light-day milestone (crossed 18 Nov) \u00b7 the "
    "Houthi strike on Riyadh\u2019s PIF tower \u00b7 the Crimean Bridge attack "
    "\u00b7 Fiji\u2019s drought declaration \u00b7 Trump defers Iran decision "
    "to 2027.")

MAP_PINS = [
    ("1", "Odisha", 196, 22), ("2", "Kyiv", 118, 12),
    ("3", "Antalya", 128, 20), ("4", "Seoul", 208, 14),
    ("5", "Wellington", 222, 44), ("6", "Brussels", 108, 8),
    ("7", "Rome", 124, 26), ("8", "Senegal", 82, 30),
    ("9", "Barcelona", 100, 18),
]


def draw_big_tile(x, y, w, h, kicker, headline, summary, source, ill, accent):
    rect(x, y, x + w, y + h, WHITE)
    border(x, y, x + w, y + h, INK, 2)
    ill(x + 2, y + 2, w - 4, 72)
    rect(x + 2, y + 74, x + w - 2, y + 76, accent)
    draw_text(x + 10, y + 90, kicker, 11, "BOLD", accent)
    draw_text(x + w - 10, y + 90, source, 9.5, "BOLD", GREY, "right")
    hl = wrap(headline, 19, "BOLD", w - 20)
    draw_lines(x + 10, y + 94, hl[:2], 19, 20, "BOLD", INK)
    sm = wrap(summary, 11, "REGULAR", w - 20)
    draw_lines(x + 10, y + 138, sm[:3], 11, 12.5, "REGULAR", INK)


def draw_rail_tile(x, y, w, h, kicker, headline, summary, source, ill):
    rect(x, y, x + w, y + h, WHITE)
    border(x, y, x + w, y + h, INK, 2)
    iw = 88
    ill(x + 2, y + 2, iw, h - 4)
    tx = x + iw + 10
    tw = w - iw - 18
    draw_text(tx, y + 14, kicker, 10, "BOLD", RED)
    hl = wrap(headline, 15.5, "BOLD", tw)
    draw_lines(tx, y + 18, hl[:2], 15.5, 16, "BOLD", INK)
    sm = wrap(summary, 10.5, "REGULAR", tw)
    n_sm = 3 if len(sm) > 2 else 2
    draw_lines(tx, y + 18 + len(hl[:2]) * 16 + 1, sm[:n_sm], 10.5, 12,
               "REGULAR", INK)
    draw_text(tx, y + h - 6, source, 9, "BOLD", (70, 64, 52))


def draw_map(x, y, w, h):
    rect(x, y, x + w, y + h, (216, 230, 224))
    border(x, y, x + w, y + h, INK, 2)
    # schematic continents (flat teal blobs)
    poly([(x + 8, y + 18), (x + 34, y + 6), (x + 58, y + 10), (x + 62, y + 24),
          (x + 44, y + 34), (x + 20, y + 32)], TEAL)          # N America
    poly([(x + 52, y + 36), (x + 66, y + 34), (x + 70, y + 46),
          (x + 58, y + 52), (x + 50, y + 44)], TEAL)          # S America
    poly([(x + 104, y + 8), (x + 128, y + 6), (x + 134, y + 16),
          (x + 118, y + 22), (x + 104, y + 18)], TEAL)        # Europe
    poly([(x + 112, y + 24), (x + 134, y + 22), (x + 142, y + 36),
          (x + 128, y + 48), (x + 114, y + 38)], TEAL)        # Africa
    poly([(x + 140, y + 6), (x + 200, y + 4), (x + 222, y + 16),
          (x + 208, y + 30), (x + 168, y + 32), (x + 144, y + 20)],
         TEAL)                                                # Asia
    poly([(x + 208, y + 40), (x + 224, y + 38), (x + 226, y + 48),
          (x + 210, y + 50)], TEAL)                           # Oceania
    for (num, _name, px, py) in MAP_PINS:
        circle(x + px, y + py, 7, RED)
        draw_text(x + px, y + py + 3, num, 8, "BOLD", WHITE, "center")


def build():
    fill_paper()

    # --- masthead band ---------------------------------------------------
    rect(MX, 14, RX, 68, RED)
    rect(MX, 68, RX, 71, RED_DK)
    draw_text(MX + 16, 54, "FRIDAY 20 NOVEMBER 2026", 40, "BOLD", WHITE)
    draw_text(RX - 16, 50, "26 STORIES · 6 CONTINENTS", 15, "BOLD", WHITE,
              "right")
    draw_text(512, 88, "A cyclone comes ashore · Missiles rain on Kyiv · "
              "COP31\u2019s final day", 15, "REGULAR", INK, "center")

    # --- hero ------------------------------------------------------------
    hero_scene(MX, 92, RX, 330)
    border(MX, 92, RX, 330, INK, 2)
    # kicker chip
    rect(MX + 12, 100, MX + 152, 122, TEAL_DK)
    draw_text(MX + 82, 117, "ODISHA · STORM", 12, "BOLD", WHITE, "center")
    # gold pin
    rect(752, 100, 984, 146, GOLD)
    border(752, 100, 984, 146, INK, 2)
    draw_text(868, 120, "300,000 EVACUATED", 16, "BOLD", INK, "center")
    draw_text(868, 139, "9,341 SHELTERS · 423 TEAMS", 10.5, "BOLD", INK,
              "center")
    # headline box, bottom-left of the hero
    rect(MX + 12, 238, MX + 560, 322, INK)
    draw_text(MX + 26, 270, "AKVAN COMES ASHORE", 30, "BOLD", WHITE)
    draw_text(MX + 26, 290,
              "Severe cyclone crosses the coast near Gopalpur on Friday",
              12.5, "REGULAR", WHITE)
    draw_text(MX + 26, 306,
              "morning; winds gusting to 110 km/h.",
              12.5, "REGULAR", WHITE)
    draw_text(MX + 26, 318, "IMD / The Hindu", 10, "BOLD", GOLD_LT)

    # --- 3 big tiles ------------------------------------------------------
    tile_w = 316
    for i, (kicker, headline, summary, source, ill, accent) in enumerate(BIG_TILES):
        draw_big_tile(MX + i * (tile_w + 10), 338, tile_w, 184,
                      kicker, headline, summary, source, ill, accent)

    # --- stats strip ------------------------------------------------------
    rect(MX, 530, RX, 576, CREAM)
    border(MX, 530, RX, 576, INK, 2)
    for i, (val, lab1, lab2) in enumerate(STATS):
        cx = MX + i * (CW // 6) + CW // 12
        draw_text(cx, 550, val, 22, "BOLD", GOLD if i != 0 else RED, "center")
        draw_text(cx, 562, lab1, 10, "REGULAR", INK, "center")
        draw_text(cx, 572, lab2, 9, "BOLD", INK, "center")
        if i:
            rect(MX + i * (CW // 6), 536, MX + i * (CW // 6) + 1, 568,
                 (200, 190, 160))

    # --- masonry rail -----------------------------------------------------
    rail_y = [584, 692]
    rail_h = [104, 108]
    for idx, (kicker, headline, summary, source, ill) in enumerate(RAIL):
        col = idx % 3
        row = idx // 3
        draw_rail_tile(MX + col * (tile_w + 10), rail_y[row], tile_w,
                       rail_h[row], kicker, headline, summary, source, ill)

    # --- map + legend -----------------------------------------------------
    draw_text(MX, 818, "WHERE IT HAPPENED", 11, "BOLD", INK)
    draw_map(MX, 822, 232, 54)
    lx, ly = MX, 882
    for i, (num, name, _px, _py) in enumerate(MAP_PINS):
        col = i % 2
        row = i // 2
        px = lx + col * 118
        py = ly + row * 7.5
        circle(px + 5, py + 2, 5, RED)
        draw_text(px + 5, py + 5, num, 6.5, "BOLD", WHITE, "center")
        draw_text(px + 14, py + 6, name, 8, "BOLD", INK)

    # --- ALSO ON ----------------------------------------------------------
    ax = 274
    draw_text(ax, 818, "ALSO ON", 12, "BOLD", RED)
    draw_text(ax + 78, 818, "— the rest of Friday in brief", 11, "REGULAR",
              GREY)
    col_w = 355
    for i, (num, place, fact, src) in enumerate(ALSO_ON):
        col = i % 2
        row = i // 2
        x = ax + col * (col_w + 12)
        y = 830 + row * 11
        line = "%s %s — %s (%s)" % (num, place, fact, src)
        draw_text(x, y, line, 8.5, "BOLD", INK)

    # --- DATE CHECK -------------------------------------------------------
    rect(MX, 922, RX, 976, (253, 244, 230))
    border(MX, 922, RX, 976, RED, 3)
    dlines = wrap("DATE CHECK — " + DATE_CHECK, 9.5, "REGULAR", RX - MX - 24)
    draw_lines(MX + 12, 926, dlines[:5], 9.5, 10.5, "REGULAR", INK)

    # --- footer -----------------------------------------------------------
    draw_text(512, 994,
              "Friday 20 November 2026 · Sources: IMD, The Hindu, Reuters, "
              "AP, AFP, ESA, UN News, ICC, ENA, FIFA, ATP, RNZ, UKMTO, "
              "CGIL, SBS, PBOC · Original drawings, made in code. "
              "Compiled 20 Nov 2026.",
              9, "REGULAR", (70, 64, 52), "center")


# --- PNG encoder -----------------------------------------------------------
def chunk(typ, data):
    c = struct.pack(">I", len(data)) + typ + data
    c += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
    return c


def write_png(path):
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        for x in range(W):
            r = g = b = 0
            for dy in range(SS):
                for dx in range(SS):
                    o = ((y * SS + dy) * W2 + (x * SS + dx)) * 3
                    r += buf[o]
                    g += buf[o + 1]
                    b += buf[o + 2]
            raw.append(r // (SS * SS))
            raw.append(g // (SS * SS))
            raw.append(b // (SS * SS))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


if __name__ == "__main__":
    build()
    n = write_png(sys.argv[1] if len(sys.argv) > 1 else "entry.png")
    print("wrote entry.png: %d bytes" % n)
