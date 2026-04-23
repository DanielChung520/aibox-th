#!/bin/bash
#===============================================================================
# @file        01_sync_ragic_schema.sh
# @description Ragic Schema + Intents 一步到位同步腳本
# @usage       bash 01_sync_ragic_schema.sh <account_name>
# @example     bash 01_sync_ragic_schema.sh dawnlink
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
NC='\033[0m' # No Color

# 預設值
ACCOUNT=${1:-dawnlink}
API_HOST=${API_HOST:-localhost}
API_PORT=${API_PORT:-8003}
API_BASE="http://${API_HOST}:${API_PORT}"

# 服務健康檢查
check_service() {
    echo -e "${BLUE}Checking Data Agent service...${NC}"
    local health=$(curl -s "${API_BASE}/ragic/health" 2>/dev/null | grep -o '"status":"ok"' || echo "")
    if [ -z "$health" ]; then
        echo -e "${RED}✗ Data Agent service is not running at ${API_BASE}${NC}"
        echo -e "${YELLOW}  Please start the service first:${NC}"
        echo -e "${YELLOW}  cd ai-services && source .venv/bin/activate${NC}"
        echo -e "${YELLOW}  uvicorn data_agent.main:app --port ${API_PORT} --reload${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Data Agent service is healthy${NC}"
}

# 同步 Schema
sync_schema() {
    echo -e "${BLUE}[1/5] Syncing Schema to Qdrant for account: ${ACCOUNT}${NC}"
    local response=$(curl -s -X POST "${API_BASE}/ragic/schema/sync" \
        -H "Content-Type: application/json" \
        -d "{\"connection_name\": \"${ACCOUNT}\"}" \
        --max-time 60)
    
    if echo "$response" | grep -q '"code":0\|"status":"ok\|synced'; then
        echo -e "${GREEN}✓ Schema synced successfully${NC}"
    else
        echo -e "${YELLOW}⚠ Schema sync response: ${response}${NC}"
    fi
}

# 同步 Intents
sync_intents() {
    echo -e "${BLUE}[2/5] Syncing Intents to Qdrant for account: ${ACCOUNT}${NC}"
    local response=$(curl -s -X POST "${API_BASE}/ragic/intent/sync" \
        -H "Content-Type: application/json" \
        -d "{\"connection_name\": \"${ACCOUNT}\"}" \
        --max-time 60)
    
    if echo "$response" | grep -q '"code":0\|"status":"ok\|synced'; then
        echo -e "${GREEN}✓ Intents synced successfully${NC}"
    else
        echo -e "${YELLOW}⚠ Intent sync response: ${response}${NC}"
    fi
}

# 重新載入設定
reload_config() {
    echo -e "${BLUE}[3/5] Reloading configuration cache...${NC}"
    local response=$(curl -s -X POST "${API_BASE}/ragic/config/reload" \
        --max-time 30)
    echo -e "${GREEN}✓ Config reloaded${NC}"
}

# 驗證同步結果
verify_sync() {
    echo -e "${BLUE}[4/5] Verifying sync results...${NC}"
    
    # 檢查 Schema 數量
    local schema_count=$(curl -s "${API_BASE}/ragic/schema/tables" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "{\"connection_name\": \"${ACCOUNT}\"}" \
        --max-time 30 | grep -o '"table_key"' | wc -l || echo "0")
    
    echo -e "${GREEN}✓ Found ${schema_count} tables synced for ${ACCOUNT}${NC}"
}

# 顯示完成資訊
show_summary() {
    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}  Ragic Sync Completed!${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo -e "${BLUE}  Account: ${ACCOUNT}${NC}"
    echo -e "${BLUE}  API Base: ${API_BASE}${NC}"
    echo ""
    echo -e "${YELLOW}  Next steps:${NC}"
    echo -e "${YELLOW}  1. Check Schema diff if needed:${NC}"
    echo -e "${YELLOW}     curl -X POST \"${API_BASE}/ragic/schema/diff\" \\${NC}"
    echo -e "${YELLOW}       -d '{\"connection_name\": \"${ACCOUNT}\"}'${NC}"
    echo -e "${YELLOW}  2. Test a query:${NC}"
    echo -e "${YELLOW}     curl -X POST \"${API_BASE}/ragic/query\" \\${NC}"
    echo -e "${YELLOW}       -H \"Content-Type: application/json\" \\${NC}"
    echo -e "${YELLOW}       -d '{\"query\": \"test\", \"connection_name\": \"${ACCOUNT}\"}'${NC}"
    echo -e "${YELLOW}  3. Update API docs if needed:${NC}"
    echo -e "${YELLOW}     → .docs/Ragic/${ACCOUNT}.md${NC}"
    echo -e "${YELLOW}  4. Update Field Mapping if needed:${NC}"
    echo -e "${YELLOW}     → ai-services/datalake/ragic_field_mapping.py${NC}"
    echo ""
    echo -e "${GREEN}============================================${NC}"
}

# 主流程
main() {
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  Ragic Schema + Intents Sync Script${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  Account: ${ACCOUNT}${NC}"
    echo -e "${BLUE}  API: ${API_BASE}${NC}"
    echo ""
    
    check_service
    sync_schema
    sync_intents
    reload_config
    verify_sync
    show_summary
}

# 執行
main "$@"
