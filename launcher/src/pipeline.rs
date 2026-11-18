//! The build itself: runs the project's `build.py` on the game folder the user
//! picked, then copies the finished files to the SD card. The launcher does
//! not reimplement the build; `build.py` stays the single source of truth.

use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

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

/// One line of the requirements report shown when the launcher starts.
pub struct Check {
    pub name: &'static str,
    pub ok: bool,
    pub detail: String,
}

/// The folder holding `build.py`: the launcher's own folder, or one of its
/// parents (so `cargo run` from `launcher/` finds the repository). `DINO_ROOT`
/// overrides the search.
pub fn project_root() -> Option<PathBuf> {
    if let Some(p) = std::env::var_os("DINO_ROOT").map(PathBuf::from) {
        return p.join("build.py").is_file().then_some(p);
    }
    let mut dir = std::env::current_exe().ok()?.parent()?.to_path_buf();
    loop {
        if dir.join("build.py").is_file() {
            return Some(dir);
        }
        if !dir.pop() {
            return None;
        }
    }
}

/// Runs a program quietly and reports whether it exited successfully.
fn succeeds(program: &str, args: &[&str]) -> bool {
    let mut cmd = Command::new(program);
    cmd.args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    hide_window(&mut cmd);
    cmd.status().map(|s| s.success()).unwrap_or(false)
}

/// A Python 3 that has Pillow and NumPy, as the program and its leading args.
fn python() -> Option<(String, Vec<String>)> {
    let candidates: Vec<(&str, Vec<&str>)> = if cfg!(windows) {
        vec![("py", vec!["-3"]), ("python", vec![])]
    } else {
        vec![("python3", vec![]), ("python", vec![])]
    };
    candidates.into_iter().find_map(|(program, args)| {
        let mut probe = args.clone();
        probe.extend(["-c", "import PIL, numpy"]);
        succeeds(program, &probe).then(|| {
            (
                program.to_string(),
                args.iter().map(|a| a.to_string()).collect(),
            )
        })
    })
}

/// The devkitARM folder, from `DEVKITARM`, else `DEVKITPRO`, else the default.
fn devkitarm() -> Option<PathBuf> {
    let dka = std::env::var_os("DEVKITARM").map(PathBuf::from).unwrap_or_else(|| {
        let dkp = std::env::var_os("DEVKITPRO")
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from(if cfg!(windows) { "C:/devkitPro" } else { "/opt/devkitpro" }));
        dkp.join("devkitARM")
    });
    let gcc = dka
        .join("bin")
        .join(format!("arm-none-eabi-gcc{}", std::env::consts::EXE_SUFFIX));
    gcc.is_file().then_some(dka)
}

/// A helper program from the launcher's `tools/` folder, else from PATH.
fn find_tool(name: &str) -> Option<PathBuf> {
    let exe = format!("{name}{}", std::env::consts::EXE_SUFFIX);
    if let Some(local) = project_root().map(|r| r.join("tools").join(&exe)) {
        if local.is_file() {
            return Some(local);
        }
    }
    std::env::var_os("PATH").and_then(|paths| {
        std::env::split_paths(&paths)
            .map(|d| d.join(&exe))
            .find(|p| p.is_file())
    })
}

/// FFDec's `ffdec.jar`, from `FFDEC_JAR` or the bundled `ffdec*/` folder.
fn find_ffdec() -> Option<PathBuf> {
    if let Some(jar) = std::env::var_os("FFDEC_JAR").map(PathBuf::from) {
        return jar.is_file().then_some(jar);
    }
    let root = project_root()?;
    std::fs::read_dir(&root)
        .ok()?
        .flatten()
        .map(|e| e.path())
        .filter(|p| {
            p.is_dir()
                && p.file_name()
                    .is_some_and(|n| n.to_string_lossy().starts_with("ffdec"))
        })
        .map(|d| d.join("ffdec.jar"))
        .find(|j| j.is_file())
}

/// Which `.cia` helper programs are missing (empty when the `.cia` can be built).
pub fn cia_missing() -> Vec<&'static str> {
    ["makerom", "bannertool"]
        .into_iter()
        .filter(|t| find_tool(t).is_none())
        .collect()
}

/// What this computer has for a build, one line each. Missing items say how to get them.
pub fn requirements() -> Vec<Check> {
    let mut checks = vec![match python() {
        Some(_) => Check { name: "Python 3 with Pillow and NumPy", ok: true, detail: "found".into() },
        None => Check {
            name: "Python 3 with Pillow and NumPy",
            ok: false,
            detail: "install Python 3, then: pip install -r requirements.txt".into(),
        },
    }];
    checks.push(Check {
        name: "Java",
        ok: succeeds("java", &["-version"]),
        detail: "install a Java runtime (needed by FFDec)".into(),
    });
    checks.push(Check {
        name: "FFmpeg",
        ok: succeeds("ffmpeg", &["-version"]),
        detail: "install FFmpeg and put it on PATH".into(),
    });
    checks.push(Check {
        name: "FFDec (ffdec.jar)",
        ok: find_ffdec().is_some(),
        detail: "the ffdec_26.4.0 folder is missing from the launcher's folder".into(),
    });
    checks.push(Check {
        name: "devkitPro (devkitARM)",
        ok: devkitarm().is_some(),
        detail: "install devkitPro with the 3DS tools, or set DEVKITPRO".into(),
    });
    let cia = cia_missing();
    checks.push(Check {
        name: ".cia tools (makerom, bannertool)",
        ok: cia.is_empty(),
        detail: format!("not found: {}. Only needed for .cia.", cia.join(", ")),
    });
    checks
}

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
        Err(format!("{} failed ({status})", Path::new(&name).file_name().unwrap_or_default().to_string_lossy()))
    }
}

pub fn install(o: &Options, log: &Log) -> Result<(), String> {
    if !o.want_3dsx && !o.want_cia {
        return Err("choose .3dsx, .cia or both".into());
    }
    let root = project_root()
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

    let ffdec = find_ffdec().ok_or("FFDec isn't in the launcher's folder (ffdec_26.4.0/ffdec.jar)")?;
    let (py, py_args) = python().ok_or("Python 3 with Pillow and NumPy isn't installed or isn't on PATH")?;
    if o.want_cia {
        let gone = cia_missing();
        if !gone.is_empty() {
            return Err(format!("the .cia needs {} (in the launcher's tools folder or on PATH). Untick .cia to build only the .3dsx.", gone.join(" and ")));
        }
    }

    let out = work_dir().join("out");
    std::fs::remove_dir_all(&out).ok();
    std::fs::create_dir_all(&out).map_err(|e| format!("{}: {e}", out.display()))?;

    log("Step 1/2: building the game files (the first build takes a long while)");
    let mut cmd = Command::new(&py);
    cmd.args(&py_args)
        .arg(root.join("build.py"))
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
    if o.want_cia {
        for tool in ["makerom", "bannertool"] {
            let path = find_tool(tool).unwrap_or_default();
            cmd.arg(format!("--{tool}")).arg(path);
        }
    }
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
