# da_intents 設計方案 - Sales 模組

## 設計原則

### 感知層 (Perception Layer)
- **nl_examples**：真實場景語句，包含「動作詞 + 維度 + 條件」
- **action**：query / count / sum / update
- **domain**：sales / crm / contract / inventory

### 對策層 (Strategy Layer)
- **query_type**：simple_filter（Path A）/ aggregate（Path B）
- **tool_schema**：根據 table capabilities 自動生成

### 學習層 (Learning Layer)
- **expected_output**：留空，待實際執行後填入
- **golden_sql**：留空，待驗證後填入
- **difficulty_level**：easy / medium / hard

---

## 設計清單

### Core Tables（aggregate = true）- 4 個場景

---

#### FORMS4_2: 潛在交易對象
```json
{
  "intent_id": "FORMS4_2_default",
  "agent_scope": "data_agent",
  "name": "潛在交易對象查詢",
  "description": "CRM潛在交易對象名單管理",

  "nl_examples": [
    "查詢產業別為科技的潛在交易對象",
    "統計各狀態的潛在客戶數量",
    "找出公司人數超過100人的廠商",
    "列出最近一個月有聯絡的潛在客戶"
  ],
  "action": "query",
  "domain": "crm",

  "table_key": "FORMS4_2",
  "query_type": "simple_filter",
  "capabilities": { "simple_filter": true, "aggregate": true }
}
```

---

#### FORMS4_8: 顧客分析
```json
{
  "intent_id": "FORMS4_8_default",
  "agent_scope": "data_agent",
  "name": "顧客交易分析",
  "description": "顧客交易行為分析統計",

  "nl_examples": [
    "查詢總交易金額最高的TOP 10客戶",
    "統計平均訂單價值超過5000的客戶",
    "找出總交易次數少於5次的顧客",
    "列出總交易金額前十名公司"
  ],
  "action": "sum",
  "domain": "sales",

  "table_key": "FORMS4_8",
  "query_type": "aggregate",
  "capabilities": { "simple_filter": true, "aggregate": true }
}
```

---

#### FORMS4_9: 產品統計分析
```json
{
  "intent_id": "FORMS4_9_default",
  "agent_scope": "data_agent",
  "name": "產品銷售統計",
  "description": "產品銷售與庫存統計分析",

  "nl_examples": [
    "統計各產品類別的總利潤",
    "查詢平均月銷量前三名的商品",
    "找出庫存量低於安全庫存的產品",
    "列出總利潤最高的產品線"
  ],
  "action": "sum",
  "domain": "sales",

  "table_key": "FORMS4_9",
  "query_type": "aggregate",
  "capabilities": { "simple_filter": true, "aggregate": true }
}
```

---

#### FORMS4_10: 應收帳款分析
```json
{
  "intent_id": "FORMS4_10_default",
  "agent_scope": "data_agent",
  "name": "應收帳款統計",
  "description": "應收帳款回收分析",

  "nl_examples": [
    "統計本月應收帳款總金額",
    "查詢已收金額超過10萬的發票",
    "找出未收帳款逾期超過30天的客戶",
    "列出應收帳款最高的前五家公司"
  ],
  "action": "sum",
  "domain": "finance",

  "table_key": "FORMS4_10",
  "query_type": "aggregate",
  "capabilities": { "simple_filter": true, "aggregate": true }
}
```

---

#### FORMS4_11: 丟單原因分析
```json
{
  "intent_id": "FORMS4_11_default",
  "agent_scope": "data_agent",
  "name": "丟單原因統計",
  "description": "銷售丟單原因分析",

  "nl_examples": [
    "統計各種丟單原因的數量分布",
    "查詢本月丟單的業務人員",
    "找出預計金額超過50萬的丟單案件",
    "列出最常見的丟單原因"
  ],
  "action": "count",
  "domain": "sales",

  "table_key": "FORMS4_11",
  "query_type": "aggregate",
  "capabilities": { "simple_filter": true, "aggregate": true }
}
```

---

#### FORMS4_13: 機會和風險分析
```json
{
  "intent_id": "FORMS4_13_default",
  "agent_scope": "data_agent",
  "name": "商機風險分析",
  "description": "銷售機會與風險評估",

  "nl_examples": [
    "統計各風險等級的機會數量",
    "查詢預計金額最高的專案",
    "找出高風險機會的負責人",
    "列出待追蹤的機會清單"
  ],
  "action": "count",
  "domain": "sales",

  "table_key": "FORMS4_13",
  "query_type": "aggregate",
  "capabilities": { "simple_filter": true, "aggregate": true }
}
```

---

