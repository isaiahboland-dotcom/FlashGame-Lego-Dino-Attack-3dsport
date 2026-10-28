# Architecture

The port is a native C implementation for libctru, citro2d, and citro3d. It
does not run the original Flash code. Python tools inspect supplied SWFs and
use FFDec to export artwork and map scripts, FFmpeg to decode sounds, and
`tex3ds` to prepare textures.

`build.py` checks inputs and tools and invokes the campaign build. The level
builder (`tools/build_level_tests.py`) calls `tools/build_prototype.py` once
per level, creating generated maps, collision masks, texture atlases, and
sound data in temporary projects. It combines those projects with the campaign
menu or the separate development selector, then compiles and links a 3DSX.
For CIA output, `tools/build_cia.py` derives HOME Menu art from the supplied
launcher JPEG and invokes bannertool and makerom on the linked ELF.

The runtime in `dino-port/source/main.c` handles rendering, movement,
collisions, pickups, enemies, weapons, and level completion. The shared audio
module owns DSP channels for the menu theme, vehicle loops, and effects.
`tools/campaign_menu.c` launches the generated levels and manages progress;
`tools/level_test_menu.c` is a separate selector for testing all levels.
The levels currently contain separately compiled copies of the runtime, each
with its own generated level data and atlases.

The campaign progress record contains a current level and highest unlocked
level, plus a version, game-data fingerprint, generation, and checksum. Two
alternating slots allow recovery when a write fails or a slot is damaged.
The development selector does not modify these files. The game records level
boundaries, so a resumed level begins fresh.

The SWF parser and conversion code support the identified game data and are
not general-purpose Flash implementations. Compatibility with other builds of
the game, gameplay accuracy, save behavior on hardware, and the full campaign
should be tested before calling the port complete.
