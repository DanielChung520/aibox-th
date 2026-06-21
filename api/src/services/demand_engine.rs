use crate::db::{get_db, DemandLog};
use crate::error::ApiError;
use chrono::Utc;
use serde_json::{json, Value};

/// DemandEngine — 需求狀態機引擎
///
/// 管理需求（agent_demands）的生命週期狀態轉移。
/// 狀態集合：draft → submitted → qualified → online | cancelled | superseded
/// 參照 .docs/Spec/系統開發/01-需求提交與審查.md
pub struct DemandEngine;

/// 正式轉移表（from, to, condition_label）
const VALID_TRANSITIONS: &[(&str, &str, &str)] = &[
    ("draft", "submitted", "submit"),
    ("submitted", "qualified", "qualify"),
    ("submitted", "cancelled", "withdraw"),
    ("qualified", "cancelled", "withdraw (with dev check)"),
    ("qualified", "online", "kanban completed"),
    ("cancelled", "draft", "reactivate"),
];

impl DemandEngine {
    /// 提交需求：draft → submitted
    /// 前端須先通過 AI 審查（score ≥ 70），此處僅驗證狀態
    pub async fn submit(demand_key: &str, actor: &str) -> Result<(), ApiError> {
        Self::transition(demand_key, "submitted", actor, None, None).await
    }

    /// 判定合格：submitted → qualified
    /// 自動建立對應的 agent_requirements 看板記錄
    pub async fn qualify(demand_key: &str, agent_key: &str, actor: &str) -> Result<(), ApiError> {
        let db = get_db();

        // 讀取目前 demand 取得 version
        let demand = Self::get_demand(demand_key).await?;
        let version = demand.get("version").and_then(|v| v.as_str()).unwrap_or("v1.0");

        // 執行轉移
        Self::transition(demand_key, "qualified", actor, None, None).await?;

        // 自動建立看板記錄
        Self::auto_create_requirement(demand_key, agent_key, version).await?;

        Ok(())
    }

    /// 撤銷需求：submitted/qualified → cancelled
    /// 若為 qualified 狀態，須檢查看板是否已進入開發階段
    pub async fn withdraw(demand_key: &str, actor: &str, reason: Option<&str>) -> Result<(), ApiError> {
        let db = get_db();
        let demand = Self::get_demand(demand_key).await?;
        let current_status = demand.get("status").and_then(|v| v.as_str()).unwrap_or("");

        // qualified 狀態需檢查開發中阻擋
        if current_status == "qualified" {
            let version = demand.get("version").and_then(|v| v.as_str()).unwrap_or("v1.0");
            let blocked = Self::check_dev_in_progress(demand_key, version).await?;
            if blocked {
                return Err(ApiError::bad_request(
                    "此需求已進入開發階段，無法撤銷。請使用「變更需求」功能建立新版。",
                ));
            }
        }

        Self::transition(demand_key, "cancelled", actor, reason, None).await
    }

