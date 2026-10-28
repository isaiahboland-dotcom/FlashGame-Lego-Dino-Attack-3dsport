#!/usr/bin/env python3
"""Build the 3DS prototype from a user's original game files."""
import argparse
import json
import hashlib
import math
import re
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from PIL import Image
import bake_sprites
import collision_masks
import gen_skeleton
import extract_audio
import pack_atlases
import swf
from resolve import Resolver

REPO = Path(__file__).resolve().parent.parent


def run(cmd, **kwargs):
    print('+', ' '.join(map(str, cmd)), flush=True)
    subprocess.run([str(x) for x in cmd], check=True, **kwargs)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('game_dir', type=Path, help='game folder containing mobile.swf and main.swf')
    ap.add_argument('--ffdec', type=Path, required=True, help='path to FFDec ffdec.jar')
    ap.add_argument('--output', type=Path, required=True, help='output .3dsx file')
    ap.add_argument('--test-level', type=int, choices=(1, 2, 3, 4, 5, 6, 7, 8, 9), default=1, help='level for development builds (default: 1)')
    ap.add_argument('--project-output', type=Path, help='copy generated project for development bundling')
    args = ap.parse_args()
    game = args.game_dir.resolve()
    output = args.output.resolve()
    if output == game or game in output.parents:
        ap.error('output must be outside the game directory')
    for path in (game / 'mobile.swf', game / 'main.swf', game / 'intro.swf', game / 'player/hammer.swf', args.ffdec):
        if not path.is_file():
            ap.error('file not found: %s' % path)
    tex3ds = Path(os.environ.get('DEVKITPRO', '/opt/devkitpro')) / 'tools/bin/tex3ds'
    if not tex3ds.is_file():
        ap.error('tex3ds not found at %s; set DEVKITPRO' % tex3ds)

    with tempfile.TemporaryDirectory(prefix='dino-prototype-') as tmp:
        work = Path(tmp)
        map_dir = work / 'maps'
        run([sys.executable, REPO / 'tools/extract_maps.py', game,
             '--ffdec', args.ffdec.resolve(), '--output', map_dir])
        level = json.loads((map_dir / ('map%d.json' % args.test_level)).read_text())
        # The original level 8 map has a vertical strip of NaN background IDs.
        # Use the adjacent outer-edge tile; preserve its foreground and entities.
        if args.test_level == 8:
            repaired = 0
            for row in level['grid']:
                for col, cell in enumerate(row):
                    if cell['b'] is None:
                        if col == 0 or row[col - 1]['b'] != 7:
                            raise ValueError('unexpected nonfinite level 8 background tile')
                        cell['b'] = row[col - 1]['b']
                        repaired += 1
            if repaired:
                print('Replaced %d nonfinite level 8 edge tiles with adjacent tile 7' % repaired, flush=True)
        sprite_root = work / 'sprites'
        parsed = {}
        for name in ('mobile', 'main'):
            source = game / (name + '.swf')
            parsed[name] = swf.load(str(source))
            if parsed[name].get('errors'):
                raise ValueError('%s has SWF parser errors: %s' % (source, parsed[name]['errors']))
            dest = sprite_root / name
            dest.mkdir(parents=True)
            log = work / (name + '-ffdec.log')
            with log.open('w') as fh:
                run(['java', '-Djava.awt.headless=true', '-Duser.home=' + str(work),
                     '-jar', args.ffdec.resolve(), '-format', 'sprite:png',
                     '-export', 'sprite', dest, source], stdout=fh, stderr=subprocess.STDOUT)
            export_log = log.read_text(errors='replace')
            if 'Export finished.' not in export_log or not any(dest.glob('DefineSprite_*/*.png')):
                raise RuntimeError('FFDec export failed for %s:\n%s' % (source, export_log[-3000:]))

        vehicle_name = 'typhon' if args.test_level in (7, 8, 9) else 'predator' if args.test_level in (4, 5, 6) else 'hammer'
        hammer_file = game / ('player/' + vehicle_name + '.swf')
        hammer_data = swf.load(str(hammer_file))
        if hammer_data.get('errors'):
            raise ValueError('SWF parser errors in hammer.swf')
        hammer_dest = sprite_root / 'hammer'
        hammer_dest.mkdir(parents=True)
        hammer_log = work / 'hammer-ffdec.log'
        with hammer_log.open('w') as fh:
            run(['java', '-Djava.awt.headless=true', '-Duser.home=' + str(work),
                 '-jar', args.ffdec.resolve(), '-format', 'sprite:png,shape:png',
                 '-export', 'sprite,shape', hammer_dest, hammer_file],
                stdout=fh, stderr=subprocess.STDOUT)
        if 'Export finished.' not in hammer_log.read_text(errors='replace'):
            raise RuntimeError('FFDec failed to export Hammer sprites')

        bake_sprites.SPR_ROOT = str(sprite_root)
        baked = work / 'baked'
        dino_dir = baked / 'dino'
        bake_sprites.bake_dino(bake_sprites.Sheet('mobile', Resolver(parsed['mobile'])),
                               't_rex_rouge' if args.test_level == 9 else 't_rex_jaune' if args.test_level == 6 else 't_rex_vert', str(dino_dir))
        dino = json.loads((dino_dir / 'meta.json').read_text())
        items = [('dino/t_rex_vert/zone', dino_dir / 'zone.png')]
        for rel in dino['states']['wait']['frames']:
            items.append(('dino/t_rex_vert/' + rel.replace('/', '_')[:-4], dino_dir / rel))
        if args.test_level in (3, 6, 9):
            for state in ('run', 'prerugi', 'rugi', 'postrugi', 'dead'):
                frames = dino['states'][state]['frames']
                for n in range(min(6, len(frames))):
                    rel = frames[n * len(frames) // min(6, len(frames))]
                    items.append(('boss/%s/f%03d' % (state, n + 1), dino_dir / rel))

        vehicle_dir = baked / 'hammer'
        bake_sprites.bake_vehicle(bake_sprites.Sheet('hammer', Resolver(hammer_data)), str(vehicle_dir))
        vehicle = json.loads((vehicle_dir / 'meta.json').read_text())
        items.append(('vehicle/hammer/pose', vehicle_dir / vehicle['poses'][0]))
        if args.test_level in (7, 8, 9):
            for n, rel in enumerate(vehicle['rotor_frames'], 1):
                items.append(('vehicle/typhon/rotor/f%03d' % n, vehicle_dir / rel))
        if args.test_level in (4, 5, 6):
            if not vehicle.get('turret'):
                raise ValueError('missing Predator turret artwork')
            items.append(('vehicle/predator/turret', vehicle_dir / vehicle['turret']['file']))

        mobile_sheet = bake_sprites.Sheet('mobile', Resolver(parsed['mobile']))
        projectile_origins = {}
        for name in ('plasma', 'acid', 'choc', 'intel', 'fire') + (('nrg', 'nrgintel', 'dbz') if args.test_level in (4, 5, 6) else ()) + (('flame',) if args.test_level in (5, 7, 8, 9) else ()) + (('eggball',) if args.test_level == 6 else ()) + (('superflame',) if args.test_level == 9 else ()) + (('plasmatyphon', 'nrginteltyphon', 'dbztyphon', 'lazer') if args.test_level in (7, 8, 9) else ()):
            cid = mobile_sheet.r.exports.get(name)
            if cid is None:
                raise ValueError('missing %s projectile in mobile.swf' % name)
            layers = []
            for part in mobile_sheet.r.compile(cid)['frames'][0]['parts']:
                # Hit clips are hidden at runtime but FFDec renders their red art.
                if (part.get('name') or '').startswith('mcHit'):
                    continue
                if part['char'] not in mobile_sheet.r.sprites:
                    raise ValueError('unsupported %s projectile artwork' % name)
                image = bake_sprites.apply_cx(mobile_sheet.png(part['char'], 1), part.get('cxform'))
                matrix = bake_sprites.compose(part['matrix'], mobile_sheet.art_off(part['char']))
                layers.append((image, matrix))
            if not layers:
                raise ValueError('missing visible %s artwork' % name)
            image, origin = bake_sprites.comp_items(layers)
            path = baked / (name + '.png')
            image.save(path)
            projectile_origins[name] = (-origin[0], -origin[1])
            items.append(('projectile/' + name, path))
            if name in ('choc', 'intel'):
                # These projectiles grow across four nested animation frames.
                for frame in range(1, 5):
                    animated_layers = []
                    for part in mobile_sheet.r.compile(cid)['frames'][0]['parts']:
                        if (part.get('name') or '').startswith('mcHit'):
                            continue
                        image = bake_sprites.apply_cx(mobile_sheet.png(part['char'], frame), part.get('cxform'))
                        matrix = bake_sprites.compose(part['matrix'], mobile_sheet.art_off(part['char']))
                        animated_layers.append((image, matrix))
                    image, origin = bake_sprites.comp_items(animated_layers)
                    key = '%s_f%03d' % (name, frame)
                    path = baked / (key + '.png')
                    image.save(path)
                    projectile_origins[key] = (-origin[0], -origin[1])
                    items.append(('projectile/%s/f%03d' % (name, frame), path))
            if name == 'superflame':
                # The original flame grows over its 15-frame lifetime.
                for frame_index in range(6):
                    frame = 1 + frame_index * 14 // 5
                    animated_layers = []
                    for part in mobile_sheet.r.compile(cid)['frames'][0]['parts']:
                        if (part.get('name') or '').startswith('mcHit'):
                            continue
                        image = bake_sprites.apply_cx(mobile_sheet.png(part['char'], frame), part.get('cxform'))
                        matrix = bake_sprites.compose(part['matrix'], mobile_sheet.art_off(part['char']))
                        animated_layers.append((image, matrix))
                    image, origin = bake_sprites.comp_items(animated_layers)
                    key = 'superflame_f%03d' % (frame_index + 1)
                    path = baked / (key + '.png')
                    image.save(path)
                    projectile_origins[key] = (-origin[0], -origin[1])
                    items.append(('projectile/superflame/f%03d' % (frame_index + 1), path))

        pickup_origins = {}
        pickup_parts = {}
        shape_ids = set()
        for name in ('bonus_hp', 'bonus_weapon', 'bonus_egg'):
            cid = mobile_sheet.r.exports.get(name)
            if cid is None:
                raise ValueError('missing pickup ' + name)
            parts = [p for p in mobile_sheet.r.compile(cid)['frames'][0]['parts']
                     if p.get('name') != 'mcZone' and not (p.get('name') or '').startswith('mcHit')]
            pickup_parts[name] = parts
            shape_ids.update(p['char'] for p in parts if p['char'] in mobile_sheet.r.shapes)
        prop_names = ('box_void', 'box_hp', 'box_weapon', 'carcasse0', 'carcasse1')
        level_props = {}
        for row in level['grid']:
            for cell in row:
                for entity_id, entity in cell['m'].items():
                    if entity.get('l') in prop_names:
                        if entity_id in level_props and level_props[entity_id] != entity:
                            raise ValueError('conflicting prop placements')
                        level_props[entity_id] = entity
        prop_parts = {}
        for name in {p['l'] for p in level_props.values()}:
            cid = mobile_sheet.r.exports[name]
            parts = [p for p in mobile_sheet.r.compile(cid)['frames'][0]['parts']
                     if p.get('name') not in ('mcZone', 'mcHint') and not (p.get('name') or '').startswith('mcHit')]
            prop_parts[name] = parts
            shape_ids.update(p['char'] for p in parts if p['char'] in mobile_sheet.r.shapes)
        if shape_ids:
            shape_dest = sprite_root / 'mobile' / 'shapes'
            shape_dest.mkdir()
            with (work / 'pickup-shapes.log').open('w') as fh:
                run(['java', '-Djava.awt.headless=true', '-Duser.home=' + str(work),
                     '-jar', args.ffdec.resolve(), '-selectid', ','.join(map(str, sorted(shape_ids))),
                     '-format', 'shape:png', '-export', 'shape', shape_dest,
                     game / 'mobile.swf'], stdout=fh, stderr=subprocess.STDOUT)
            if 'Export finished.' not in (work / 'pickup-shapes.log').read_text(errors='replace'):
                raise ValueError('FFDec failed to export pickup shapes')
        for name, parts in pickup_parts.items():
            layers = []
            for p in parts:
                cid = p['char']
                image = mobile_sheet.spng(cid) if cid in mobile_sheet.r.shapes else mobile_sheet.png(cid, 1)
                layers.append((bake_sprites.apply_cx(image, p.get('cxform')),
                               bake_sprites.compose(p['matrix'], mobile_sheet.art_off(cid))))
            if not layers:
                raise ValueError('missing pickup artwork: ' + name)
            image, origin = bake_sprites.comp_items(layers)
            path = baked / (name + '.png')
            image.save(path)
            pickup_origins[name] = (-origin[0], -origin[1])
            items.append(('pickup/' + name, path))

        prop_origins = {}
        for name, parts in prop_parts.items():
            layers = []
            for p in parts:
                cid = p['char']
                image = mobile_sheet.spng(cid) if cid in mobile_sheet.r.shapes else mobile_sheet.png(cid, 1)
                layers.append((bake_sprites.apply_cx(image, p.get('cxform')),
                               bake_sprites.compose(p['matrix'], mobile_sheet.art_off(cid))))
            if not layers:
                raise ValueError('missing prop artwork: ' + name)
            image, origin = bake_sprites.comp_items(layers)
            path = baked / (name + '.png')
            image.save(path)
            prop_origins[name] = (-origin[0], -origin[1])
            items.append(('prop/' + name, path))

        enemy_meta = {}
        for enemy_name in ('lezard_vert', 'lezard_vert_sp', 'lezard_jaune', 'lezard_rouge', 'raptor_vert', 'lezard_jaune_sp', 'raptor_jaune') + (('raptor_rouge', 'ptero_vert', 'ptero_jaune', 'ptero_rouge') if args.test_level in (7, 8, 9) else ('raptor_rouge',) if args.test_level == 5 else ('raptor_vert_sp',) if args.test_level == 6 else ()):
            enemy_dir = baked / enemy_name
            bake_sprites.bake_dino(mobile_sheet, enemy_name, str(enemy_dir))
            meta = json.loads((enemy_dir / 'meta.json').read_text())
            enemy_meta[enemy_name] = meta
            for state in (('wait', 'run', 'preshoot', 'shoot', 'hurt', 'dead', 'jump') if enemy_name.startswith('raptor_') else ('wait', 'run', 'preshoot', 'shoot', 'hurt', 'dead')):
                source_state = state if state in meta['states'] else ('run' if state in ('wait', 'preshoot', 'shoot') else 'wait')
                frames = meta['states'][source_state]['frames']
                if args.test_level in (7, 8, 9) and enemy_name.startswith('ptero_'):
                    count = min(8, len(frames))
                    frames = [frames[i * len(frames) // count] for i in range(count)]
                for frame_no, rel in enumerate(frames, 1):
                    if (args.test_level in (7, 8) and enemy_name in ('lezard_rouge', 'raptor_vert', 'raptor_rouge', 'ptero_vert', 'ptero_jaune', 'ptero_rouge')) or (args.test_level == 6 and enemy_name == 'raptor_vert_sp') or (args.test_level not in (3, 6, 7, 8, 9) and (args.test_level in (4, 5) or enemy_name not in ('lezard_jaune_sp', 'raptor_jaune'))):
                        items.append(('enemy/%s/%s/f%03d' % (enemy_name, state, frame_no), enemy_dir / rel))

        # This is the illustrated scene used by the intro menu timeline.
        # It has no linkage name in this version of intro.swf.
        intro = swf.load(str(game / 'intro.swf'))
        intro_resolver = Resolver(intro)
        if intro.get('errors') or 115 not in intro_resolver.sprites:
            raise ValueError('unsupported intro.swf: menu background was not found')
        menu_dest = sprite_root / 'intro'
        menu_dest.mkdir(parents=True)
        with (work / 'intro-menu.log').open('w') as fh:
            run(['java', '-Djava.awt.headless=true', '-Duser.home=' + str(work),
                 '-jar', args.ffdec.resolve(), '-selectid', '115', '-format', 'sprite:png',
                 '-export', 'sprite', menu_dest, game / 'intro.swf'],
                stdout=fh, stderr=subprocess.STDOUT)
        if 'Export finished.' not in (work / 'intro-menu.log').read_text(errors='replace'):
            raise ValueError('FFDec failed to export the original menu artwork')
        menu_path = bake_sprites.Sheet('intro', intro_resolver).pngs(115).get(1)
        if not menu_path:
            raise ValueError('missing exported menu background')
        with Image.open(menu_path) as menu_image:
            if menu_image.size != (600, 500):
                raise ValueError('unsupported intro.swf: menu artwork has unexpected dimensions')
        items.append(('menu/background', Path(menu_path)))

        # Find the HUD by its instance names, rather than assuming character IDs
        # match every copy of the original game.
        main = Resolver(parsed['main'])
        required = {'mcHP': 'health', 'mcRadar': 'radar', 'mcScore': 'score'}
        candidates = []
        for cid in main.sprites:
            frames = main.compile(cid)['frames']
            if not frames:
                continue
            parts = {p.get('name'): p['char'] for p in frames[0]['parts'] if p.get('name')}
            if required.keys() <= parts.keys():
                candidates.append(parts)
        if len(candidates) != 1:
            raise ValueError('could not identify a unique HUD in main.swf')
        hud_sheet = bake_sprites.Sheet('main', main)
        for instance, name in required.items():
            path = hud_sheet.pngs(candidates[0][instance]).get(1)
            if not path:
                raise ValueError('missing HUD sprite: ' + instance)
            items.append(('hud/main/' + name + '/f001', Path(path)))

        # Compose decor from visual children only. The SWF also contains red
        # collision/effect markers that are not terrain artwork.
        tile_offsets = {}
        background_changes = {}
        for decor_name, field, layer_name in (('bclip', 'b', 'background'), ('fclip', 'f', 'foreground')):
            decor_file = game / 'editor/decor' / (decor_name + '.swf')
            decor_data = swf.load(str(decor_file))
            if decor_data.get('errors'):
                raise ValueError('SWF parser errors in ' + decor_name)
            decor = Resolver(decor_data)
            marker_ids = {cid for name, cid in decor.exports.items()
                          if name.startswith(('bounce_', 'effect_', 'action_'))}
            outer_frames = decor.compile(decor.exports['clip'])['frames']
            tile_ids = sorted({cell[field] for row in level['grid'] for cell in row})
            if field == 'f':
                tile_ids = sorted(set(tile_ids) | {1, 10})
            if field == 'b':
                script_dir = work / 'background-scripts'
                script_dir.mkdir()
                with (work / 'background-scripts.log').open('w') as fh:
                    run(['java', '-Djava.awt.headless=true', '-Duser.home=' + str(work),
                         '-jar', args.ffdec.resolve(), '-export', 'script', script_dir, decor_file],
                        stdout=fh, stderr=subprocess.STDOUT)
                if 'Export finished.' not in (work / 'background-scripts.log').read_text(errors='replace'):
                    raise ValueError('FFDec failed to export background scripts')
                for tile in list(tile_ids):
                    outer, inner_index = divmod(tile - 1, 25)
                    mcid = next(p['char'] for p in outer_frames[outer]['parts'] if p.get('name') == 'mc')
                    state = decor.frame_states(mcid)[inner_index]
                    effect = next((p for p in state if p.get('char') == decor.exports.get('effect_house')), None)
                    if not effect:
                        continue
                    action = None
                    for frame in range(inner_index, -1, -1):
                        changes = [p for p in decor.sprites[mcid]['frames'][frame]['place'] if p['depth'] == effect['depth']]
                        if changes and changes[-1].get('clip_actions'):
                            paths = list((script_dir / 'scripts' / ('DefineSprite_%d' % mcid) / ('frame_%d' % (frame + 1))).glob(
                                'PlaceObject*_%d_*_%d/*.as' % (effect['char'], effect['depth'])))
                            if len(paths) != 1:
                                raise ValueError('missing background destruction action for tile %d' % tile)
                            action = paths[0].read_text()
                            break
                        if changes and not changes[-1].get('move'):
                            break
                    hp = re.search(r'\bhp\s*=\s*(\d+)\s*;', action or '')
                    label = re.search(r'\blabel\s*=\s*(\d+)\s*;', action or '')
                    is_background = re.search(r'\bisF\s*=\s*false\s*;', action or '')
                    if not hp or not label or not is_background:
                        raise ValueError('unsupported background destruction action for tile %d' % tile)
                    resistant = bool(re.search(r'\bisPR\s*=\s*true\s*;', action))
                    background_changes[tile] = (int(label.group(1)), int(hp.group(1)) * (3 if resistant else 1), resistant)
                tile_ids = sorted(set(tile_ids) | {v[0] for v in background_changes.values()})
            # Some nested sprites hide editor-only graphics with frame-1
            # ActionScript. FFDec's sprite PNG export does not run those scripts.
            hidden_ids = set()
            if field == 'f':
                script_dir = work / 'foreground-scripts'
                script_dir.mkdir()
                log = work / 'foreground-scripts.log'
                with log.open('w') as fh:
                    run(['java', '-Djava.awt.headless=true', '-Duser.home=' + str(work),
                         '-jar', args.ffdec.resolve(), '-export', 'script', script_dir,
                         decor_file], stdout=fh, stderr=subprocess.STDOUT)
                if 'Export finished.' not in log.read_text(errors='replace'):
                    raise RuntimeError('FFDec failed to export foreground scripts')
                for script in (script_dir / 'scripts').glob('DefineSprite_*/frame_1/DoAction.as'):
                    if re.search(r'(?m)^\s*_visible\s*=\s*false\s*;', script.read_text()):
                        match = re.match(r'DefineSprite_(\d+)', script.parent.parent.name)
                        if match:
                            hidden_ids.add(int(match.group(1)))

            def contains_hidden(cid, stack=()):
                if cid in hidden_ids:
                    return True
                if cid not in decor.sprites or cid in stack:
                    return False
                frames = decor.compile(cid)['frames']
                return bool(frames and any(contains_hidden(p['char'], stack + (cid,))
                                           for p in frames[0]['parts']))

            def leaves(cid, matrix, color, stack=()):
                if cid in hidden_ids:
                    return []
                if cid in stack:
                    raise ValueError('cyclic sprite in foreground')
                if cid in decor.shapes or not contains_hidden(cid):
                    return [(cid, matrix, color)]
                frames = decor.compile(cid)['frames']
                if not frames:
                    return []
                out = []
                for child in frames[0]['parts']:
                    out.extend(leaves(child['char'], bake_sprites.compose(matrix, child['matrix']),
                                      bake_sprites.chain_cx(color, child.get('cxform')), stack + (cid,)))
                return out

            tile_parts = {}
            child_ids = set()
            shape_ids = set()
            for tile_id in tile_ids:
                if not isinstance(tile_id, int) or tile_id < 1:
                    raise ValueError('unsupported background tile ID: %r' % tile_id)
                outer_index, inner_index = divmod(tile_id - 1, 25)
                if outer_index >= len(outer_frames):
                    raise ValueError('background tile ID outside clip: %s' % tile_id)
                inner = next((p['char'] for p in outer_frames[outer_index]['parts'] if p.get('name') == 'mc'), None)
                if inner not in decor.sprites or decor.sprites[inner]['declared_frames'] != 25:
                    raise ValueError('unsupported decor timeline for tile %s' % tile_id)
                parts = decor.compile(inner)['frames'][inner_index]['parts']
                parts = [p for p in parts if p['char'] not in marker_ids and
                         p.get('name') != 'mcZone' and not (p.get('name') or '').startswith('inclin')]
                visual = []
                for p in parts:
                    visual.extend(leaves(p['char'], p['matrix'], p.get('cxform')))
                for cid, _, _ in visual:
                    if cid in decor.sprites:
                        child_ids.add(cid)
                    elif cid in decor.shapes:
                        shape_ids.add(cid)
                    else:
                        raise ValueError('unsupported decor character %s' % cid)
                tile_parts[tile_id] = visual
            dest = sprite_root / decor_name
            dest.mkdir(parents=True)
            log = work / (decor_name + '-ffdec.log')
            if child_ids:
                with log.open('w') as fh:
                    run(['java', '-Djava.awt.headless=true', '-Duser.home=' + str(work),
                         '-jar', args.ffdec.resolve(), '-selectid', ','.join(map(str, sorted(child_ids))),
                         '-format', 'sprite:png', '-export', 'sprite', dest, decor_file],
                        stdout=fh, stderr=subprocess.STDOUT)
                if 'Export finished.' not in log.read_text(errors='replace'):
                    raise RuntimeError('FFDec failed to export ' + decor_name + ' sprites')
            if shape_ids:
                (dest / 'shapes').mkdir()
                with (work / (decor_name + '-shapes.log')).open('w') as fh:
                    run(['java', '-Djava.awt.headless=true', '-Duser.home=' + str(work),
                         '-jar', args.ffdec.resolve(), '-selectid', ','.join(map(str, sorted(shape_ids))),
                         '-format', 'shape:png', '-export', 'shape', dest / 'shapes', decor_file],
                        stdout=fh, stderr=subprocess.STDOUT)
                if 'Export finished.' not in (work / (decor_name + '-shapes.log')).read_text(errors='replace'):
                    raise RuntimeError('FFDec failed to export ' + decor_name + ' shapes')
            decor_sheet = bake_sprites.Sheet(decor_name, decor)
            tile_dir = baked / ('tiles-' + field)
            tile_dir.mkdir()
            for tile_id, parts in tile_parts.items():
                layers = []
                for cid, transform, color in parts:
                    image = decor_sheet.spng(cid) if cid in decor.shapes else decor_sheet.png(cid, 1)
                    image = bake_sprites.apply_cx(image, color)
                    matrix = bake_sprites.compose(transform, decor_sheet.art_off(cid))
                    layers.append((image, matrix))
                if not layers:
                    continue  # transparent cell: no graphic to draw
                image, origin = bake_sprites.comp_items(layers)
                if image.getbbox() is None:
                    continue
                path = tile_dir / ('%d.png' % tile_id)
                image.save(path)
                key = 'tile/%s/%d' % (layer_name, tile_id)
                tile_offsets[key] = origin
                items.append((key, path))
            print('Prepared %s tiles; %d source IDs' % (layer_name, len(tile_ids)), flush=True)

        trimmed = []
        for key, path in items:
            with Image.open(path) as source:
                img = source.convert('RGBA')
            bb = img.getbbox()
            if bb is None:
                raise ValueError('empty prototype sprite: %s' % key)
            img = img.crop(bb)
            fw, fh = img.size
            img = img.resize((max(1, round(fw * .5)), max(1, round(fh * .5))), Image.Resampling.LANCZOS)
            dx, dy = tile_offsets.get(key, (0, 0))
            trimmed.append((key, img, bb[0] + dx, bb[1] + dy, fw, fh))
        sheets, placed = pack_atlases.shelf_pack([(key, im.width, im.height) for key, im, *_ in trimmed])
        atlases = work / 'atlases'
        atlases.mkdir()
        canvases = [Image.new('RGBA', (512, 512)) for _ in sheets]
        sprites = {}
        for key, img, ox, oy, fw, fh in trimmed:
            si, x, y = placed[key]
            canvases[si].paste(img, (x, y))
            sprites[key] = dict(sheet=si, x=x, y=y, w=img.width, h=img.height,
                                ox=ox, oy=oy, fw=fw, fh=fh)
        for i, canvas in enumerate(canvases):
            canvas.save(atlases / ('atlas_%02d.png' % i))
        (atlases / 'atlas_meta.json').write_text(json.dumps({'sprites': sprites, 'data': {'dino/t_rex_vert': dino}}))

        finish_resolver = Resolver(swf.load(str(game / 'editor/decor/fclip.swf')))
        finish_outer = finish_resolver.compile(finish_resolver.exports['clip'])['frames']
        finish_ids = set()
        destructible = {}
        for tile in {c['f'] for row in level['grid'] for c in row}:
            outer, inner = divmod(tile - 1, 25)
            cid = next(p['char'] for p in finish_outer[outer]['parts'] if p.get('name') == 'mc')
            parts = finish_resolver.compile(cid)['frames'][inner]['parts']
            if any(p['char'] == finish_resolver.exports['effect_arrive'] for p in parts):
                finish_ids.add(tile)
            if any(p['char'] == finish_resolver.exports['effect_house'] for p in parts):
                destructible[tile] = 1
            elif any(p['char'] == finish_resolver.exports['effect_tree'] for p in parts):
                destructible[tile] = 2
        if not finish_ids and args.test_level not in (3, 6, 9):
            raise ValueError('no finish tiles found for this level')
        collision, collision_layers, shot_layers = collision_masks.extract(work, game, args.ffdec.resolve(), level, {'b': [v[0] for v in background_changes.values()], 'f': [1, 10]})
        if len(collision) > 255:
            raise ValueError('too many distinct collision masks')

        project = work / 'project'
        (project / 'source').mkdir(parents=True)
        shutil.copy2(REPO / 'dino-port/source/main.c', project / 'source/main.c')
        shutil.copy2(REPO / 'dino-port/source/audio.c', project / 'source/audio.c')
        shutil.copy2(REPO / 'dino-port/source/audio.h', project / 'source/audio.h')
        if args.test_level != 1 or args.project_output:
            source_file = project / 'source/main.c'
            source_file.write_text('#define DINO_TEST_BUILD 1\n' + source_file.read_text())
        # The map view is a diagnostic; tile IDs are not the final artwork.
        cells = [cell for row in level['grid'] for cell in row]
        with (project / 'source/level1.h').open('w') as header:
            header.write('#pragma once\n#include <stdint.h>\n')
            save_hash = hashlib.sha256()
            for relative in ('mobile.swf', 'editor/decor/bclip.swf', 'editor/decor/fclip.swf', ('editor/maps/mtrx%d.swf' % args.test_level)):
                save_hash.update((game / relative).read_bytes())
            for mask in collision:
                save_hash.update(mask)
            for layer in ('b', 'f'):
                for tile, index in sorted(collision_layers[layer].items()):
                    save_hash.update(('%s:%d:%d;' % (layer, tile, index)).encode())
            header.write('#define SAVE_FINGERPRINT 0x%su\n' % save_hash.hexdigest()[:8])
            header.write('#define COLLISION_MASK_COUNT %d\n' % len(collision))
            header.write('#define LEVEL_COLS %d\n#define LEVEL_ROWS %d\n#define LEVEL_MAX_TILE %d\n#define LEVEL_MAX_FG %d\n' % (level['cols'], level['rows'], max([c['b'] for c in cells] + [v[0] for v in background_changes.values()]), max(c['f'] for c in cells)))
            header.write('#define LEVEL_SPAWN_X %.1ff\n#define LEVEL_SPAWN_Y %.1ff\n' % {1: (500, 2150), 2: (650, 1950), 3: (700, 1500), 4: (350, 2050), 5: (600, 750), 6: (850, 1700), 7: (550, 1550), 8: (650, 800), 9: (850, 1700)}[args.test_level])
            header.write('#define LEVEL_SPAWN_ANGLE %.1ff\n' % (-45 if args.test_level == 8 else 0))
            header.write('#define LEVEL_PREDATOR %d\n#define LEVEL_TYPHON %d\n#define PLAYER_MAX_HP %d\n#define LEVEL_RED_RAPTOR %d\n' % (args.test_level in (4, 5, 6), args.test_level in (7, 8, 9), 20 if args.test_level in (4, 5, 6, 7, 8, 9) else 10, args.test_level in (5, 7, 8, 9)))
            if args.test_level in (7, 8, 9):
                for name, pos in vehicle['pose_anchors']['1'].items():
                    header.write('#define TYPHON_%s_X %.2ff\n#define TYPHON_%s_Y %.2ff\n' % (name.upper(), pos[0], name.upper(), pos[1]))
            if args.test_level in (4, 5, 6):
                turret = vehicle['turret']
                header.write('#define TURRET_ORIGIN_X %.2ff\n#define TURRET_ORIGIN_Y %.2ff\n#define TURRET_X %.2ff\n#define TURRET_Y %.2ff\n' % (*turret['origin'], *turret['tour_matrix']))
                header.write('#define GUN_X %.2ff\n#define GUN_Y %.2ff\n' % tuple(turret['anchors']['mcShoot0']))
            bosses = {str(eid): e for cell in cells for eid, e in cell['m'].items() if e.get('l') == ('t_rex_rouge' if args.test_level == 9 else 't_rex_jaune' if args.test_level == 6 else 't_rex_vert')}
            if args.test_level in (3, 6, 9) and len(bosses) != 1:
                raise ValueError('level 3 must contain one green T. rex')
            header.write('#define LEVEL_HAS_BOSS %d\n#define LEVEL_BOSS_YELLOW %d\n#define LEVEL_BOSS_RED %d\n' % (args.test_level in (3, 6, 9), args.test_level == 6, args.test_level == 9))
            if args.test_level in (3, 6, 9):
                header.write('#define BOSS_MAX_HP %d\n#define BOSS_CONTACT_DAMAGE %d\n#define BOSS_SCORE %d\n#define BOSS_BOMB_DAMAGE %d\n' % ((2650, 3, 5000000, 663) if args.test_level == 9 else (700, 3, 2000000, 175) if args.test_level == 6 else (350, 2, 1000000, 88)))
                boss = next(iter(bosses.values()))
                header.write('#define BOSS_X %.2ff\n#define BOSS_Y %.2ff\n#define BOSS_ANGLE %.2ff\n' % (boss['x'], boss['y'], boss.get('a', 0)))
                header.write('#define BOSS_ORIGIN_X %.1ff\n#define BOSS_ORIGIN_Y %.1ff\n' % tuple(dino['origin']))
            header.write('#define HAMMER_ORIGIN_X %s\n#define HAMMER_ORIGIN_Y %s\n' % tuple(vehicle['origin']))
            for name, origin in projectile_origins.items():
                header.write('#define %s_ORIGIN_X %d\n#define %s_ORIGIN_Y %d\n' %
                             (name.upper(), origin[0], name.upper(), origin[1]))
            enemy_names = ('lezard_vert', 'lezard_vert_sp', 'lezard_jaune', 'lezard_rouge', 'raptor_vert', 'lezard_jaune_sp', 'raptor_jaune') + (('raptor_rouge', 'ptero_vert', 'ptero_jaune', 'ptero_rouge') if args.test_level in (7, 8, 9) else ('raptor_rouge',) if args.test_level == 5 else ('raptor_vert_sp',) if args.test_level == 6 else ())
            for index, enemy_name in enumerate(enemy_names):
                meta = enemy_meta[enemy_name]
                zone = Image.open(baked / enemy_name / 'zone.png').getbbox()
                if not zone:
                    raise ValueError('empty collision zone for ' + enemy_name)
                origin_x, origin_y = meta['origin']
                header.write('#define ENEMY_ORIGIN_%d_X %s\n#define ENEMY_ORIGIN_%d_Y %s\n' % (index, origin_x, index, origin_y))
                header.write('#define ENEMY_ZONE_%d_X %sf\n#define ENEMY_ZONE_%d_Y %sf\n' % (index, (zone[0] + zone[2]) / 2 - origin_x, index, (zone[1] + zone[3]) / 2 - origin_y))
                header.write('#define ENEMY_ZONE_%d_RX %sf\n#define ENEMY_ZONE_%d_RY %sf\n' % (index, (zone[2] - zone[0]) / 2, index, (zone[3] - zone[1]) / 2))
            enemies = {}
            for cell in cells:
                for entity_id, entity in cell['m'].items():
                    if entity.get('l') in enemy_names:
                        if entity_id in enemies and enemies[entity_id] != entity:
                            raise ValueError('conflicting enemy placements')
                        enemies[entity_id] = entity
            header.write('static const EnemySpawn LEVEL_ENEMIES[] = {\n')
            for entity_id, enemy in sorted(enemies.items(), key=lambda item: int(item[0])):
                kind = enemy_names.index(enemy['l'])
                header.write('{%ff,%ff,%ff,%d,%d},\n' % (enemy['x'], enemy['y'], enemy.get('a', 0), kind, (3, 3, 5, 7, 15, 5, 30, 50, 20, 40, 50)[kind]))
            if args.test_level == 6:
                for _ in range(3): header.write('{0.0f,0.0f,0.0f,7,0},\n')
            header.write('};\n#define LEVEL_ENEMY_COUNT %d\n' % (len(enemies) + (3 if args.test_level == 6 else 0)))
            header.write('#define LEVEL_ENEMY_TYPES_MASK %d\n' % (sum(1 << enemy_names.index(name) for name in {e['l'] for e in enemies.values()}) | (128 if args.test_level == 6 else 0)))
            pickup_names = ('bonus_hp', 'bonus_weapon', 'bonus_egg')
            for index, name in enumerate(pickup_names):
                ox, oy = pickup_origins[name]
                header.write('#define PICKUP_ORIGIN_%d_X %d\n#define PICKUP_ORIGIN_%d_Y %d\n' % (index, ox, index, oy))
            pickups = {}
            for cell in cells:
                for entity_id, entity in cell['m'].items():
                    if entity.get('l') in pickup_names:
                        if entity_id in pickups and pickups[entity_id] != entity:
                            raise ValueError('conflicting pickup placements')
                        pickups[entity_id] = entity
            # Boxes spawn their pickup only after they are destroyed.
            sorted_props = sorted(level_props.items(), key=lambda item: int(item[0]))
            drop_indices = {}
            for entity_id, prop in sorted_props:
                if prop['l'] in ('box_hp', 'box_weapon'):
                    drop_indices[entity_id] = len(pickups)
                    pickups['box-' + entity_id] = {'x': prop['x'], 'y': prop['y'],
                                                  'l': 'bonus_hp' if prop['l'] == 'box_hp' else 'bonus_weapon',
                                                  'active': False}
            header.write('static const Prop LEVEL_PROPS[%d] = {\n' % max(1, len(sorted_props)))
            for entity_id, prop in sorted_props:
                header.write('{%ff,%ff,%ff,%d,%d,true},\n' %
                             (prop['x'], prop['y'], prop.get('a', 0), prop_names.index(prop['l']), drop_indices.get(entity_id, -1)))
            header.write('};\n#define LEVEL_PROP_COUNT %d\n#define LEVEL_PROP_CAPACITY %d\n' % (len(sorted_props), max(1, len(sorted_props))))
            for kind, name in enumerate(prop_names):
                ox, oy = prop_origins.get(name, (0, 0))
                header.write('#define PROP_ORIGIN_%d_X %d\n#define PROP_ORIGIN_%d_Y %d\n' % (kind, ox, kind, oy))
            header.write('static const Pickup LEVEL_PICKUPS[] = {\n')
            for entity_id, pickup in sorted(pickups.items(), key=lambda item: (item[0].startswith('box-'), int(item[0].removeprefix('box-')))):
                header.write('{%ff,%ff,%d,%s},\n' % (pickup['x'], pickup['y'], pickup_names.index(pickup['l']), 'true' if pickup.get('active', True) else 'false'))
            header.write('};\n#define LEVEL_PICKUP_COUNT %d\n' % len(pickups))
            header.write('#define LEVEL_EGG_TOTAL %d\n' % sum(p['l'] == 'bonus_egg' for p in pickups.values()))
            header.write('static const uint16_t LEVEL_BACKGROUND[] = {\n')
            for cell in cells:
                value = cell['b']
                if value is None or not 0 <= value <= 65535:
                    raise ValueError('unsupported level 1 background tile ID')
                header.write('%d,' % value)
            header.write('\n};\n')
            if any(tile not in collision_layers['f'] for tile in (1, 10)):
                raise ValueError('missing replacement foreground collision data')
            header.write('#define RUBBLE_COLLISION %d\n#define RUBBLE_SHOT_COLLISION %d\n' %
                         (collision_layers['f'][10], shot_layers['f'][10]))
            header.write('#define EMPTY_COLLISION %d\n#define EMPTY_SHOT_COLLISION %d\n' %
                         (collision_layers['f'][1], shot_layers['f'][1]))
            header.write('static const uint16_t LEVEL_B_REPLACEMENT[] = {%s};\n' %
                         ','.join(str(background_changes.get(cell['b'], (0, 0, False))[0]) for cell in cells))
            header.write('static const uint8_t LEVEL_B_HEALTH[] = {%s};\n' %
                         ','.join(str(background_changes.get(cell['b'], (0, 0, False))[1]) for cell in cells))
            header.write('static const uint8_t LEVEL_B_REPLACEMENT_COLLISION[] = {%s};\n' %
                         ','.join(str(collision_layers['b'].get(background_changes.get(cell['b'], (0, 0, False))[0], 0)) for cell in cells))
            header.write('static const uint8_t LEVEL_B_REPLACEMENT_SHOT[] = {%s};\n' %
                         ','.join(str(shot_layers['b'].get(background_changes.get(cell['b'], (0, 0, False))[0], 0)) for cell in cells))
            header.write('static const uint8_t LEVEL_DESTRUCT_KIND[] = {%s};\n' %
                         ','.join(str(destructible.get(cell['f'], 0)) for cell in cells))
            header.write('static const uint16_t LEVEL_FINISH_IDS[] = {%s};\n' % ','.join(map(str, sorted(finish_ids))))
            header.write('#define LEVEL_FINISH_COUNT %d\n' % len(finish_ids))
            header.write('static const uint16_t LEVEL_FOREGROUND[] = {\n')
            for cell in cells:
                header.write('%d,' % cell['f'])
            header.write('\n};\n')
            for layer in ('b', 'f'):
                header.write('static const uint8_t LEVEL_COLLISION_%s[] = {\n' % layer.upper())
                for cell in cells:
                    header.write('%d,' % collision_layers[layer][cell[layer]])
                header.write('\n};\n')
            for layer in ('b', 'f'):
                header.write('static const uint8_t LEVEL_SHOT_%s[] = {\n' % layer.upper())
                for cell in cells:
                    header.write('%d,' % shot_layers[layer][cell[layer]])
                header.write('\n};\n')
            header.write('static const uint8_t COLLISION_MASKS[%d][1250] = {\n' % len(collision))
            for mask in collision:
                header.write('{' + ','.join(str(v) for v in mask) + '},\n')
            header.write('};\n')
            anchors = vehicle['anchors']
            hits = [anchors['mcHit%d' % i] for i in range(4)]
            hits.sort(key=lambda hit: math.atan2(hit[1], hit[0]))
            header.write('static const float HAMMER_HITS[4][2] = {%s};\n' %
                         ','.join('{%ff,%ff}' % (x, y) for x, y in hits))
        extract_audio.extract(game, project / 'data')
        run([sys.executable, REPO / 'tools/gen_skeleton.py' , '--src', atlases,
             '--project', project, '--tex3ds', tex3ds])
        run([sys.executable, REPO / 'tools/build3ds.py', project])
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(project / 'dinodino.3dsx', output)
        if args.project_output:
            destination = args.project_output.resolve()
            if destination.exists():
                raise ValueError('project output already exists: %s' % destination)
            shutil.copytree(project, destination)
        print('Built 3DS prototype:', output)
        print('The game is a work in progress; some behavior remains approximate.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as exc:
        print('Prototype build failed:', exc, file=sys.stderr)
        sys.exit(1)
