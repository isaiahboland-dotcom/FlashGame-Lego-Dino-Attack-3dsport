//! The outside programs the build needs, and how the launcher finds them.
//!
//! Each tool is found automatically (the environment, PATH, the usual install
//! folders, the copies bundled in the launcher's folder). A path set in the
//! Settings tab replaces the automatic one.

use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use crate::{hide_window, settings::Settings};

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Tool {
    Python,
    Java,
    FFmpeg,
    DevkitPro,
    FFDec,
    Makerom,
    Bannertool,
}

/// Every tool, in the order the Settings tab lists them.
pub const ALL: [Tool; 7] = [
    Tool::Python,
    Tool::Java,
    Tool::FFmpeg,
    Tool::DevkitPro,
    Tool::FFDec,
    Tool::Makerom,
    Tool::Bannertool,
];

impl Tool {
    /// The key for this tool in the settings file.
    pub fn key(self) -> &'static str {
        match self {
            Tool::Python => "python",
            Tool::Java => "java",
            Tool::FFmpeg => "ffmpeg",
            Tool::DevkitPro => "devkitpro",
            Tool::FFDec => "ffdec",
            Tool::Makerom => "makerom",
            Tool::Bannertool => "bannertool",
        }
    }

    /// The name used in the Build tab's messages.
    pub fn short(self) -> &'static str {
        match self {
            Tool::Python => "Python",
            Tool::Java => "Java",
            Tool::FFmpeg => "FFmpeg",
            Tool::DevkitPro => "devkitPro",
            Tool::FFDec => "FFDec",
            Tool::Makerom => "makerom",
            Tool::Bannertool => "bannertool",
        }
    }

    pub fn label(self) -> &'static str {
        match self {
            Tool::Python => "Python 3, with Pillow and NumPy",
            Tool::Java => "Java (runs FFDec)",
            Tool::FFmpeg => "FFmpeg",
            Tool::DevkitPro => "devkitPro folder (the one that contains devkitARM)",
            Tool::FFDec => "FFDec (ffdec.jar)",
            Tool::Makerom => "makerom (only for .cia)",
            Tool::Bannertool => "bannertool (only for .cia)",
        }
    }

    /// True for the tools that only the `.cia` needs.
    pub fn needs_cia(self) -> bool {
        matches!(self, Tool::Makerom | Tool::Bannertool)
    }

    /// The path is a folder rather than a program or jar.
    pub fn is_folder(self) -> bool {
        self == Tool::DevkitPro
    }

    fn missing_hint(self) -> &'static str {
        match self {
            Tool::Python => "install Python 3, then run: pip install -r requirements.txt",
            Tool::Java => "install a Java runtime",
            Tool::FFmpeg => "install FFmpeg and put it on PATH",
            Tool::DevkitPro => "install devkitPro's 3DS tools (the 3ds-dev group)",
            Tool::FFDec => "the ffdec_26.4.0 folder is missing from the launcher's folder",
            Tool::Makerom | Tool::Bannertool => "not in the launcher's tools folder or on PATH",
        }
    }
}

/// A tool that works, and where it came from.
pub struct Found {
    pub path: PathBuf,
    /// True when the path was set in the Settings tab rather than found automatically.
    pub custom: bool,
}

