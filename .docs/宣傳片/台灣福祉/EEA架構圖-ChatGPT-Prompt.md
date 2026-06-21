---
lastUpdate: 2026-06-16
author: Sisyphus
---

# EEA AIBox 總覽架構圖 — ChatGPT/DALL-E Prompt

請直接複製以下 prompt 到 ChatGPT，讓它生成架構圖（DALL-E 3）。

---

## Prompt 1：EEA 整體架構圖（英文，效果較好）

```
Create a professional enterprise AI platform architecture diagram in a clean, dark navy and graphite color scheme with electric blue accents.

Title: "Edges Enterprise AI (EEA) — AIBox 平台架構"

The architecture should show 6 horizontal layers from bottom to top, connected by vertical data flow arrows:

=== LAYER 6 (TOP) — AI SERVICES LAYER ===
- AI 艾企助手 (AIQ Assistant) — Context-aware side assistant
- AITask Service — AI Task Orchestration
- MCP Tools — External Tool Integration
- BPA Agents — Business Process Automation

=== LAYER 5 — INTELLIGENT AGENT LAYER ===
- 預測中心 (Forecasting) — Demand/Price/Risk
- 異常偵測 (Anomaly Detection) — Cross-dimensional
- 決策建議 (Decision Engine) — TCO/Alternatives
- 自動溝通 (Auto Communication) — LINE/Email
- 跨系統串聯 (Cross-system) — Full Chain

=== LAYER 4 — KNOWLEDGE & DATA LAYER ===
- GraphRAG Knowledge Graph (Ontology: Domain/Major/Basic)
- Data Graph — Ragic Integration
- Enterprise Memory (海馬體)
- Vector Database (Qdrant)

=== LAYER 3 — AI MODEL LAYER ===
- Cloud LLMs (GPT / Gemini) — Left side, for general reasoning
- Private Local 30B+ Model — Right side, for sensitive data
- Hybrid Model Gateway switching between them
- Label: "Bounded Reasoning — 有邊界的推理"

=== LAYER 2 — DATA INFRASTRUCTURE ===
- ArangoDB — Document/Graph Database
- DuckDB — SQL-on-Parquet Query Engine
- SeaweedFS — Distributed File Storage
- Ragic — Business Data Tables

=== LAYER 1 (BOTTOM) — COMMUNICATION & ACCESS ===
- LINE / WeChat / DingTalk / WhatsApp
- Tauri Desktop App (React + Rust)
- REST API Gateway (Port 6500)
- WebSocket / SSE

On the right side, add a vertical bar titled "安全邊界 (Security Boundary)" spanning all layers, showing:
- Data Isolation
- Role-based Access Control
- On-premise Processing
- Audit Trail

Bottom of the diagram should have the EEA Logo and tagline: "降本·增效·提質·創收·固安"

Style: Clean corporate infographic, dark background (#1a1a2e to #16213e gradient), cyan (#00d4ff) and electric blue (#0066ff) accents, white text labels, subtle grid background, professional and not cartoonish.

Format: Generate as a clean architectural diagram suitable for presentation slides.
```

---

## Prompt 2：智能體中心概念圖（中文，用於頁面 Header）

```
生成一張企業 AI 智能體中心的概念圖，視覺風格為深色科技風，深藍與石墨色調。

畫面中心是一個發光的立方體/中樞，代表「智能體中心 (Agent Center)」。
圍繞中樞漂浮著 6 個不同顏色和圖示的模組，代表不同部門的智能體：
1. 預測中心 — 圖表/趨勢 icon（青色）
2. 異常偵測 — 警示/雷達 icon（琥珀色）
3. 自然語言查詢 — 對話框 icon（綠色）
4. 決策建議 — 輕重/方案 icon（金色）
5. 自動溝通 — 訊息/LINE icon（紫色）
6. 跨系統串聯 — 節點/鏈條 icon（電藍色）

每個模組之間有發光的連線，表示資料和任務流動。
背景隱約可見企業資料圖譜的節點網路。

風格：高階企業科技品牌、電影級打光、體積光效果、乾淨構圖。
不要卡通風格、不要遊戲風格、不要加密貨幣風格。
```

---

## Prompt 3：知識圖譜 + 思維轉變概念圖

```
生成一張企業「知識圖譜 (Knowledge Graph)」的抽象視覺圖，用於展現 AI 導入中思維轉變比工具更重要的理念。

視覺分為兩部分：

左半邊（舊思維）：灰色的傳統文件架構 — 文件堆疊、資料孤島、ISO 文件靜止不動，壓抑的構圖。

右半邊（新思維）：發光的知識節點網路，以「密納瓦思考 (Minerva Thinking)」為核心，從文件節點延伸出：
- 業務問題提出 (Business Problem Discovery)
- 管理思維轉變 (Management Mindset Shift)
- AI 顧問協作分工 (AI Consultant Collaboration)

中央有一條從左到右的過渡弧線，象徵「從文件管理到思維進化」。

節點顏色：從灰轉為青藍色和金色，代表從靜態到動態。

風格：高階企業品牌影片風格、深色背景、體積光、乾淨優雅。
```

---

## 使用建議

1. **先跑 Prompt 1** 生成主架構圖 → 放到 EEA AIBox 總覽頁面 Header 區
2. **Prompt 2** 生成智能體中心的概念裝飾圖 → 放在智能體中心頁面頂部
3. **Prompt 3** 生成知識圖譜的思維轉變圖 → 放在知識圖譜頁面

> 💡 如果生成結果不理想，可以加「infographic diagram style」「flat design」「2D architectural diagram」等關鍵詞讓它更接近資訊圖表而非藝術畫。
