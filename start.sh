#!/usr/bin/env bash
# ============================================================================
# @file        start.sh
# @description ABC Desktop 服務管理腳本 — Rust API + Static + Python AI Services
# @lastUpdate  2026-06-14
# @author      Daniel Chung
# @version     2.5.0
# ============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$SCRIPT_DIR/api"
SERVER_DIR="$SCRIPT_DIR/server"
AI_DIR="$SCRIPT_DIR/ai-services"
PID_DIR="$SCRIPT_DIR/.pids"
VENV_PYTHON="$AI_DIR/.venv/bin/python"

mkdir -p "$PID_DIR"

source "$API_DIR/.env" 2>/dev/null || true
API_PORT="${PORT:-6500}"
OPENCODE_PORT=11500

# ─── Python AI Services 定義 ────────────────────────────────────────────────
# 格式: "名稱:端口:模組路徑"
# 注意：已整合到 unified_agents 的服務（da/ka/memory/backup/mcp）不再單獨啟動
# bpa_mm_agent (8005) 為歷史遺留（legacy），已停用，不再啟動
AI_SERVICES=(
  "aitask:8001:aitask.main:app"
  "skills_rag:8012:skills_rag.main:app"
  "mcp_tools:8004:mcp_tools.main:app"
  "aiq_agent:8009:aiq_agent.main:app"
  "unified_agents:8011:unified_agents.main:app"
)

# ─── 共用函數 ────────────────────────────────────────────────────────────────

kill_port() {
  local port=$1
  local pid
  pid=$(lsof -ti :"$port" 2>/dev/null || true)
  if [ -n "$pid" ]; then
    echo "  -> Stopping process on port $port (PID: $pid)"
    # 先送 SIGTERM 給優雅關閉的機會（tunnel 健康檢查不會誤判）
    kill -15 $pid 2>/dev/null || true
    # 等待最多 8 秒讓 process 自己結束
    local waited=0
    while [ $waited -lt 8 ]; do
      if ! kill -0 $pid 2>/dev/null; then
        break
      fi
      sleep 1
      waited=$((waited + 1))
    done
    # 如果還在，才強制 SIGKILL
    if kill -0 $pid 2>/dev/null; then
      echo "  -> Force killing $pid (graceful shutdown timed out)"
      kill -9 $pid 2>/dev/null || true
    fi
    sleep 1
  fi
}

# 真正的健康檢查：curl HTTP 端點，回傳 0=healthy / 1=unhealthy
# 用法: health_check <url> [timeout_seconds]
health_check() {
  local url=$1
  local timeout=${2:-3}
  curl -sf --max-time "$timeout" "$url" > /dev/null 2>&1
}

wait_for_port() {
  local port=$1
  local label=$2
  local max_wait=${3:-60}
  local elapsed=0
  while [ $elapsed -lt $max_wait ]; do
    if curl -sf "http://localhost:$port/health" > /dev/null 2>&1 || \
       curl -sf "http://localhost:$port/docs" > /dev/null 2>&1 || \
       lsof -ti :"$port" > /dev/null 2>&1; then
      echo "  ✅ $label started on port $port (${elapsed}s)"
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  echo "  ❌ $label failed to start within ${max_wait}s"
  return 1
}

# ─── Rust API Gateway (port 6500) ───────────────────────────────────────────

start_api() {
  echo "═══════════════════════════════════════"
  echo " Rust API Gateway (port $API_PORT)"
  echo "═══════════════════════════════════════"

  kill_port "$API_PORT"

  # Export all .env vars for the cargo process
  set -a
  source "$API_DIR/.env"
  set +a

  cd "$SCRIPT_DIR"
  # 預先編譯（workspace 根目錄），減少啟動時間
  echo "  -> Pre-compiling release build..."
  cargo build --release -p abc-api > /tmp/abc-api-build.log 2>&1
  if [ $? -ne 0 ]; then
    echo "  ❌ Compilation failed"
    tail -30 /tmp/abc-api-build.log
    return 1
  fi

  set -m
  ./target/release/abc-api > /tmp/abc-api.log 2>&1 &
  set +m
  echo $! > "$PID_DIR/api.pid"

  echo "  -> Waiting for API Server to respond (max 30s)..."
  local elapsed=0
  local max_wait=30
  while [ $elapsed -lt $max_wait ]; do
    if curl -sf "http://localhost:$API_PORT/health" > /dev/null 2>&1; then
      echo "  ✅ API Server started on http://localhost:$API_PORT (${elapsed}s)"
      return 0
    fi
    # Check if process is still alive
    local pid
    pid=$(cat "$PID_DIR/api.pid" 2>/dev/null)
    if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
      echo "  ❌ API Server process exited unexpectedly"
      tail -20 /tmp/abc-api.log
      return 1
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  echo "  ❌ API Server failed to start within ${max_wait}s"
  tail -30 /tmp/abc-api.log
  return 1
}

