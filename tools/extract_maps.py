#!/usr/bin/env python3
"""Convert the nine user-supplied SWF maps into validated JSON data."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

TOKEN = re.compile(r'\s*(?:(//[^\n]*|/\*[\s\S]*?\*/)|("(?:\\.|[^"\\])*")|(-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)|([A-Za-z_$][\w$]*)|([\[\]{}:;,=.]))')


class Parser:
    def __init__(self, text):
        self.tokens = []
        pos = 0
        while pos < len(text):
            m = TOKEN.match(text, pos)
            if not m:
                if not text[pos:].strip():
                    break
                raise ValueError('unsupported map syntax at offset %d: %r' % (pos, text[pos:pos+40]))
            pos = m.end()
            if not m.group(1):
                self.tokens.append(next(x for x in m.groups()[1:] if x is not None))
        self.pos = 0

    def take(self, wanted=None):
        if self.pos >= len(self.tokens):
            raise ValueError('unexpected end of map script')
        tok = self.tokens[self.pos]
        self.pos += 1
        if wanted is not None and tok != wanted:
            raise ValueError('expected %r, got %r' % (wanted, tok))
        return tok

    def value(self):
        tok = self.take()
        if tok == '[':
            out = []
            while self.tokens[self.pos] != ']':
                if out:
                    self.take(',')
                out.append(self.value())
            self.take(']')
            return out
        if tok == '{':
            out = {}
            while self.tokens[self.pos] != '}':
                if out:
                    self.take(',')
                key = self.take()
                if key.startswith('"'):
                    key = json.loads(key)
                self.take(':')
                if key in out:
                    raise ValueError('duplicate property %s' % key)
                out[key] = self.value()
            self.take('}')
            return out
        if tok.startswith('"'):
            return json.loads(tok)
        if tok in ('true', 'false', 'null', 'NaN'):
            return {'true': True, 'false': False, 'null': None, 'NaN': None}[tok]
        try:
            return float(tok) if any(c in tok for c in '.eE') else int(tok)
        except ValueError:
            raise ValueError('unsupported value %r' % tok) from None

    def parse(self):
        self.take('lMap'); self.take('=')
        grid = self.value(); self.take(';')
        if not grid or not isinstance(grid, list) or not all(isinstance(r, list) and len(r) == len(grid[0]) for r in grid):
            raise ValueError('map grid must be a nonempty rectangle')
        for row in grid:
            for cell in row:
                if not isinstance(cell, dict) or set(cell) != {'b', 'f', 'm'} or cell['m'] != {} or not all(cell[k] is None or (type(cell[k]) is int and cell[k] >= 0) for k in ('b', 'f')):
                    raise ValueError('unexpected map cell')
        while self.pos < len(self.tokens):
            self.take('lMap'); self.take('['); j = int(self.take()); self.take(']')
            self.take('['); i = int(self.take()); self.take(']'); self.take('.'); self.take('m')
            self.take('['); entity_id = int(self.take()); self.take(']'); self.take('=')
            value = self.value(); self.take(';')
            if not (0 <= j < len(grid) and 0 <= i < len(grid[0])) or entity_id < 0:
                raise ValueError('entity reference outside map')
            if not isinstance(value, dict) or not isinstance(value.get('dat'), dict):
                raise ValueError('invalid entity data')
            if str(entity_id) in grid[j][i]['m']:
                raise ValueError('duplicate entity reference')
            grid[j][i]['m'][str(entity_id)] = value['dat']
        return grid


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('game_dir', type=Path)
    ap.add_argument('--ffdec', type=Path, required=True, help='path to FFDec ffdec.jar')
    ap.add_argument('--output', type=Path, required=True, help='output directory outside the game folder')
    args = ap.parse_args()
    game, out = args.game_dir.resolve(), args.output.resolve()
    if out == game or game in out.parents:
        ap.error('output must be outside the game directory')
    jar = args.ffdec.resolve()
    files = [game / 'editor/maps' / ('mtrx%d.swf' % i) for i in range(1, 10)]
    for path in [jar] + files:
        if not path.is_file():
            ap.error('missing file: %s' % path)
    results = []
    with tempfile.TemporaryDirectory(prefix='dino-maps-') as tmp:
        temp = Path(tmp)
        for index, path in enumerate(files, 1):
            dest = temp / str(index)
            dest.mkdir()
            proc = subprocess.run(['java', '-Djava.awt.headless=true', '-Duser.home=' + str(temp), '-jar', str(jar), '-export', 'script', str(dest), str(path)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            script = dest / 'scripts/frame_1/DoAction.as'
            if proc.returncode or 'Export finished.' not in proc.stdout or not script.is_file():
                raise ValueError('FFDec failed for %s: %s' % (path, proc.stdout[-2000:]))
            grid = Parser(script.read_text(encoding='utf-8-sig')).parse()
            entities = {}
            refs = 0
            for row in grid:
                for cell in row:
                    for entity_id, data in cell['m'].items():
                        if entity_id in entities and entities[entity_id] != data:
                            raise ValueError('conflicting data for entity %s in %s' % (entity_id, path))
                        entities[entity_id] = data
                        refs += 1
            results.append({'level': index, 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                            'rows': len(grid), 'cols': len(grid[0]), 'entity_count': len(entities),
                            'entity_references': refs, 'nonfinite_tile_count': sum(cell[k] is None for row in grid for cell in row for k in ('b', 'f')), 'grid': grid})
            print('Level %d: %d x %d, %d entities (%d cell references), %d NaN tiles' % (index, len(grid[0]), len(grid), len(entities), refs, results[-1]['nonfinite_tile_count']), flush=True)
    out.mkdir(parents=True, exist_ok=True)
    for result in results:
        (out / ('map%d.json' % result['level'])).write_text(json.dumps(result, separators=(',', ':')) + '\n', encoding='utf-8')
    print('Map data written to', out)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, IndexError) as exc:
        print('Map extraction failed:', exc, file=sys.stderr)
        sys.exit(1)
