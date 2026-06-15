//! ABC Desktop 桌面殼入口
//!
//! # Description
//! Tauri 應用初始化 — 簡化版本，僅保留 AI 助理視窗的 show/hide/toggle 指令
//! 移除所有 expand/sync/geometry 邏輯，作為 Drawer 模式的 safety fallback
//!
//! # Last Update: 2026-06-15 10:30:00
//! # Author: Daniel Chung
//! # Version: 2.0.0

use tauri::{window::Color, Manager, WebviewUrl, WebviewWindowBuilder};

const AI_ASSISTANT_LABEL: &str = "ai-assistant";

fn assistant_window_url() -> WebviewUrl {
    if cfg!(debug_assertions) {
        WebviewUrl::App("http://localhost:1420/ai-assistant".into())
    } else {
        WebviewUrl::App("ai-assistant".into())
    }
}

#[derive(Default)]
struct AssistantWindowState;

fn build_assistant_window(app: &tauri::AppHandle) -> Result<tauri::WebviewWindow, String> {
    let window = WebviewWindowBuilder::new(app, AI_ASSISTANT_LABEL, assistant_window_url())
        .title("艾企 AI 助手")
        .inner_size(1008.0, 1591.0)
        .min_inner_size(720.0, 400.0)
        .resizable(true)
        .maximizable(false)
        .decorations(false)
        .transparent(true)
        .background_color(Color(0, 0, 0, 0))
        .shadow(false)
        .skip_taskbar(true)
        .always_on_top(true)
        .visible(false)
        .build()
        .map_err(|e| e.to_string())?;
    Ok(window)
}

fn ensure_assistant_window(app: &tauri::AppHandle) -> Result<tauri::WebviewWindow, String> {
    if let Some(window) = app.get_webview_window(AI_ASSISTANT_LABEL) {
        return Ok(window);
    }
    build_assistant_window(app)
}

#[tauri::command]
async fn toggle_ai_assistant(app: tauri::AppHandle) -> Result<(), String> {
    let window = ensure_assistant_window(&app)?;
    if window.is_visible().unwrap_or(false) {
        window.hide().map_err(|e| e.to_string())?;
    } else {
        window.show().map_err(|e| e.to_string())?;
        window.set_focus().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
async fn show_ai_assistant(app: tauri::AppHandle) -> Result<(), String> {
    let window = ensure_assistant_window(&app)?;
    window.show().map_err(|e| e.to_string())?;
    window.set_focus().map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
async fn hide_ai_assistant(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window(AI_ASSISTANT_LABEL) {
        window.hide().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(AssistantWindowState::default())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            #[cfg(desktop)]
            app.handle()
                .plugin(tauri_plugin_updater::Builder::new().build())?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            toggle_ai_assistant,
            show_ai_assistant,
            hide_ai_assistant,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