fn exe(name: &str) -> String {
    format!("{name}{}", std::env::consts::EXE_SUFFIX)
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
fn succeeds(program: &Path, args: &[&str]) -> bool {
    let mut cmd = Command::new(program);
    cmd.args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    hide_window(&mut cmd);
    cmd.status().map(|s| s.success()).unwrap_or(false)
}

/// A program of this name on PATH.
fn on_path(name: &str) -> Option<PathBuf> {
    let file = exe(name);
    std::env::var_os("PATH").and_then(|paths| {
        std::env::split_paths(&paths)
            .map(|d| d.join(&file))
            .find(|p| p.is_file())
    })
}

/// The Windows program folders, where Java and FFmpeg installers usually land.
fn program_dirs() -> Vec<PathBuf> {
    ["ProgramFiles", "ProgramFiles(x86)"]
        .iter()
        .filter_map(|v| std::env::var_os(v).map(PathBuf::from))
        .collect()
}

/// Looks for `rel` directly in each root, then in the folders up to `levels`
/// deep beneath them (later-sorted, so newer version folders come first).
fn find_under(roots: &[PathBuf], rel: &Path, levels: u32) -> Option<PathBuf> {
    for root in roots {
        let direct = root.join(rel);
        if direct.is_file() {
            return Some(direct);
        }
    }
    if levels == 0 {
        return None;
    }
    let mut subs: Vec<PathBuf> = roots
        .iter()
        .filter_map(|r| std::fs::read_dir(r).ok())
        .flatten()
        .flatten()
        .map(|e| e.path())
        .filter(|p| p.is_dir())
        .collect();
    subs.sort();
    subs.reverse();
    find_under(&subs, rel, levels - 1)
}

/// Whether `path` really is this tool (Python with the packages, a Java or
/// FFmpeg that runs, a devkitPro folder with devkitARM in it, a file that exists).
pub fn works(tool: Tool, path: &Path) -> bool {
    match tool {
        Tool::Python => succeeds(path, &["-c", "import PIL, numpy"]),
        Tool::Java | Tool::FFmpeg => path.is_file() && succeeds(path, &["-version"]),
        Tool::DevkitPro => path
            .join("devkitARM")
            .join("bin")
            .join(exe("arm-none-eabi-gcc"))
            .is_file(),
        Tool::FFDec | Tool::Makerom | Tool::Bannertool => path.is_file(),
    }
}

fn detect_python() -> Option<PathBuf> {
    let mut candidates: Vec<(&str, Vec<&str>)> = Vec::new();
    if cfg!(windows) {
        candidates.push(("py", vec!["-3"]));
    }
    candidates.push(("python3", vec![]));
    candidates.push(("python", vec![]));
    for (program, args) in candidates {
        // Ask Python where it lives, so the build uses that exact interpreter.
        let mut cmd = Command::new(program);
        cmd.args(&args)
            .args(["-c", "import PIL, numpy, sys; print(sys.executable)"])
            .stdin(Stdio::null())
            .stderr(Stdio::null());
        hide_window(&mut cmd);
        let Ok(out) = cmd.output() else { continue };
        if !out.status.success() {
            continue;
        }
        let text = String::from_utf8_lossy(&out.stdout);
        let path = PathBuf::from(text.lines().last().unwrap_or("").trim());
        if path.is_file() {
            return Some(path);
        }
    }
    None
}

fn detect_java() -> Option<PathBuf> {
    let mut found: Vec<PathBuf> = on_path("java").into_iter().collect();
    if let Some(home) = std::env::var_os("JAVA_HOME") {
        found.push(PathBuf::from(home).join("bin").join(exe("java")));
    }
    if let Some(p) = find_under(&program_dirs(), &Path::new("bin").join(exe("java")), 2) {
        found.push(p);
    }
    found.into_iter().find(|p| works(Tool::Java, p))
}

fn detect_ffmpeg() -> Option<PathBuf> {
    let mut found: Vec<PathBuf> = on_path("ffmpeg").into_iter().collect();
    if cfg!(windows) {
        let mut roots = program_dirs();
        roots.push(PathBuf::from("C:/ffmpeg"));
        if let Some(p) = find_under(&roots, &Path::new("bin").join(exe("ffmpeg")), 2) {
            found.push(p);
        }
    }
    found.into_iter().find(|p| works(Tool::FFmpeg, p))
}

fn detect_devkitpro() -> Option<PathBuf> {
    let mut found: Vec<PathBuf> = Vec::new();
    if let Some(p) = std::env::var_os("DEVKITPRO") {
        found.push(PathBuf::from(p));
    }
    if let Some(p) = std::env::var_os("DEVKITARM").and_then(|p| PathBuf::from(p).parent().map(Path::to_path_buf)) {
        found.push(p);
    }
    found.push(PathBuf::from(if cfg!(windows) { "C:/devkitPro" } else { "/opt/devkitpro" }));
    found.into_iter().find(|p| works(Tool::DevkitPro, p))
}

fn detect_ffdec() -> Option<PathBuf> {
    let mut found: Vec<PathBuf> = Vec::new();
    if let Some(jar) = std::env::var_os("FFDEC_JAR") {
        found.push(PathBuf::from(jar));
    }
    if let Some(root) = project_root() {
        if let Ok(entries) = std::fs::read_dir(&root) {
            let mut dirs: Vec<PathBuf> = entries
                .flatten()
                .map(|e| e.path())
                .filter(|p| {
                    p.is_dir()
                        && p.file_name()
                            .is_some_and(|n| n.to_string_lossy().starts_with("ffdec"))
                })
                .collect();
            dirs.sort();
            found.extend(dirs.into_iter().map(|d| d.join("ffdec.jar")));
        }
    }
    found.into_iter().find(|p| works(Tool::FFDec, p))
}

fn detect_helper(name: &str) -> Option<PathBuf> {
    let local = project_root().map(|r| r.join("tools").join(exe(name)));
    local.filter(|p| p.is_file()).or_else(|| on_path(name))
}

/// The automatically found path for a tool, if there is one.
fn detect(tool: Tool) -> Option<PathBuf> {
    match tool {
        Tool::Python => detect_python(),
        Tool::Java => detect_java(),
        Tool::FFmpeg => detect_ffmpeg(),
        Tool::DevkitPro => detect_devkitpro(),
        Tool::FFDec => detect_ffdec(),
        Tool::Makerom => detect_helper("makerom"),
        Tool::Bannertool => detect_helper("bannertool"),
    }
}

/// The working path for one tool: the one set in Settings when there is one
/// (and it works), otherwise the automatic one. On failure, the message says why.
pub fn resolve(tool: Tool, settings: &Settings) -> Result<Found, String> {
    if let Some(custom) = settings.get(tool.key()) {
        let path = PathBuf::from(custom);
        return if works(tool, &path) {
            Ok(Found { path, custom: true })
        } else {
            Err(format!("the path set in Settings doesn't work: {custom}"))
        };
    }
    detect(tool)
        .map(|path| Found { path, custom: false })
        .ok_or_else(|| tool.missing_hint().to_string())
}

/// Every tool with its status, in `ALL` order, for the Settings tab and the
/// Build tab's checks.
pub fn check_all(settings: &Settings) -> Vec<(Tool, Result<Found, String>)> {
    ALL.iter().map(|t| (*t, resolve(*t, settings))).collect()
}

/// Sets up a child process to see the same tools the launcher checked: the
/// Java and FFmpeg folders go first on PATH, and devkitPro's variables point
/// at the chosen folder (the build reads both).
pub fn apply_env(cmd: &mut Command, java: &Path, ffmpeg: &Path, devkitpro: &Path) {
    let mut paths: Vec<PathBuf> = [java, ffmpeg]
        .iter()
        .filter_map(|p| p.parent().map(Path::to_path_buf))
        .collect();
    if let Some(old) = std::env::var_os("PATH") {
        paths.extend(std::env::split_paths(&old));
    }
    if let Ok(joined) = std::env::join_paths(paths) {
        cmd.env("PATH", joined);
    }
    cmd.env("DEVKITPRO", devkitpro)
        .env("DEVKITARM", devkitpro.join("devkitARM"));
}
