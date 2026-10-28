#!/usr/bin/env python3
"""Validate a supplied Dino Attack installation and inspect its SWF files.

This prepares research data for the unfinished port; it does not build a game.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import swf

ROOT_SWFS = ("Launcher", "introsplash", "intro", "main", "kernel", "mobile",
             "soundmain", "soundgame", "boss1", "trans1", "trans2", "trans3",
             "win1", "win2", "win3")
REQUIRED = ([f"{name}.swf" for name in ROOT_SWFS]
            + [f"player/{name}.swf" for name in ("hammer", "predator", "typhon")]
            + [f"editor/decor/{name}.swf" for name in ("bclip", "fclip")]
            + [f"editor/maps/mtrx{i}.swf" for i in range(1, 10)]
            + ["lang.xml", "yamzsound.xml"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game_dir", type=Path, help="user-supplied game directory containing Launcher.swf")
    parser.add_argument("--output", type=Path, required=True, help="directory for generated research data")
    args = parser.parse_args()
    game = args.game_dir.resolve()
    output = args.output.resolve()
    if output == game or game in output.parents:
        parser.error("output must be outside the supplied game directory")
    missing = [name for name in REQUIRED if not (game / name).is_file()]
    if missing:
        print("Missing required files:\n  " + "\n  ".join(missing), file=sys.stderr)
        return 1
    results = []
    try:
        for name in REQUIRED:
            path = game / name
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            entry = {"path": name, "sha256": digest}
            if path.suffix.lower() == ".swf":
                parsed = swf.load(str(path))
                errors = parsed.get("errors", [])
                entry.update({"fps": parsed["fps"], "frames": parsed["frame_count"],
                              "parser_errors": len(errors)})
                results.append((entry, {k: v for k, v in parsed.items() if k != "sound_blobs"}))
            else:
                results.append((entry, None))
    except (OSError, ValueError, EOFError, IndexError, KeyError) as exc:
        print(f"Failed to read {name}: {exc}", file=sys.stderr)
        return 1
    output.mkdir(parents=True, exist_ok=True)
    for entry, parsed in results:
        if parsed is not None:
            dest = output / Path(entry["path"]).with_suffix(".json")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(parsed, indent=1) + "\n", encoding="utf-8")
    (output / "manifest.json").write_text(json.dumps({"files": [e for e, _ in results]}, indent=2) + "\n", encoding="utf-8")
    errors = sum(e.get("parser_errors", 0) for e, _ in results)
    print(f"Inspected {len(results)} files; {errors} SWF parser errors. Output: {output}")
    print("This is research data, not a playable 3DS build.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
