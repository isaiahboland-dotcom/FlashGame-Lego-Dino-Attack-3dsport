#!/usr/bin/env python3
"""Pack baked sprites into 512x512 RGBA atlas sheets + master meta.

Scans /workspace/bake for game assets, trims each frame to content, shelf-packs
into atlas sheets, and writes /workspace/assets3ds/atlas_meta.json describing
every sprite (sheet index, atlas rect, content offset, plus the original game
meta data for dinos/vehicles/cells/shots/HUD).
"""
import os
import json
import glob
from PIL import Image

BAKE = "/workspace/bake"
OUT = "/workspace/assets3ds"
SHEET = 512
PAD = 1
SCALE = 0.5  # game renders at ~0.48 on 3DS; bake textures at half res


def collect():
    """[(key, png_path, extra_meta_key_or_None)]"""
    items = []
    data = {}

    for dino in sorted(os.listdir(os.path.join(BAKE, "mobile"))):
        ddir = os.path.join(BAKE, "mobile", dino)
        if not os.path.isdir(ddir) or dino == "shots":
            continue
        meta = json.load(open(os.path.join(ddir, "meta.json")))
        items.append(("dino/%s/zone" % dino, os.path.join(ddir, "zone.png")))
        st = {}
        for name, sm in meta["states"].items():
            fr = []
            for rel in sm["frames"]:
                key = "dino/%s/%s" % (dino, rel.replace("/", "_")[:-4])
                items.append((key, os.path.join(ddir, rel)))
                fr.append(key)
            st[name] = {"frames": fr, "T": sm["T"], "Td": sm["Td"],
                        "frame1": sm["frame1"]}
        data["dino/%s" % dino] = {"origin": meta["origin"], "size": meta["size"],
                                  "states": st, "hits": meta["hits"]}
    for swf in ("hammer", "predator", "typhon"):
        vdir = os.path.join(BAKE, swf, "player%s" % swf)
        meta = json.load(open(os.path.join(vdir, "meta.json")))
        for p in sorted(glob.glob(os.path.join(vdir, "pose_*.png"))):
            items.append(("veh/%s/%s" % (swf, os.path.basename(p)[:-4]), p))
        items.append(("veh/%s/zone" % swf, os.path.join(vdir, "zone.png")))
        if meta.get("turret"):
            items.append(("veh/%s/turret" % swf,
                          os.path.join(vdir, meta["turret"]["file"])))
        data["veh/%s" % swf] = meta
    sdir = os.path.join(BAKE, "mobile", "shots")
    smeta = json.load(open(os.path.join(sdir, "meta.json")))
    for name, sm in smeta.items():
        fr = {}
        for f, info in sm["frames"].items():
            if info is None:
                continue
            key = "shot/%s/f%03d" % (name, int(f))
            items.append((key, os.path.join(sdir, name, "f%03d.png" % int(f))))
            fr[int(f)] = key
        data["shot/%s" % name] = {"T": sm["T"],
                                  "frames": {str(k): v for k, v in fr.items()}}
    for swf in ("bclip", "fclip"):
        cmeta = json.load(open(os.path.join(BAKE, swf, "meta.json")))
        cells = {}
        for label, cm in cmeta["cells"].items():
            key = "cell/%s/%s" % (swf[0], label)
            items.append((key, os.path.join("/workspace", cm["file"])))
            cells[label] = {"key": key, "off": cm["off"]}
        data["cells/%s" % swf] = {"cut": cmeta["cut"],
                                  "outer_frames": cmeta["outer_frames"],
                                  "cells": cells}
    for swf in ("kernel", "main", "intro"):
        root = os.path.join(BAKE, swf)
        fmeta = json.load(open(os.path.join(root, "meta.json")))
        hud = {}
        for name, sm in fmeta.items():
            fr = {}
            for f, info in sm["frames"].items():
                if info is None:
                    continue
                key = "hud/%s/%s/f%03d" % (swf, name, int(f))
                items.append((key, os.path.join(root, name,
                                                "f%03d.png" % int(f))))
                fr[int(f)] = key
            hud[name] = {"T": sm["T"], "frames": {str(k): v
                                                  for k, v in fr.items()}}
        data["hud/%s" % swf] = hud
    return items, data


def shelf_pack(rects):
    """rects = [(key, w, h)] -> {key: (sheet, x, y)}; shelf packing."""
    placed = {}
    sheets = []
    for key, w, h in sorted(rects, key=lambda t: (-t[2], -t[1])):
        done = False
        for si, sh in enumerate(sheets):
            for row in sh["rows"]:
                if row["x"] + w <= SHEET and row["y"] + h <= SHEET:
                    placed[key] = (si, row["x"], row["y"])
                    row["x"] += w + PAD
                    done = True
                    break
            if done:
                break
        if done:
            continue
        for si, sh in enumerate(sheets):
            if sh["used_y"] + h <= SHEET:
                sh["rows"].append({"y": sh["used_y"], "h": h, "x": w + PAD})
                sh["used_y"] += h + PAD
                placed[key] = (si, 0, sh["used_y"] - h - PAD)
                done = True
                break
        if not done:
            sheets.append({"rows": [{"y": 0, "h": h, "x": w + PAD}],
                           "used_y": h + PAD})
            placed[key] = (len(sheets) - 1, 0, 0)
    return sheets, placed


def main():
    items, data = collect()
    print("packing", len(items), "sprites at x%.2f" % SCALE)
    trimmed = []
    for key, path in items:
        img = Image.open(path).convert("RGBA")
        bb = img.getbbox()
        ox, oy = 0, 0
        if bb:
            img = img.crop(bb)
            ox, oy = bb[0], bb[1]
        fw, fh = img.size
        img = img.resize((max(1, round(fw * SCALE)),
                          max(1, round(fh * SCALE))), Image.LANCZOS)
        trimmed.append((key, img, ox, oy, fw, fh))
    sheets, placed = shelf_pack([(k, im.size[0], im.size[1])
                                 for k, im, _, _, _, _ in trimmed])
    os.makedirs(OUT, exist_ok=True)
    nsheets = len(sheets)
    canvases = [Image.new("RGBA", (SHEET, SHEET), (0, 0, 0, 0))
                for _ in range(nsheets)]
    sprites = {}
    for key, img, ox, oy, fw, fh in trimmed:
        si, x, y = placed[key]
        canvases[si].paste(img, (x, y))
        sprites[key] = {"sheet": si, "x": x, "y": y,
                        "w": img.size[0], "h": img.size[1],
                        "ox": ox, "oy": oy, "fw": fw, "fh": fh}
    for i, cv in enumerate(canvases):
        cv.save(os.path.join(OUT, "atlas_%02d.png" % i))
    with open(os.path.join(OUT, "atlas_meta.json"), "w") as fh:
        json.dump({"sheets": nsheets, "size": SHEET, "scale": SCALE,
                   "sprites": sprites, "data": data}, fh)
    print("%d sheets, %d sprites" % (nsheets, len(sprites)))


if __name__ == "__main__":
    main()
