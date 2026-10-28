#!/usr/bin/env python3
"""Minimal SWF (Flash 6-8, AS2-era) structural parser.

Extracts (no pixel decoding):
  - stage rect, fps, frame count, file version
  - ExportAssets  -> linkage name -> character id
  - FrameLabel    -> per-sprite timeline labels
  - PlaceObject/2/3 trees -> per-frame placements {char, name, matrix, depth}
  - DefineShape/2/3/4 bounds (twips -> px)
  - DefineSprite frame structure (nested)
  - DefineSound   -> raw MP3 payloads (SoundDataFormat 2), dumped to files

Usage:
  python3 swf.py <file.swf> [--json OUT.json] [--sounds DIR/]

Dumped sound files are named <charid>.mp3 plus a sounds.json index
linking ExportAssets names to char ids.
"""
import sys, json, zlib, struct


RATE_MAP = {0: 5512, 1: 11025, 2: 22050, 3: 44100}


class BitReader:
    __slots__ = ("d", "pos")

    def __init__(self, data, bytepos=0):
        self.d = data
        self.pos = bytepos * 8

    def u_bits(self, n):
        v = 0
        for _ in range(n):
            if self.pos >= len(self.d) * 8:
                raise EOFError("bit stream exhausted")
            b = self.d[self.pos >> 3]
            v = (v << 1) | ((b >> (7 - (self.pos & 7))) & 1)
            self.pos += 1
        return v

    def s_bits(self, n):
        if n == 0:
            return 0
        v = self.u_bits(n)
        if v & (1 << (n - 1)):
            v -= (1 << n)
        return v

    @property
    def byte_pos(self):
        return (self.pos + 7) >> 3

    def align(self):
        self.pos = (self.pos + 7) & ~7

    def u16(self):
        self.pos = (self.pos + 7) & ~7  # byte-align
        p = self.pos >> 3
        if p + 2 > len(self.d):
            raise EOFError("bit stream exhausted")
        v = self.d[p] | (self.d[p + 1] << 8)
        self.pos += 16
        return v


def read_rect(d, pos):
    br = BitReader(d, pos)
    n = br.u_bits(5)
    vals = [br.s_bits(n) for _ in range(4)]
    return vals, br.byte_pos


def read_matrix(br):
    if br.u_bits(1):
        ns = br.u_bits(5)
        sx = br.s_bits(ns) / 65536.0
        sy = br.s_bits(ns) / 65536.0
    else:
        sx = sy = 1.0
    if br.u_bits(1):
        nr = br.u_bits(5)
        r0 = br.s_bits(nr) / 65536.0
        r1 = br.s_bits(nr) / 65536.0
    else:
        r0 = r1 = 0.0
    nt = br.u_bits(5)
    tx = br.s_bits(nt) / 20.0
    ty = br.s_bits(nt) / 20.0
    return {"sx": sx, "sy": sy, "r0": r0, "r1": r1, "tx": tx, "ty": ty}


def read_cxform(br):
    has_add = br.u_bits(1)
    has_mul = br.u_bits(1)
    nb = br.u_bits(4)
    mul = [1.0, 1.0, 1.0, 1.0]
    add = [0.0, 0.0, 0.0, 0.0]
    if has_mul:
        mul = [br.s_bits(nb) / 256.0 for _ in range(4)]
    if has_add:
        add = [br.s_bits(nb) / 256.0 for _ in range(4)]
    return {"mul": mul, "add": add}