# ─── Dev Mode: Rust API with auto-reload (cargo watch) ──────────
# 注意：cargo watch 每次存檔會重啟，可能導致 tunnel 短暫斷線
# 建議僅在需要頻繁修改 Rust 程式碼時使用
dev_api() {
  echo "═══════════════════════════════════════"
  echo " Rust API Gateway — DEV MODE (cargo watch)"
  echo "═══════════════════════════════════════"

  kill_port "$API_PORT"

  set -a
  source "$API_DIR/.env"
  set +a

  cd "$SCRIPT_DIR"
  set -m
  cargo watch -x 'run --release -p abc-api' > /tmp/abc-api.log 2>&1 &
  set +m
  echo $! > "$PID_DIR/api.pid"
  echo "  -> cargo watch started (PID: $(cat "$PID_DIR/api.pid"))"
  echo "  -> Auto-reload on file change. Tunnel may disconnect during compilation."
}

stop_api() {
  if [ -f "$PID_DIR/api.pid" ]; then
    local pid
    pid=$(cat "$PID_DIR/api.pid")
    if kill -0 "$pid" 2>/dev/null; then
      echo "  -> Stopping API Server (PID: $pid)"
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_DIR/api.pid"
  fi
  kill_port "$API_PORT"
}

# ─── Web Static Site (port 3505) ────────────────────────────────────────────

start_web() {
  echo "═══════════════════════════════════════"
  echo " Web Static Site (port 3505)"
  echo "═══════════════════════════════════════"

  kill_port 3505

  local web_dir="$SCRIPT_DIR/web"
  if [ ! -d "$web_dir" ]; then
    echo "  ⚠️  $web_dir not found, skipping web server"
    return 0
  fi

  cd "$web_dir"
  set -m
  python3 -m http.server 3505 --bind 0.0.0.0 > /tmp/abc-web.log 2>&1 &
  set +m
  echo $! > "$PID_DIR/web.pid"

  sleep 2
  if lsof -ti :3505 > /dev/null 2>&1; then
    echo "  ✅ Web Server started on http://localhost:3505"
  else
    echo "  ❌ Web Server failed to start"
  fi
}

stop_web() {
  if [ -f "$PID_DIR/web.pid" ]; then
    local pid
    pid=$(cat "$PID_DIR/web.pid")
    if kill -0 "$pid" 2>/dev/null; then
      echo "  -> Stopping Web Server (PID: $pid)"
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_DIR/web.pid"
  fi
  kill_port 3505
}

# ─── Frontend Dev Server (port 1420) ────────────────────────────────────────

start_frontend() {
  echo "═══════════════════════════════════════"
  echo " Frontend (port 1420, PWA enabled)"
  echo "═══════════════════════════════════════"

  kill_port 1420

  cd "$SCRIPT_DIR"
  if [ ! -f "$SCRIPT_DIR/dist/index.html" ]; then
    echo "  ⚠️  dist/ not found, running npm run build..."
    npm run build || { echo "  ❌ Build failed"; return 1; }
  fi
  set -m
  npx vite --port 1420 < /dev/null > /tmp/abc-frontend.log 2>&1 &
  set +m
  echo $! > "$PID_DIR/frontend.pid"

  echo "  -> Waiting for Vite (max 30s)..."
  local elapsed=0
  local max_wait=30
  while [ $elapsed -lt $max_wait ]; do
    if curl -sf "http://localhost:1420/" > /dev/null 2>&1; then
      echo "  ✅ Vite dev server is up (port 1420, with API proxy)"
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  echo "  ❌ Vite failed to start"
  return 1
}

stop_frontend() {
  if [ -f "$PID_DIR/frontend.pid" ]; then
    local pid
    pid=$(cat "$PID_DIR/frontend.pid")
    if kill -0 "$pid" 2>/dev/null; then
      echo "  -> Stopping Frontend (PID: $pid)"
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_DIR/frontend.pid"
  fi
  kill_port 1420
}

# ─── OpenCode Web Server (port 11500) ────────────────────────────────────

