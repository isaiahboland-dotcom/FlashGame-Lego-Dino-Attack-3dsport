#!/usr/bin/env python3
"""Package a campaign ELF with HOME Menu art extracted from the user's game."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile
import wave

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent


def find_tool(name):
    local = ROOT / 'tools' / name
    return str(local) if local.is_file() else shutil.which(name)


def run(command, **kwargs):
    print('+', ' '.join(map(str, command)), flush=True)
    subprocess.run([str(x) for x in command], check=True, **kwargs)


def package(game, ffdec, elf, output, makerom, bannertool):
    game, ffdec, elf, output = map(lambda p: Path(p).resolve(), (game, ffdec, elf, output))
    if output == game or game in output.parents:
        raise ValueError('output must be outside the supplied game directory')
    if not (game / 'Launcher.swf').is_file() or not ffdec.is_file() or not elf.is_file():
        raise ValueError('Launcher.swf, FFDec, and the campaign ELF are required')
    with tempfile.TemporaryDirectory(prefix='dino-cia-') as tmp:
        work = Path(tmp)
        export = work / 'images'
        export.mkdir()
        with (work / 'ffdec.log').open('w') as log:
            run(['java', '-Djava.awt.headless=true', '-Duser.home=' + str(work), '-jar', ffdec,
                 '-export', 'image', export, game / 'Launcher.swf'], stdout=log, stderr=subprocess.STDOUT)
        if 'Export finished.' not in (work / 'ffdec.log').read_text(errors='replace'):
            raise ValueError('FFDec failed to export launcher images')
        candidates = []
        for path in sorted(export.glob('*')):
            try:
                with Image.open(path) as im:
                    if im.format == 'JPEG' and im.size == (326, 121):
                        candidates.append(path)
            except OSError:
                continue
        if len(candidates) != 1:
            raise ValueError('expected one 326x121 launcher JPEG; unsupported game version')
        with Image.open(candidates[0]) as original:
            original = original.convert('RGB')
            # The right-hand part of the launcher strip shows the dinosaur's face.
            icon = ImageOps.fit(original.crop((190, 3, 323, 85)), (48, 48), method=Image.Resampling.LANCZOS, centering=(0.63, 0.5))
            icon.save(work / 'icon.png')
            banner = Image.new('RGB', (256, 128), (15, 14, 20))
            strip = ImageOps.contain(original.crop((0, 0, 326, 89)), (256, 112), method=Image.Resampling.LANCZOS)
            banner.paste(strip, ((256 - strip.width) // 2, (128 - strip.height) // 2))
            banner.save(work / 'banner.png')
        # A short silent jingle keeps the HOME Menu banner quiet.
        with wave.open(str(work / 'banner.wav'), 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(22050)
            wav.writeframes(bytes(22050))
        run([bannertool, 'makesmdh', '-s', 'Dino Attack', '-l', 'Dino Attack 3DS fan port',
             '-p', 'Fan port', '-i', work / 'icon.png', '-o', work / 'icon.icn',
             '-r', 'regionfree', '-f', 'visible'])
        run([bannertool, 'makebanner', '-i', work / 'banner.png', '-a', work / 'banner.wav', '-o', work / 'banner.bnr'])
        run([makerom, '-f', 'cia', '-target', 't', '-o', work / 'campaign.cia', '-elf', elf,
             '-rsf', ROOT / 'tools/campaign.rsf', '-icon', work / 'icon.icn', '-banner', work / 'banner.bnr'])
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(work / 'campaign.cia', output)
        print('Built CIA:', output)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('game_dir', type=Path)
    ap.add_argument('--ffdec', type=Path, required=True)
    ap.add_argument('--elf', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--makerom', default=find_tool('makerom'))
    ap.add_argument('--bannertool', default=find_tool('bannertool'))
    args = ap.parse_args()
    if not args.makerom or not args.bannertool:
        ap.error('makerom and bannertool must be in PATH or provided explicitly')
    package(args.game_dir, args.ffdec, args.elf, args.output, args.makerom, args.bannertool)


if __name__ == '__main__':
    main()
