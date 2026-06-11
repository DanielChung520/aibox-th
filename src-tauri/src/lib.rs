//! ABC Desktop 桌面殼入口
//!
//! # Description
//! Tauri 應用初始化，註冊 opener / process / updater 外掛
//!
//! # Last Update: 2026-04-23 19:40:17
//! # Author: Daniel Chung
//! # Version: 1.5.0

use std::sync::Mutex;

use tauri::{
    window::Color, Manager, PhysicalPosition, PhysicalSize, Position, Size, WebviewUrl,
    WebviewWindowBuilder, WindowEvent,
};

const AI_ASSISTANT_LABEL: &str = "ai-assistant";
const AI_ASSISTANT_WIDTH: f64 = 1008.0;
const AI_ASSISTANT_HEIGHT: f64 = 1591.0;
const AI_ASSISTANT_MIN_WIDTH: f64 = 720.0;
const AI_ASSISTANT_MIN_HEIGHT: f64 = 400.0;
const AI_ASSISTANT_MARGIN_X: i32 = 24;
const AI_ASSISTANT_MARGIN_Y: i32 = 24;
const AI_ASSISTANT_EXPANDED_WIDTH_RATIO: f64 = 0.92;
const AI_ASSISTANT_EXPANDED_HEIGHT_RATIO: f64 = 0.80;
#[derive(Clone, Copy)]
struct WindowGeometry {
    x: i32,
    y: i32,
    width: u32,
    height: u32,
}

#[derive(Default)]
struct AssistantWindowRuntimeState {
    reopen_after_restore: bool,
    is_expanded: bool,
    restore_geometry: Option<WindowGeometry>,
}

fn assistant_window_url() -> WebviewUrl {
    if cfg!(debug_assertions) {
        WebviewUrl::App("http://localhost:1420/ai-assistant".into())
    } else {
        WebviewUrl::App("ai-assistant".into())
    }
}

#[derive(Default)]
struct AssistantWindowState {
    runtime: Mutex<AssistantWindowRuntimeState>,
}

fn set_reopen_after_restore(app: &tauri::AppHandle, value: bool) -> Result<(), String> {
    let state = app.state::<AssistantWindowState>();
    let mut runtime = state
        .runtime
        .lock()
        .map_err(|_| "assistant window state lock poisoned".to_string())?;
    runtime.reopen_after_restore = value;
    Ok(())
}

fn take_reopen_after_restore(app: &tauri::AppHandle) -> Result<bool, String> {
    let state = app.state::<AssistantWindowState>();
    let mut runtime = state
        .runtime
        .lock()
        .map_err(|_| "assistant window state lock poisoned".to_string())?;
    let should_reopen = runtime.reopen_after_restore;
    runtime.reopen_after_restore = false;
    Ok(should_reopen)
}

fn is_assistant_expanded(app: &tauri::AppHandle) -> Result<bool, String> {
    let state = app.state::<AssistantWindowState>();
    let runtime = state
        .runtime
        .lock()
        .map_err(|_| "assistant window state lock poisoned".to_string())?;
    Ok(runtime.is_expanded)
}

fn set_assistant_expanded_flag(app: &tauri::AppHandle, value: bool) -> Result<(), String> {
    let state = app.state::<AssistantWindowState>();
    let mut runtime = state
        .runtime
        .lock()
        .map_err(|_| "assistant window state lock poisoned".to_string())?;
    runtime.is_expanded = value;
    Ok(())
}

fn remember_restore_geometry(
    app: &tauri::AppHandle,
    geometry: Option<WindowGeometry>,
) -> Result<(), String> {
    let state = app.state::<AssistantWindowState>();
    let mut runtime = state
        .runtime
        .lock()
        .map_err(|_| "assistant window state lock poisoned".to_string())?;
    runtime.restore_geometry = geometry;
    Ok(())
}

fn take_restore_geometry(app: &tauri::AppHandle) -> Result<Option<WindowGeometry>, String> {
    let state = app.state::<AssistantWindowState>();
    let mut runtime = state
        .runtime
        .lock()
        .map_err(|_| "assistant window state lock poisoned".to_string())?;
    Ok(runtime.restore_geometry.take())
}

