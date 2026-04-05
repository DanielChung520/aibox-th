//! ABC Desktop 桌面殼入口
//!
//! # Description
//! Tauri 應用初始化，註冊 opener / process / updater 外掛
//!
//! # Last Update: 2026-03-25 13:03:52
//! # Author: Daniel Chung
//! # Version: 1.1.0

use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            #[cfg(desktop)]
            app.handle()
                .plugin(tauri_plugin_updater::Builder::new().build())?;

            let window = app.get_webview_window("main").unwrap();
            window
                .eval("window.__TAURI_INTERNALS__ = window.__TAURI_INTERNALS__ || {};")
                .ok();
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
