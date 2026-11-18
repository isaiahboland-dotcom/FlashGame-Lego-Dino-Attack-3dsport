//! The paths set in the Settings tab, kept between runs as plain `key=path`
//! lines. A missing or unreadable file just means nothing is overridden.

use std::collections::BTreeMap;
use std::fmt::Write;
use std::path::PathBuf;

#[derive(Default, Clone)]
pub struct Settings {
    paths: BTreeMap<String, String>,
}

/// Where settings are saved: %APPDATA% on Windows, the Application Support
/// folder on macOS, ~/.config elsewhere. `DINO_SETTINGS` overrides the file.
pub fn file() -> Option<PathBuf> {
    if let Some(p) = std::env::var_os("DINO_SETTINGS") {
        return Some(PathBuf::from(p));
    }
    let base = if cfg!(windows) {
        std::env::var_os("APPDATA").map(PathBuf::from)
    } else if cfg!(target_os = "macos") {
        std::env::var_os("HOME").map(|h| PathBuf::from(h).join("Library/Application Support"))
    } else {
        std::env::var_os("XDG_CONFIG_HOME")
            .map(PathBuf::from)
            .or_else(|| std::env::var_os("HOME").map(|h| PathBuf::from(h).join(".config")))
    };
    base.map(|b| b.join("dinoattack-3ds-launcher").join("settings.txt"))
}

impl Settings {
    pub fn load() -> Settings {
        let mut s = Settings::default();
        let Some(text) = file().and_then(|f| std::fs::read_to_string(f).ok()) else {
            return s;
        };
        for line in text.lines() {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            if let Some((key, value)) = line.split_once('=') {
                s.set(key.trim(), value);
            }
        }
        s
    }

    pub fn get(&self, key: &str) -> Option<&str> {
        self.paths.get(key).map(String::as_str)
    }

    /// Sets a path; an empty value removes the override (back to automatic).
    pub fn set(&mut self, key: &str, value: &str) {
        let value = value.trim();
        if value.is_empty() {
            self.paths.remove(key);
        } else {
            self.paths.insert(key.to_string(), value.to_string());
        }
    }

    pub fn save(&self) -> Result<(), String> {
        let path = file().ok_or("there's no folder to save the settings in")?;
        if let Some(dir) = path.parent() {
            std::fs::create_dir_all(dir).map_err(|e| format!("{}: {e}", dir.display()))?;
        }
        let mut text = String::from("# Dino Attack 3DS launcher settings. A path here replaces the automatic one.\n");
        for (key, value) in &self.paths {
            let _ = writeln!(text, "{key}={value}");
        }
        std::fs::write(&path, text).map_err(|e| format!("{}: {e}", path.display()))
    }
}
