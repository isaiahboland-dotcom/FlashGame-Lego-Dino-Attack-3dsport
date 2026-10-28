#!/usr/bin/env python3
"""Build the 3DS-port skeleton asset set: pack a subset of atlas sprites into
small sheets, convert to T3X via tex3ds, and emit a C header with the sprite
table + dino state meta.

Usage: gen_skeleton.py
Outputs:
  /workspace/dino-port/gfx/atlas_*.png -> .t3x (via tex3ds)
  /workspace/dino-port/source/gfx_meta.h
"""
import os
import json
import subprocess
import argparse
from PIL import Image

SRC = "/workspace/assets3ds"
OUT = "/workspace/dino-port/gfx"
HDR = "/workspace/dino-port/source/gfx_meta.h"
TEX3DS = "/opt/devkitpro/tools/bin/tex3ds"
SHEET = 512

NEEDED = [
    # (prefix, count limit or None)
    ("dino/t_rex_vert/wait", None),
    ("dino/t_rex_vert/zone", None),
    ("boss/", None),
    ("hud/main/health", None),
    ("hud/main/radar", None),
    ("hud/main/score", None),
    ("tile/background/", None),
    ("tile/foreground/", None),
    ("vehicle/hammer/pose", None),
    ("vehicle/predator/turret", None),
    ("vehicle/typhon/rotor/", None),
    ("projectile/", None),
    ("enemy/", None),
    ("pickup/", None),
    ("prop/", None),
    ("menu/background", None),
]


def natkey(k):
    """Natural sort so state frame lists come out in numeric frame order."""
    import re
    return [int(t) if t.isdigit() else t
            for t in re.split(r"(\d+)", k)]


def main():
    global SRC, OUT, HDR, TEX3DS
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default=SRC)
    parser.add_argument("--project", default="/workspace/dino-port")
    parser.add_argument("--tex3ds", default=TEX3DS)
    args = parser.parse_args()
    SRC, TEX3DS = args.src, args.tex3ds
    OUT = os.path.join(args.project, "gfx")
    HDR = os.path.join(args.project, "source", "gfx_meta.h")
    m = json.load(open(os.path.join(SRC, "atlas_meta.json")))
    sprites = m["sprites"]
    want = [k for k in sprites
            if any(k.startswith(p) for p, _ in NEEDED)]
    want.sort(key=natkey)
    # keep states: also need the dino state meta
    dino_meta = m["data"]["dino/t_rex_vert"]
    os.makedirs(OUT, exist_ok=True)
    # repack subset
    imgs = []
    for k in want:
        s = sprites[k]
        sheet = Image.open(os.path.join(SRC, "atlas_%02d.png" % s["sheet"]))
        img = sheet.crop((s["x"], s["y"], s["x"] + s["w"], s["y"] + s["h"]))
        imgs.append((k, img))
    # simple shelf pack at 512x512
    sheets = []
    placed = {}
    order = sorted(range(len(imgs)),
                   key=lambda i: (-imgs[i][1].size[1], -imgs[i][1].size[0]))
    for i in order:
        k, img = imgs[i]
        w, h = img.size
        if w > SHEET or h > SHEET:
            raise ValueError("sprite exceeds sheet size: %s" % k)
        ok = False
        for si, sh in enumerate(sheets):
            for row in sh:
                if row["x"] + w <= SHEET and h <= row["h"]:
                    placed[k] = (si, row["x"], row["y"])
                    row["x"] += w + 1
                    ok = True
                    break
            if ok:
                break
        if not ok:
            for si, sh in enumerate(sheets):
                used = sum(r["h"] + 1 for r in sh)
                if used + h <= SHEET:
                    sh.append({"y": used, "h": h, "x": w + 1})
                    placed[k] = (si, 0, used)
                    ok = True
                    break
        if not ok:
            sheets.append([{"y": 0, "h": h, "x": w + 1}])
            placed[k] = (len(sheets) - 1, 0, 0)
    canvases = [Image.new("RGBA", (SHEET, SHEET), (0, 0, 0, 0))
                for _ in sheets]
    for k, img in imgs:
        si, x, y = placed[k]
        canvases[si].paste(img, (x, y))
    nsheets = len(canvases)
    for i, cv in enumerate(canvases):
        png = os.path.join(OUT, "atlas_%d.png" % i)
        cv.save(png)
        t3x = os.path.join(OUT, "atlas_%d.t3x" % i)
        subprocess.run([TEX3DS, "-f", "rgba4", "-o", t3x, png], check=True)
    # header
    with open(HDR, "w") as fh:
        fh.write("#pragma once\n#include <stdint.h>\n\n")
        fh.write("#define GFX_SHEETS %d\n" % nsheets)
        fh.write("#define DINO_CANVAS_W %d\n#define DINO_CANVAS_H %d\n" % tuple(dino_meta["size"]))
        for i in range(nsheets):
            fh.write("extern const uint8_t atlas_%d_t3x[];\nextern const uint32_t atlas_%d_t3x_size;\n" % (i, i))
        fh.write("static const uint8_t *const GFX_DATA[] = {%s};\n" % ",".join("atlas_%d_t3x" % i for i in range(nsheets)))
        fh.write("static const uint32_t *const GFX_DATA_SIZE[] = {%s};\n" % ",".join("&atlas_%d_t3x_size" % i for i in range(nsheets)))
        fh.write("typedef struct { int sheet,x,y,w,h,ox,oy,fw,fh; } Gfx;\n")
        fh.write("static const Gfx GFX[] = {\n")
        for k in want:
            s = sprites[k]
            si, x, y = placed[k]
            fh.write(' { %d,%d,%d,%d,%d,%d,%d,%d,%d }, /* %s */\n'
                     % (si, x, y, s["w"], s["h"], s["ox"], s["oy"],
                        s["fw"], s["fh"], k))
        fh.write("};\n#define GFX_N %d\n" % len(want))
        # name index
        fh.write("static const char* GFX_KEY[] = {\n")
        for k in want:
            fh.write(' "%s",\n' % k)
        fh.write("};\n")
        # dino state meta
        fh.write("static const char DINO_STATES[] =\n")
        st = json.dumps(dino_meta["states"])
        for i in range(0, len(st), 100):
            fh.write(' "%s"\n' % st[i:i + 100].replace('"', '\\"'))
        fh.write(";\n")
    print("skeleton: %d sprites -> %d sheets" % (len(want), nsheets))


if __name__ == "__main__":
    main()