start_opencode() {
  echo "═══════════════════════════════════════"
  echo " OpenCode Web Server (port $OPENCODE_PORT)"
  echo "═══════════════════════════════════════"

  kill_port "$OPENCODE_PORT"

  if [ -z "${OPENCODE_SERVER_PASSWORD:-}" ]; then
    echo "  ⚠️  OPENCODE_SERVER_PASSWORD not set, skipping"
    echo "     Export it in your shell: export OPENCODE_SERVER_PASSWORD=your_password"
    return 1
  fi

  set -m
  OPENCODE_SERVER_USERNAME="${OPENCODE_SERVER_USERNAME:-opencode}" \
    OPENCODE_SERVER_PASSWORD="$OPENCODE_SERVER_PASSWORD" \
    nohup opencode web \
    --port "$OPENCODE_PORT" \
    --hostname 0.0.0.0 \
    --cors https://twhc.ent4i.com \
    > /tmp/opencode-web.log 2>&1 &
  set +m
  echo $! > "$PID_DIR/opencode.pid"

  echo "  -> Waiting for OpenCode (max 30s)..."
  local elapsed=0
  local max_wait=30
  while [ $elapsed -lt $max_wait ]; do
    if lsof -ti :"$OPENCODE_PORT" > /dev/null 2>&1; then
      echo "  ✅ OpenCode started on http://localhost:$OPENCODE_PORT (${elapsed}s)"
      return 0
    fi
    local pid
    pid=$(cat "$PID_DIR/opencode.pid" 2>/dev/null)
    if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
      echo "  ❌ OpenCode process exited unexpectedly"
      tail -10 /tmp/opencode-web.log
      return 1
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  echo "  ❌ OpenCode failed to start within ${max_wait}s"
  tail -10 /tmp/opencode-web.log
  return 1
}

stop_opencode() {
  if [ -f "$PID_DIR/opencode.pid" ]; then
    local pid
    pid=$(cat "$PID_DIR/opencode.pid")
    if kill -0 "$pid" 2>/dev/null; then
      echo "  -> Stopping OpenCode (PID: $pid)"
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_DIR/opencode.pid"
  fi
  kill_port "$OPENCODE_PORT"
}

# ─── Static File Server (port 6000) ─────────────────────────────────────────

start_static() {
  echo "═══════════════════════════════════════"
  echo " Static File Server (port 6000)"
  echo "═══════════════════════════════════════"

  kill_port 6000

  if [ ! -d "$SERVER_DIR" ]; then
    echo "  ⚠️  $SERVER_DIR not found, skipping static server"
    return 0
  fi

  cd "$SERVER_DIR"
  set -m
  python3 -m http.server 6000 > /tmp/abc-static.log 2>&1 &
  set +m
  echo $! > "$PID_DIR/static.pid"

  sleep 2
  if lsof -ti :6000 > /dev/null 2>&1; then
    echo "  ✅ Static Server started on http://localhost:6000"
  else
    echo "  ❌ Static Server failed to start"
  fi
}

stop_static() {
  if [ -f "$PID_DIR/static.pid" ]; then
    local pid
    pid=$(cat "$PID_DIR/static.pid")
    if kill -0 "$pid" 2>/dev/null; then
      echo "  -> Stopping Static Server (PID: $pid)"
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_DIR/static.pid"
  fi
  kill_port 6000
}

# ─── Celery Worker ───────────────────────────────────────────────────────────

start_celery() {
  echo "═══════════════════════════════════════"
  echo " Celery Worker"
  echo "═══════════════════════════════════════"

  if [ -f "$PID_DIR/celery.pid" ]; then
    local old_pid
    old_pid=$(cat "$PID_DIR/celery.pid")
    if kill -0 "$old_pid" 2>/dev/null; then
      echo "  -> Killing old Celery worker (PID: $old_pid)"
      kill "$old_pid" 2>/dev/null || true
      sleep 2
    fi
    rm -f "$PID_DIR/celery.pid"
  fi

  if [ ! -x "$VENV_PYTHON" ]; then
    echo "  ❌ Python venv not found: $VENV_PYTHON"
    return 1
  fi

  cd "$AI_DIR"
  # set -m: 啟用 job control，讓 & 背景 process 獲得獨立 process group
  # 避免 macOS 在父 shell 結束時對整個 process group 發 SIGTERM
  set -m
  PYTHONPATH="$AI_DIR" "$AI_DIR/.venv/bin/watchfiles" \
    --filter python \
    "$AI_DIR/.venv/bin/celery -A celery_app.app worker --loglevel=info --concurrency=2" \
    "$AI_DIR" \
    > /tmp/abc-celery.log 2>&1 &
  set +m
  echo $! > "$PID_DIR/celery.pid"

  sleep 2
  local pid
  pid=$(cat "$PID_DIR/celery.pid")
  if kill -0 "$pid" 2>/dev/null; then
    echo "  ✅ Celery Worker started (PID: $pid, auto-reload on file change)"
  else
    echo "  ❌ Celery Worker failed to start"
    tail -10 /tmp/abc-celery.log
  fi
}

