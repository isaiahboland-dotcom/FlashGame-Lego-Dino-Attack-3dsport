#!/usr/bin/env python3
"""Build the 3DS .3dsx without make/host-gcc: drives devkitARM directly.

Usage: build3ds.py [project dir (default: repository dino-port)]
"""
import os
import subprocess
import sys
import glob

DKP = os.environ.get("DEVKITPRO", "/opt/devkitpro")
DKA = os.environ.get("DEVKITARM", DKP + "/devkitARM")
BIN = DKA + "/bin"
GCC = BIN + "/arm-none-eabi-gcc"
AS = BIN + "/arm-none-eabi-as"
BIN2S = DKP + "/tools/bin/bin2s"
TOOL = DKP + "/tools/bin/3dsxtool"
PROJ = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                       os.path.join(os.path.dirname(__file__), "..", "dino-port"))

ARCH = ("-march=armv6k -mtune=mpcore -mfloat-abi=hard -mtp=soft "
        "-mword-relocations -ffunction-sections")
CFLAGS = (ARCH + " -g -O2 -Wall -D__3DS__ "
          "-I%s/libctru/include -I%s/source" % (DKP, PROJ))
LIBS = "-L%s/libctru/lib -lcitro2d -lcitro3d -lctru -lm" % DKP
SPECS = "-specs=%s/arm-none-eabi/lib/3dsx.specs" % DKA


def run(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if p.returncode != 0:
        print(" ".join(cmd))
        print(p.stdout[-4000:])
        print(p.stderr[-4000:])
        sys.exit(1)
    return p


def main():
    bld = os.path.join(PROJ, "build")
    os.makedirs(bld, exist_ok=True)
    ofiles = []
    # t3x -> bin2s -> .o
    for t3x in sorted(glob.glob(os.path.join(PROJ, "gfx", "*.t3x")) +
                       glob.glob(os.path.join(PROJ, "data", "*.pcm"))):
        base = os.path.basename(t3x).replace(".", "_")
        sfile = os.path.join(bld, base + ".s")
        with open(sfile, "w") as fh:
            p = run([BIN2S, t3x])
            fh.write(p.stdout)
        o = os.path.join(bld, base + ".o")
        run([AS, "-o", o, sfile])
        ofiles.append(o)
    for src in sorted(glob.glob(os.path.join(PROJ, "source", "*.c"))):
        o = os.path.join(bld, os.path.basename(src)[:-2] + ".o")
        run([GCC, "-c", src, "-o", o] + CFLAGS.split())
        ofiles.append(o)
    elf = os.path.join(PROJ, os.path.basename(PROJ) + ".elf")
    run([GCC, "-g"] + ARCH.split() +
        ofiles + [SPECS] + LIBS.split() +
        ["-Wl,-Map," + os.path.join(bld, "link.map"),
         "-o", elf])
    out = os.path.join(PROJ, "dinodino.3dsx")
    run([TOOL, elf, out])
    print("built", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
