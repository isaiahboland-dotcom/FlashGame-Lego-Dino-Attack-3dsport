//! The window: a Build tab (two folder pickers, two checkboxes, a Build button
//! and a log) and a Settings tab (the paths of the outside programs).

use std::path::PathBuf;
use std::sync::mpsc::{channel, Receiver};

use eframe::egui;

use crate::settings::{self, Settings};
use crate::tools::{self, Found, Tool};
use crate::pipeline;

enum Msg {
    Line(String),
    Done(Result<(), String>),
}

#[derive(PartialEq, Clone, Copy)]
enum Tab {
    Build,
    Settings,
}

type Check = (Tool, Result<Found, String>);

struct App {
    tab: Tab,
    game: String,
    sd: String,
    want_3dsx: bool,
    want_cia: bool,
    settings: Settings,
    /// The text of each Settings field, in `tools::ALL` order.
    custom: Vec<String>,
    checks: Vec<Check>,
    settings_note: Option<String>,
    log: Vec<String>,
    running: bool,
    result: Option<Result<(), String>>,
    rx: Option<Receiver<Msg>>,
}

impl App {
    fn new() -> App {
        let settings = Settings::load();
        let custom = tools::ALL
            .iter()
            .map(|t| settings.get(t.key()).unwrap_or("").to_string())
            .collect();
        let checks = tools::check_all(&settings);
        // The game folder is pre-filled when it sits next to the launcher (a
        // source checkout); a packaged launcher leaves it empty to pick.
        let game = tools::project_root()
            .map(|r| r.join("DinoAttackGame"))
            .filter(|p| p.join("Launcher.swf").is_file())
            .map(|p| p.display().to_string())
            .unwrap_or_default();
        App {
            tab: Tab::Build,
            game,
            sd: String::new(),
            want_3dsx: true,
            want_cia: false,
            settings,
            custom,
            checks,
            settings_note: None,
            log: Vec::new(),
            running: false,
            result: None,
            rx: None,
        }
    }

    fn refresh(&mut self) {
        self.checks = tools::check_all(&self.settings);
    }

    /// Stores the field's text for tool `i` in the settings file.
    fn apply_custom(&mut self, i: usize) {
        self.settings.set(tools::ALL[i].key(), &self.custom[i]);
        self.settings_note = self.settings.save().err();
    }

