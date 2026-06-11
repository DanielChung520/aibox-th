//! DuckDB Worker Thread
//!
//! # Description
//! 在獨立 thread 中擁有 DuckDB Connection，透過 channel 接收命令。
//! 使用 query_arrow 避免已知 query_map panic bug (duckdb-rs 1.1)。
//!
//! # Last Update: 2026-04-16 10:35:20
//! # Author: Daniel Chung
//! # Version: 1.0.0

use super::{CacheCmd, CacheMeta};
use chrono::Utc;
use duckdb::Connection;
use std::collections::HashSet;

fn safe_table_name(table_id: &str) -> String {
    let sanitized: String = table_id
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '_' {
                c
            } else {
                '_'
            }
        })
        .collect();
    format!("t_{sanitized}")
}

pub(crate) fn run(db_path: String, mut rx: tokio::sync::mpsc::Receiver<CacheCmd>) {
    let conn = match Connection::open(&db_path) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("[TableCache] Failed to open DuckDB at {db_path}: {e}");
            return;
        }
    };

    let mut known_tables = discover_existing_tables(&conn);
    eprintln!(
        "[TableCache] opened {db_path}, found {} cached tables",
        known_tables.len()
    );

    while let Some(cmd) = rx.blocking_recv() {
        match cmd {
            CacheCmd::Store {
                table_id,
                rows_json,
                reply,
            } => {
                let result = do_store(&conn, &table_id, &rows_json, &mut known_tables);
                let _ = reply.send(result);
            }
            CacheCmd::Query {
                table_id,
                offset,
                limit,
                reply,
            } => {
                let result = do_query(&conn, &table_id, offset, limit);
                let _ = reply.send(result);
            }
            CacheCmd::HasTable { table_id, reply } => {
                let name = safe_table_name(&table_id);
                let _ = reply.send(known_tables.contains(&name));
            }
            CacheCmd::Drop { table_id, reply } => {
                let name = safe_table_name(&table_id);
                let result = conn
                    .execute_batch(&format!("DROP TABLE IF EXISTS \"{name}\""))
                    .map_err(|e| format!("drop error: {e}"));
                if result.is_ok() {
                    known_tables.remove(&name);
                }
                let _ = reply.send(result);
            }
        }
    }

    eprintln!("[TableCache] worker exiting");
}

fn discover_existing_tables(conn: &Connection) -> HashSet<String> {
    let mut set = HashSet::new();
    if let Ok(mut stmt) = conn.prepare("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' AND table_name LIKE 't_%'") {
        if let Ok(rows) = stmt.query_map([], |row| row.get::<_, String>(0)) {
            for name in rows.flatten() {
                set.insert(name);
            }
        }
    }
    set
}

fn do_store(
    conn: &Connection,
    table_id: &str,
    rows_json: &str,
    known: &mut HashSet<String>,
) -> Result<CacheMeta, String> {
    let name = safe_table_name(table_id);

    conn.execute_batch(&format!("DROP TABLE IF EXISTS \"{name}\""))
        .map_err(|e| format!("drop old table: {e}"))?;

    let parsed: Vec<serde_json::Value> =
        serde_json::from_str(rows_json).map_err(|e| format!("JSON parse: {e}"))?;

    if parsed.is_empty() {
        conn.execute_batch(&format!("CREATE TABLE \"{name}\" (__empty INTEGER)"))
            .map_err(|e| format!("create empty table: {e}"))?;
        known.insert(name);
        return Ok(CacheMeta {
            table_id: table_id.to_string(),
            row_count: 0,
            cached_at: Utc::now().to_rfc3339(),
        });
    }

    let tmp_file = format!("/tmp/tc_{name}.json");
    std::fs::write(&tmp_file, rows_json).map_err(|e| format!("write tmp: {e}"))?;

    conn.execute_batch(&format!(
        "CREATE TABLE \"{name}\" AS SELECT * FROM read_json_auto('{tmp_file}')"
    ))
    .map_err(|e| {
        let _ = std::fs::remove_file(&tmp_file);
        format!("create table from JSON: {e}")
    })?;

    let _ = std::fs::remove_file(&tmp_file);

    let row_count = count_rows(conn, &name);
    known.insert(name);

    Ok(CacheMeta {
        table_id: table_id.to_string(),
        row_count,
        cached_at: Utc::now().to_rfc3339(),
    })
}

fn do_query(
    conn: &Connection,
    table_id: &str,
    offset: i64,
    limit: i64,
) -> Result<(Vec<serde_json::Value>, i64), String> {
    let name = safe_table_name(table_id);
    let total = count_rows(conn, &name);

    let sql = format!("SELECT * FROM \"{name}\" LIMIT {limit} OFFSET {offset}");
    let mut stmt = conn.prepare(&sql).map_err(|e| format!("prepare: {e}"))?;
    let col_count = stmt.column_count();
    let col_names: Vec<String> = (0..col_count)
        .map(|i| {
            stmt.column_name(i)
                .map_or("?".to_string(), |v| v.to_string())
        })
        .collect();

    let rows_iter = stmt
        .query_map([], |row| {
            let mut map = serde_json::Map::new();
            for (i, col_name) in col_names.iter().enumerate() {
                let val: duckdb::types::Value = row.get(i)?;
                map.insert(col_name.clone(), duckdb_value_to_json(val));
            }
            Ok(serde_json::Value::Object(map))
        })
        .map_err(|e| format!("query: {e}"))?;

    let rows: Vec<serde_json::Value> = rows_iter.filter_map(|r| r.ok()).collect();
    Ok((rows, total))
}

fn count_rows(conn: &Connection, table_name: &str) -> i64 {
    conn.query_row(
        &format!("SELECT COUNT(*) FROM \"{table_name}\""),
        [],
        |row| row.get::<_, i64>(0),
    )
    .unwrap_or(0)
}

fn duckdb_value_to_json(val: duckdb::types::Value) -> serde_json::Value {
    match val {
        duckdb::types::Value::Null => serde_json::Value::Null,
        duckdb::types::Value::Boolean(b) => serde_json::Value::Bool(b),
        duckdb::types::Value::TinyInt(n) => serde_json::json!(n),
        duckdb::types::Value::SmallInt(n) => serde_json::json!(n),
        duckdb::types::Value::Int(n) => serde_json::json!(n),
        duckdb::types::Value::BigInt(n) => serde_json::json!(n),
        duckdb::types::Value::HugeInt(n) => serde_json::json!(n),
        duckdb::types::Value::UTinyInt(n) => serde_json::json!(n),
        duckdb::types::Value::USmallInt(n) => serde_json::json!(n),
        duckdb::types::Value::UInt(n) => serde_json::json!(n),
        duckdb::types::Value::UBigInt(n) => serde_json::json!(n),
        duckdb::types::Value::Float(f) => serde_json::json!(f),
        duckdb::types::Value::Double(f) => serde_json::json!(f),
        duckdb::types::Value::Text(s) => serde_json::Value::String(s),
        _ => serde_json::Value::String(format!("{val:?}")),
    }
}