def parse_placeobj(code, d):
    o = {}
    d = bytes(d)
    br = BitReader(d, 0)
    if code == 4:  # PlaceObject: char, depth, matrix[, name]
        o["char"] = br.u16()
        o["depth"] = br.u16()
        o["matrix"] = read_matrix(br)
        o["name"] = ""
        try:
            p = br.byte_pos
            z = d.index(0, p)
            o["name"] = d[p:p + z].decode("utf8", "replace")
        except (ValueError, IndexError):
            pass
        return o
    f0 = br.u_bits(8)
    has_clip_depth = (f0 >> 6) & 1
    has_name = (f0 >> 5) & 1
    has_ratio = (f0 >> 4) & 1
    has_cxform = (f0 >> 3) & 1
    has_matrix = (f0 >> 2) & 1
    has_char = (f0 >> 1) & 1
    o["move"] = f0 & 1
    o["depth"] = br.u16()
    if has_char:
        o["char"] = br.u16()
    if has_matrix:
        o["matrix"] = read_matrix(br)
    if has_cxform:
        br.align()
        o["cxform"] = read_cxform(br)
    if has_ratio:
        o["ratio"] = br.u16()
    if has_name:
        br.align()
        p = br.byte_pos
        z = d.find(0, p)
        if z >= 0:
            o["name"] = d[p:z].decode("utf8", "replace")
            br.pos = (z + 1) * 8
    if has_clip_depth:
        o["clip_depth"] = br.u16()
    if f0 & 0x80:
        o["clip_actions"] = True
    return o


def parse_sound(data):
    """DefineSound (tag 14): SoundId, flags, sample count, mp3 frames."""
    sid, head = struct.unpack_from("<HB", data, 0)
    fmt = (head >> 4) & 0xF
    rate = (head >> 2) & 0x3
    typ = head & 0x1
    scount = struct.unpack_from("<H", data, 3)[0]
    o = {"id": sid, "format": fmt, "rate": RATE_MAP.get(rate), "rate_bits": rate,
         "mono": typ == 0, "samples": scount, "raw": bytes(data[5:])}
    if fmt == 2:  # MP3 frame data
        o["seek"] = struct.unpack_from("<H", data, 5)[0]
        o["mp3"] = bytes(data[7:])
    return o


def parse_stream(buf, store):
    """Parse a tag list. store gets: frames/labels for sprite timelines.

    Returns discovery dict {sprites, shapes, exports, errors, sounds} found
    in this stream; caller merges upward (char ids are global and unique).
    """
    disc = {"sprites": {}, "shapes": {}, "exports": [], "errors": [], "sounds": []}
    frames = []
    cur = {"place": [], "rm": []}
    frames.append(cur)
    labels = {}
    frame = 0
    pos = 0
    while pos < len(buf):
        if pos + 2 > len(buf):
            break
        code_len = struct.unpack_from("<H", buf, pos)[0]
        code = code_len >> 6
        ln = code_len & 0x3F
        pos += 2
        if ln == 0x3F:
            if pos + 4 > len(buf):
                break
            ln = struct.unpack_from("<I", buf, pos)[0]
            pos += 4
        data = buf[pos:pos + ln]
        pos += ln
        if code == 0:  # End
            break
        try:
            if code == 1:  # ShowFrame
                frame += 1
                cur = {"place": [], "rm": []}
                frames.append(cur)
            elif code == 39:  # DefineSprite (charId U16, frameCount U16)
                cid, fc = struct.unpack_from("<HH", data, 0)
                sub = {"char_id": cid, "declared_frames": fc, "frames": [], "labels": {}}
                child_disc = parse_stream(data[4:], sub)
                for k in ("sprites", "shapes"):
                    disc[k].update(child_disc[k])
                disc["exports"] += child_disc["exports"]
                disc["errors"] += child_disc["errors"]
                disc["sounds"] += child_disc["sounds"]
                disc["sprites"][cid] = sub
                disc.setdefault("sound_blobs", disc.get("sound_blobs", []))
                disc["sound_blobs"] = (disc.get("sound_blobs", []) +
                                       child_disc.get("sound_blobs", []))
            elif code in (2, 22, 32, 83):  # DefineShape*
                cid = struct.unpack_from("<H", data, 0)[0]
                bounds, _ = read_rect(data, 2)
                disc["shapes"][cid] = [bounds[0] / 20, bounds[1] / 20,
                                       bounds[2] / 20, bounds[3] / 20]
            elif code == 43:  # FrameLabel
                s = data.rstrip(b"\x00").decode("utf-8", "replace")
                labels.setdefault(s, frame + 1)
            elif code == 56:  # ExportAssets: count, [cid, name]
                n = struct.unpack_from("<H", data, 0)[0]
                off = 2
                for _ in range(n):
                    cid = struct.unpack_from("<H", data, off)[0]
                    e = data.index(b"\x00", off + 2)
                    name = data[off + 2:e].decode("utf-8", "replace")
                    disc["exports"].append((name, cid))
                    off = e + 1
            elif code == 14:  # DefineSound
                snd = parse_sound(data)
                disc["sounds"].append({k: v for k, v in snd.items()
                                       if not isinstance(v, bytes)})
                if "mp3" in snd:
                    disc.setdefault("sound_blobs", []).append((snd["id"], snd["mp3"]))
            elif code in (4, 26, 70):  # PlaceObject*
                cur["place"].append(parse_placeobj(code, data))
            elif code == 28:  # RemoveObject2
                cur["rm"].append(struct.unpack_from("<H", data, 0)[0])
        except Exception as ex:
            disc["errors"].append("tag%d@%d: %s" % (code, frame, ex))
    if store is not None:
        store["frames"] = frames
        store["labels"] = labels
        store["frame_count"] = frame + 1
    return disc


