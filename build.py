#!/usr/bin/env python3
"""Build the Dino Attack 3DS campaign from a user's original game files."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent


def find_tool(name):
    local = ROOT / 'tools' / name
    return str(local) if local.is_file() else shutil.which(name)


def default_ffdec():
    configured = os.environ.get('FFDEC_JAR')
    if configured:
        return Path(configured)
    candidates = sorted(ROOT.glob('ffdec*/ffdec.jar'))
    return candidates[0] if len(candidates) == 1 else None


def existing_executable(name):
    return bool(name and (shutil.which(str(name)) or
                          (Path(name).is_file() and os.access(name, os.X_OK))))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
        epilog='Set FFDEC_JAR or pass --ffdec. By default both formats are built.')
    parser.add_argument('game_dir', type=Path, help='path to your original DinoAttackGame folder')
    formats = parser.add_mutually_exclusive_group()
    formats.add_argument('--3dsx-only', dest='only_3dsx', action='store_true', help='build only the homebrew launcher .3dsx')
    formats.add_argument('--cia-only', dest='only_cia', action='store_true', help='build only the installable .cia')
    parser.add_argument('--ffdec', type=Path, default=default_ffdec(), help='path to FFDec ffdec.jar')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'build-output', help='output directory (default: build-output)')
    parser.add_argument('--makerom', default=find_tool('makerom'), help='makerom executable (CIA only)')
    parser.add_argument('--bannertool', default=find_tool('bannertool'), help='bannertool executable (CIA only)')
    args = parser.parse_args(argv)
    game, out = args.game_dir.resolve(), args.output_dir.resolve()
    if not game.is_dir(): parser.error('game directory does not exist: %s' % game)
    if out == game or game in out.parents: parser.error('output directory must be outside the supplied game directory')
    if not args.ffdec or not args.ffdec.is_file(): parser.error('FFDec jar not found; use --ffdec or set FFDEC_JAR')
    required = ['Launcher.swf', 'mobile.swf', 'main.swf', 'intro.swf', 'soundmain.swf', 'soundgame.swf',
                'editor/decor/bclip.swf', 'editor/decor/fclip.swf']
    required += ['player/%s.swf' % n for n in ('hammer', 'predator', 'typhon')]
    required += ['editor/maps/mtrx%d.swf' % n for n in range(1, 10)]
    missing = [p for p in required if not (game / p).is_file()]
    if missing: parser.error('missing game files:\n  ' + '\n  '.join(missing))
    for name in ('java', 'ffmpeg'):
        if not shutil.which(name): parser.error('required executable not found on PATH: %s' % name)
    for module in ('PIL', 'numpy'):
        try: __import__(module)
        except ImportError: parser.error('missing Python dependency: %s (install Pillow and NumPy)' % module)
    dkp = Path(os.environ.get('DEVKITPRO', '/opt/devkitpro'))
    dka = Path(os.environ.get('DEVKITARM', str(dkp / 'devkitARM')))
    for exe in (dka / 'bin/arm-none-eabi-gcc', dka / 'bin/arm-none-eabi-as',
                dkp / 'tools/bin/tex3ds', dkp / 'tools/bin/bin2s', dkp / 'tools/bin/3dsxtool'):
        if not existing_executable(exe): parser.error('devkitPro executable not found: %s' % exe)
    for lib in ('ctru', 'citro2d', 'citro3d'):
        if not (dkp / 'libctru/lib' / ('lib%s.a' % lib)).is_file(): parser.error('devkitPro library not found: %s' % lib)
    if not args.only_3dsx:
        for label, tool in (('makerom', args.makerom), ('bannertool', args.bannertool)):
            if not existing_executable(tool): parser.error('%s not found; install it or pass --%s' % (label, label))
    with tempfile.TemporaryDirectory(prefix='dino-build-output-') as tmp:
        target_3dsx = Path(tmp) / 'dinodino.3dsx' if args.only_cia else out / 'dinodino.3dsx'
        command = [sys.executable, ROOT / 'tools/build_level_tests.py', game, '--campaign',
                   '--ffdec', args.ffdec.resolve(), '--output', target_3dsx]
        if not args.only_3dsx:
            command += ['--cia-output', out / 'dinodino.cia', '--makerom', args.makerom, '--bannertool', args.bannertool]
        try:
            subprocess.run([str(x) for x in command], check=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            print('Build failed: %s' % exc, file=sys.stderr)
            return 1
    print('\nFinished:')
    if not args.only_cia: print('  %s' % (out / 'dinodino.3dsx'))
    if not args.only_3dsx: print('  %s' % (out / 'dinodino.cia'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
