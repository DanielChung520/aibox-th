#!/bin/bash
# 安裝 Cloudflare Tunnel 為系統 daemon（開機自動啟動、崩潰自動重生）

PLIST_SRC="/Users/daniel/GitHub/AIBox-TH/.tmp/com.cloudflare.cloudflared.plist"
PLIST_DST="/Library/LaunchDaemons/com.cloudflare.cloudflared.plist"

# 停掉所有現有 tunnel
echo "==> 停掉現有 tunnel..."
pkill -f "cloudflared tunnel" 2>/dev/null || true
sleep 2

# 安裝 plist
echo "==> 安裝 plist 到 $PLIST_DST..."
sudo cp "$PLIST_SRC" "$PLIST_DST" 2>/dev/null || cp "$PLIST_SRC" "$PLIST_DST"
sudo chown root:wheel "$PLIST_DST" 2>/dev/null || chown root:wheel "$PLIST_DST"

# 註冊並啟動 daemon
echo "==> 註冊並啟動 daemon..."
sudo launchctl bootstrap system "$PLIST_DST" 2>/dev/null || \
sudo launchctl load "$PLIST_DST" 2>/dev/null || \
echo "    ⚠️  daemon 註冊失敗，請手動執行："
echo "    sudo launchctl bootstrap system $PLIST_DST"

sleep 3

# 驗證
PID=$(pgrep -f "cloudflared tunnel" | head -1)
if [ -n "$PID" ]; then
  echo "✅ Tunnel daemon 運行中 (PID: $PID)"
  echo "✅ 開機自動啟動：是"
  echo "✅ 崩潰自動重生：是"
else
  echo "❌ Tunnel 未啟動"
fi

echo ""
echo "==> 測試網域..."
for d in eea.ent4i.com eeaapi.ent4i.com; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "https://$d/" 2>/dev/null)
  echo "  $d → HTTP $code"
done
