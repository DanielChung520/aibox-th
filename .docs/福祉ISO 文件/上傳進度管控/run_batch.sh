#!/bin/bash
# 福祉ISO 批次上傳 — 快速執行腳本
# 用法: ./run_batch.sh [phase] [options]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../../.." || exit 1  # 回到專案根目錄

# 啟動 AI Services 虛擬環境
if [ -d "ai-services/.venv" ]; then
    source ai-services/.venv/bin/activate
elif [ -d "ai-services/.venv-314" ]; then
    source ai-services/.venv-314/bin/activate
fi

python3 "$SCRIPT_DIR/batch_upload_welfare_iso.py" "$@"
