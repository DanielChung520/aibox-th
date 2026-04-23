#!/bin/bash
#===============================================================================
# @file        02_sync_ragic_intents.sh
# @description Ragic Intents 專用同步腳本（不含 Schema）
# @usage       bash 02_sync_ragic_intents.sh <account_name>
# @example     bash 02_sync_ragic_intents.sh dawnlink
# @lastUpdate  2026-04-18
# @author      Daniel Chung
# @version     1.0.0
#===============================================================================

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 預設值
ACCOUNT=${1:-dawnlink}
API_HOST=${API_HOST:-localhost}
API_PORT=${API_PORT:-8003}
API_BASE="http://${API_HOST}:${API_PORT}"

check_service() {
    echo -e "${BLUE}Checking Data Agent service...${NC}"
    local health=$(curl -s "${API_BASE}/ragic/health" 2>/dev/null | grep -o '"status":"ok"' || echo "")
    if [ -z "$health" ]; then
        echo -e "${RED}✗ Data Agent service is not running at ${API_BASE}${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Data Agent service is healthy${NC}"
}

sync_intents() {
    echo -e "${BLUE}[1/3] Syncing Intents to Qdrant for account: ${ACCOUNT}${NC}"
    local response=$(curl -s -X POST "${API_BASE}/ragic/intent/sync" \
        -H "Content-Type: application/json" \
        -d "{\"connection_name\": \"${ACCOUNT}\"}" \
        --max-time 120)
    
    if echo "$response" | grep -q '"code":0\|"status":"ok\|synced'; then
        echo -e "${GREEN}✓ Intents synced successfully${NC}"
    else
        echo -e "${YELLOW}⚠ Intent sync response: ${response}${NC}"
    fi
}

reload_config() {
    echo -e "${BLUE}[2/3] Reloading configuration cache...${NC}"
    curl -s -X POST "${API_BASE}/ragic/config/reload" --max-time 30 > /dev/null
    echo -e "${GREEN}✓ Config reloaded${NC}"
}

show_summary() {
    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}  Intent Sync Completed!${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo -e "${BLUE}  Account: ${ACCOUNT}${NC}"
    echo ""
}

main() {
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  Ragic Intents Sync Script${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
    
    check_service
    sync_intents
    reload_config
    show_summary
}

main "$@"
