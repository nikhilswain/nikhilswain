"""Turn assets/luffy.jpg into coloured ASCII art (assets/ascii.json).

Run locally once (needs Pillow). The daily build only reads the JSON, so the
GitHub Action does not need any image libraries.

    python scripts/make_ascii.py [cols]
"""
import json
import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "luffy.jpg"
OUT = ROOT / "assets" / "ascii.json"

COLS = int(sys.argv[1]) if len(sys.argv) > 1 else 52
CHAR_ASPECT = 0.547  # char width / line height (10px font, 11px lines)
RAMP = " .:-=+*#%@"  # sparse -> dense


def is_background(rgb):
    r, g, b = rgb
    # blue sky and white/grey clouds: blue channel at least as strong as red
    return b >= r - 6 and b > 120


def background_mask(img):
    """Flood-fill sky/cloud pixels connected to the image border."""
    w, h = img.size
    px = img.load()
    bg = bytearray(w * h)
    q = deque()
    for x in range(w):
        q.extend([(x, 0), (x, h - 1)])
    for y in range(h):
        q.extend([(0, y), (w - 1, y)])
    while q:
        x, y = q.popleft()
        i = y * w + x
        if bg[i] or not is_background(px[x, y]):
            continue
        bg[i] = 1
        if x > 0: q.append((x - 1, y))
        if x < w - 1: q.append((x + 1, y))
        if y > 0: q.append((x, y - 1))
        if y < h - 1: q.append((x, y + 1))
    return bg


def main():
    img = Image.open(SRC).convert("RGB")
    w, h = img.size
    mask = background_mask(img)
    edges = img.convert("L").filter(ImageFilter.FIND_EDGES).load()
    px = img.load()

    rows = round(COLS * (h / w) * CHAR_ASPECT)
    cw, ch = w / COLS, h / rows
    grid = []
    for r in range(rows):
        line = []
        for c in range(COLS):
            x0, x1 = int(c * cw), int((c + 1) * cw)
            y0, y1 = int(r * ch), int((r + 1) * ch)
            tot = fg = 0
            sr = sg = sb = se = 0
            for y in range(y0, y1):
                for x in range(x0, x1):
                    tot += 1
                    if mask[y * w + x]:
                        continue
                    fg += 1
                    p = px[x, y]
                    sr += p[0]; sg += p[1]; sb += p[2]
                    se += edges[x, y]
            if fg < tot * 0.35:
                line.append([" ", None])
                continue
            rgb = (sr // fg, sg // fg, sb // fg)
            lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
            edge = se / fg
            if lum < 70:
                # black hair / outlines: dense glyph, tinted later per theme
                ch_ = "#" if lum < 45 else "%"
                line.append([ch_, "ink"])
                continue
            idx = 1 + int((lum / 255) * (len(RAMP) - 2) + 0.5)
            if edge > 60:
                idx = max(idx - 2, 1)  # soften cells that sit on a line
            line.append([RAMP[min(idx, len(RAMP) - 1)], "#%02x%02x%02x" % rgb])
        grid.append(line)

    # trim empty rows top/bottom and empty columns left/right
    def empty_row(l): return all(ch == " " for ch, _ in l)
    while grid and empty_row(grid[0]): grid.pop(0)
    while grid and empty_row(grid[-1]): grid.pop()
    left = min(next(i for i, (ch, _) in enumerate(l) if ch != " ") for l in grid if not empty_row(l))
    right = max(max(i for i, (ch, _) in enumerate(l) if ch != " ") for l in grid if not empty_row(l))
    grid = [l[left:right + 1] for l in grid]

    OUT.write_text(json.dumps({"cols": len(grid[0]), "rows": len(grid), "cells": grid}))
    for l in grid:
        print("".join(ch for ch, _ in l))
    print(f"{len(grid[0])}x{len(grid)} -> {OUT}")


if __name__ == "__main__":
    main()