fn default_assistant_geometry(app: &tauri::AppHandle) -> Result<WindowGeometry, String> {
    let main = app
        .get_webview_window("main")
        .ok_or_else(|| "main window not found".to_string())?;

    let main_pos = main.outer_position().map_err(|e| e.to_string())?;
    let main_size = main.outer_size().map_err(|e| e.to_string())?;
    let width = AI_ASSISTANT_WIDTH.round() as u32;
    let height = AI_ASSISTANT_HEIGHT.round() as u32;
    let x = main_pos.x + main_size.width as i32 - width as i32 - AI_ASSISTANT_MARGIN_X;
    let y = main_pos.y + main_size.height as i32 - height as i32 - AI_ASSISTANT_MARGIN_Y;

    Ok(WindowGeometry {
        x: x.max(0),
        y: y.max(0),
        width,
        height,
    })
}

fn expanded_assistant_geometry(app: &tauri::AppHandle) -> Result<WindowGeometry, String> {
    let main = app
        .get_webview_window("main")
        .ok_or_else(|| "main window not found".to_string())?;

    let main_pos = main.outer_position().map_err(|e| e.to_string())?;
    let main_size = main.outer_size().map_err(|e| e.to_string())?;
    let margin_x = AI_ASSISTANT_MARGIN_X.max(0) as u32;
    let margin_y = AI_ASSISTANT_MARGIN_Y.max(0) as u32;
    let min_width = AI_ASSISTANT_MIN_WIDTH.round() as u32;
    let min_height = AI_ASSISTANT_MIN_HEIGHT.round() as u32;
    let available_width = main_size.width.saturating_sub(margin_x * 2);
    let available_height = main_size.height.saturating_sub(margin_y * 2);
    let target_width = ((main_size.width as f64) * AI_ASSISTANT_EXPANDED_WIDTH_RATIO).round() as u32;
    let target_height = ((main_size.height as f64) * AI_ASSISTANT_EXPANDED_HEIGHT_RATIO).round() as u32;
    let width = target_width.clamp(min_width, available_width.max(min_width));
    let height = target_height.clamp(min_height, available_height.max(min_height));
    let x = main_pos.x + main_size.width as i32 - width as i32 - AI_ASSISTANT_MARGIN_X;
    let y = main_pos.y + main_size.height as i32 - height as i32 - AI_ASSISTANT_MARGIN_Y;

    Ok(WindowGeometry {
        x: x.max(0),
        y: y.max(0),
        width,
        height,
    })
}

fn apply_assistant_geometry(
    window: &tauri::WebviewWindow,
    geometry: WindowGeometry,
) -> Result<(), String> {
    window
        .set_size(Size::Physical(PhysicalSize::new(
            geometry.width,
            geometry.height,
        )))
        .map_err(|e| e.to_string())?;
    window
        .set_position(Position::Physical(PhysicalPosition::new(
            geometry.x,
            geometry.y,
        )))
        .map_err(|e| e.to_string())?;

    Ok(())
}

fn position_assistant_relative_to_main(app: &tauri::AppHandle) -> Result<(), String> {
    let assistant = app
        .get_webview_window(AI_ASSISTANT_LABEL)
        .ok_or_else(|| "assistant window not found".to_string())?;
    let geometry = if is_assistant_expanded(app)? {
        expanded_assistant_geometry(app)?
    } else {
        default_assistant_geometry(app)?
    };

    apply_assistant_geometry(&assistant, geometry)
}

fn build_assistant_window(app: &tauri::AppHandle) -> Result<tauri::WebviewWindow, String> {
    let window = WebviewWindowBuilder::new(
        app,
        AI_ASSISTANT_LABEL,
        assistant_window_url(),
    )
    .title("艾企 AI 助手")
    .inner_size(AI_ASSISTANT_WIDTH, AI_ASSISTANT_HEIGHT)
    .min_inner_size(AI_ASSISTANT_MIN_WIDTH, AI_ASSISTANT_MIN_HEIGHT)
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

    position_assistant_relative_to_main(app)?;

    Ok(window)
}