stop_celery() {
  if [ -f "$PID_DIR/celery.pid" ]; then
    local pid
    pid=$(cat "$PID_DIR/celery.pid")
    if kill -0 "$pid" 2>/dev/null; then
      echo "  -> Stopping Celery Worker (PID: $pid)"
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_DIR/celery.pid"
  fi
}

reload_celery() {
  echo "═══════════════════════════════════════"
  echo " 🔄 Hot-reloading Celery Worker"
  echo "═══════════════════════════════════════"

  if [ ! -f "$PID_DIR/celery.pid" ]; then
    echo "  ❌ Celery Worker is not running"
    return 1
  fi

  local pid
  pid=$(cat "$PID_DIR/celery.pid")
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "  ❌ Celery Worker PID $pid not found"
    rm -f "$PID_DIR/celery.pid"
    return 1
  fi

  # SIGHUP triggers graceful restart: finish current tasks, reload code, restart workers
  kill -HUP "$pid"
  echo "  ✅ SIGHUP sent to PID $pid — workers will reload code after current tasks finish"
}

start_celery_beat() {
  echo "═══════════════════════════════════════"
  echo " Celery Beat (Scheduler)"
  echo "═══════════════════════════════════════"

  if [ -f "$PID_DIR/celery-beat.pid" ]; then
    local old_pid
    old_pid=$(cat "$PID_DIR/celery-beat.pid")
    if kill -0 "$old_pid" 2>/dev/null; then
      kill "$old_pid" 2>/dev/null || true
      sleep 1
    fi
    rm -f "$PID_DIR/celery-beat.pid"
  fi

  cd "$AI_DIR"
  set -m
  PYTHONPATH="$AI_DIR" "$AI_DIR/.venv/bin/celery" \
    -A celery_app.app beat --loglevel=info \
    > /tmp/abc-celery-beat.log 2>&1 &
  set +m
  echo $! > "$PID_DIR/celery-beat.pid"

  sleep 2
  local pid
  pid=$(cat "$PID_DIR/celery-beat.pid")
  if kill -0 "$pid" 2>/dev/null; then
    echo "  ✅ Celery Beat started (PID: $pid)"
  else
    echo "  ❌ Celery Beat failed to start"
    tail -5 /tmp/abc-celery-beat.log
  fi
}

stop_celery_beat() {
  if [ -f "$PID_DIR/celery-beat.pid" ]; then
    local pid
    pid=$(cat "$PID_DIR/celery-beat.pid")
    if kill -0 "$pid" 2>/dev/null; then
      echo "  -> Stopping Celery Beat (PID: $pid)"
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_DIR/celery-beat.pid"
  fi
}

# ─── Python AI Services ─────────────────────────────────────────────────────

start_ai_service() {
  local name=$1 port=$2 module=$3

  echo "---------------------------------------"
  echo " $name (port $port)"
  echo "---------------------------------------"

  kill_port "$port"

  if [ ! -x "$VENV_PYTHON" ]; then
    echo "  ❌ Python venv not found: $VENV_PYTHON"
    echo "     Run: cd ai-services && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    return 1
  fi

  set -m
  "$VENV_PYTHON" -m uvicorn "$module" --host 127.0.0.1 --port "$port" --reload \
    > "/tmp/abc-${name}.log" 2>&1 &
  set +m
  echo $! > "$PID_DIR/${name}.pid"

  wait_for_port "$port" "$name" 30
}

stop_ai_service() {
  local name=$1 port=$2

  if [ -f "$PID_DIR/${name}.pid" ]; then
    local pid
    pid=$(cat "$PID_DIR/${name}.pid")
    if kill -0 "$pid" 2>/dev/null; then
      echo "  -> Stopping $name (PID: $pid)"
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_DIR/${name}.pid"
  fi
  kill_port "$port"
}

start_all_ai() {
  echo "═══════════════════════════════════════"
  echo " Python AI Services"
  echo "═══════════════════════════════════════"

  cd "$AI_DIR"
  for entry in "${AI_SERVICES[@]}"; do
    IFS=':' read -r name port module <<< "$entry"
    start_ai_service "$name" "$port" "$module"
  done
}

stop_all_ai() {
  for entry in "${AI_SERVICES[@]}"; do
    IFS=':' read -r name port module <<< "$entry"
    stop_ai_service "$name" "$port"
  done
}

find_ai_service() {
  local target=$1
  for entry in "${AI_SERVICES[@]}"; do
    IFS=':' read -r name port module <<< "$entry"
    if [ "$name" = "$target" ]; then
      echo "$name:$port:$module"
      return 0
    fi
  done
  return 1
}

