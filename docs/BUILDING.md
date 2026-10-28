# Building and installing

## Setup

The documented workflow has been used on Linux. Other environments may need
adjustments and have not been verified. Install Python 3, Java, FFmpeg,
[FFDec](https://github.com/jindrapetrik/jpexs-decompiler), and the
[devkitPro 3DS toolchain](https://devkitpro.org/wiki/Getting_Started). The
builder uses devkitARM, libctru, citro2d, citro3d, tex3ds, bin2s, and 3dsxtool.
Install the Python packages from the repository root:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Activate the virtual environment before running the build in a new shell.

For CIA packaging install [makerom](https://github.com/3DSGuy/Project_CTR/tree/master/makerom)
and [bannertool](https://github.com/carstene1ns/3ds-bannertool) separately.
Place them on PATH or in `tools/`, or pass their paths with `--makerom` and
`--bannertool`. These tools are not needed with `--3dsx-only`.

FFDec is invoked as `java -jar .../ffdec.jar`. The distribution may require
other files alongside the jar, so keep the extracted FFDec installation intact.
Use `--ffdec` to specify the jar, or set `FFDEC_JAR` once in your shell.
If `DEVKITPRO` is unset, the scripts look in `/opt/devkitpro`; `DEVKITARM`
defaults to its `devkitARM` subdirectory.

## One-command campaign build

Supply the path to the directory containing `Launcher.swf`, `player/`, and
`editor/`, and the location of FFDec:

```sh
python3 build.py "/path/to/DinoAttackGame" --ffdec "/path/to/ffdec/ffdec.jar"
```

The default builds both `build-output/dinodino.3dsx` and
`build-output/dinodino.cia`. Append one of these flags to select a format:

```sh
python3 build.py "/path/to/DinoAttackGame" --ffdec "/path/to/ffdec/ffdec.jar" --3dsx-only
python3 build.py "/path/to/DinoAttackGame" --ffdec "/path/to/ffdec/ffdec.jar" --cia-only
```

To choose a different destination, append `--output-dir "/path/to/output"`.
The output directory cannot be the game directory or a subdirectory of it.
The build uses temporary directories to extract and compile the assets. A
CIA-only build still compiles an intermediate 3DSX in a temporary directory,
but only the CIA is saved in the chosen output directory. Conversion runs nine
individual level builds, so allow time and disk space.

The build requires the files listed in the [README](../README.md). It checks
for missing files and tools before starting; unsupported versions can still
fail later if their Flash structures differ. Asset extraction and the result
are derived from the user's own files.

## Installing and testing

Copy `dinodino.3dsx` to an SD card location recognized by the Homebrew
Launcher. Alternatively, install `dinodino.cia` with a title manager on a
3DS configured to run homebrew. The CIA uses homebrew title ID
`000400000D1A7700`; its HOME Menu icon and banner are derived from the supplied
launcher artwork. The banner is silent. The CIA and 3DSX read the same SD-card
campaign saves in `sdmc:/3ds/dinodino/`.

The separate development selector makes all nine levels available immediately
and does not use campaign saves:

```sh
python3 tools/build_level_tests.py "/path/to/DinoAttackGame" \
  --ffdec "/path/to/ffdec/ffdec.jar" --output build-output/dinodino-level-tests.3dsx
```

START returns from a level to the selector. This is a testing tool and is not
the normal campaign experience.

## Troubleshooting

- **Missing files:** point to the game folder itself, not its parent, and keep
  the original directory structure shown in the README.
- **FFDec or Java error:** verify the jar path, Java installation, and FFDec
  distribution. Only the identified game version has been exercised.
- **devkitPro tool or library missing:** install the 3DS development components
  and check `DEVKITPRO` and `DEVKITARM`.
- **CIA tools missing:** put both executables on PATH or use their explicit
  flags. For a 3DSX without them, use `--3dsx-only`.
- **No sound:** check the system volume and DSP firmware; audio has not been
  fully verified across devices. Playback should fail silently if DSP setup
  is unavailable, leaving the game playable.
- **Save error:** check that the SD card is writable. Progress is saved at
  level boundaries, not at the current position.

Do not upload the supplied game files, generated executables, extracted data,
or third-party tool binaries as part of this repository. The ignore rules help
with this but do not remove files that Git is already tracking.

Before publishing, inspect `git status --short` and `git ls-files` in your
actual repository. If it already tracked local files, remove those entries from
the index before publishing. The project owner should also choose a license for
the port's original code; none has been selected in this workspace.
