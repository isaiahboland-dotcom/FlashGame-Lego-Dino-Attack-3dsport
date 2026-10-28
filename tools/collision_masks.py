"""Extract level collision masks from the original decor clips.

Uses FFDec-rendered hit-zone sprites and their timeline transforms. This is a
pixel-resolution approximation of Flash's shape hit tests, not bounce physics.
"""
from pathlib import Path
import re
import subprocess

from PIL import Image
import bake_sprites
import swf
from resolve import Resolver


def extract(work, game, jar, level, extra_tiles=None):
    masks = [bytes(1250)]  # index zero is empty
    indices = {masks[0]: 0}
    layers = {}
    shot_layers = {}
    for name, field in (('bclip', 'b'), ('fclip', 'f')):
        source = game / 'editor' / 'decor' / (name + '.swf')
        parsed = swf.load(str(source))
        if parsed.get('errors'):
            raise ValueError('SWF parser errors in ' + str(source))
        r = Resolver(parsed)
        dest = work / ('collision-' + name)
        scripts = dest / 'scripts-output'
        scripts.mkdir(parents=True)
        cmd = ['java', '-Djava.awt.headless=true', '-Duser.home=' + str(work),
               '-jar', str(jar), '-export', 'script', str(scripts), str(source)]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)
        if 'Export finished.' not in proc.stdout:
            raise ValueError('FFDec did not export collision scripts for ' + name)
        root = scripts / 'scripts'
        outer_frames = r.compile(r.exports['clip'])['frames']
        solid_ids = {r.exports[n] for n in ('bounce_simple', 'bounce_free_shot') if n in r.exports}
        ignore_ids = {r.exports[n] for n in ('bounce_none', 'bounce_back') if n in r.exports}
        tiles = sorted({c[field] for row in level['grid'] for c in row} | set((extra_tiles or {}).get(field, ())))
        zones = {}
        pass_through = set()
        needed = set()
        for tile in tiles:
            if not isinstance(tile, int) or tile < 1:
                raise ValueError('unsupported collision tile: %r' % tile)
            outer, inner = divmod(tile - 1, 25)
            if outer >= len(outer_frames):
                raise ValueError('collision tile out of range: %d' % tile)
            cid = next(p['char'] for p in outer_frames[outer]['parts'] if p.get('name') == 'mc')
            if r.sprites[cid]['declared_frames'] != 25:
                raise ValueError('unsupported collision timeline for tile %d' % tile)
            placements = r.frame_states(cid)[inner]
            solid = [p for p in placements if p.get('char') in solid_ids]
            if len(solid) > 1:
                raise ValueError('multiple collision markers on tile %d' % tile)
            if not solid:
                zones[tile] = ('empty', None)
                continue
            marker = solid[0]
            if marker['char'] == r.exports.get('bounce_free_shot'):
                pass_through.add(tile)
            action = None
            for frame in range(inner, -1, -1):
                matches = [p for p in r.sprites[cid]['frames'][frame]['place']
                           if p['depth'] == marker['depth']]
                if matches:
                    p = matches[-1]
                    if p.get('clip_actions'):
                        candidates = list((root / ('DefineSprite_%d' % cid) / ('frame_%d' % (frame + 1))).glob(
                            'PlaceObject*_%d_*_%d/*.as' % (marker['char'], marker['depth'])))
                        if len(candidates) != 1:
                            raise ValueError('cannot find collision action for %s tile %d' % (name, tile))
                        action = candidates[0].read_text()
                        break
                    if not p.get('move'):
                        break
            if action is None:
                # A bounce clip with no initialize action has no bounce0 or
                # params; the original AS2 fallback treats the whole cell as solid.
                if not marker.get('clip_actions'):
                    zones[tile] = ('full', None)
                    continue
                raise ValueError('missing collision parameters for %s tile %d' % (name, tile))
            matches = re.findall(r'\bbounce(\d+)\s*=\s*"([^"]*)"\s*;', action)
            if not matches or matches[0][0] != '0':
                raise ValueError('unsupported collision parameters for %s tile %d' % (name, tile))
            names = [value for _, value in matches if value]
            if not names:
                zones[tile] = ('full', None)
                continue
            byname = {p.get('name'): p for p in placements if p.get('name')}
            parts = []
            for zone_name in names:
                if zone_name not in byname:
                    raise ValueError('missing collision zone %s in %s tile %d' % (zone_name, name, tile))
                zone = byname[zone_name]
                if zone['char'] not in r.sprites:
                    raise ValueError('unsupported collision shape for %s tile %d' % (name, tile))
                needed.add(zone['char'])
                parts.append(zone)
            zones[tile] = ('zones', parts)
        images = dest / 'sprites'
        images.mkdir()
        if needed:
            cmd = ['java', '-Djava.awt.headless=true', '-Duser.home=' + str(work), '-jar', str(jar),
                   '-selectid', ','.join(map(str, sorted(needed))), '-format', 'sprite:png',
                   '-export', 'sprite', str(images), str(source)]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)
            if 'Export finished.' not in proc.stdout:
                raise ValueError('FFDec did not export collision zones for ' + name)
        # Sheet.pngs expects the path <root>/<swf>.
        bake_sprites.SPR_ROOT = str(work)
        alias = work / name
        alias.symlink_to(images, target_is_directory=True)
        sheet = bake_sprites.Sheet(name, r)
        lookup = {}
        for tile, (kind, parts) in zones.items():
            mask = Image.new('RGBA', (100, 100))
            if kind == 'full':
                mask = Image.new('RGBA', (100, 100), (255, 255, 255, 255))
            elif kind == 'zones':
                for p in parts:
                    img = sheet.png(p['char'], 1)
                    matrix = bake_sprites.compose(p['matrix'], sheet.art_off(p['char']))
                    bake_sprites.paste_affine(mask, img, matrix)
            alpha = mask.getchannel('A')
            data = bytearray(1250)
            for y in range(100):
                for x in range(100):
                    if alpha.getpixel((x, y)) >= 128:
                        n = y * 100 + x
                        data[n // 8] |= 1 << (n % 8)
            key = bytes(data)
            if key not in indices:
                indices[key] = len(masks)
                masks.append(key)
            lookup[tile] = indices[key]
        layers[field] = lookup
        shot_layers[field] = {tile: 0 if tile in pass_through else mask for tile, mask in lookup.items()}
        print('%s: %d tiles, %d with collision' % (name, len(lookup), sum(bool(v) for v in lookup.values())), flush=True)
    return masks, layers, shot_layers