    /// The core tools (everything but the `.cia` ones) that aren't working.
    fn missing_core(&self) -> Vec<&'static str> {
        self.checks
            .iter()
            .filter(|(t, r)| !t.needs_cia() && r.is_err())
            .map(|(t, _)| t.short())
            .collect()
    }

    fn cia_ready(&self) -> bool {
        self.checks
            .iter()
            .filter(|(t, _)| t.needs_cia())
            .all(|(_, r)| r.is_ok())
    }

    fn start(&mut self, ctx: &egui::Context) {
        let o = pipeline::Options {
            game: PathBuf::from(self.game.trim()),
            sd: PathBuf::from(self.sd.trim()),
            want_3dsx: self.want_3dsx,
            want_cia: self.want_cia,
        };
        let (tx, rx) = channel();
        let (tx_log, ctx_log) = (tx.clone(), ctx.clone());
        self.rx = Some(rx);
        self.log.clear();
        self.result = None;
        self.running = true;
        let ctx = ctx.clone();
        std::thread::spawn(move || {
            let tx_line = std::sync::Mutex::new(tx_log);
            let r = pipeline::install(&o, &move |l: &str| {
                tx_line.lock().unwrap().send(Msg::Line(l.to_string())).ok();
                ctx_log.request_repaint();
            });
            tx.send(Msg::Done(r)).ok();
            ctx.request_repaint();
        });
    }

    fn build_tab(&mut self, ui: &mut egui::Ui, ctx: &egui::Context) {
        ui.heading("Dino Attack for 3DS");
        ui.label("You need your own copy of the Dino Attack game files (the DinoAttackGame folder from the original Flash game).");
        ui.add_space(8.0);
        let idle = !self.running;
        folder_row(
            ui,
            "1. Dino Attack game folder (the DinoAttackGame folder, which contains Launcher.swf)",
            &mut self.game,
            idle,
            "e.g. the DinoAttackGame folder you copied from your original game",
        );
        folder_row(
            ui,
            "2. SD card (the card's top-level folder or drive)",
            &mut self.sd,
            idle,
            "put the SD card in this computer, then Browse",
        );
        ui.label("3. What to build");
        ui.horizontal(|ui| {
            ui.add_enabled(idle, egui::Checkbox::new(&mut self.want_3dsx, ".3dsx (Homebrew Launcher)"));
            let cia_ok = self.cia_ready();
            let cia = ui.add_enabled(idle && cia_ok, egui::Checkbox::new(&mut self.want_cia, ".cia (HOME Menu, install with FBI)"));
            if !cia_ok {
                let missing: Vec<&str> = self
                    .checks
                    .iter()
                    .filter(|(t, r)| t.needs_cia() && r.is_err())
                    .map(|(t, _)| t.short())
                    .collect();
                cia.on_disabled_hover_text(format!("not found: {}. Set it in the Settings tab.", missing.join(", ")));
                self.want_cia = false;
            } else if cfg!(windows) {
                ui.colored_label(egui::Color32::from_rgb(230, 140, 20), "EXPERIMENTAL on Windows: untested, may not build");
            }
        });
        ui.add_space(8.0);
        let missing = self.missing_core();
        let ready = idle
            && !self.game.trim().is_empty()
            && !self.sd.trim().is_empty()
            && (self.want_3dsx || self.want_cia)
            && missing.is_empty();
        ui.horizontal(|ui| {
            if ui.add_enabled(ready, egui::Button::new("Build")).clicked() {
                self.start(ctx);
            }
            if self.running {
                ui.spinner();
                ui.label("Working... the first build takes a long while. Don't remove the SD card.");
            }
        });
        if !missing.is_empty() {
            ui.colored_label(
                egui::Color32::from_rgb(220, 60, 50),
                format!("Not found: {}. Open the Settings tab to set where they are.", missing.join(", ")),
            );
        }
        match &self.result {
            Some(Ok(())) => {
                ui.colored_label(egui::Color32::from_rgb(40, 160, 70), "Finished. See the notes below.");
            }
            Some(Err(e)) => {
                ui.colored_label(egui::Color32::from_rgb(220, 60, 50), format!("Failed: {e}"));
            }
            None => {}
        }
        ui.add_space(6.0);
        egui::ScrollArea::vertical().stick_to_bottom(true).auto_shrink([false, false]).show(ui, |ui| {
            for l in &self.log {
                ui.monospace(l);
            }
        });
    }

    fn settings_tab(&mut self, ui: &mut egui::Ui) {
        ui.heading("Settings");
        ui.label("The launcher finds these programs on its own. If your setup is unusual (devkitPro in a custom folder, Python in a virtual environment, and so on), set the path here. Clear a field to go back to the automatic one.");
        ui.add_space(8.0);
        let idle = !self.running;
        let green = egui::Color32::from_rgb(40, 160, 70);
        let red = egui::Color32::from_rgb(220, 60, 50);
        let mut touched = None;
        let mut refresh = false;
        egui::ScrollArea::vertical().auto_shrink([false, false]).show(ui, |ui| {
            for (i, tool) in tools::ALL.iter().enumerate() {
                ui.strong(tool.label());
                match &self.checks[i].1 {
                    Ok(found) => {
                        let source = if found.custom { "set by you" } else { "found automatically" };
                        ui.colored_label(green, format!("ok: {} ({source})", found.path.display()));
                    }
                    Err(e) => {
                        ui.colored_label(red, format!("not working: {e}"));
                    }
                }
                ui.horizontal(|ui| {
                    let hint = if tool.is_folder() { "automatic: a devkitPro folder" } else { "automatic" };
                    let edit = ui.add_enabled(
                        idle,
                        egui::TextEdit::singleline(&mut self.custom[i])
                            .desired_width(ui.available_width() - 250.0)
                            .hint_text(hint),
                    );
                    if edit.changed() {
                        touched = Some(i);
                    }
                    if edit.lost_focus() {
                        refresh = true;
                    }
                    if ui.add_enabled(idle, egui::Button::new("Browse...")).clicked() {
                        let mut dialog = rfd::FileDialog::new();
                        if let Some(dir) = std::path::Path::new(self.custom[i].trim()).parent().filter(|d| d.is_dir()) {
                            dialog = dialog.set_directory(dir);
                        }
                        let picked = if tool.is_folder() { dialog.pick_folder() } else { dialog.pick_file() };
                        if let Some(p) = picked {
                            self.custom[i] = p.display().to_string();
                            touched = Some(i);
                            refresh = true;
                        }
                    }
                    if ui
                        .add_enabled(idle && !self.custom[i].is_empty(), egui::Button::new("Automatic"))
                        .clicked()
                    {
                        self.custom[i].clear();
                        touched = Some(i);
                        refresh = true;
                    }
                });
                ui.add_space(10.0);
            }
            ui.horizontal(|ui| {
                if ui.add_enabled(idle, egui::Button::new("Detect again")).clicked() {
                    refresh = true;
                }
            });
            if let Some(note) = &self.settings_note {
                ui.colored_label(red, format!("Couldn't save settings: {note}"));
            }
            if let Some(path) = settings::file() {
                ui.label(format!("Settings are saved in {}", path.display()));
            }
        });
        if let Some(i) = touched {
            self.apply_custom(i);
        }
        if refresh {
            self.refresh();
        }
    }
}

