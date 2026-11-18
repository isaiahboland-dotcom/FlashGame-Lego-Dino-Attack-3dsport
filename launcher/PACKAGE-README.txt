Dino Attack for Nintendo 3DS - launcher
=======================================

An unofficial, work-in-progress fan port of the Flash game Dino Attack. This
package holds the port's code, the build scripts, FFDec and the .cia tools.
You need your own copy of the Dino Attack game files (the DinoAttackGame
folder from the original Flash game). Nothing from the game is in this package.

THIS PACKAGE DOES NOT INCLUDE EVERYTHING THE BUILD NEEDS.
Install these once. The launcher finds them by itself; its Settings tab shows
what it found, and the Build tab says what is missing.

  Python 3, with Pillow and NumPy
      Windows:  winget install Python.Python.3.12
                then, in this folder:  py -3 -m pip install -r requirements.txt
      Linux:    sudo pacman -S python-pillow python-numpy
                (Debian/Ubuntu: sudo apt install python3-pil python3-numpy)

  Java 8 or newer (runs FFDec, which is in ffdec_26.4.0/)
      Windows:  winget install EclipseAdoptium.Temurin.21.JDK
      Linux:    sudo pacman -S jre-openjdk-headless
                (Debian/Ubuntu: sudo apt install default-jre-headless)

  FFmpeg
      Windows:  winget install Gyan.FFmpeg
      Linux:    sudo pacman -S ffmpeg   (Debian/Ubuntu: sudo apt install ffmpeg)

  devkitPro's 3DS tools (the 3ds-dev group)
      Windows:  install the devkitPro Updater from https://devkitpro.org and
                select the 3DS development tools.
      Linux:    install devkitPro's pacman (https://devkitpro.org/wiki/devkitPro_pacman),
                then:  sudo dkp-pacman -S 3ds-dev

The package names above are the usual ones and can differ between distributions
and versions. Open a new terminal after installing, so the programs are on PATH.

Then:

  1. Run dino-launcher (dino-launcher.exe on Windows). Keep it in this folder,
     next to build.py, tools/ and ffdec_26.4.0/.
  2. Check the Settings tab. If a program is somewhere unusual (devkitPro in a
     custom folder, Python in a virtual environment), set its path there with
     Browse. "Automatic" goes back to finding it by itself.
  3. Pick your DinoAttackGame folder (the one that contains Launcher.swf).
  4. Put the 3DS's SD card in this computer and pick it.
  5. Tick .3dsx and/or .cia, and press Build. The first build takes a long
     while; later builds are faster.

The launcher copies the finished files to the card:

  - .3dsx: 3ds/dinodino.3dsx. Start it from the Homebrew Launcher.
  - .cia:  cias/dinodino.cia. Install it with FBI, then start it from the
           HOME Menu. (.cia is experimental, and the Windows .cia is untested.)

Your saves in 3ds/dinodino/ are never touched.

Sound needs the console's DSP firmware at 3ds/dspfirm.cdc on the card (run
DSP1 once). The launcher tells you if it is missing.

Settings are saved in %APPDATA%\dinoattack-3ds-launcher\settings.txt on
Windows and ~/.config/dinoattack-3ds-launcher/settings.txt on Linux.

If something fails, the window shows why. The same steps can be run from a
terminal; see docs/BUILDING.md. `dino-launcher --check` prints where each
program was found.

Project and source: https://github.com/isaiahboland-dotcom/FlashGame-Lego-Dino-Attack-3dsport
Licence: MIT for the project's code (see LICENSE.md). It does not cover the game.