    /// 變更需求：建立新版 draft，舊版保持原有狀態
    /// 回傳新建立的 demand document
    pub async fn change(
        demand_key: &str,
        _agent_key: &str,
        actor: &str,
        change_reason: &str,
    ) -> Result<Value, ApiError> {
        let db = get_db();

        // 讀取舊版 demand
        let old = Self::get_demand(demand_key).await?;
        let old_version = old.get("version").and_then(|v| v.as_str()).unwrap_or("v1.0");
        let old_status = old.get("status").and_then(|v| v.as_str()).unwrap_or("");

        // 僅 qualified / online 可變更
        if old_status != "qualified" && old_status != "online" {
            return Err(ApiError::bad_request(
                &format!("目前狀態為「{}」，無法發起變更。僅 qualified / online 可變更。", old_status),
            ));
        }

        // 計算新版本號
        let new_version = Self::next_version(old_version);

        // 建立新版 demand（複製舊版資料為基底）
        let new_demand_key = uuid::Uuid::new_v4().to_string();
        let now = Utc::now().to_rfc3339();

        let mut doc = old.clone();
        if let Some(obj) = doc.as_object_mut() {
            obj.insert("_key".to_string(), json!(new_demand_key));
            obj.insert("version".to_string(), json!(new_version));
            obj.insert("status".to_string(), json!("draft"));
            obj.insert("supersedes".to_string(), json!(demand_key));
            obj.insert("superseded_by".to_string(), json!(null));
            obj.insert("change_reason".to_string(), json!(change_reason));
            obj.insert("created_at".to_string(), json!(now));
            obj.insert("updated_at".to_string(), json!(now));
            obj.insert("submitted_at".to_string(), json!(null));
            obj.insert("accepted_at".to_string(), json!(null));
            obj.insert("cancelled_at".to_string(), json!(null));
            obj.insert("online_at".to_string(), json!(null));
            // 清除舊版的審查與時間戳
            obj.remove("ai_review");
        }

        let demand_col = db.collection("agent_demands")
            .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;
        demand_col.create_document(doc.clone(), Default::default())
            .await.map_err(|e| ApiError::internal_error(&format!("Create demand failed: {e}")))?;

        // 更新舊版的 superseded_by（軟連結，非 superseded 狀態）
        let _ = db.aql_bind_vars::<Value>(
            "FOR d IN agent_demands FILTER d._key == @key UPDATE d WITH { superseded_by: @new_key, updated_at: @now } IN agent_demands",
            [
                ("key", json!(demand_key)),
                ("new_key", json!(new_demand_key)),
                ("now", json!(now)),
            ].into(),
        ).await;

        // 記錄變更歷史到舊版
        let history_entry = json!({
            "from_version": old_version,
            "to_version": new_version,
            "new_demand_key": new_demand_key,
            "changed_at": now,
            "actor": actor,
            "reason": change_reason,
        });
        let _ = db.aql_bind_vars::<Value>(
            "FOR d IN agent_demands FILTER d._key == @key UPDATE d WITH { change_history: APPEND(d.change_history || [], [@entry]), updated_at: @now } IN agent_demands",
            [
                ("key", json!(demand_key)),
                ("entry", history_entry),
                ("now", json!(now)),
            ].into(),
        ).await;

        // Audit log for the old demand
        Self::add_log(demand_key, old_status, "qualified", actor, Some(change_reason),
            Some(json!({ "event": "change_initiated", "new_version": new_version, "new_key": new_demand_key }))
        ).await?;

        // Audit log for the new draft
        Self::add_log(&new_demand_key, "draft", "draft", actor, Some(change_reason),
            Some(json!({ "event": "created_from_change", "supersedes": demand_key, "original_version": old_version }))
        ).await?;

        Ok(doc)
    }

    /// 重新開啟：cancelled → draft
    pub async fn reactivate(demand_key: &str, actor: &str) -> Result<(), ApiError> {
        Self::transition(demand_key, "draft", actor, None, None).await
    }

    /// 標記為上線（由看板 completed 觸發）
    pub async fn mark_online(demand_key: &str, actor: &str) -> Result<(), ApiError> {
        Self::transition(demand_key, "online", actor, None, None).await
    }

    /// 當新版 qualified 時，將舊版標為 superseded
    pub async fn supersede_old_version(old_demand_key: &str, new_demand_key: &str) -> Result<(), ApiError> {
        let db = get_db();
        let now = Utc::now().to_rfc3339();

        // 檢查舊版目前狀態：只有 qualified / online 才能被 supersede
        let old = Self::get_demand(old_demand_key).await?;
        let old_status = old.get("status").and_then(|v| v.as_str()).unwrap_or("");
        if old_status != "qualified" && old_status != "online" && old_status != "superseded" {
            // 如果已經 cancelled 則跳過
            if old_status == "cancelled" {
                return Ok(());
            }
        }

        let demand_col = db.collection("agent_demands")
            .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;
        demand_col.update_document(old_demand_key, json!({
            "status": "superseded",
            "superseded_by": new_demand_key,
            "updated_at": now,
        }), Default::default())
            .await.map_err(|e| ApiError::internal_error(&format!("Supersede failed: {e}")))?;

        Self::add_log(old_demand_key, old_status, "superseded", "system",
            Some(&format!("被新版 {} 取代", new_demand_key)),
            Some(json!({ "new_demand_key": new_demand_key }))
        ).await?;

        Ok(())
    }

    // ─── 內部方法 ─────────────────────────────────────────────

