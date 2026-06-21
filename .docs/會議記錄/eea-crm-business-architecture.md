# EEA-CRM 業務架構圖

```mermaid
flowchart LR
    %% 樣式設定
    classDef source fill:#E8F5E9,stroke:#4CAF50,stroke-width:2px
    classDef actor fill:#FFF3E0,stroke:#FF9800,stroke-width:2px
    classDef core fill:#E3F2FD,stroke:#2196F3,stroke-width:2px
    classDef output fill:#F3E5F5,stroke:#9C27B0,stroke-width:2px
    classDef erp fill:#FFEBEE,stroke:#F44336,stroke-width:2px

    subgraph 業務角色
        SALES[🧑‍💼 業務人員]
        CUSTOMER[👥 客戶 / 機構]
    end

    subgraph 資料來源
        LINE[💬 LINE 即時對話<br/>業務與客戶的溝通記錄]
        ACTIVITY[📋 業務活動記錄<br/>實體拜訪・電話通話・備忘錄]
        ERP[Ragic ERP 客戶表單]
        
        subgraph ERP表單
            Q[📄 報價單]
            S[🚚 出貨單]
            R[↩️ 退貨單]
            C[⚠️ 客訴單]
        end
    end

    TIMELINE[📊 客戶 Timeline<br/>所有客戶互動的統一時間軸]

    subgraph 業務應用
        MAP[🗺️ 客戶地圖<br/>地理視角掌握客戶分佈]
        AGENT[🤖 AI Agent 助手<br/>頁面感知的智能輔助]
        DASHBOARD[📈 績效 Dashboard<br/>業務看板數位化]
    end

    %% 業務角色之間的互動
    SALES <-->|LINE 溝通| LINE
    SALES -->|記錄| ACTIVITY
    SALES -->|操作| ERP

    %% 資料流向 Timeline
    LINE --> TIMELINE
    ACTIVITY --> TIMELINE
    ERP --> TIMELINE
    Q --> ERP
    S --> ERP
    R --> ERP
    C --> ERP

    %% Timeline 流向業務應用
    TIMELINE --> MAP
    TIMELINE --> AGENT
    TIMELINE --> DASHBOARD

    %% 業務應用回饋給業務人員
    MAP -.->|視覺化呈現| SALES
    AGENT -.->|智能建議| SALES
    DASHBOARD -.->|績效追蹤| SALES

    %% 套用樣式
    class SALES,CUSTOMER actor
    class LINE,ACTIVITY source
    class ERP,Q,S,R,C erp
    class TIMELINE core
    class MAP,AGENT,DASHBOARD output
```

---

## 業務架構說明

### 資料來源（左側）

| 來源 | 內容 | 說明 |
|------|------|------|
| **💬 LINE 即時對話** | 業務人員與客戶/機構的 LINE 對話記錄 | 自動歸檔，形成溝通歷程 |
| **📋 業務活動記錄** | 業務人員自行記錄的客戶互動（實體拜訪、電話通話、備忘錄） | 補充 LINE 以外的互動 |
| **📄 Ragic ERP 表單** | 報價單、出貨單、退貨單、客訴單等客戶相關單據 | 客戶交易的正式記錄 |

### 核心機制（中間）

- **客戶 Timeline**：將上述三大資料來源彙整為統一的客戶互動時間軸，從「溝通記錄 → 業務活動 → 交易單據」一目了然

### 業務應用（右側）

| 應用 | 功能 | 使用者價值 |
|------|------|-----------|
| **🗺️ 客戶地圖** | 地理視角呈現客戶分佈、附近查詢、順路拜訪規劃 | 直覺掌握區域客戶狀況 |
| **🤖 AI Agent 助手** | 頁面感知的智能輔助，根據當前頁面推薦對應 Agent | 減少操作路徑，提升效率 |
| **📈 績效 Dashboard** | 業務看板數位化，即時掌握營收、業績排行與趨勢 | 數據驅動的業務管理 |
