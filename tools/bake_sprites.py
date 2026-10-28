#!/usr/bin/env python3
"""Compose baked sprites from ffdec frame PNGs + resolved placements.

Coordinate convention: SWF matrix [sx r1 tx / r0 sy ty] maps local (x,y) -> abs
(x',y'). All bboxes are px (twips/20), origin = container origin.

Bake products live under /workspace/bake/<swf>/<item>/...
"""
import os
import sys
import glob
import json
import math
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from resolve import Resolver, compose, transform_box  # noqa: E402
from PIL import Image  # noqa: E402

SPR_ROOT = "/workspace/assets/spr"
BAKE_ROOT = "/workspace/bake"
ID = {"sx": 1.0, "sy": 1.0, "r0": 0.0, "r1": 0.0, "tx": 0.0, "ty": 0.0}


def _mul(m, k):
    return {q: v * k for q, v in m.items()}


def _extent(m, w, h):
    corners = [(0, 0), (w, 0), (0, h), (w, h)]
    pts = [
        (m["sx"] * x + m["r1"] * y + m["tx"], m["r0"] * x + m["sy"] * y + m["ty"])
        for x, y in corners
    ]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


class Sheet:
    def __init__(self, swfn, resolver):
        self.swfn = swfn
        self.r = resolver
        self._cache = {}

    def pngs(self, cid):
        """{frame: path} for a char id, with linkage-suffixed dir fallback."""
        key = (self.swfn, int(cid))
        if key in self._cache:
            return self._cache[key]
        base = os.path.join(SPR_ROOT, self.swfn)
        hits = []
        stem = "DefineSprite_%d" % int(cid)
        dirs = [d for parent in (base, os.path.join(base, "sprites"))
                for d in glob.glob(os.path.join(parent, stem + "*"))
                if os.path.basename(d) == stem or os.path.basename(d).startswith(stem + "_")]
        # Prefer the unsuffixed directory, then use linkage aliases deterministically.
        for d in sorted(dirs, key=lambda path: (os.path.basename(path) != stem, path)):
            for f in sorted(glob.glob(os.path.join(d, "*.png"))):
                hits.append((int(os.path.splitext(os.path.basename(f))[0]), f))
        out = {}
        # a char may export under several dirs (linkage aliases); dir order stable
        for fr, path in hits:
            out.setdefault(fr, path)
        self._cache[key] = out
        return out

    def png(self, cid, frame):
        got = self.pngs(cid).get(int(frame))
        if not got:
            raise IOError("no image %s/%s f%d" % (self.swfn, cid, frame))
        return Image.open(got).convert("RGBA")

    def bbox(self, cid):
        return self.r.bbox_recursive(int(cid), ID)

    def spng(self, cid):
        """Raw DefineShape PNG (ffdec -format shape:png export)."""
        key = ("shape", self.swfn, int(cid))
        if key not in self._cache:
            p = os.path.join(SPR_ROOT, self.swfn, "shapes", "%d.png" % cid)
            self._cache[key] = Image.open(p).convert("RGBA")
        return self._cache[key]

    def art_off(self, cid):
        b = self.bbox(cid)
        return {"sx": 1.0, "sy": 1.0, "r0": 0.0, "r1": 0.0,
                "tx": b[0], "ty": b[1]}


def chain_cx(a, b):
    """Combine two cxforms (0..1 color space): out = in*mul + add."""
    if a is None:
        return b
    if b is None:
        return a
    mul = [a["mul"][i] * b["mul"][i] for i in range(4)]
    add = [a["add"][i] * b["mul"][i] + b["add"][i] for i in range(4)]
    return {"mul": mul, "add": add}


