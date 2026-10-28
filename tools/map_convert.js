#!/usr/bin/env node
// Convert decompiled mtrx*.as lMap literal -> clean JSON.
// Usage: node map_convert.js <mtrx.as> [<mtrx.as> ...] --out <dir>
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const argv = process.argv.slice(2);
let outDir = null;
const inputs = [];
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === '--out') { outDir = argv[++i]; continue; }
  inputs.push(argv[i]);
}
if (!inputs.length || !outDir) {
  console.error('usage: node map_convert.js <mtrx.as> ... --out <dir>');
  process.exit(1);
}
fs.mkdirSync(outDir, { recursive: true });

for (const file of inputs) {
  const src = fs.readFileSync(file, 'utf8');
  // decompiled file is frame_1/DoAction.as content:  "lMap = [...]" plus
  // subsequent "lMap[j][i].m[n] = {dat:{...}}" statements.
  // Strip comments and eval in a sandbox.
  const code = src.replace(/^\/\/.*$/gm, '');
  const sandbox = {};
  try {
    vm.runInNewContext(code, sandbox, { filename: path.basename(file) });
  } catch (e) {
    console.error(file, 'ERR', e.message);
    continue;
  }
  const lMap = sandbox.lMap;
  if (!Array.isArray(lMap)) { console.error(file, 'no lMap'); continue; }
  // count stats + convert 0-based refs to ints
  let cells = 0, mobs = 0;
  const map = lMap.map((row, j) => row.map((c, i) => {
    cells++;
    const cell = { b: c.b, f: c.f, m: [] };
    for (const k in c.m || {}) {
      const e = c.m[k];
      if (e && e.dat) {
        const d = e.dat;
        cell.m.push({
          id: Number(k),
          x: Number(d.x), y: Number(d.y),
          a: Number(d.a || 0), l: d.l, z: Number(d.z),
          i: Number(d.i), j: Number(d.j),
          xg: d.xg !== undefined ? Number(d.xg) : null,
          yg: d.yg !== undefined ? Number(d.yg) : null
        });
        mobs++;
      }
    }
    return cell;
  }));
  const rows = map.length, cols = map[0].length;
  const name = path.basename(file, '.as').replace(/^mtrx/i, 'map');
  fs.writeFileSync(path.join(outDir, name + '.json'), JSON.stringify({
    rows, cols, cells, mobs, map
  }));
  console.log(file.replace(/.*\/(?=)/,''), '->', name + '.json', `${rows}x${cols}`, 'mobs', mobs);
}
