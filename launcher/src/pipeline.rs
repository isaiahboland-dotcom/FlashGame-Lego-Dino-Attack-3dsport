//! The build itself: runs the project's `build.py` on the game folder the user
//! picked, then copies the finished files to the SD card. The launcher does
//! not reimplement the build; `build.py` stays the single source of truth.

use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use crate::settings::Settings;
use crate::tools::{self, Tool};
use crate::{hide_window, Log};

#[derive(Clone)]
pub struct Options {
    pub game: PathBuf,
    pub sd: PathBuf,
    pub want_3dsx: bool,
    pub want_cia: bool,
}

/// The files a Dino Attack game folder must hold (the same list `build.py`
/// checks, so a bad folder is reported before any work starts).
const GAME_FILES: [&str; 20] = [
    "Launcher.swf",
    "intro.swf",
    "main.swf",
    "mobile.swf",
    "soundmain.swf",
    "soundgame.swf",
    "editor/decor/bclip.swf",
    "editor/decor/fclip.swf",
    "player/hammer.swf",
    "player/predator.swf",
    "player/typhon.swf",
    "editor/maps/mtrx1.swf",
    "editor/maps/mtrx2.swf",
    "editor/maps/mtrx3.swf",
    "editor/maps/mtrx4.swf",
    "editor/maps/mtrx5.swf",
    "editor/maps/mtrx6.swf",
    "editor/maps/mtrx7.swf",
    "editor/maps/mtrx8.swf",
    "editor/maps/mtrx9.swf",
];

/// Where downloads and scratch files go.
pub fn work_dir() -> PathBuf {
    if let Some(p) = std::env::var_os("DINO_WORK") {
        return PathBuf::from(p);
    }
    let base = if cfg!(windows) {
        std::env::var_os("LOCALAPPDATA").map(PathBuf::from)
    } else if cfg!(target_os = "macos") {
        std::env::var_os("HOME").map(|h| PathBuf::from(h).join("Library/Application Support"))
    } else {
        std::env::var_os("XDG_DATA_HOME")
            .map(PathBuf::from)
            .or_else(|| std::env::var_os("HOME").map(|h| PathBuf::from(h).join(".local/share")))
    };
    base.unwrap_or_else(std::env::temp_dir)
        .join("dinoattack-3ds-launcher")
}

/// Runs a program, passing its output lines to the log.
fn run(cmd: &mut Command, log: &Log) -> Result<(), String> {
    hide_window(cmd);
    let name = cmd.get_program().to_string_lossy().into_owned();
    let mut child = cmd
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("{name}: {e}"))?;
    let (out, err) = (child.stdout.take().unwrap(), child.stderr.take().unwrap());
    std::thread::scope(|s| {
        for stream in [
            Box::new(out) as Box<dyn std::io::Read + Send>,
            Box::new(err),
        ] {
            s.spawn(move || {
                use std::io::BufRead;
                for line in std::io::BufReader::new(stream)
                    .lines()
                    .map_while(Result::ok)
                {
                    if !line.trim().is_empty() {
                        log(&format!("  {line}"));
                    }
                }
            });
        }
    });
    let status = child.wait().map_err(|e| e.to_string())?;
    if status.success() {
        Ok(())
    } else {
        Err(format!(
            "{} failed ({status})",
            Path::new(&name)
                .file_name()
                .unwrap_or_default()
                .to_string_lossy()
        ))
    }
}

/// Resolves one tool for a build, logging where it came from.
fn need(tool: Tool, settings: &Settings, log: &Log) -> Result<PathBuf, String> {
    let found = tools::resolve(tool, settings)
        .map_err(|e| format!("{}: {e}. Set it in the Settings tab.", tool.label()))?;
    let source = if found.custom { "from Settings" } else { "found automatically" };
    log(&format!("{}: {} ({source})", tool.short(), found.path.display()));
    Ok(found.path)
}