do_single() {
  local action=$1 target=$2

  case "$target" in
    api)
      [ "$action" = "stop" ] || [ "$action" = "restart" ] && stop_api
      [ "$action" = "start" ] || [ "$action" = "restart" ] && start_api
      ;;
    dev-api)
      # dev-api only supports "start" — use cargo watch for auto-reload
      if [ "$action" = "start" ]; then
        dev_api
      elif [ "$action" = "stop" ]; then
        stop_api
      elif [ "$action" = "restart" ]; then
        stop_api && dev_api
      fi
      ;;
    static)
      [ "$action" = "stop" ] || [ "$action" = "restart" ] && stop_static
      [ "$action" = "start" ] || [ "$action" = "restart" ] && start_static
      ;;
    celery)
      [ "$action" = "stop" ] || [ "$action" = "restart" ] && stop_celery
      [ "$action" = "start" ] || [ "$action" = "restart" ] && start_celery
      ;;
    web)
      [ "$action" = "stop" ] || [ "$action" = "restart" ] && stop_web
      [ "$action" = "start" ] || [ "$action" = "restart" ] && start_web
      ;;
    eea|frontend)
      [ "$action" = "stop" ] || [ "$action" = "restart" ] && stop_frontend
      [ "$action" = "start" ] || [ "$action" = "restart" ] && start_frontend
      ;;
    opencode)
      [ "$action" = "stop" ] || [ "$action" = "restart" ] && stop_opencode
      [ "$action" = "start" ] || [ "$action" = "restart" ] && start_opencode
      ;;
    *)
      local entry
      entry=$(find_ai_service "$target") || {
        echo "❌ Unknown service: $target"
        echo "   Available: api, static, web, eea, opencode, $(printf '%s' "${AI_SERVICES[*]}" | tr ' ' '\n' | cut -d: -f1 | tr '\n' ' ')"
        return 1
      }
      IFS=':' read -r name port module <<< "$entry"
      [ "$action" = "stop" ] || [ "$action" = "restart" ] && stop_ai_service "$name" "$port"
      if [ "$action" = "start" ] || [ "$action" = "restart" ]; then
        cd "$AI_DIR"
        start_ai_service "$name" "$port" "$module"
      fi
      ;;
  esac
}

# ─── Status ──────────────────────────────────────────────────────────────────

