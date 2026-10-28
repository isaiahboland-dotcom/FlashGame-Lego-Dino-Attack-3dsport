#!/usr/bin/env python3
"""Compile SWF sprite trees (from tools/swf.py) into per-frame geometry.

For each character id, produces:
  labels {name: 1-based frame}
  per-frame {bbox:[x0,y0,x1,y1], hits:{name:(x,y)}, parts:[{name,char,matrix}]}

Handles PlaceObject 'move' merging by depth, RemoveObject2 clearing, and
recursion into child sprites (child resolved per-frame; static children
unioned over their whole timeline).

Usage: python3 resolve.py parsed.json --json out.json [--links]
"""
import sys, json, argparse

ID = {"sx": 1.0, "sy": 1.0, "r0": 0.0, "r1": 0.0, "tx": 0.0, "ty": 0.0}


def compose(a, b):
    """Compose matrices A*B (SWF layout [sx r1 tx / r0 sy ty])."""
    return {
        "sx": a["sx"] * b["sx"] + a["r1"] * b["r0"],
        "r1": a["sx"] * b["r1"] + a["r1"] * b["sy"],
        "r0": a["r0"] * b["sx"] + a["sy"] * b["r0"],
        "sy": a["r0"] * b["r1"] + a["sy"] * b["sy"],
        "tx": a["sx"] * b["tx"] + a["r1"] * b["ty"] + a["tx"],
        "ty": a["r0"] * b["tx"] + a["sy"] * b["ty"] + a["ty"],
    }


def transform_box(b, m):
    x0, y0, x1, y1 = b
    pts = [(x0, y0), (x0, y1), (x1, y0), (x1, y1)]
    xs, ys = [], []
    for px, py in pts:
        xs.append(m["sx"] * px + m["r1"] * py + m["tx"])
        ys.append(m["r0"] * px + m["sy"] * py + m["ty"])
    return [min(xs), min(ys), max(xs), max(ys)]


def grow(un, cb):
    if un[0] is None:
        return [cb[0], cb[1], cb[2], cb[3]]
    un[0] = min(un[0], cb[0])
    un[1] = min(un[1], cb[1])
    un[2] = max(un[2], cb[2])
    un[3] = max(un[3], cb[3])
    return un


class Resolver:
    def __init__(self, parsed):
        self.sprites = {int(k): v for k, v in parsed["sprites"].items()}
        self.shapes = {int(k): v for k, v in parsed["shapes"].items()}
        self.exports = {n: cid for n, cid in parsed["exports"]}
        self.exports_rev = {}
        for n, cid in parsed["exports"]:
            self.exports_rev.setdefault(cid, []).append(n)
        self._compiled = {}
        self._rbbox = {}

    # -------- per-depth placement state across the timeline --------
    def frame_states(self, cid):
        sp = self.sprites[cid]
        state = {}
        out = []
        for fr in sp["frames"]:
            for d in fr["rm"]:
                state.pop(d, None)
            for pl in fr["place"]:
                depth = pl["depth"]
                if pl.get("move") and depth in state:
                    merged = dict(state[depth])
                    for k in ("char", "matrix", "name"):
                        if k in pl:
                            merged[k] = pl[k]
                    state[depth] = merged
                else:
                    state[depth] = pl
            # keep insertion order of depths deterministic
            out.append([state[d] for d in sorted(state)])
        return out

    # -------- recursive bounds --------
    def bbox_recursive(self, cid, m, seen=None):
        if seen is None:
            seen = set()
        if cid in seen:
            return None
        b = self.shapes.get(cid)
        if b is not None:
            return transform_box([b[0], b[2], b[1], b[3]], m)
        if cid not in self.sprites:
            return None
        # compute (or recall) the union in this sprite's LOCAL space
        if cid not in self._rbbox:
            sp = self.sprites[cid]
            st = {}
            union = None
            seen = set(seen)
            seen.add(cid)
            for fr in sp["frames"]:
                for d in fr["rm"]:
                    st.pop(d, None)
                for pl in fr["place"]:
                    depth = pl["depth"]
                    if pl.get("move") and depth in st:
                        merged = dict(st[depth])
                        for k in ("char", "matrix", "name"):
                            if k in pl:
                                merged[k] = pl[k]
                        st[depth] = merged
                    else:
                        st[depth] = pl
                for pl in st.values():
                    ch = pl.get("char")
                    if ch is None:
                        continue
                    cb = self.bbox_recursive(ch, compose(ID, pl.get("matrix") or ID), seen)
                    if cb is not None:
                        union = cb if union is None else grow(union, cb)
            self._rbbox[cid] = union
            if union is None:
                return None
            return transform_box(union, m)
        local = self._rbbox[cid]
        return transform_box(local, m) if local is not None else None

    # -------- per-frame compile --------
    def compile(self, cid):
        """Per-frame geometry of sprite cid: bbox/hits/parts."""
        if cid in self._compiled:
            return self._compiled[cid]
        if cid not in self.sprites:
            return None
        sp = self.sprites[cid]
        frames = []
        for i, placements in enumerate(self.frame_states(cid)):
            parts = []
            hits = {}
            un = [None, None, None, None]
            for pl in placements:
                ch = pl.get("char")
                if ch is None:
                    continue
                m = pl.get("matrix")
                nm = pl.get("name")
                cb = self.bbox_recursive(ch, m or ID)
                parts.append({"name": nm, "char": ch, "matrix": m, "bbox": cb,
                              "cxform": pl.get("cxform")})
                if nm and nm.startswith("mcHit") and m:
                    hits[nm] = [round(m["tx"], 2), round(m["ty"], 2)]
                if cb is not None:
                    un = grow(un, cb)
            if un[0] is None:
                un = [0.0, 0.0, 0.0, 0.0]
            frames.append({"bbox": [round(v, 2) for v in un],
                           "hits": hits, "parts": parts})
        info = {"labels": sp.get("labels", {}),
                "declared_frames": sp["declared_frames"],
                "frame_count": len(frames), "frames": frames}
        self._compiled[cid] = info
        return info

    def compile_exported(self):
        out = {}
        for name, cid in self.exports.items():
            out[name] = {"cid": cid, "out": self.compile(cid)}
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("parsed")
    ap.add_argument("--json")
    ap.add_argument("--links", action="store_true")
    ap.add_argument("--cid", type=int, default=None)
    args = ap.parse_args()
    parsed = json.load(open(args.parsed))
    r = Resolver(parsed)
    if args.cid is not None:
        c = r.compile(args.cid)
        print(json.dumps(c, indent=1))
        return
    ex = r.compile_exported()
    if args.links:
        for n, e in ex.items():
            if e["out"]:
                o = e["out"]
                print("%-22s cid=%-5d frames=%3d labels=%s" % (
                    n, e["cid"], o["frame_count"], list(o["labels"].items())))
    if args.json:
        json.dump({"exports": {k: {"cid": v["cid"], "compiled": v["out"]}
                               for k, v in ex.items()},
                   "shapes": {str(k): v for k, v in r.shapes.items()}},
                  open(args.json, "w"))


if __name__ == "__main__":
    main()
