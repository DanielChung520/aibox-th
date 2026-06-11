#!/bin/bash
#
# deploy-site.sh — 部署產品下載頁 + DMG 到伺服器
#
# 用法:
#   ./deploy-site.sh user@your-server
#
# 執行後會：
#   1. 上傳 site/index.html 到伺服器 ~/abc-site/
#   2. 上傳 DMG 到伺服器 ~/abc-site/downloads/
#   3. 在伺服器上啟動 python3 靜態伺服器 (port 6000)
#
# 前提：伺服器需有 python3，abc.k84.org 已指向伺服器的 port 6000

set -e

SERVER="${1:?用法: ./deploy-site.sh user@your-server}"
REMOTE_DIR="abc-site"

ARM_DMG="target/aarch64-apple-darwin/release/bundle/dmg/ABC管理系统_1.0.0_aarch64.dmg"
INTEL_DMG="target/x86_64-apple-darwin/release/bundle/dmg/ABC管理系统_1.0.0_x64.dmg"

echo "=== 部署 ABC Desktop 下載頁 ==="
echo "目標伺服器: $SERVER"
echo ""

for f in "site/index.html" "$ARM_DMG" "$INTEL_DMG"; do
  if [ ! -f "$f" ]; then
    echo "錯誤: 找不到 $f"
    echo "請先執行 npm run tauri:build:mac-arm 和 npm run tauri:build:mac-intel"
    exit 1
  fi
done

echo "[1/4] 建立遠端目錄..."
ssh "$SERVER" "mkdir -p ~/$REMOTE_DIR/downloads"

echo "[2/4] 上傳 index.html..."
scp site/index.html "$SERVER:~/$REMOTE_DIR/index.html"

echo "[3/4] 上傳 DMG 檔案（可能需要幾分鐘）..."
scp "$ARM_DMG" "$SERVER:~/$REMOTE_DIR/downloads/"
scp "$INTEL_DMG" "$SERVER:~/$REMOTE_DIR/downloads/"

echo "[4/4] 啟動靜態伺服器 (port 6000)..."
ssh "$SERVER" "
  # 停止舊的伺服器（如果有）
  pkill -f 'python3 -m http.server 6000' 2>/dev/null || true
  sleep 1
  # 啟動新的
  cd ~/$REMOTE_DIR && nohup python3 -m http.server 6000 > /dev/null 2>&1 &
  echo 'PID:' \$!
"

echo ""
echo "=== 部署完成 ==="
echo "下載頁: https://abc.k84.org"
echo "ARM DMG: https://abc.k84.org/downloads/ABC管理系统_1.0.0_aarch64.dmg"
echo "Intel DMG: https://abc.k84.org/downloads/ABC管理系统_1.0.0_x64.dmg"