status() {
  echo "═══════════════════════════════════════"
  echo " ABC Desktop Services Status"
  echo "═══════════════════════════════════════"
  echo ""

  # --- Rust API: /health JSON 深度檢查 ---
  printf "  %-22s (port %s): " "Rust API Gateway" "$API_PORT"
  local api_health
  api_health=$(curl -sf --max-time 3 "http://localhost:$API_PORT/health" 2>/dev/null || echo "")
  if [ -n "$api_health" ]; then
    local api_pid api_status
    api_pid=$(lsof -ti :"$API_PORT" 2>/dev/null | head -1)
    api_status=$(echo "$api_health" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
    if [ "$api_status" = "healthy" ]; then
      echo "✅ Healthy (PID: $api_pid)"
    else
      local arango_ok qdrant_ok
      arango_ok=$(echo "$api_health" | python3 -c "import sys,json; print(json.load(sys.stdin).get('services',{}).get('arangodb',False))" 2>/dev/null)
      qdrant_ok=$(echo "$api_health" | python3 -c "import sys,json; print(json.load(sys.stdin).get('services',{}).get('qdrant',False))" 2>/dev/null)
      local issues=""
      [ "$arango_ok" != "True" ] && issues="${issues}ArangoDB "
      [ "$qdrant_ok" != "True" ] && issues="${issues}Qdrant "
      echo "⚠️  Degraded (PID: $api_pid) — down: ${issues:-unknown}"
    fi
  else
    if lsof -ti :"$API_PORT" > /dev/null 2>&1; then
      echo "⚠️  Port open but /health unreachable"
    else
      echo "❌ Not running"
    fi
  fi

  # --- Web Static Site: HTTP 可達性 ---
  printf "  %-22s (port %s): " "Web Server" "3505"
  if health_check "http://localhost:3505/" 2; then
    local web_pid
    web_pid=$(lsof -ti :3505 2>/dev/null | head -1)
    echo "✅ Healthy (PID: $web_pid)"
  elif lsof -ti :3505 > /dev/null 2>&1; then
    echo "⚠️  Port open but not responding"
  else
    echo "❌ Not running"
  fi

  # --- Static Server: HTTP 可達性 ---
  printf "  %-22s (port %s): " "Static Server" "6000"
  if health_check "http://localhost:6000/" 2; then
    local static_pid
    static_pid=$(lsof -ti :6000 2>/dev/null | head -1)
    echo "✅ Healthy (PID: $static_pid)"
  elif lsof -ti :6000 > /dev/null 2>&1; then
    echo "⚠️  Port open but not responding"
  else
    echo "❌ Not running"
  fi

  # --- EEA Frontend (port 1420) ---
  printf "  %-22s (port %s): " "EEA Frontend" "1420"
  if health_check "http://localhost:1420/" 2; then
    local fe_pid
    fe_pid=$(lsof -ti :1420 2>/dev/null | head -1)
    echo "✅ Healthy (PID: $fe_pid)"
  elif lsof -ti :1420 > /dev/null 2>&1; then
    echo "⚠️  Port open but not responding"
  else
    echo "❌ Not running"
  fi

  # --- OpenCode Web Server (port 11500) ---
  printf "  %-22s (port %s): " "OpenCode" "$OPENCODE_PORT"
  if [ -f "$PID_DIR/opencode.pid" ] && kill -0 "$(cat "$PID_DIR/opencode.pid")" 2>/dev/null; then
    echo "✅ Healthy (PID: $(cat "$PID_DIR/opencode.pid"))"
  elif lsof -ti :"$OPENCODE_PORT" > /dev/null 2>&1; then
    local oc_pid
    oc_pid=$(lsof -ti :"$OPENCODE_PORT" 2>/dev/null | head -1)
    echo "⚠️  Port open but not managed by this script (PID: $oc_pid)"
  else
    echo "❌ Not running"
  fi

  # --- Python AI Services: /docs 端點 ---
  for entry in "${AI_SERVICES[@]}"; do
    IFS=':' read -r name port module <<< "$entry"
    printf "  %-22s (port %s): " "$name" "$port"
    if health_check "http://localhost:$port/docs" 3; then
      local svc_pid
      svc_pid=$(lsof -ti :"$port" 2>/dev/null | head -1)
      echo "✅ Healthy (PID: $svc_pid)"
    elif lsof -ti :"$port" > /dev/null 2>&1; then
      echo "⚠️  Port open but /docs unreachable"
    else
      echo "❌ Not running"
    fi
  done

  # --- Celery Worker: inspect ping ---
  printf "  %-22s            : " "Celery Worker"
  if [ -f "$PID_DIR/celery.pid" ] && kill -0 "$(cat "$PID_DIR/celery.pid")" 2>/dev/null; then
    local celery_ping
    celery_ping=$(cd "$AI_DIR" && PYTHONPATH="$AI_DIR" "$AI_DIR/.venv/bin/celery" \
      -A celery_app.app inspect ping --timeout 3 2>/dev/null || echo "")
    if echo "$celery_ping" | grep -q "pong"; then
      echo "✅ Healthy (PID: $(cat "$PID_DIR/celery.pid"))"
    else
      echo "⚠️  PID alive but worker not responding"
    fi
  else
    echo "❌ Not running"
  fi

  echo ""
  echo "  External (not managed by this script):"

  printf "  %-22s (port %s): " "ArangoDB" "8529"
  local arango_http
  arango_http=$(curl -so /dev/null -w "%{http_code}" --max-time 3 "http://localhost:8529/_api/version" 2>/dev/null || echo "000")
  if [ "$arango_http" != "000" ]; then
    echo "✅ Healthy (HTTP $arango_http)"
  elif lsof -ti :8529 > /dev/null 2>&1; then
    echo "⚠️  Port open but API unreachable"
  else
    echo "❌ Not running"
  fi

  printf "  %-22s (port %s): " "Qdrant" "6333"
  if curl -sf --max-time 3 "http://localhost:6333/collections" > /dev/null 2>&1; then
    echo "✅ Healthy"
  elif lsof -ti :6333 > /dev/null 2>&1; then
    echo "⚠️  Port open but API unreachable"
  else
    echo "❌ Not running"
  fi

  printf "  %-22s (port %s): " "SeaWeedFS Filer" "8888"
  local seaweed_http
  seaweed_http=$(curl -so /dev/null -w "%{http_code}" --max-time 3 "http://localhost:8888/" 2>/dev/null || echo "000")
  if [ "$seaweed_http" != "000" ]; then
    echo "✅ Healthy (HTTP $seaweed_http)"
  elif lsof -ti :8888 > /dev/null 2>&1; then
    echo "⚠️  Port open but not responding"
  else
    echo "❌ Not running"
  fi

  printf "  %-22s (port %s): " "Ollama" "11434"
  if curl -sf --max-time 3 "http://127.0.0.1:11400/v1/models" > /dev/null 2>&1; then
    echo "✅ Healthy"
  elif lsof -ti :11434 > /dev/null 2>&1; then
    echo "⚠️  Port open but API unreachable"
  else
    echo "❌ Not running"
  fi

  echo ""
}

# ─── Build ───────────────────────────────────────────────────────────────────

build_app() {
  echo "═══════════════════════════════════════"
  echo " Building ABC Desktop App..."
  echo "═══════════════════════════════════════"

  cd "$SCRIPT_DIR"

  echo "  -> Building frontend with production API..."
  VITE_API_URL=https://abcapi.k84.org npm run build

  echo "  -> Building Tauri (Intel)..."
  cd src-tauri
  cargo build --release --target x86_64-apple-darwin
  cd ..

  echo "  -> Building Tauri (ARM)..."
  npm run tauri build

  echo "  -> Copying Intel binary to bundle..."
  cp src-tauri/target/x86_64-apple-darwin/release/abc-desktop \
    "src-tauri/target/release/bundle/macos/ABC管理系统.app/Contents/MacOS/abc-desktop"

  echo "  -> Copying frontend to bundle..."
  cp -R dist/* "src-tauri/target/release/bundle/macos/ABC管理系统.app/Contents/Resources/"

  echo "  -> Creating DMG..."
  hdiutil create -ov -format UDRO \
    -srcfolder "src-tauri/target/release/bundle/macos/ABC管理系统.app" \
    -o "server/abc-desktop.dmg"

  echo ""
  echo "  ✅ Build complete: server/abc-desktop.dmg"
}

# ─── Logs ────────────────────────────────────────────────────────────────────

logs() {
  local target=${2:-all}
  local lines=${3:-30}

  if [ "$target" = "all" ]; then
    echo "=== API Server ===" && tail -"$lines" /tmp/abc-api.log 2>/dev/null || true
    echo ""
    for entry in "${AI_SERVICES[@]}"; do
      IFS=':' read -r name port module <<< "$entry"
      echo "=== $name ===" && tail -"$lines" "/tmp/abc-${name}.log" 2>/dev/null || true
      echo ""
    done
  else
    tail -"$lines" "/tmp/abc-${target}.log" 2>/dev/null || echo "No log found for $target"
  fi
}

# ─── Infrastructure: Docker + External Services ────────────────────────────

start_infra() {
  echo "═══════════════════════════════════════"
  echo " Infrastructure Services (Docker)"
  echo "═══════════════════════════════════════"

  # 確保 colima docker socket 可用
  export DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock"

  # ─── 1. Colima / Docker ──────────────────────────────────────────────────────
  echo "  -> Checking Docker..."
  if docker info > /dev/null 2>&1; then
    echo "  ✅ Docker is running"
  else
    echo "  -> Docker not running, starting Colima..."
    if colima start 2>&1; then
      echo "  ✅ Colima started"
    else
      echo "  ⚠️  colima start failed, attempting recovery (stop → delete → recreate)..."
      colima stop 2>/dev/null || true
      sleep 2
      colima delete --force 2>/dev/null || true
      sleep 3
      colima start --cpu 4 --memory 8 --disk 100 2>&1 || {
        echo "  ❌ Colima failed to start after recovery"
        echo "     Manual fix: colima stop && colima delete && colima start"
        echo "  ⚠️  Continuing without Docker — app services will fail if they need ArangoDB/Qdrant"
        return 1
      }
      echo "  ✅ Colima recovered and started"
    fi
  fi

  # ─── 2. Docker Compose Infra ────────────────────────────────────────────────
  local compose_file="$SCRIPT_DIR/docker-compose.infra.yml"
  if [ ! -f "$compose_file" ]; then
    echo "  ⚠️  $compose_file not found, skipping infrastructure containers"
    return 0
  fi

  echo "  -> Checking infrastructure containers..."
  local running=0
  local total=0
  running=$(docker compose -f "$compose_file" ps --status running -q 2>/dev/null | wc -l | tr -d ' ')
  total=$(docker compose -f "$compose_file" config --services 2>/dev/null | wc -l | tr -d ' ')

  if [ "$running" -ge "$total" ] 2>/dev/null; then
    echo "  ✅ Infrastructure containers already running (${running}/${total})"
  else
    echo "  ▶ Starting Docker Compose infrastructure..."
    docker compose -f "$compose_file" up -d --wait 2>&1 || {
      echo "  ⚠️  docker compose --wait failed, starting without --wait..."
      docker compose -f "$compose_file" up -d 2>&1
    }
    echo "  ✅ Docker Compose infrastructure started"
  fi

  # ─── 3. Wait for critical services ───────────────────────────────────────────
  echo ""
  echo "  -> Waiting for infrastructure services..."

  # ArangoDB (port 8529) — Rust API 直接依賴
  local arango_elapsed=0
  printf "  ⏳ Waiting for ArangoDB (max 60s)..."
  while [ $arango_elapsed -lt 60 ]; do
    if curl -sf --max-time 3 "http://localhost:8529/_api/version" > /dev/null 2>&1; then
      printf " ✅ (%ss)\n" "$arango_elapsed"
      break
    fi
    sleep 3
    arango_elapsed=$((arango_elapsed + 3))
  done
  if [ $arango_elapsed -ge 60 ]; then
    printf " ❌\n"
    echo "  ⚠️  ArangoDB not ready — Rust API will fail to start"
  fi

  # 其他基礎服務
  wait_for_port 6333 "Qdrant" 30
  wait_for_port 6379 "Redis" 30
  wait_for_port 8888 "SeaweedFS Filer" 30

  echo "  ✅ Infrastructure check complete"
  echo ""
}

# ─── Main ────────────────────────────────────────────────────────────────────

case "${1:-status}" in
  start)
    if [ -n "${2:-}" ]; then
      do_single start "$2"
    else
      set +e  # 單一服務失敗不中斷整體啟動流程
      start_infra
      start_api
      start_frontend
      start_static
      start_web
      start_all_ai
      start_celery
      start_opencode
      set -e
      echo ""
      echo "═══════════════════════════════════════"
      echo " All services started!"
      echo "═══════════════════════════════════════"
      status
    fi
    ;;
  stop)
    if [ -n "${2:-}" ]; then
      do_single stop "$2"
    else
      stop_api
      stop_frontend
      stop_static
      stop_web
      stop_all_ai
      stop_celery
      stop_opencode
      echo "  ✅ All services stopped"
    fi
    ;;
  restart)
    if [ -n "${2:-}" ]; then
      do_single restart "$2"
    else
      stop_api
      stop_frontend
      stop_static
      stop_web
      stop_all_ai
      stop_celery
      stop_opencode
      sleep 2
      set +e  # 單一服務失敗不中斷整體重啟流程
      start_infra
      start_api
      start_frontend
      start_static
      start_web
      start_all_ai
      start_celery
      start_opencode
      set -e
      echo ""
      status
    fi
    ;;
  start-ai)
    start_all_ai
    ;;
  stop-ai)
    stop_all_ai
    echo "  ✅ All AI services stopped"
    ;;
  restart-ai)
    stop_all_ai
    sleep 1
    start_all_ai
    ;;
  status)
    status
    ;;
  build)
    build_app
    ;;
  logs)
    logs "$@"
    ;;
  help|*)
    echo "Usage: $0 <command> [service]"
    echo ""
    echo "Batch Commands:"
    echo "  start           Start all services (API + Frontend + Static + AI)"
    echo "  stop            Stop all services"
    echo "  restart         Restart all services"
    echo "  start-ai        Start all Python AI services"
    echo "  stop-ai         Stop all Python AI services"
    echo "  restart-ai      Restart all Python AI services"
    echo ""
    echo "Single Service Commands:"
    echo "  start   <name>  Start a single service"
    echo "  stop    <name>  Stop a single service"
    echo "  restart <name>  Restart a single service"
    echo ""
    echo "Available services:"
    echo "  api               Rust API Gateway (port $API_PORT, pre-compiled, stable)"
    echo "  dev-api           Rust API Gateway (cargo watch, auto-reload, may disrupt tunnel)"
    echo "  static            Static File Server (port 6000)"
    echo "  web               Web Static Site (port 3505)"
    echo "  eea               Frontend Dev Server / React SPA (port 1420)"
  echo "  frontend          Alias for 'eea'"
  echo "  opencode          OpenCode Web Server (port $OPENCODE_PORT, remote via twhc.ent4i.com)"
  echo "  celery            Celery Worker (async task queue)"
    for entry in "${AI_SERVICES[@]}"; do
      IFS=':' read -r name port module <<< "$entry"
      if [ "$name" = "unified_agents" ]; then
        printf "  %-18s  Unified entry (port %s) - replaces da/ka/memory/backup/mcp\n" "$name" "$port"
      elif [ "$name" = "aiq_agent" ]; then
        printf "  %-18s  AIQ 意圖引擎 (port %s)\n" "$name" "$port"
      else
        printf "  %-18s  Python AI service (port %s)\n" "$name" "$port"
      fi
    done
    echo ""
    echo "Other Commands:"
    echo "  status          Show all service status"
    echo "  build           Build Tauri desktop app"
    echo "  logs [name]     Show service logs (default: all)"
    echo "  help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 restart api          Restart only Rust API"
    echo "  $0 restart frontend     Restart only Frontend Dev Server"
    echo "  $0 start aitask         Start only aitask service"
    echo "  $0 stop data_agent      Stop only data_agent"
    echo "  $0 logs aitask          Show aitask logs"
    exit 1
    ;;
esac
