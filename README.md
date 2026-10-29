# Lego Dino Attack 3DS

An unofficial port for the Nintendo 3DS of the original Flash game
Lego Dino Attack. This repository supplies the port and build tools. **You must
supply your own copy of the original game files**; the game, its artwork, and
its audio are not included. The build extracts assets from those files and
embeds them in the generated executables. Do not publish those generated files
as a substitute for supplying the original game.

**AI disclosure:** This codebase, its build scripts, and its documentation were
written by AI assistants under the project owner's direction. Behavior was
reconstructed from the game files and refined through player testing; it is
not an official source release or a complete reproduction of the original.

All nine levels are playable individually in the development builds. The
campaign, save progression, audio, and recent rendering fixes still need a
complete playthrough and further hardware testing. Some mechanics and animation
timings are approximations, and the original ending movies are not implemented.

## Build from your files

The build pipeline has been developed on Linux. You need:

- Python 3, [Pillow and NumPy](requirements.txt), Java, and FFmpeg on PATH.
- [devkitPro](https://devkitpro.org/wiki/Getting_Started), including devkitARM,
  libctru, citro2d, citro3d, and the 3DS tools. The default installation is
  `/opt/devkitpro`; set `DEVKITPRO` and `DEVKITARM` for another location.
- [JPEXS FFDec](https://github.com/jindrapetrik/jpexs-decompiler), tested with
  version 26.4.0. You need the `ffdec.jar` from its distribution.
- For CIA output, [makerom](https://github.com/3DSGuy/Project_CTR/tree/master/makerom)
  and [bannertool](https://github.com/carstene1ns/3ds-bannertool) on PATH or
  placed in `tools/` as executables. They are not included in this repository.

Install the Python dependencies once:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Then run **one command** from the repository root, replacing both paths with
locations on your machine. Keep the quotes if either path contains spaces:

```sh
python3 build.py "/path/to/DinoAttackGame" --ffdec "/path/to/ffdec/ffdec.jar"
```

This creates `build-output/dinodino.3dsx` and `build-output/dinodino.cia`.
To build just one format, add `--3dsx-only` or `--cia-only`:

```sh
python3 build.py "/path/to/DinoAttackGame" --ffdec "/path/to/ffdec/ffdec.jar" --3dsx-only
python3 build.py "/path/to/DinoAttackGame" --ffdec "/path/to/ffdec/ffdec.jar" --cia-only
```

You can set `FFDEC_JAR` once instead of passing `--ffdec` each time:

```sh
export FFDEC_JAR="/path/to/ffdec/ffdec.jar"
python3 build.py "/path/to/DinoAttackGame"
```

Use `--output-dir` to choose another output directory, and `--makerom` and
`--bannertool` to specify those executables explicitly. Run `python3 build.py --help` for all options.
The output directory must be outside the original game folder. The first build
extracts and converts all nine levels and can take a while.

Your game folder must contain the original files in this layout:

```text
DinoAttackGame/
  Launcher.swf  intro.swf  main.swf  mobile.swf
  soundmain.swf  soundgame.swf
  player/hammer.swf  player/predator.swf  player/typhon.swf
  editor/decor/bclip.swf  editor/decor/fclip.swf
  editor/maps/mtrx1.swf ... editor/maps/mtrx9.swf
```

The builder checks for these files, but other game versions may have different
assets or structures and are not guaranteed to work. See the [build
notes](docs/BUILDING.md) for installation, prerequisites, troubleshooting,
and the separate development selector.

## Playing

Copy the `.3dsx` to your SD card and launch it through the Homebrew Launcher.
The `.cia` can be installed with a title manager on a suitably configured 3DS.
Both formats use the same campaign saves.

The main menu offers **Play**, **Continue**, and **Level Select**. Play starts
at level 1. Continue starts at the beginning of the current level; completing a
level saves and unlocks the next one. Level Select offers unlocked levels, and
starting a new game keeps previous unlocks. Press **A** on a completion screen
to advance. **START** returns to the menu.

Drive and steer with the **D-pad**, or steer with the **Circle Pad** and use
**A/B** for forward/reverse. **L/R** fire; hold and release to use charged
weapons after collecting upgrades. **X** uses a bomb and **SELECT** restarts
the current level.

The game uses the original menu theme, vehicle sounds, and selected combat,
pickup, and boss effects. Audio timing and balance still need 3DS testing.
There is no background music during normal gameplay, matching the original
launcher behavior. Audio playback may require the console's DSP firmware.

## Project documentation

- [Build and installation guide](docs/BUILDING.md)
- [Porting decisions and known limitations](docs/DECISIONS.md)
- [Architecture and asset pipeline](docs/ARCHITECTURE.md)
