#!/bin/bash
# ============================================================================
# @file        colima-start.sh
# @description Colima VM 開機啟動 wrapper — 自動處理 VM 磁碟鎖定/損毀
# @lastUpdate  2026-05-30
# @author      Daniel Chung
# @version     1.0.0
# ============================================================================
# colima 在 macOS 重開機後有時會因 VM 狀態損毀而無法啟動（disk in use）。
# 此 wrapper 自動嘗試修復：先正常啟動，失敗則砍掉重建。

LOG_FILE="/tmp/aibox-th-colima-wrapper.log"

exec >> "$LOG_FILE" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ═══════════════════════════════════════"
echo "[$(date '+%Y-%m-%d %H:%M:%S')]  Colima Boot Startup"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ═══════════════════════════════════════"

export HOME="/Users/daniel"
export USER="daniel"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

# 等待系統就緒
sleep 10

# 嘗試 1: 正常啟動
echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ▶ Attempt 1: colima start..."
if colima start 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ✅ Colima started"
    colima status 2>&1 | head -3
    exit 0
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ⚠️  colima start failed, trying recovery..."
sleep 3

# 清理 zombie 狀態
echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ▶ Stopping and deleting broken instance..."
colima stop 2>/dev/null || true
sleep 2
colima delete --force 2>/dev/null || true
sleep 3

# 嘗試 2: 砍掉重建（確保指定正確的 CPU/記憶體）
echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ▶ Attempt 2: colima start --cpu 4 --memory 8 --disk 100..."
if colima start --cpu 4 --memory 8 --disk 100 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ✅ Colima recovered and started"
    exit 0
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')]  ❌ Colima failed to start after recovery"
exit 1
