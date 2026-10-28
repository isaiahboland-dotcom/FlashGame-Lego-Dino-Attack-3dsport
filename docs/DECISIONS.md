# Porting decisions

This project was built by AI assistants and guided by the project owner's
incremental 3DS tests. The original Flash game is the reference for extracted
assets and observed behavior. The following notes describe decisions in the
current implementation, including approximations that should be revisited.

## Files and distribution

Each player supplies their own game files. The build extracts maps, graphics,
collision shapes, sound, and menu art locally; it then embeds the derived data
in the 3DS executable. Generated executables and intermediate exports are not
part of the intended source repository. Third-party tools are installed
separately. A default-deny `.gitignore` helps prevent accidental inclusion of
local game files and research material.

## Display and controls

The top screen shows the game world and the bottom screen carries the HUD,
using the second screen for health, radar, score, pickups, and other status.
The camera includes extra tiles past the edges to avoid visible pop-in, and
adjoining background tiles overlap slightly to reduce rasterization seams.
The seam adjustment needs continued hardware verification.

The D-pad supports steering and movement. The Circle Pad points the vehicle in
an intended direction, while A and B control forward and reverse. L and R both
fire; charged shots use unlocked weapon upgrades, and X uses a bomb. This
preserves a simple control layout for a game with relatively few actions.

## Collision and levels

The maps, placements, and collision masks are derived from the supplied SWFs.
Collision is an approximation of Flash shape tests, not a full Flash runtime.
Flyers use foreground collision to avoid passing through tall buildings while
remaining able to cross ground obstacles. Level 8 contains 14 invalid original
background values at the map edge; the exporter substitutes the neighboring
edge tile for those values.

The Predator's shots were intentionally extended to reach the visible screen
edge after testing showed the original shorter range felt restrictive. Enemy,
boss, combat, scenery, and animation behavior are reconstructed and may differ
from the Flash game. The car's charged projectiles use their growing animation
frames instead of remaining on the tiny first frame.

## Menus and saves

The main menu uses artwork from the original intro. Play, Continue, and Level
Select are additions for the 3DS port. Play begins at level 1; Continue starts
at the beginning of the current level; Level Select is limited to previously
unlocked levels. Starting over preserves unlocked levels.

Finishing a level records the next checkpoint before the player advances.
The game writes two versioned, checked SD-card save slots and binds them to a
fingerprint of the supplied game data. A damaged slot can fall back to the
other. The current position, enemies, pickups, health, and score within a
partially played level are not saved. Old prototype saves are not migrated.
These semantics and full campaign progression need more hardware testing.

A separate development-only selector allows immediate access to every level.
It does not read or write campaign progression and is not the campaign menu.

## Audio and ending

The menu and completion screens use the original theme; the original launcher
fades the theme out before gameplay. Vehicle loops and selected weapon, pickup,
enemy, and boss effects are extracted from the game's sound banks. The timing,
volume, and coverage are approximations and require hardware testing. The
HOME Menu CIA banner has a silent jingle.

Defeating the last boss displays a completion message and returns to the main
menu. The original ending movies and some original effects and transitions are
not implemented. A full end-to-end playthrough has not yet verified the port.
