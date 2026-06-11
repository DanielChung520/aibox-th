//! Theme Templates Module
//!
//! # Last Update: 2026-03-22 19:14:02
//! # Author: Daniel Chung
//! # Version: 1.0.0

use arangors::client::reqwest::ReqwestClient;
use arangors::Database;
use chrono::Utc;
use serde::{Deserialize, Serialize};
use serde_json::json;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThemeTemplate {
    #[serde(rename = "_key")]
    pub _key: Option<String>,
    pub name: String,
    pub description: String,
    pub template_type: String,
    pub tokens: serde_json::Value,
    pub is_default: bool,
    pub status: String,
    pub created_at: String,
    pub updated_at: String,
}

pub async fn seed_theme_templates(db: &Database<ReqwestClient>) -> Result<(), String> {
    let count: serde_json::Value = db
        .aql_str("RETURN LENGTH(theme_templates)")
        .await
        .map_err(|e| format!("AQL error: {e}"))?
        .into_iter()
        .next()
        .unwrap_or(serde_json::Value::Number(0.into()));

    if count.as_u64().unwrap_or(0) > 0 {
        return Ok(());
    }

    let col = db
        .collection("theme_templates")
        .await
        .map_err(|e| format!("theme_templates collection: {e}"))?;
    let now = Utc::now().to_rfc3339();

    let templates = vec![
        ThemeTemplate {
            _key: Some("shell.default".into()),
            name: "預設外殼".into(),
            description: "系統預設外殼主題".into(),
            template_type: "shell".into(),
            tokens: json!({
                "siderBg": "#1e293b",
                "headerBg": "#0f172a",
                "menuItemColor": "#94a3b8",
                "menuItemHoverBg": "#334155",
                "menuItemSelectedBg": "#3b82f6",
                "menuItemSelectedColor": "#ffffff",
                "logoColor": "#ffffff",
                "siderBorder": "#334155",
                "headerShadow": "0 2px 8px rgba(0, 0, 0, 0.4)",
                "siderShadow": "2px 0 8px rgba(0, 0, 0, 0.3)"
            }),
            is_default: true,
            status: "enabled".into(),
            created_at: now.clone(),
            updated_at: now.clone(),
        },
        ThemeTemplate {
            _key: Some("content.light".into()),
            name: "淺色內容".into(),
            description: "淺色內容主題".into(),
            template_type: "content".into(),
            tokens: json!({
                "colorPrimary": "#1e40af", "colorSuccess": "#22c55e", "colorWarning": "#f59e0b", "colorError": "#dc2626", "colorInfo": "#1e40af",
                "colorBgBase": "#696d6f", "colorTextBase": "#030213", "borderRadius": 10,
                "fontFamily": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
                "boxShadow": "0 4px 16px rgba(30, 64, 175, 0.12)", "boxShadowSecondary": "0 8px 32px rgba(30, 64, 175, 0.20)",
                "tableExpandedRowBg": "#f0f4ff", "tableHeaderBg": "#f0f4ff", "chatInputBg": "#f1f5f9", "chatUserBubble": "#dbeafe", "chatAssistantBubble": "#e2e8f0",
                "textSecondary": "#64748b", "iconDefault": "#64748b", "iconHover": "#1e40af",
                "btnClear": "#f59e0b", "btnClearHover": "#d97706", "btnSend": "#1e40af", "btnSendHover": "#1e3a8a", "btnText": "#030213",
                "cardShadow": "0 4px 16px rgba(30, 64, 175, 0.12)", "cardShadowHover": "0 8px 32px rgba(30, 64, 175, 0.20)"
            }),
            is_default: true,
            status: "enabled".into(),
            created_at: now.clone(),
            updated_at: now.clone(),
        },
        ThemeTemplate {
            _key: Some("content.dark".into()),
            name: "深色內容".into(),
            description: "深色內容主題".into(),
            template_type: "content".into(),
            tokens: json!({
                "colorPrimary": "#3b82f6", "colorSuccess": "#22c55e", "colorWarning": "#f59e0b", "colorError": "#ef4444", "colorInfo": "#3b82f6",
                "colorBgBase": "#0f172a", "colorTextBase": "#f1f5f9", "borderRadius": 10,
                "fontFamily": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
                "boxShadow": "0 4px 16px rgba(100, 80, 220, 0.25)", "boxShadowSecondary": "0 8px 32px rgba(100, 80, 220, 0.40)",
                "tableExpandedRowBg": "#0a1120", "tableHeaderBg": "#1a2235", "chatInputBg": "#1e293b", "chatUserBubble": "#1e3a8a", "chatAssistantBubble": "#1e293b",
                "textSecondary": "#8892a0", "iconDefault": "#8892a0", "iconHover": "#ffffff",
                "btnClear": "#f59e0b", "btnClearHover": "#d97706", "btnSend": "#3b82f6", "btnSendHover": "#2563eb", "btnText": "#ffffff",
                "cardShadow": "0 4px 16px rgba(100, 80, 220, 0.25)", "cardShadowHover": "0 8px 32px rgba(100, 80, 220, 0.40)"
            }),
            is_default: false,
            status: "enabled".into(),
            created_at: now.clone(),
            updated_at: now.clone(),
        },
    ];

    for template in templates {
        col.create_document(template, Default::default())
            .await
            .map_err(|e| format!("Seed theme template failed: {e}"))?;
    }
    Ok(())
}
