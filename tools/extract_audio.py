#!/usr/bin/env python3
"""Decode the original game's sound bank to 3DS-ready PCM."""
from pathlib import Path
import subprocess
import tempfile
import swf

SOUNDS = {
    'theme': ('soundmain', 'theme_bass'),
    **{name: ('soundgame', name) for name in (
        'motor', 'tankmotor', 'helico', 'plasma', 'tankshoot', 'lazer',
        'spirale', 'mitraille', 'tirspecial', 'bonus', 'bonus_egg',
        'bonus_egg_all', 'caisse', 'explo', 'impact', 'lezardattack',
        'raptorattack', 'pterocri', 'lezardjaune', 'flame', 'dinolazer',
        'trexcri', 'trexdie', 'trexattack', 'charge', 'accel', 'accel_tank')},
}


def extract(game, destination):
    game, destination = Path(game), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    banks = {}
    for bank in ('soundmain', 'soundgame'):
        path = game / (bank + '.swf')
        if not path.is_file():
            raise ValueError('missing sound bank: %s' % path)
        parsed = swf.load(str(path))
        if parsed.get('errors'):
            raise ValueError('invalid sound bank: %s' % path)
        banks[bank] = (dict(parsed['exports']), dict(parsed.get('sound_blobs', [])))
    with tempfile.TemporaryDirectory(prefix='dino-sounds-') as tmp:
        source = Path(tmp) / 'sound.mp3'
        for name, (bank, key) in SOUNDS.items():
            exports, blobs = banks[bank]
            blob = blobs.get(exports.get('id_' + key))
            if not blob:
                raise ValueError('missing sound id_%s in %s.swf' % (key, bank))
            source.write_bytes(blob)
            output = destination / ('snd_' + name + '.pcm')
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(source), '-f', 's16le',
                            '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '22050', str(output)], check=True)
            if not output.stat().st_size or output.stat().st_size % 2:
                raise ValueError('invalid decoded sound: %s' % name)
