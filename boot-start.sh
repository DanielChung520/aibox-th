#!/usr/bin/env bash
# ============================================================================
# @file        boot-start.sh
# @description 開機自動啟動腳本 — 由 LaunchDaemon 觸發，無需登錄
# @lastUpdate  2026-05-29
# @author      Daniel Chung
# @version     1.1.0
# ============================================================================
#
# 依序啟動：
#   1. 等待 Docker (colima) ready
#   2. docker compose infra (ArangoDB, Qdrant, Redis, SeaweedFS)
#   3. ./start.sh start (Rust API + Python AI Services + Frontend)
#
# 日誌：/tmp/aibox-th-boot.log
# ============================================================================

set -euo pipefail

# ─── 使用 Colima Docker socket ───────────────────────────────────────────────
export DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock"

PROJECT_DIR="/Users/daniel/GitHub/AIBox-TH"
LOG_FILE="/tmp/aibox-th-boot.log"
START_SCRIPT="$PROJECT_DIR/start.sh"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.infra.yml"

# ─── 日誌 ────────────────────────────────────────────────────────────────────
exec > "$LOG_FILE" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ═══════════════════════════════════════"
echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ABC Desktop — Boot Startup"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ═══════════════════════════════════════"

# ─── Helper: 等待條件 ─────────────────────────────────────────────────────────
wait_for() {
    local label="$1"
    local max_wait="$2"   # 秒
    local interval="$3"   # 秒
    local cmd="$4"        # 回傳 0 = 成功
    local elapsed=0

    echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ⏳ Waiting for $label (max ${max_wait}s)..."
    while [ $elapsed -lt "$max_wait" ]; do
        if eval "$cmd" > /dev/null 2>&1; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ✅ $label is ready (${elapsed}s)"
            return 0
        fi
        sleep "$interval"
        elapsed=$((elapsed + interval))
    done
    echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ❌ $label failed to start within ${max_wait}s"
    return 1
}

# ─── 0. 確保 Colima 已啟動 ─────────────────────────────────────────────────────
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ─── Step 0/5: Ensure Colima is running ────"
if colima status 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ✅ Colima already running"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ▶ Starting Colima..."
    colima start 2>&1 || true
fi

# ─── 1. 等待 Docker ───────────────────────────────────────────────────────────
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ─── Step 1/5: Wait for Docker ────────────"

# 先等 docker socket 出現（colima socket + desktop socket）
wait_for "Docker socket" 60 2 "[ -S /var/run/docker.sock ] || [ -S ~/.docker/run/docker.sock ] || [ -S ~/.colima/default/docker.sock ] || docker info > /dev/null 2>&1"

# 再確認 docker info 可用
wait_for "Docker daemon" 60 3 "docker info > /dev/null 2>&1"

# ─── 2. 啟動 Docker Compose Infra ────────────────────────────────────────────
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ─── Step 2/4: Docker Compose Infra ───────"

cd "$PROJECT_DIR"

# 檢查 compose infra 是否已在運行
RUNNING_CONTAINERS=$(docker compose -f "$COMPOSE_FILE" ps --status running -q 2>/dev/null | wc -l | tr -d ' ')
TOTAL_SERVICES=$(docker compose -f "$COMPOSE_FILE" config --services 2>/dev/null | wc -l | tr -d ' ')

if [ "$RUNNING_CONTAINERS" -ge "$TOTAL_SERVICES" ] 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ✅ Infra containers already running (${RUNNING_CONTAINERS}/${TOTAL_SERVICES})"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ▶ Starting Docker Compose infra..."
    docker compose -f "$COMPOSE_FILE" up -d --wait 2>&1 || {
        echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ⚠️  docker compose --wait failed, trying without --wait..."
        docker compose -f "$COMPOSE_FILE" up -d 2>&1
    }
    echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ✅ Docker Compose infra started"
fi

# ─── 3. 等待 Infra 服務健康 ──────────────────────────────────────────────────
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ─── Step 3/4: Wait for Infra Health ──────"

# ArangoDB (port 8529)
wait_for "ArangoDB" 60 3 \
    "curl -sf --max-time 3 http://localhost:8529/_api/version > /dev/null 2>&1" || true

# Qdrant (port 6333)
wait_for "Qdrant" 30 3 \
    "curl -sf --max-time 3 http://localhost:6333/collections > /dev/null 2>&1" || true

# Redis (port 6379) — 透過 docker exec 檢查，免裝 redis-cli
wait_for "Redis" 30 2 \
    "docker exec redis redis-cli ping 2>/dev/null | grep -q PONG" || true

# ─── 4. 啟動 Project Services (start.sh) ─────────────────────────────────────
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ─── Step 4/4: Start Project Services ─────"

# 確保 VENV 存在（start.sh 會用到）
if [ -f "$PROJECT_DIR/ai-services/.venv/bin/python" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ✅ Python venv found"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ❌ Python venv not found at ai-services/.venv/"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ⚠️  Will skip Python AI services"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ▶ Running start.sh start..."
bash "$START_SCRIPT" start 2>&1 || {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ⚠️  start.sh exited with code $?"
}

# ─── 完成 ─────────────────────────────────────────────────────────────────────
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ═══════════════════════════════════════"
echo "[$(date '+%Y-%m-%d %H:%M:%S')️]  ✅ Boot startup complete"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ═══════════════════════════════════════"