def apply_cx(img, cx):
    if not cx:
        return img
    import numpy as np
    arr = np.asarray(img).astype(np.float32) / 255.0
    m = cx["mul"]
    a = cx["add"]
    for i in range(4):
        arr[..., i] = arr[..., i] * m[i] + a[i]
    arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def paste_affine(canvas, img, m):
    """Draw img (RGBA) onto canvas so that img(x,y) lands at m @ (x,y)."""
    w, h = img.size
    x0, y0, x1, y1 = _extent(m, w, h)
    bx0, by0 = int(math.floor(x0)) - 2, int(math.floor(y0)) - 2
    bx1, by1 = int(math.ceil(x1)) + 3, int(math.ceil(y1)) + 3
    ox, oy = -bx0, -by0  # destination crop offset
    out_size = (bx1 - bx0, by1 - by0)
    det = m["sx"] * m["sy"] - m["r0"] * m["r1"]
    if abs(det) < 1e-12:
        return
    a = m["sy"] / det
    b = -m["r1"] / det
    cc = m["sx"] / det
    dd = -m["r0"] / det
    # inverse maps out -> in: in = Ainv @ (out + shift)
    Ainv00 = a
    Ainv01 = b
    Ainv10 = dd
    Ainv11 = cc
    oxv = -(Ainv00 * (ox + m["tx"]) + Ainv01 * (oy + m["ty"]))
    oyv = -(Ainv10 * (ox + m["tx"]) + Ainv11 * (oy + m["ty"]))
    data = (Ainv00, Ainv01, oxv, Ainv10, Ainv11, oyv)
    try:
        piece = img.transform(out_size, Image.AFFINE, data, resample=Image.BICUBIC,
                              fillcolor=(0, 0, 0, 0))
    except ValueError:
        return
    holder = Image.new("RGBA", out_size, (0, 0, 0, 0))
    holder.alpha_composite(piece)
    canvas.alpha_composite(holder, (bx0, by0))
    return (bx0, by0, bx1, by1)


def comp_items(items, canvas_size=None):
    """items: list of (image, matrix) drawn bottom -> top on shared canvas."""
    boxes = []
    for img, m in items:
        w, h = img.size
        boxes.append(_extent(m, w, h))
    u = [min(b[0] for b in boxes), min(b[1] for b in boxes),
         max(b[2] for b in boxes), max(b[3] for b in boxes)]
    if canvas_size is None:
        bx0 = int(math.floor(u[0])) - 2
        by0 = int(math.floor(u[1])) - 2
        bx1 = int(math.ceil(u[2])) + 3
        by1 = int(math.ceil(u[3])) + 3
        canvas_size = (bx1 - bx0, by1 - by0)
        origin = (bx0, by0)
    else:
        origin = (0, 0)
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    shift = {"sx": 1.0, "sy": 1.0, "r0": 0.0, "r1": 0.0,
             "tx": -origin[0], "ty": -origin[1]}
    for img, m in items:
        paste_affine(canvas, img, compose(shift, m))
    return canvas, origin