fn folder_row(ui: &mut egui::Ui, label: &str, value: &mut String, enabled: bool, hint: &str) {
    ui.label(label);
    ui.horizontal(|ui| {
        ui.add_enabled(
            enabled,
            egui::TextEdit::singleline(value)
                .desired_width(ui.available_width() - 90.0)
                .hint_text(hint),
        );
        if ui
            .add_enabled(enabled, egui::Button::new("Browse..."))
            .clicked()
        {
            let mut dialog = rfd::FileDialog::new();
            if std::path::Path::new(value.trim()).is_dir() {
                dialog = dialog.set_directory(value.trim());
            }
            if let Some(p) = dialog.pick_folder() {
                *value = p.display().to_string();
            }
        }
    });
    ui.add_space(6.0);
}

impl eframe::App for App {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        if let Some(rx) = &self.rx {
            while let Ok(m) = rx.try_recv() {
                match m {
                    Msg::Line(l) => self.log.push(l),
                    Msg::Done(r) => {
                        self.running = false;
                        self.result = Some(r);
                    }
                }
            }
        }
        egui::CentralPanel::default().show(ctx, |ui| {
            ui.horizontal(|ui| {
                ui.selectable_value(&mut self.tab, Tab::Build, "Build");
                ui.selectable_value(&mut self.tab, Tab::Settings, "Settings");
            });
            ui.separator();
            match self.tab {
                Tab::Build => self.build_tab(ui, ctx),
                Tab::Settings => self.settings_tab(ui),
            }
        });
    }
}

/// Opens the window with OpenGL, or Direct3D/Vulkan when OpenGL isn't there
/// (a virtual machine without 3D acceleration only has OpenGL 1.1).
pub fn run() -> Result<(), String> {
    let mut errors = Vec::new();
    for renderer in [eframe::Renderer::Glow, eframe::Renderer::Wgpu] {
        let options = eframe::NativeOptions {
            viewport: egui::ViewportBuilder::default()
                .with_inner_size([760.0, 560.0])
                .with_title("Dino Attack 3DS launcher"),
            renderer,
            ..Default::default()
        };
        match eframe::run_native(
            "Dino Attack 3DS launcher",
            options,
            Box::new(|_| Ok(Box::new(App::new()))),
        ) {
            Ok(()) => return Ok(()),
            Err(e) => errors.push(format!("{renderer:?}: {e}")),
        }
    }
    Err(format!("couldn't open the window ({})", errors.join("; ")))
}