#### FORMS4_15: 生產資訊透明
```json
{
  "intent_id": "FORMS4_15_default",
  "agent_scope": "data_agent",
  "name": "生產狀況統計",
  "description": "生產數據統計分析",

  "nl_examples": [
    "統計各產線的生產數量",
    "查詢良品率低於95%的產線",
    "找出生產數量最高的產品",
    "列出本月的生產概況"
  ],
  "action": "sum",
  "domain": "manufacturing",

  "table_key": "FORMS4_15",
  "query_type": "aggregate",
  "capabilities": { "simple_filter": true, "aggregate": true }
}
```

---

#### RAGICSALES_12: 潛在客戶
```json
{
  "intent_id": "RAGICSALES_12_default",
  "agent_scope": "data_agent",
  "name": "潛在客戶管理",
  "description": "潛在客戶名單與追蹤",

  "nl_examples": [
    "查詢產業別為科技的潛在客戶",
    "統計各部門的潛在客戶數量",
    "找出公司人數超過50人的廠商",
    "列出狀態為積極開發的客戶"
  ],
  "action": "query",
  "domain": "crm",

  "table_key": "RAGICSALES_12",
  "query_type": "simple_filter",
  "capabilities": { "simple_filter": true, "aggregate": true }
}
```

---

#### RAGICSALES_14: 合約
```json
{
  "intent_id": "RAGICSALES_14_default",
  "agent_scope": "data_agent",
  "name": "合約管理",
  "description": "客戶合約到期管理",

  "nl_examples": [
    "查詢即將到期的合約",
    "統計各狀態的合約數量",
    "找出合約長度超過一年的客戶",
    "列出本月的合約總數"
  ],
  "action": "query",
  "domain": "contract",

  "table_key": "RAGICSALES_14",
  "query_type": "simple_filter",
  "capabilities": { "simple_filter": true, "aggregate": true }
}
```

---

#### RAGICSALES_17: 客供料庫存管理
```json
{
  "intent_id": "RAGICSALES_17_default",
  "agent_scope": "data_agent",
  "name": "客供料庫存查詢",
  "description": "客供物料庫存追蹤",

  "nl_examples": [
    "查詢特定料號的庫存數量",
    "統計各庫存地點的存貨分佈",
    "找出庫存數量為零的料號",
    "列出最近更新的庫存記錄"
  ],
  "action": "query",
  "domain": "inventory",

  "table_key": "RAGICSALES_17",
  "query_type": "simple_filter",
  "capabilities": { "simple_filter": true, "aggregate": true }
}
```

---

#### RAGICSALES_2: 活動展覽
```json
{
  "intent_id": "RAGICSALES_2_default",
  "agent_scope": "data_agent",
  "name": "活動管理",
  "description": "行銷活動與展覽管理",

  "nl_examples": [
    "查詢本月即將舉辦的活動",
    "統計各活動類型的參加人數",
    "找出參加人數最多的展覽",
    "列出過期的活動清單"
  ],
  "action": "query",
  "domain": "marketing",

  "table_key": "RAGICSALES_2",
  "query_type": "simple_filter",
  "capabilities": { "simple_filter": true, "aggregate": true }
}
```

---

### Basic Tables（2-3 個場景）

---

#### FORMS4_1: CRM-聯絡人管理
```json
{
  "intent_id": "FORMS4_1_default",
  "agent_scope": "data_agent",
  "name": "聯絡人查詢",
  "description": "CRM聯絡人名單",

  "nl_examples": [
    "查詢特定公司的聯絡人",
    "列出所有業務聯絡人"
  ],
  "action": "query",
  "domain": "crm",

  "table_key": "FORMS4_1",
  "query_type": "simple_filter",
  "capabilities": { "simple_filter": true, "aggregate": false }
}
```

---

#### FORMS4_3: CRM-工作項目
```json
{
  "intent_id": "FORMS4_3_default",
  "agent_scope": "data_agent",
  "name": "工作項目管理",
  "description": "CRM工作項目追蹤",

  "nl_examples": [
    "查詢待辦工作項目",
    "列出逾期的工作任務"
  ],
  "action": "query",
  "domain": "crm",

  "table_key": "FORMS4_3",
  "query_type": "simple_filter",
  "capabilities": { "simple_filter": true, "aggregate": false }
}
```

---

#### FORMS4_4: CRM-銷售機會
```json
{
  "intent_id": "FORMS4_4_default",
  "agent_scope": "data_agent",
  "name": "銷售機會追蹤",
  "description": "CRM銷售機會管理",

  "nl_examples": [
    "查詢進行中的銷售機會",
    "統計各階段的機會數量"
  ],
  "action": "query",
  "domain": "sales",

  "table_key": "FORMS4_4",
  "query_type": "simple_filter",
  "capabilities": { "simple_filter": true, "aggregate": true }
}
```

---

## 統計

| 類型 | 數量 |
|------|------|
| Core Tables（4 個場景） | 11 |
| Basic Tables（2 個場景） | 3 |
| **總計** | **14 tables** |

---

## 下一步

確認設計後，再進行代碼實作
