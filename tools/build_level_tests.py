#!/usr/bin/env python3
"""Build an isolated 3DS selector for the available level tests."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from build_cia import find_tool

ROOT = Path(__file__).resolve().parent.parent


def run(command):
    print('+', ' '.join(map(str, command)), flush=True)
    subprocess.run([str(x) for x in command], check=True)


def combine(projects, output, work, campaign=False, cia=None):
    merged = work / 'selector-project'
    source = merged / 'source'
    (merged / 'gfx').mkdir(parents=True)
    (merged / 'data').mkdir()
    source.mkdir()
    shutil.copy2(ROOT / ('tools/campaign_menu.c' if campaign else 'tools/level_test_menu.c'), source / 'menu.c')
    shutil.copy2(ROOT / 'dino-port/source/audio.c', source / 'audio.c')
    shutil.copy2(ROOT / 'dino-port/source/audio.h', source / 'audio.h')
    fingerprints = []
    for level, project in enumerate(projects, 1):
        dest = source / ('level%d' % level)
        dest.mkdir()
        for name in ('main.c', 'level1.h'):
            shutil.copy2(project / 'source' / name, dest / name)
        if campaign:
            level_main = dest / 'main.c'
            level_main.write_text('#define DINO_CAMPAIGN 1\n' + level_main.read_text())
            level_header = (dest / 'level1.h').read_text()
            fingerprints.append(re.search(r'#define SAVE_FINGERPRINT (0x[0-9a-f]+)u', level_header).group(1))
        header = (project / 'source/gfx_meta.h').read_text()
        header = re.sub(r'\batlas_(\d+)_t3x', 'level%d_atlas_\\1_t3x' % level, header)
        (dest / 'gfx_meta.h').write_text(header)
        if campaign and level == 1:
            match = re.search(r'\{\s*(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\s*\}, /\* menu/background \*/', header)
            if not match:
                raise ValueError('menu background missing from level 1')
            sheet, x, y, w, h, ox, oy, fw, fh = map(int, match.groups())
            art = '#include <stdint.h>\nextern const uint8_t level1_atlas_%d_t3x[];\nextern const uint32_t level1_atlas_%d_t3x_size;\n' % (sheet, sheet)
            art += '#define CAMPAIGN_ART_DATA level1_atlas_%d_t3x\n#define CAMPAIGN_ART_SIZE level1_atlas_%d_t3x_size\n' % (sheet, sheet)
            for name, value in zip(('X', 'Y', 'W', 'H', 'OX', 'OY', 'FW', 'FH'), (x,y,w,h,ox,oy,fw,fh)):
                art += '#define ART_%s %d\n' % (name, value)
            (source / 'campaign_art.h').write_text(art)
        (source / ('level%d.c' % level)).write_text(
            '#define main dino_level%d_main\n#include "level%d/main.c"\n' % (level, level))
        for texture in (project / 'gfx').glob('atlas_*.t3x'):
            shutil.copy2(texture, merged / 'gfx' / ('level%d_' % level + texture.name))
        from extract_audio import SOUNDS
        for name in SOUNDS:
            sound = project / 'data' / ('snd_' + name + '.pcm')
            target = merged / 'data' / sound.name
            if target.exists() and target.read_bytes() != sound.read_bytes():
                raise ValueError('level projects contain different sound banks')
            if not target.exists():
                shutil.copy2(sound, target)
    if campaign:
        import hashlib
        fingerprint = int.from_bytes(hashlib.sha256(','.join(fingerprints).encode()).digest()[:4], 'big')
        with (source / 'campaign_art.h').open('a') as out:
            out.write('#define CAMPAIGN_FINGERPRINT 0x%08xu\n' % fingerprint)
    run([sys.executable, ROOT / 'tools/build3ds.py', merged])
    if cia:
        from build_cia import package
        game, ffdec, cia_output, makerom, bannertool = cia
        package(game, ffdec, merged / (merged.name + '.elf'), cia_output, makerom, bannertool)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(merged / 'dinodino.3dsx', output)
    print('Built %s:' % ('campaign' if campaign else 'isolated level test'), output)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('game_dir', type=Path)
    ap.add_argument('--ffdec', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--campaign', action='store_true', help='build the playable campaign instead of the development selector')
    ap.add_argument('--cia-output', type=Path, help='also build an installable campaign CIA')
    ap.add_argument('--makerom', default=find_tool('makerom'))
    ap.add_argument('--bannertool', default=find_tool('bannertool'))
    args = ap.parse_args()
    if args.cia_output and (not args.campaign or not args.makerom or not args.bannertool):
        ap.error('--cia-output requires --campaign and makerom and bannertool on PATH or explicitly specified')
    game = args.game_dir.resolve()
    output = args.output.resolve()
    if output == game or game in output.parents:
        ap.error('output must be outside the supplied game directory')
    with tempfile.TemporaryDirectory(prefix='dino-level-tests-') as tmp:
        work = Path(tmp)
        projects = []
        for level in (1, 2, 3, 4, 5, 6, 7, 8, 9):
            project = work / ('level%d' % level)
            run([sys.executable, ROOT / 'tools/build_prototype.py', game,
                 '--ffdec', args.ffdec.resolve(), '--test-level', str(level),
                 '--project-output', project, '--output', work / ('level%d.3dsx' % level)])
            projects.append(project)
        cia = (game, args.ffdec, args.cia_output, args.makerom, args.bannertool) if args.cia_output else None
        combine(projects, output, work, campaign=args.campaign, cia=cia)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print('Level test build failed:', exc, file=sys.stderr)
        sys.exit(1)
