Dino Attack for Nintendo 3DS - launcher
=======================================

An unofficial, work-in-progress fan port of the Flash game Dino Attack. This
package holds the port's code and build tools only. You need your own copy of
the Dino Attack game files (the DinoAttackGame folder from the original Flash
game). Nothing from the game is in this package. The launcher converts your
copy on this computer and builds the 3DS files from it.

Install these once (the launcher's log says which ones are missing):

  - Python 3, with Pillow and NumPy. In this folder run:
        python -m pip install -r requirements.txt
  - Java (runs FFDec, which is included in ffdec_26.4.0/).
  - FFmpeg, on PATH.
  - devkitPro with the 3DS tools (devkitARM, libctru, citro2d, citro3d, and
    the 3DS tools). See https://devkitpro.org/wiki/Getting_Started. If it is
    not in C:\devkitPro (Windows) or /opt/devkitpro (Linux), set DEVKITPRO.

Then:

  1. Run dino-launcher (dino-launcher.exe on Windows).
  2. Pick your DinoAttackGame folder (the one that contains Launcher.swf).
  3. Put the 3DS's SD card in this computer and pick it.
  4. Tick .3dsx and/or .cia, and press Build. The first build takes a long
     while; later builds are faster.

The launcher copies the finished files to the card:

  - .3dsx: 3ds/dinodino.3dsx. Start it from the Homebrew Launcher.
  - .cia:  cias/dinodino.cia. Install it with FBI, then start it from the
           HOME Menu. (.cia is experimental, and the Windows .cia is untested.)

Your saves in 3ds/dinodino/ are never touched.

Sound needs the console's DSP firmware at 3ds/dspfirm.cdc on the card (run
DSP1 once). The launcher tells you if it is missing.

If something fails, the window shows why. The same steps can be run from a
terminal; see docs/BUILDING.md:

  dino-launcher --cli --game "path/to/DinoAttackGame" --sd "path/to/SD" [--cia] [--no-3dsx]

Project and source: https://github.com/isaiahboland-dotcom/FlashGame-Lego-Dino-Attack-3dsport
Licence: MIT for the project's code (see LICENSE). It does not cover the game.