def load(path):
    raw = open(path, "rb").read()
    sig = raw[:3]
    if sig == b"CWS":
        body = zlib.decompress(raw[8:])
    elif sig == b"FWS":
        body = raw[8:]
    else:
        raise ValueError("bad sig %r" % sig)
    rect, pos = read_rect(body, 0)
    pos = read_rect(body, 0)[1]
    stage = [v / 20 for v in rect]
    fps = struct.unpack_from("<H", body, pos)[0] / 256.0
    fc = struct.unpack_from("<H", body, pos + 2)[0]
    d = parse_stream(body[pos + 4:], None)
    root = {"sound_blobs": d.get("sound_blobs", [])}
    return {"ver": raw[3], "stage": stage, "fps": fps, "frame_count": fc, **d, **root}


def main():
    argv = sys.argv[1:]
    out = load(argv[0])
    if "--json" in argv:
        slim = {k: v for k, v in out.items() if k != "sound_blobs"}
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump(slim, f, indent=1)
    if "--sounds" in argv:
        sdir = argv[argv.index("--sounds") + 1]
        import os
        os.makedirs(sdir, exist_ok=True)
        by_id = {}
        for n, cid in out["exports"]:
            by_id.setdefault(cid, []).append(n)
        idx = []
        blobs = dict(out.get("sound_blobs", []))
        for snd in out["sounds"]:
            if snd["format"] != 2 or snd["id"] not in blobs:
                continue
            fid = snd["id"]
            raw = blobs[fid]
            # find first MPEG sync (11 bits set)
            start = 0
            for r in range(len(raw) - 1):
                if raw[r] == 0xFF and (raw[r + 1] & 0xE0) == 0xE0:
                    start = r
                    break
            names = by_id.get(fid, ["%d" % fid])
            for nm in names:
                fn = os.path.join(sdir, "%s.mp3" % nm)
                open(fn, "wb").write(raw[start:])
            idx.append({"file": "%d.mp3" % fid, "names": names,
                        "rate": snd["rate"], "mono": snd["mono"],
                        "samples": snd["samples"], "skipped": start})
        json.dump(idx, open(os.path.join(sdir, "index.json"), "w"), indent=1)
        print("wrote %d mp3s to %s" % (len(idx), sdir))
    print("stage=%s fps=%s frames=%s sprites=%d shapes=%d exports=%d sounds=%d err=%d" % (
        out["stage"], out["fps"], out["frame_count"], len(out["sprites"]),
        len(out["shapes"]), len(out["exports"]), len(out["sounds"]),
        len(out.get("errors", []))))


if __name__ == "__main__":
    main()