    /// 通用狀態轉移（含 Audit Trail）
    async fn transition(
        demand_key: &str,
        to_status: &str,
        actor: &str,
        reason: Option<&str>,
        metadata: Option<Value>,
    ) -> Result<(), ApiError> {
        let db = get_db();
        let demand = Self::get_demand(demand_key).await?;
        let from_status = demand.get("status").and_then(|v| v.as_str()).unwrap_or("");
        let version = demand.get("version").and_then(|v| v.as_str()).unwrap_or("v1.0");

        // 驗證轉移合法性
        Self::validate_transition(from_status, to_status)?;

        let now = Utc::now().to_rfc3339();
        let demand_col = db.collection("agent_demands")
            .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;

        let mut update = json!({
            "status": to_status,
            "updated_at": now,
        });

        // Side-effects per status
        match to_status {
            "submitted" => { update["submitted_at"] = json!(now); }
            "cancelled" => { update["cancelled_at"] = json!(now); }
            "online" => { update["online_at"] = json!(now); }
            _ => {}
        }

        demand_col.update_document(demand_key, update, Default::default())
            .await.map_err(|e| ApiError::internal_error(&format!("Update demand failed: {e}")))?;

        // Audit log
        Self::add_log(demand_key, from_status, to_status, actor, reason, metadata).await?;

        Ok(())
    }

    /// 驗證轉移是否合法
    fn validate_transition(from: &str, to: &str) -> Result<(), ApiError> {
        let valid = VALID_TRANSITIONS.iter().any(|(f, t, _)| *f == from && *t == to);
        if !valid {
            return Err(ApiError::bad_request(
                &format!("不允許的狀態轉移：從「{}」到「{}」", from, to),
            ));
        }
        Ok(())
    }

    /// 檢查看板是否已進入開發階段（in_development 或 completed）
    async fn check_dev_in_progress(demand_key: &str, version: &str) -> Result<bool, ApiError> {
        let db = get_db();
        let blocked: Vec<Value> = db.aql_bind_vars(
            "FOR r IN agent_requirements FILTER r.demand_key == @key AND r.demand_version == @ver AND r.status IN ['in_development', 'completed'] LIMIT 1 RETURN r",
            [
                ("key", json!(demand_key)),
                ("ver", json!(version)),
            ].into(),
        ).await.map_err(|e| ApiError::internal_error(&format!("Query failed: {e}")))?;
        Ok(!blocked.is_empty())
    }

    /// 自動建立 agent_requirements 看板記錄（qualify 時呼叫）
    async fn auto_create_requirement(demand_key: &str, agent_key: &str, version: &str) -> Result<(), ApiError> {
        let db = get_db();
        let demand = Self::get_demand(demand_key).await?;
        let now = Utc::now().to_rfc3339();

        // 從 agents 集合讀取名稱
        let agent_name: String = db.aql_bind_vars(
            "FOR a IN agents FILTER a._key == @key LIMIT 1 RETURN a.name",
            [("key", json!(agent_key))].into(),
        ).await.map_err(|e| ApiError::internal_error(&format!("Query failed: {e}")))
            .map(|v: Vec<Value>| {
                v.into_iter().next()
                    .and_then(|n| n.as_str().map(String::from))
                    .unwrap_or_else(|| agent_key.to_string())
            })?;

        // 檢查是否已有相同 demand_key+version 的看板記錄
        let existing: Vec<Value> = db.aql_bind_vars(
            "FOR r IN agent_requirements FILTER r.demand_key == @key AND r.demand_version == @ver LIMIT 1 RETURN r",
            [
                ("key", json!(demand_key)),
                ("ver", json!(version)),
            ].into(),
        ).await.map_err(|e| ApiError::internal_error(&format!("Query failed: {e}")))?;

        if existing.is_empty() {
            let account = demand.get("account").and_then(|v| v.as_str()).unwrap_or("system");
            let goal = demand.get("goal").and_then(|v| v.as_str()).unwrap_or("");
            let expected_effect = demand.get("expected_effect").and_then(|v| v.as_str()).unwrap_or("");
            let problem_description = demand.get("problem_description").and_then(|v| v.as_str()).unwrap_or("");
            let ai_review = demand.get("ai_review");

            // 產生需求編號（格式：A01-2618-001）
            let req_no = Self::generate_req_no(agent_key).await?;

            let col = db.collection("agent_requirements")
                .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;

            let doc = json!({
                "_key": demand_key,
                "req_no": req_no,
                "demand_key": demand_key,
                "demand_version": version,
                "agent_key": agent_key,
                "agent_name": agent_name,
                "account": account,
                "version": version,
                "status": "pending_accept",
                "goal": goal,
                "expected_effect": expected_effect,
                "problem_description": problem_description,
                "ai_review": ai_review,
                "change_type": "initial",
                "submitted_at": now,
                "created_at": now,
                "updated_at": now,
            });

            col.create_document(doc, Default::default())
                .await.map_err(|e| ApiError::internal_error(&format!("Create requirement failed: {e}")))?;
        }

        Ok(())
    }