fn ensure_assistant_window(app: &tauri::AppHandle) -> Result<tauri::WebviewWindow, String> {
    if let Some(window) = app.get_webview_window(AI_ASSISTANT_LABEL) {
        return Ok(window);
    }
    build_assistant_window(app)
}

fn sync_assistant_visibility_with_main(app: &tauri::AppHandle) -> Result<(), String> {
    let main = app
        .get_webview_window("main")
        .ok_or_else(|| "main window not found".to_string())?;

    if main.is_minimized().map_err(|e| e.to_string())? {
        if let Some(assistant) = app.get_webview_window(AI_ASSISTANT_LABEL) {
            if assistant.is_visible().unwrap_or(false) {
                set_reopen_after_restore(app, true)?;
                assistant.hide().map_err(|e| e.to_string())?;
            }
        }
        return Ok(());
    }

    if take_reopen_after_restore(app)? {
        let assistant = ensure_assistant_window(app)?;
        position_assistant_relative_to_main(app)?;
        assistant.show().map_err(|e| e.to_string())?;
    }

    Ok(())
}

#[tauri::command]
async fn toggle_ai_assistant(app: tauri::AppHandle) -> Result<(), String> {
    let window = ensure_assistant_window(&app)?;
    position_assistant_relative_to_main(&app)?;

    if window.is_visible().unwrap_or(false) {
        set_reopen_after_restore(&app, false)?;
        window.hide().map_err(|e| e.to_string())?;
    } else {
        window.show().map_err(|e| e.to_string())?;
        window.set_focus().map_err(|e| e.to_string())?;
        set_reopen_after_restore(&app, false)?;
    }
    Ok(())
}

#[tauri::command]
async fn show_ai_assistant(app: tauri::AppHandle) -> Result<(), String> {
    let window = ensure_assistant_window(&app)?;
    position_assistant_relative_to_main(&app)?;
    window.show().map_err(|e| e.to_string())?;
    window.set_focus().map_err(|e| e.to_string())?;
    set_reopen_after_restore(&app, false)?;
    Ok(())
}

#[tauri::command]
async fn hide_ai_assistant(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window(AI_ASSISTANT_LABEL) {
        set_reopen_after_restore(&app, false)?;
        window.hide().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
async fn get_ai_assistant_expanded(app: tauri::AppHandle) -> Result<bool, String> {
    is_assistant_expanded(&app)
}

#[tauri::command]
async fn set_ai_assistant_expanded(app: tauri::AppHandle, expanded: bool) -> Result<bool, String> {
    let window = ensure_assistant_window(&app)?;

    if expanded {
        if !is_assistant_expanded(&app)? {
            let position = window.outer_position().map_err(|e| e.to_string())?;
            let size = window.outer_size().map_err(|e| e.to_string())?;
            remember_restore_geometry(
                &app,
                Some(WindowGeometry {
                    x: position.x,
                    y: position.y,
                    width: size.width,
                    height: size.height,
                }),
            )?;
        }

        set_assistant_expanded_flag(&app, true)?;
        apply_assistant_geometry(&window, expanded_assistant_geometry(&app)?)?;
    } else {
        set_assistant_expanded_flag(&app, false)?;
        let geometry = take_restore_geometry(&app)?.unwrap_or(default_assistant_geometry(&app)?);
        apply_assistant_geometry(&window, geometry)?;
    }

    Ok(expanded)
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

            let window = app.get_webview_window("main").unwrap();
            window
                .eval("window.__TAURI_INTERNALS__ = window.__TAURI_INTERNALS__ || {};")
                .ok();

            let app_handle = app.handle().clone();
            window.on_window_event(move |event| {
                match event {
                    WindowEvent::Moved(_) | WindowEvent::Resized(_) | WindowEvent::ScaleFactorChanged { .. } => {
                        let _ = position_assistant_relative_to_main(&app_handle);
                        let _ = sync_assistant_visibility_with_main(&app_handle);
                    }
                    WindowEvent::Focused(_) => {
                        let _ = sync_assistant_visibility_with_main(&app_handle);
                    }
                    _ => {}
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            toggle_ai_assistant,
            show_ai_assistant,
            hide_ai_assistant,
            get_ai_assistant_expanded,
            set_ai_assistant_expanded,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