pub fn install(o: &Options, log: &Log) -> Result<(), String> {
    if !o.want_3dsx && !o.want_cia {
        return Err("choose .3dsx, .cia or both".into());
    }
    let root = tools::project_root()
        .ok_or("can't find build.py: keep the launcher in the dinoattack folder it came with")?;
    if !o.game.is_dir() {
        return Err(format!("{} isn't a folder", o.game.display()));
    }
    let lost: Vec<&str> = GAME_FILES
        .iter()
        .copied()
        .filter(|f| !o.game.join(f).is_file())
        .collect();
    if !lost.is_empty() {
        return Err(format!(
            "{} doesn't look like the Dino Attack game folder (it should contain Launcher.swf). Missing: {}. Copy the whole DinoAttackGame folder from your original game.",
            o.game.display(),
            lost.join(", ")
        ));
    }
    log(&format!("Game: {}", o.game.display()));
    if !o.sd.is_dir() {
        return Err(format!("{} isn't a folder (is the SD card inserted?)", o.sd.display()));
    }
    let probe = o.sd.join(".dino-write-test");
    std::fs::write(&probe, b"x").map_err(|e| format!("can't write to {}: {e}", o.sd.display()))?;
    std::fs::remove_file(&probe).ok();

    let settings = Settings::load();
    let python = need(Tool::Python, &settings, log)?;
    let java = need(Tool::Java, &settings, log)?;
    let ffmpeg = need(Tool::FFmpeg, &settings, log)?;
    let devkitpro = need(Tool::DevkitPro, &settings, log)?;
    let ffdec = need(Tool::FFDec, &settings, log)?;
    let cia_tools = if o.want_cia {
        Some((
            need(Tool::Makerom, &settings, log)?,
            need(Tool::Bannertool, &settings, log)?,
        ))
    } else {
        None
    };

    let out = work_dir().join("out");
    std::fs::remove_dir_all(&out).ok();
    std::fs::create_dir_all(&out).map_err(|e| format!("{}: {e}", out.display()))?;

    log("Step 1/2: building the game files (the first build takes a long while)");
    let mut cmd = Command::new(&python);
    cmd.arg(root.join("build.py"))
        .arg(&o.game)
        .arg("--ffdec")
        .arg(&ffdec)
        .arg("--output-dir")
        .arg(&out);
    match (o.want_3dsx, o.want_cia) {
        (true, false) => {
            cmd.arg("--3dsx-only");
        }
        (false, true) => {
            cmd.arg("--cia-only");
        }
        _ => {}
    }
    if let Some((makerom, bannertool)) = &cia_tools {
        cmd.arg("--makerom").arg(makerom).arg("--bannertool").arg(bannertool);
    }
    tools::apply_env(&mut cmd, &java, &ffmpeg, &devkitpro);
    cmd.current_dir(&root).env("PYTHONUNBUFFERED", "1");
    run(&mut cmd, log)?;

    log("Step 2/2: copying to the SD card");
    let mut copied = Vec::new();
    if o.want_3dsx {
        copied.push(copy_to(&out.join("dinodino.3dsx"), &o.sd.join("3ds"))?);
    }
    if o.want_cia {
        copied.push(copy_to(&out.join("dinodino.cia"), &o.sd.join("cias"))?);
    }
    for f in &copied {
        if let Ok(h) = std::fs::File::open(f) {
            h.sync_all().ok();
        }
    }
    log(&format!("Copied {} file(s).", copied.len()));
    std::fs::remove_dir_all(&out).ok();

    if !o.sd.join("3ds/dspfirm.cdc").is_file() {
        log("Note: there's no 3ds/dspfirm.cdc on the card. Run DSP1 on the console once, or the game has no sound.");
    }
    log("Your saves in 3ds/dinodino/ were left alone.");
    log("Done! Eject the SD card safely.");
    if o.want_3dsx {
        log("  .3dsx: start Dino Attack from the Homebrew Launcher.");
    }
    if o.want_cia {
        log("  .cia: install cias/dinodino.cia with FBI, then start it from the HOME Menu.");
    }
    Ok(())
}

/// Copies one built file into `dir`, creating `dir` if needed, and returns the new path.
fn copy_to(src: &Path, dir: &Path) -> Result<PathBuf, String> {
    if !src.is_file() {
        return Err(format!("the build finished but {} is missing", src.display()));
    }
    std::fs::create_dir_all(dir).map_err(|e| format!("{}: {e}", dir.display()))?;
    let dst = dir.join(src.file_name().unwrap_or_default());
    std::fs::copy(src, &dst).map_err(|e| format!("copying to {}: {e}", dst.display()))?;
    Ok(dst)
}
