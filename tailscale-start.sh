#!/bin/bash
# ============================================================================
# @file        tailscale-start.sh
# @description Tailscale 開機啟動 — 官網版系統 Network Extension
# @lastUpdate  2026-05-30
# @author      Daniel Chung
# @version     1.2.0
# ============================================================================

LOG_FILE="/tmp/aibox-th-tailscale.log"
TAILSCALE="/usr/local/bin/tailscale"

exec >> "$LOG_FILE" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ═══════════════════════════════════════"
echo "[$(date '+%Y-%m-%d %H:%M:%S')]  Tailscale Boot Startup"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ═══════════════════════════════════════"

# ─── 等待 System Extension 就緒（最長 60s）────────────────────────────────
echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ⏳ Waiting for Tailscale extension..."
for i in $(seq 1 20); do
    if "$TAILSCALE" status > /dev/null 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ✅ Extension ready (${i}x3s)"
        break
    fi
    sleep 3
    if [ "$i" -eq 20 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ❌ Extension not ready after 60s, will retry via LaunchDaemon"
        exit 0
    fi
done

# ─── 執行 tailscale up ───────────────────────────────────────────────────────
echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ▶ Running tailscale up..."
if ! "$TAILSCALE" up --accept-routes 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ❌ tailscale up failed"
    exit 1
fi
echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ✅ tailscale up succeeded"

# ─── 確認連線真正活著（tailscale up 回傳 0 但可能仍 offline）─────────────
echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ⏳ Waiting for active connection..."

for i in $(seq 1 10); do
    sleep 3
    IP=$("$TAILSCALE" ip -4 2>/dev/null)
    if [ -n "$IP" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ✅ Tailscale connected (IP: $IP, ${i}x3s)"
        "$TAILSCALE" status 2>&1
        exit 0
    fi
    echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ⏳ still waiting (attempt $i)..."
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ⚠️  timeout waiting for active connection, LaunchDaemon will retry"
"$TAILSCALE" status 2>&1
exit 0