def union_box(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


# --------------------------------------------------------------------------
def bake_dino(sh, expname, outdir):
    """Generic top-view dino baker.

    Container frame1 placements:
      mcRep    -> zone clip (baked separately; engine toggles visibility)
      mcShade  -> per-state black shadow arts (t_rex family)   [optional]
      <unnamed art with mul[0,0,0,a]> -> static shadow shape   [optional]
      mcHurt   -> mcMob -> per-state body arts
    """
    tr = sh.r.exports[expname]
    parts = sh.r.compile(tr)["frames"][0]["parts"]
    byname = {p.get("name"): p for p in parts if p.get("name")}
    mcRep = byname["mcRep"]["char"]
    mcShade = byname.get("mcShade")
    mcHurt = byname["mcHurt"]
    rep_parts = sh.r.compile(mcRep)["frames"][0]["parts"]
    zpart = next(p for p in rep_parts if p.get("name") == "mcZone")
    zone_clip, zone_m = zpart["char"], zpart["matrix"]

    hparts = sh.r.compile(mcHurt["char"])["frames"][0]["parts"]
    mcMob = next(p for p in hparts if p.get("name") == "mcMob")
    cx_mob = mcMob.get("cxform")
    mob_parts = sh.r.compile(mcMob["char"])
    s343 = sh.r.sprites[byname["mcShade"]["char"]] if mcShade else None
    sh_states = s343.get("labels", {}) if s343 else mob_parts.get("labels", {})

    M_shade = byname["mcShade"]["matrix"] if mcShade else None
    cx_shade = byname["mcShade"].get("cxform") if mcShade else None
    cx_hurt = mcHurt.get("cxform")
    cx_body = chain_cx(cx_hurt, cx_mob)

    # static shadow shape (raptor/ptero/lezard): unnamed placement w/ black mul
    static_shade = None
    for p in parts:
        if p.get("name") is None and p.get("cxform") and \
                all(v == 0.0 for v in p["cxform"]["mul"][:3]):
            static_shade = p
            break

    plan = {}
    for st, fs in sh_states.items():
        c_sh = sh.r.compile(mcShade["char"])["frames"][fs - 1]["parts"] if mcShade else None
        pl_sh = next((p for p in c_sh if p.get("name") == "mcAnim"), None)
        c_bs = mob_parts["frames"][fs - 1]["parts"]
        pl_bd = next((p for p in c_bs if p.get("name") == "mcAnim"), None)
        if not pl_bd:
            continue
        M = pl_bd["matrix"]
        cid_bd = pl_bd["char"]
        cid_sh = pl_sh["char"] if pl_sh else None
        T = sh.r.sprites[cid_sh]["declared_frames"] if cid_sh else 1
        Td = sh.r.sprites[cid_bd]["declared_frames"]
        plan[st] = (cid_sh, cid_bd, T, Td, M, fs)
    boxes = []
    for st, (cid_sh, cid_bd, T, Td, M, fs) in plan.items():
        if cid_sh and T in sh.pngs(cid_sh):
            boxes.append(transform_box(sh.bbox(cid_sh), compose(M_shade, M)))
        if Td in sh.pngs(cid_bd):
            boxes.append(transform_box(sh.bbox(cid_bd), M))
    if static_shade is not None:
        boxes.append(transform_box(sh.bbox(static_shade["char"]),
                                   static_shade["matrix"] or ID))
    boxes.append(transform_box(sh.bbox(zone_clip), zone_m))
    u = union_box(boxes)
    box = (int(math.floor(u[0])) - 2, int(math.floor(u[1])) - 2,
           int(math.ceil(u[2])) + 3, int(math.ceil(u[3])) + 3)
    origin = (-box[0], -box[1])
    W, H = box[2] - box[0], box[3] - box[1]
    canvas_size = (W, H)
    shift = {"sx": 1.0, "sy": 1.0, "r0": 0.0, "r1": 0.0,
             "tx": origin[0], "ty": origin[1]}
    meta = {"exp": expname, "states": {}, "container": [tr],
            "hits": select_hits(sh, sh.r.sprites[mcRep]),
            "origin": [origin[0], origin[1]], "size": [W, H],
            "tint": {"mul": [round(v, 4) for v in cx_body["mul"]],
                     "add": [round(v, 4) for v in cx_body["add"]]}}
    os.makedirs(outdir, exist_ok=True)

    # zone sprite (separate; engine toggles)
    zone_img = sh.png(zone_clip, 1)
    zc, _ = comp_items([(zone_img, compose(shift, compose(zone_m,
                       sh.art_off(zone_clip))))],
                       canvas_size=canvas_size)
    zc.save(os.path.join(outdir, "zone.png"))

    layers_static = []
    if static_shade is not None:
        layers_static.append((apply_cx(sh.png(static_shade["char"], 1),
                                       static_shade.get("cxform")),
                              compose(shift, compose(static_shade["matrix"] or ID,
                                                     sh.art_off(static_shade["char"])))))

    for st, (cid_sh, cid_bd, T, Td, M, fs) in plan.items():
        os.makedirs(os.path.join(outdir, st), exist_ok=True)
        frames = []
        for t in range(1, max(T, Td) + 1):
            items = list(layers_static)
            if cid_sh and t <= T:
                cx = chain_cx(cx_shade, None)
                items.append((apply_cx(sh.png(cid_sh, t), cx),
                              compose(shift, compose(M_shade,
                                      compose(M, sh.art_off(cid_sh))))))
            if t <= Td:
                items.append((apply_cx(sh.png(cid_bd, t), cx_body),
                              compose(shift, compose(M, sh.art_off(cid_bd)))))
            canvas, _ = comp_items(items, canvas_size=canvas_size)
            fn = os.path.join(outdir, st, "f%03d.png" % t)
            canvas.save(fn)
            frames.append("/".join([st, os.path.basename(fn)]))
        meta["states"][st] = {"frames": frames, "T": T, "Td": Td, "frame1": fs}
    with open(os.path.join(outdir, "meta.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    print("baked", expname, "states", list(plan), "->", outdir)


def select_hits(sh, rep_sprite):
    out = {}
    f0 = rep_sprite["frames"][0]
    for p in f0["place"]:
        nm = p.get("name", "")
        if nm.startswith("mcHit") or nm in ("mcView", "mcZone", "mcShoot"):
            M = p["matrix"]
            out[nm] = [M["tx"], M["ty"]]
    return out


def bake_shots(sh, outdir, names):
    os.makedirs(outdir, exist_ok=True)
    meta = {}
    for nm in names:
        cid = sh.r.exports.get(nm)
        if cid is None:
            print("missing", nm)
            continue
        pngs = sh.pngs(cid)
        T = max(pngs)
        files = {}
        for f in range(1, T + 1):
            img = sh.png(cid, f)
            bb = img.getbbox()
            dest = os.path.join(outdir, nm)
            os.makedirs(dest, exist_ok=True)
            if bb:
                img = img.crop(bb)
                img.save(os.path.join(dest, "f%03d.png" % f))
                files[f] = [img.size[0], img.size[1], bb[0], bb[1]]
            else:
                files[f] = None
        meta[nm] = {"frames": files, "T": T}
    with open(os.path.join(outdir, "meta.json"), "w") as fh:
        json.dump(meta, fh, indent=1)


def _anchor_pos(sh, cid, m):
    """Center of a marker shape placed at matrix m (container-local px)."""
    b = sh.bbox(cid)
    cx = (b[0] + b[2]) / 2.0
    cy = (b[1] + b[3]) / 2.0
    return [round(m["sx"] * cx + m["r1"] * cy + m["tx"], 2),
            round(m["r0"] * cx + m["sy"] * cy + m["ty"], 2)]


def bake_vehicle(sh, outdir):
    """Bake player vehicle: chassis poses (w/ shade), turret, zone, anchors."""
    r = sh.r
    expname = list(r.exports)[0]
    top = r.exports[expname]
    parts = r.compile(top)["frames"][0]["parts"]
    byname = {p.get("name"): p for p in parts if p.get("name")}
    rep, shade_clip, mob = byname["mcRep"], byname["mcShade"], byname["mcMob"]
    M_shade = shade_clip["matrix"]
    rep_parts = {p.get("name"): p for p in
                 r.compile(rep["char"])["frames"][0]["parts"] if p.get("name")}
    os.makedirs(outdir, exist_ok=True)

    # ---- anchors (container-local) ----
    anchors = {}
    for nm, p in rep_parts.items():
        if nm in ("mcZone", "mcPente"):
            continue
        ch = r.compile(p["char"])["frames"][0]["parts"][0]["char"]
        anchors[nm] = _anchor_pos(sh, ch, p["matrix"])

    # ---- zone ----
    zp = rep_parts["mcZone"]
    zc_parts = r.compile(zp["char"])["frames"][0]["parts"]
    zone_cid = zc_parts[0]["char"]
    zone_m = compose(zp["matrix"], compose(zc_parts[0]["matrix"],
                                           {"sx": 1.0, "sy": 1.0, "r0": 0.0,
                                            "r1": 0.0,
                                            "tx": sh.bbox(zone_cid)[0],
                                            "ty": sh.bbox(zone_cid)[1]}))
    zone = sh.spng(zone_cid)
    zone.save(os.path.join(outdir, "zone.png"))
    zb = r.shapes[zone_cid]
    zone_box = transform_box([zb[0], zb[2], zb[1], zb[3]], zp["matrix"])

    # ---- pose plan ----
    mob_parts = r.compile(mob["char"])
    pente_m = next(p for p in mob_parts["frames"][0]["parts"]
                   if p.get("name") == "mcPente")
    pente_s = next(p for p in
                   r.compile(shade_clip["char"])["frames"][0]["parts"]
                   if p.get("name") == "mcPente")
    nposes = r.sprites[pente_m["char"]]["declared_frames"]
    plan = []
    for t in range(1, nposes + 1):
        fm = r.compile(pente_m["char"])["frames"][t - 1]["parts"]
        fs_ = r.compile(pente_s["char"])["frames"][t - 1]["parts"]
        pm = [p for p in fm if p.get("name") is None]
        ps = [p for p in fs_ if p.get("name") is None]
        extras = [p for p in fm
                  if p.get("name") not in (None, "mcPente")]
        plan.append((pm, ps, extras))

    # ---- canvas ----
    boxes = [zone_box]
    for pm, ps, extras in plan:
        for p in pm:
            boxes.append(transform_box(sh.bbox(p["char"]), p["matrix"]))
        for p in ps:
            boxes.append(transform_box(sh.bbox(p["char"]),
                                       compose(M_shade, p["matrix"])))
    u = union_box(boxes)
    box = (int(math.floor(u[0])) - 2, int(math.floor(u[1])) - 2,
           int(math.ceil(u[2])) + 3, int(math.ceil(u[3])) + 3)
    origin = (-box[0], -box[1])
    W, H = box[2] - box[0], box[3] - box[1]
    shift = {"sx": 1.0, "sy": 1.0, "r0": 0.0, "r1": 0.0,
             "tx": origin[0], "ty": origin[1]}

    zc, _ = comp_items([(zone, compose(shift, zone_m))], canvas_size=(W, H))
    zc.save(os.path.join(outdir, "zone.png"))

    # ---- turret ----
    turret = {}
    tour = next((p for p in plan[0][2] if p.get("name") == "mcTour"), None)
    if tour is not None:
        item = next(p for p in r.compile(tour["char"])["frames"][0]["parts"]
                    if p.get("name") == "mcItem")

        def rec(cid, base, out, depth=0):
            if depth > 4 or cid in seen_rec:
                return
            seen_rec.add(cid)
            for p in r.compile(cid)["frames"][0]["parts"]:
                m = compose(base, p["matrix"])
                ch = p["char"]
                if ch in r.sprites:
                    if p.get("name") and p.get("name").startswith("mcShoot"):
                        out["anchors"][p["name"]] = [round(m["tx"], 2),
                                                     round(m["ty"], 2)]
                    else:
                        rec(ch, m, out, depth + 1)
                elif ch in r.shapes:
                    off = {"sx": 1.0, "sy": 1.0, "r0": 0.0, "r1": 0.0,
                           "tx": sh.bbox(ch)[0], "ty": sh.bbox(ch)[1]}
                    out["items"].append((sh.spng(ch), compose(m, off)))

        seen_rec = set()
        tout = {"items": [], "anchors": {}}
        rec(item["char"], item["matrix"], tout)
        titems, tanchors = tout["items"], tout["anchors"]
        tl = min(int(i[1]["tx"]) - 2 for i in titems)
        tt = min(int(i[1]["ty"]) - 2 for i in titems)
        tw = max(i[0].size[0] + int(i[1]["tx"]) + 2 for i in titems) - tl
        th = max(i[0].size[1] + int(i[1]["ty"]) + 2 for i in titems) - tt
        # Compose relative to the turret pivot without clipping negative coordinates.
        tc, turret_offset = comp_items(titems)
        tl, tt = turret_offset
        tw, th = tc.size
        tc.save(os.path.join(outdir, "turret.png"))
        turret = {"file": "turret.png", "origin": [-tl, -tt],
                  "size": [tw, th], "anchors": tanchors,
                  "tour_matrix": [tour["matrix"]["tx"], tour["matrix"]["ty"]]}

    # ---- pose frames ----
    poses = []
    for t, (pm, ps, extras) in enumerate(plan, 1):
        items = []
        for p in ps:
            shade_color = chain_cx(shade_clip.get("cxform"), pente_s.get("cxform"))
            shade_color = chain_cx(shade_color, p.get("cxform"))
            image = apply_cx(sh.spng(p["char"]), shade_color)
            matrix = compose(shift, compose(M_shade,
                             compose(p["matrix"], sh.art_off(p["char"]))))
            items.append((image, matrix))
        for p in pm:
            img = (sh.spng(p["char"]) if p["char"] in r.shapes
                   else sh.png(p["char"], 1))
            mch = compose(shift, compose(p["matrix"], sh.art_off(p["char"])))
            items.append((img, mch))
        cv, _ = comp_items(items, canvas_size=(W, H))
        fn = os.path.join(outdir, "pose_%02d.png" % t)
        cv.save(fn)
        poses.append("pose_%02d.png" % t)
        panchors = {}
        for p in extras:
            if p.get("name") and p.get("name").startswith("mcShoot"):
                ch2 = r.compile(p["char"])["frames"][0]["parts"][0]["char"]
                panchors[p["name"]] = _anchor_pos(sh, ch2, p["matrix"])
        plan[t - 1] = (pm, ps, panchors)

    rotor_frames = []
    if expname == "playertyphon":
        pm, ps, _ = plan[0]
        animated = [p for p in pm if p["char"] in r.sprites and len(sh.pngs(p["char"])) > 1]
        if not animated:
            raise ValueError("Typhon rotor animation missing")
        frame_count = min(6, max(len(sh.pngs(p["char"])) for p in animated))
        for frame in range(1, frame_count + 1):
            layers = []
            for p in ps:
                shade_color = chain_cx(shade_clip.get("cxform"), pente_s.get("cxform"))
                shade_color = chain_cx(shade_color, p.get("cxform"))
                layers.append((apply_cx(sh.spng(p["char"]), shade_color), compose(shift, compose(M_shade, compose(p["matrix"], sh.art_off(p["char"]))))))
            for p in pm:
                cid = p["char"]
                images = sh.pngs(cid) if cid in r.sprites else {}
                image = sh.png(cid, sorted(images)[(frame - 1) % len(images)]) if images else sh.spng(cid)
                layers.append((image, compose(shift, compose(p["matrix"], sh.art_off(cid)))))
            canvas, _ = comp_items(layers, canvas_size=(W, H))
            filename = "rotor_%02d.png" % frame
            canvas.save(os.path.join(outdir, filename))
            rotor_frames.append(filename)

    meta = {"exp": expname, "origin": [origin[0], origin[1]],
            "size": [W, H], "poses": poses, "rotor_frames": rotor_frames, "turret": turret,
            "anchors": anchors, "pose_anchors": {str(i + 1): plan[i][2]
                                                 for i in range(len(plan))},
            "labels": r.sprites[mob["char"]].get("labels")}
    with open(os.path.join(outdir, "meta.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    print("baked vehicle", expname, nposes, "poses ->", outdir)


def bake_cells(sh, outdir):
    """Index cell art: outer frame (L-1)//T+1 picks the mc char; inner frame
    (L-1)%T+1 picks its frame. Art = ffdec pngs (placements are identity)."""
    r = sh.r
    clip = r.exports["clip"]
    n_outer = r.sprites[clip]["declared_frames"]
    os.makedirs(outdir, exist_ok=True)
    meta = {"cells": {}}
    for fo in range(1, n_outer + 1):
        parts = r.compile(clip)["frames"][fo - 1]["parts"]
        mc = next(p for p in parts if p.get("name") == "mc")
        mcid = mc["char"]
        T = r.sprites[mcid]["declared_frames"]
        pngs = sh.pngs(mcid)
        b = sh.bbox(mcid)
        for fi in range(1, T + 1):
            label = (fo - 1) * T + fi
            if fi not in pngs:
                continue
            img = Image.open(pngs[fi])
            meta["cells"][label] = {"file": os.path.relpath(pngs[fi], "/workspace"),
                                    "w": img.size[0], "h": img.size[1],
                                    "off": [b[0], b[1]]}
    meta["cut"] = T
    meta["outer_frames"] = n_outer
    with open(os.path.join(outdir, "meta.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    print("indexed", len(meta["cells"]), "cells ->", outdir)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--swf", default="mobile")
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default=BAKE_ROOT)
    a = ap.parse_args()
    json_path = "/workspace/logs/tmp/%s.json" % a.swf
    with open(json_path) as fh:
        parsed = json.load(fh)
    r = Resolver(parsed)
    sh = Sheet(a.swf, r)
    items = a.only.split(",") if a.only else None
    if a.swf == "mobile":
        dinos = ["t_rex_vert", "t_rex_jaune", "t_rex_rouge", "raptor_rouge",
                 "raptor_jaune", "raptor_vert", "raptor_vert_sp", "ptero_rouge",
                 "ptero_jaune", "ptero_vert", "lezard_vert", "lezard_rouge",
                 "lezard_jaune"]
        for nm in dinos:
            if items and nm not in items:
                continue
            bake_dino(sh, nm, os.path.join(a.out, a.swf, nm))
        shots = ["lazer", "superflame", "flame", "intel", "dbz", "dbztyphon",
                 "choc", "fire", "acid", "plasma", "plasmatyphon"]
        bake_shots(sh, os.path.join(a.out, a.swf, "shots"), shots)
    elif a.swf in ("hammer", "predator", "typhon"):
        bake_vehicle(sh, os.path.join(a.out, a.swf, list(r.exports)[0]))
    elif a.swf in ("bclip", "fclip"):
        bake_cells(sh, os.path.join(a.out, a.swf))
    elif a.swf in ("kernel", "main", "intro"):
        bake_shots(sh, os.path.join(a.out, a.swf), list(r.exports))


if __name__ == "__main__":
    main()
