#!/bin/bash
#
# @file        checkTunnel.sh
# @description Cloudflare Tunnel 狀態檢查與重啟腳本
# @lastUpdate  2026-06-13 22:00:00
# @author      Sisyphus
# @version     1.0.0
#
# 用法:
#   ./checkTunnel.sh          — 檢查狀態
#   ./checkTunnel.sh restart  — 重新啟動 daemon
#   ./checkTunnel.sh log      — 查看最近 20 筆日誌
#

PLIST="/Library/LaunchDaemons/com.cloudflare.cloudflared.plist"
TUNNEL_DOMAIN="https://eea.ent4i.com"
CLOUDFLARED="/opt/homebrew/bin/cloudflared"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
err()   { echo -e "${RED}[✗]${NC} $1"; }

check_tunnel() {
  echo "=============================="
  echo " Cloudflare Tunnel 檢查"
  echo "=============================="

  # 1. 檢查 cloudflared 是否安裝
  if [ -x "$CLOUDFLARED" ]; then
    info "cloudflared 已安裝 ($($CLOUDFLARED --version 2>/dev/null | head -1))"
  else
    err "cloudflared 未安裝或找不到"
    exit 1
  fi

  # 2. 檢查 daemon plist 是否存在
  if [ -f "$PLIST" ]; then
    info "Daemon plist 存在"
  else
    err "Daemon plist 不存在 ($PLIST)"
  fi

  # 3. 檢查 cloudflared process
  PID=$(pgrep -f "cloudflared tunnel" | head -1)
  if [ -n "$PID" ]; then
    info "Tunnel process 運行中 (PID: $PID)"
  else
    err "Tunnel process 未運行"
  fi

  # 4. 檢查 launchctl 是否已載入（system domain）
  # 注意：如果是用 sudo launchctl bootstrap system 載入的，
  # 要用 launchctl print system/ 檢查，launchctl list 只查 user domain
  if sudo launchctl print system/com.cloudflare.cloudflared 2>/dev/null | grep -q "state = running"; then
    info "Launch daemon 已載入（system domain）"
  elif launchctl list | grep -q "com.cloudflare.cloudflared" 2>/dev/null; then
    info "Launch daemon 已載入（user domain）"
  else
    warn "Launch daemon 未載入（開機後需要手動啟動）"
  fi

  # 5. 檢查 HTTPS 連線
  echo ""
  echo "--- Domain 連線測試 ---"
  for domain in "eea.ent4i.com" "eeaapi.ent4i.com" "olm.k84.org"; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "https://$domain/" 2>/dev/null || echo "TIMEOUT")
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "404" ] || [ "$HTTP_CODE" = "302" ]; then
      info "https://$domain/ → $HTTP_CODE"
    elif [ "$HTTP_CODE" = "530" ]; then
      err "https://$domain/ → 530 (Cloudflare 無法連到源站)"
    else
      warn "https://$domain/ → $HTTP_CODE"
    fi
  done

  # 6. 總結
  echo ""
  if [ -n "$PID" ]; then
    echo -e "${GREEN} Tunnel 狀態：正常${NC}"
  else
    echo -e "${RED} Tunnel 狀態：異常${NC}"
    echo "  執行以下指令重啟："
    echo "  sudo launchctl bootstrap system $PLIST"
  fi
  echo "=============================="
}

restart_tunnel() {
  echo "=== 重新啟動 Cloudflare Tunnel ==="

  # 停掉現有 process
  PID=$(pgrep -f "cloudflared tunnel" | head -1) || true
  if [ -n "$PID" ]; then
    echo "停掉現有 process (PID: $PID)..."
    kill "$PID" 2>/dev/null || true
    sleep 2
  fi

  # 重啟 daemon
  if [ -f "$PLIST" ]; then
    echo "解除舊的 daemon 註冊..."
    sudo launchctl bootout system "$PLIST" 2>/dev/null || true
    sleep 1
    echo "重新註冊並啟動 daemon..."
    sudo launchctl bootstrap system "$PLIST"
    sleep 2
    NEW_PID=$(pgrep -f "cloudflared tunnel" | head -1)
    if [ -n "$NEW_PID" ]; then
      info "Tunnel 已重啟 (PID: $NEW_PID)"
    else
      # fallback: 直接用 cloudflared 手動啟動
      echo "  -> Daemon 啟動未產生 process，嘗試手動啟動..."
      sudo launchctl kickstart -k system/com.cloudflare.cloudflared 2>/dev/null || \
      nohup "$CLOUDFLARED" tunnel run > /tmp/cloudflared.log 2>&1 &
      sleep 3
      NEW_PID=$(pgrep -f "cloudflared tunnel" | head -1)
      if [ -n "$NEW_PID" ]; then
        info "Tunnel 已啟動 (PID: $NEW_PID, 手動模式)"
      else
        err "重啟失敗，請檢查日誌：./checkTunnel.sh log"
      fi
    fi
  else
    err "找不到 plist"
  fi

  echo ""
  check_tunnel
}

show_log() {
  LOG_FILE="/Library/Logs/com.cloudflare.cloudflared.out.log"
  ERR_FILE="/Library/Logs/com.cloudflare.cloudflared.err.log"

  echo "=== Tunnel 日誌 (stdout) ==="
  if [ -f "$LOG_FILE" ]; then
    tail -20 "$LOG_FILE"
  else
    echo "無 stdout 日誌"
  fi

  echo ""
  echo "=== Tunnel 日誌 (stderr) ==="
  if [ -f "$ERR_FILE" ]; then
    tail -20 "$ERR_FILE"
  else
    echo "無 stderr 日誌"
  fi
}

# Main
case "${1:-check}" in
  check)
    check_tunnel
    ;;
  restart)
    restart_tunnel
    ;;
  log)
    show_log
    ;;
  *)
    echo "用法: $0 {check|restart|log}"
    echo "  check   — 檢查 Tunnel 狀態（預設）"
    echo "  restart — 重新啟動 Tunnel daemon"
    echo "  log     — 查看最近日誌"
    exit 1
    ;;
esac