    /// 產生需求編號（格式：{type}{tab}-{year}{week}-{seq}）
    async fn generate_req_no(agent_key: &str) -> Result<String, ApiError> {
        use chrono::Datelike;
        let db = get_db();

        let now = chrono::Utc::now();
        let iso_week = now.iso_week();
        let week_str = format!("{:02}", iso_week.week());
        let year_str = format!("{:02}", now.year() % 100);

        // 預設 agent_type=A, tab_code=01
        let prefix = format!("A01-{}{}", year_str, week_str);

        // 計算本週已產生的數量
        let count: f64 = db.aql_bind_vars(
            "FOR r IN agent_requirements FILTER STARTS_WITH(r.req_no, @prefix) RETURN 1",
            [("prefix", json!(prefix))].into(),
        ).await.map_err(|e| ApiError::internal_error(&format!("Query failed: {e}")))
            .map(|v: Vec<Value>| v.len() as f64)
            .unwrap_or(0.0);

        Ok(format!("{}-{:03}", prefix, count as i32 + 1))
    }

    /// 讀取單一 demand
    async fn get_demand(demand_key: &str) -> Result<Value, ApiError> {
        let db = get_db();
        let docs: Vec<Value> = db.aql_bind_vars(
            "FOR d IN agent_demands FILTER d._key == @key LIMIT 1 RETURN d",
            [("key", json!(demand_key))].into(),
        ).await.map_err(|e| ApiError::internal_error(&format!("Query failed: {e}")))?;
        docs.into_iter().next().ok_or_else(|| ApiError::not_found("需求"))
    }

    /// 計算下一個版本號（v1.0 → v2.0 → v3.0）
    fn next_version(current: &str) -> String {
        let num: i32 = current
            .trim_start_matches('v')
            .split('.')
            .next()
            .and_then(|s| s.parse().ok())
            .unwrap_or(1);
        format!("v{}.0", num + 1)
    }

    /// 寫入 Audit Trail
    pub async fn add_log(
        demand_key: &str,
        from_status: &str,
        to_status: &str,
        actor: &str,
        reason: Option<&str>,
        metadata: Option<Value>,
    ) -> Result<(), ApiError> {
        let db = get_db();
        let log_col = db.collection("demand_logs")
            .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;

        // 讀取 version
        let version = Self::get_demand(demand_key).await
            .ok()
            .and_then(|d| d.get("version").and_then(|v| v.as_str()).map(|s| s.to_string()))
            .unwrap_or_else(|| "unknown".to_string());

        let log = DemandLog {
            _key: None,
            demand_key: demand_key.to_string(),
            version,
            from_status: from_status.to_string(),
            to_status: to_status.to_string(),
            actor: actor.to_string(),
            reason: reason.map(|s| s.to_string()),
            created_at: Utc::now().to_rfc3339(),
            metadata,
        };

        log_col.create_document(log, Default::default())
            .await.map_err(|e| ApiError::internal_error(&format!("Create log failed: {e}")))?;
        Ok(())
    }

    /// 取得需求的變更歷史
    pub async fn get_change_history(demand_key: &str) -> Result<Value, ApiError> {
        let demand = Self::get_demand(demand_key).await?;
        let history = demand.get("change_history").cloned().unwrap_or(json!([]));
        let supersedes = demand.get("supersedes").and_then(|v| v.as_str()).map(|s| s.to_string());
        let superseded_by = demand.get("superseded_by").and_then(|v| v.as_str()).map(|s| s.to_string());

        Ok(json!({
            "current_key": demand_key,
            "supersedes": supersedes,
            "superseded_by": superseded_by,
            "change_history": history,
        }))
    }
}
