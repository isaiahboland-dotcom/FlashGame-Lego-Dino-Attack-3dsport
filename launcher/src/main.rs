//! Dino Attack 3DS launcher: pick your game folder and SD card, get the 3DS files on it.
//!
//! `dino-launcher` opens the window. `dino-launcher --cli --game DIR --sd DIR
//! [--cia] [--no-3dsx]` does the same without one.

#![cfg_attr(windows, windows_subsystem = "windows")]

mod gui;
mod pipeline;
mod settings;
mod tools;

use std::path::PathBuf;

pub type Log = dyn Fn(&str) + Send + Sync;

/// No console window flashing up for each helper program on Windows.
pub fn hide_window(cmd: &mut std::process::Command) {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000);
    }
    #[cfg(not(windows))]
    let _ = cmd;
}

fn cli(args: &[String]) -> std::process::ExitCode {
    let value = |flag: &str| {
        args.iter()
            .position(|a| a == flag)
            .and_then(|i| args.get(i + 1))
            .map(PathBuf::from)
    };
    let (Some(game), Some(sd)) = (value("--game"), value("--sd")) else {
        eprintln!("usage: dino-launcher --cli --game <game folder> --sd <SD card folder> [--cia] [--no-3dsx]");
        return std::process::ExitCode::FAILURE;
    };
    let o = pipeline::Options {
        game,
        sd,
        want_3dsx: !args.iter().any(|a| a == "--no-3dsx"),
        want_cia: args.iter().any(|a| a == "--cia"),
    };
    match pipeline::install(&o, &|l| println!("{l}")) {
        Ok(()) => std::process::ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("Error: {e}");
            std::process::ExitCode::FAILURE
        }
    }
}

/// Prints where each tool was found (or why it wasn't), for debugging a setup.
fn check() -> std::process::ExitCode {
    let settings = settings::Settings::load();
    let mut ok = true;
    for (tool, found) in tools::check_all(&settings) {
        match found {
            Ok(f) => println!("ok       {:<10} {}{}", tool.short(), f.path.display(), if f.custom { "  (from Settings)" } else { "" }),
            Err(e) => {
                if !tool.needs_cia() {
                    ok = false;
                }
                println!("missing  {:<10} {e}", tool.short());
            }
        }
    }
    if ok { std::process::ExitCode::SUCCESS } else { std::process::ExitCode::FAILURE }
}

fn main() -> std::process::ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.iter().any(|a| a == "--cli") {
        return cli(&args);
    }
    if args.iter().any(|a| a == "--check") {
        return check();
    }
    match gui::run() {
        Ok(()) => std::process::ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("{e}");
            std::process::ExitCode::FAILURE
        }
    }
}
