---
lastUpdate: 2026-04-24 13:22:28
author: Hephaestus
version: 1.0.0
---

# EEA 宣傳片 AI 鏡頭生成 Prompt v1

## 修改歷程

| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| 2026-04-24 | 1.0.0 | Hephaestus | 將 EEA-宣傳片-畫面表-v1.md 轉為 AI 影片生成 prompt |

## 使用方式

本文件是將原本的錄製畫面表，轉成可交給 AI 影片生成工具的 prompt。
每個 prompt 都已內含：

- 場景主體
- 視覺風格關鍵詞
- 鏡頭運動
- 時長建議
- 用途說明

建議搭配 `.docs/宣傳片/EEA-Seedance片段生成建議.md` 裡的**統一風格設定**使用。

---

## 統一 Base Prompt（每個鏡頭都加這段）

```
premium enterprise technology brand film, cinematic, futuristic but grounded, dark navy and graphite color palette, cyan and electric blue accents, elegant motion, volumetric light, clean composition, high-end corporate aesthetic, realistic, sophisticated, no cartoon, no gaming style, no crypto style, no cheesy effects
```

## 統一 Negative Prompt

```
cartoon, anime, low quality, oversaturated, gaming UI, cyberpunk city overload, crypto ad style, cheesy sci-fi, cluttered composition, childish, flat lighting, low detail, distorted hands, broken screens, random text, watermark
```

---

## 鏡頭 1｜企業工作混亂開場

### 基本資訊

| 項目 | 內容 |
|------|------|
| 時間碼 | 0:00–0:30 |
| 用途 | 建立企業工作混亂感 |
| 建議時長 | 6–8 秒 |
| 重要程度 | 核心开场鏡頭 |

### AI 影片生成 Prompt

```text
A cinematic overhead desk view of a professional office workspace overwhelmed by chaos, multiple floating digital windows, spreadsheets, chat message popups, document tabs, business dashboards, notification badges, a person frantically switching between screens, dragging mouse across fragmented interfaces, subtle stress and tension in movement, slow but purposeful camera push forward, premium enterprise technology brand film style, dark navy and graphite palette, cyan notification glows, realistic, high-end corporate aesthetic

Negative: cartoon, anime, gaming style, oversaturated, low quality, text overlays
```

### 用途說明

這支鏡頭是全片第一個畫面，用來讓觀眾馬上感受到「現有企業工作方式的混亂與壓力」。AI 生成後，建議你再補一段自己錄的：使用者在 AI 輸入框前停頓、打字又刪掉的畫面，疊在 AI 生成的抽象混亂畫面上。

---

## 鏡頭 2｜資料分散、知識斷裂

### 基本資訊

| 項目 | 內容 |
|------|------|
| 時間碼 | 0:30–1:00 |
| 用途 | 強化資料分散、知識斷裂的無力感 |
| 建議時長 | 5–7 秒 |
| 重要程度 | 高 |

### AI 影片生成 Prompt

```text
A cinematic split-screen montage of different office workers in separate locations, each struggling with fragmented information, one looking at a spreadsheet while receiving a chat message asking the same question, a manager reviewing printed reports while others ask for updates, information disconnected across people and systems, elegant but stressed motion, shallow depth of field, premium enterprise technology brand film, dark blue-gray corporate tone, subtle warm lamp light, realistic professional Asian business environment
```

### 用途說明

如果 AI 生成的人物畫面太假或太像庫存素材，這段果斷放棄，改用你自己錄的：主管看著多個系統、同一問題在聊天軟體來回三四次的畫面。重點是「問題沒有被解決」的感覺。

---

## 鏡頭 3｜AI 很強但企業不敢交給它

### 基本資訊

| 項目 | 內容 |
|------|------|
| 時間碼 | 1:00–1:30 |
| 用途 | 呈現一般 AI 的企業風險感 |
| 建議時長 | 5–7 秒 |
| 重要程度 | 高 |

### AI 影片生成 Prompt

```text
A powerful glowing AI neural network visualization facing a protected enterprise data zone, a translucent holographic barrier separating intelligent cloud reasoning from confidential business documents and financial data, an AI response panel showing confident answers while red warning indicators pulse nearby, elegant tension between capability and risk, premium enterprise technology brand film, dark navy background, cyan AI glow contrasting with amber-red security warnings, cinematic, volumetric light
```

### 用途說明

這支鏡頭建議純用 AI 生成，用它的抽象感來講「AI 能力很強，但企業不敢把資料交給它」。不要用真實產品介面，否則會變成功能介紹。

---

## 鏡頭 4｜有邊界概念引出

### 基本資訊

| 項目 | 內容 |
|------|------|
| 時間碼 | 1:30–2:00 |
| 用途 | 從混亂引出「有邊界」的必要性 |
| 建議時長 | 5–7 秒 |
| 重要程度 | 高 |

### AI 影片生成 Prompt

```text
Multiple scattered floating AI tool icons and application windows gradually being drawn toward and contained within a precise glowing enterprise boundary, elegant convergence, secure perimeter line forming around intelligent tools, a clean elegant division between uncontrolled AI chaos and managed enterprise AI, premium enterprise technology brand film, dark graphite background, cyan secure boundary line, electric blue containment, cinematic, slow-motion particles
```

### 用途說明

這段是全片第一個「解答」鏡頭。用 AI 生成「工具被邊界包住」的畫面，暗示「EEA 讓一切有秩序」。這段幾乎完全靠 AI 生成，你的錄影素材不一定要用。

---

## 鏡頭 5｜EEA 正式登場

### 基本資訊

| 項目 | 內容 |
|------|------|
| 時間碼 | 2:00–2:30 |
| 用途 | EEA 品牌正式出场 |
| 建議時長 | 6–8 秒 |
| 重要程度 | 核心鏡頭 |

### AI 影片生成 Prompt

```text
A central enterprise AI platform core emerging from darkness with a powerful symmetrical brand reveal, layered architecture unfolding outward in clean layers, cloud reasoning layer on top, local knowledge and data layers below, tools and agents at the base, professional workflow orchestration below, elegant central composition, premium enterprise technology brand film, dark navy and graphite palette, electric blue structural lines, volumetric light from within, cinematic, majestic but controlled reveal
```

### 用途說明

這是全片最重要的品牌鏡頭。建議用 AI 生成整體氛圍與架構感，Logo 與品牌字卡在後製時再加上。如果你的 EEA 產品已有很不錯的首頁/總覽畫面，也可以把 AI 生成版當襯底，前面蓋上真實產品畫面。

---

## 鏡頭 6｜EEA 分層架構

### 基本資訊

| 項目 | 內容 |
|------|------|
| 時間碼 | 2:30–3:00 |
| 用途 | 表現 EEA 分層架構與邊界設計 |
| 建議時長 | 5–7 秒 |
| 重要程度 | 中 |

### AI 影片生成 Prompt

```text
An elegant exploded-view diagram of enterprise AI platform architecture, layered horizontal bands separating cloud intelligence from local knowledge, business data, enterprise tools, intelligent agents, and workflow orchestration, data flow streams moving between layers, glowing boundary lines, premium enterprise technology visualization, dark navy background, cyan and electric blue flow lines, graphite structural elements, cinematic overhead camera pull-back, clean high-end composition
```

### 用途說明

這段純用 AI 生成。用它的抽象圖解感，讓觀眾快速了解 EEA 是「分層、有邊界、可協作」的系統。真實產品 UI 可能在這段不需要出現。

---

## 鏡頭 7｜文件變成知識資產

### 基本資訊

| 項目 | 內容 |
|------|------|
| 時間碼 | 3:00–3:30 |
| 用途 | 知識不再是文件堆疊，而是可理解的資產 |
| 建議時長 | 5–7 秒 |
| 重要程度 | 高 |

### AI 影片生成 Prompt

```text
Business documents and reports dissolving into structured knowledge nodes, paragraphs and tables separating into semantic clusters, clean ontology tree forming, knowledge graph connections growing between related concepts, premium enterprise AI visualization, dark navy background, cyan knowledge nodes and semantic links, elegant particle transformation, slow-motion cinematic, high-end corporate technology aesthetic
```

### 用途說明

這段要接你錄的 EEA 知識庫上傳畫面。AI 生成版用來製造「文件被理解」的魔法感，真實產品畫面用來證明「真的有這個功能」。兩段一起用，就同時有了情感說服力和產品證據。

---

## 鏡頭 8｜Ontology 與知識圖譜展開

### 基本資訊

| 項目 | 內容 |
|------|------|
| 時間碼 | 3:30–4:00 |
| 用途 | 呈現 ontology 三層結構與知識圖譜 |
| 建議時長 | 5–7 秒 |
| 重要程度 | 中 |

### AI 影片生成 Prompt

```text
A sophisticated three-layer ontology tree expanding in space, domain level at top, major level in middle, basic level at base, each node glowing and connecting to others with elegant semantic lines, knowledge graph transforming from flat list into spatial interconnected structure, premium enterprise AI brand film, dark navy and graphite, cyan luminous nodes, electric blue semantic connection lines, cinematic slow camera orbit around the graph, elegant and precise
```

### 用途說明

接你的 ontology UI 錄影。AI 生成版給「知識被結構化」的高級感，真實 UI 給觀眾「這個系統真的存在」的可信度。

---

## 鏡頭 9｜知識持續成長

### 基本資訊

| 項目 | 內容 |
|------|------|
| 時間碼 | 4:00–4:30 |
| 用途 | 表現知識系統會跟著企業使用而成長 |
| 建議時長 | 5–7 秒 |
| 重要程度 | 中 |

### AI 影片生成 Prompt

```text
A living knowledge ecosystem visualization, knowledge nodes gradually accumulating and glowing brighter over time, new connections forming between existing nodes, an enterprise knowledge base growing organically, subtle pulsing light, premium enterprise AI brand film, dark navy background, cyan growing nodes, electric blue expanding connections, elegant time-lapse feel, cinematic, realistic high-end technology aesthetic
```

### 用途說明

這段純 AI 生成，用來表達「EEA 的知識庫不是死的，會跟著企業一起成長」。如果你的產品介面有「知識持續新增」的畫面也可以補上去。

---

## 鏡頭 10｜資料表轉成關聯圖譜

### 基本資訊

| 項目 | 內容 |
|------|------|
| 時間碼 | 4:30–5:00 |
| 用途 | 把 Ragic 資料表提升為企業資料圖譜 |
| 建議時長 | 5–7 秒 |
| 重要程度 | 高 |

### AI 影片生成 Prompt

```text
Enterprise data tables transforming into a connected business relationship graph, spreadsheet rows becoming nodes, column headers becoming connection categories, cross-table relationships forming elegant luminous links, supply chain and inventory data becoming a spatial business intelligence network, premium enterprise technology visualization, dark graphite background, cyan data nodes, electric blue relational lines, cinematic transformation sequence, realistic corporate aesthetic
```

### 用途說明

接你錄的 Ragic 表格畫面。AI 版給「表格之間的關係被看見」的驚艷感，真實 UI 給「這是我們企業的實際資料」的真實感。

---

## 鏡頭 11｜批次追溯與退貨追查

### 基本資訊

| 項目 | 內容 |
|------|------|
| 時間碼 | 5:00–5:30 |
| 用途 | 拍出資料可追溯的能力 |
| 建議時長 | 6–8 秒 |
| 重要程度 | 高 |

### AI 影片生成 Prompt

```text
A cinematic enterprise traceability visualization, one returned product node triggering an elegant investigation path glowing outward, upstream connections lighting up to production batches, suppliers, machines, operators, downstream connections lighting up to current inventory, shipped quantities, affected customers, clean enterprise graph traversal, premium corporate technology brand film, dark navy, cyan investigation paths, electric blue connection nodes, slow-motion elegant data flow
```

### 用途說明

這段是全片最有說服力的產品價值鏡頭之一。AI 生成版做出「一筆異常帶出整條供應鏈」的戲劇感，你的 Ragic 實際查詢操作錄影用來證明「真的可以這樣查」。

---

## 鏡頭 12｜智能體與工具角色分工

### 基本資訊

| 項目 | 內容 |
|------|------|
| 時間碼 | 5:30–6:00 |
| 用途 | 表現工具是無狀態、專一責任的；智能體是協調者 |
| 建議時長 | 5–7 秒 |
| 重要程度 | 高 |

### AI 影片生成 Prompt

```text
Multiple enterprise tool modules orbiting an intelligent central agent coordinator, each tool appearing as a distinct modular icon, being activated selectively by the agent, elegant task coordination sequence, tools lighting up one by one as tasks are assigned, premium enterprise automation brand film, dark navy background, cyan tool modules, electric blue agent core, cinematic orbit camera, clean high-end technology aesthetic
```

### 用途說明

接你錄的 agent marketplace / tool marketplace 畫面。AI 版做出「工具被智能體調度」的系統感，真實 UI 給「真的有這些工具」的可信度。

---

## 鏡頭 13｜PDCA 工作編排

### 基本資訊

| 項目 | 內容 |
|------|------|
| 時間碼 | 6:00–6:30 |
| 用途 | 呈現任務不是回答問題，而是被推進與驗證 |
| 建議時長 | 5–7 秒 |
| 重要程度 | 中 |

### AI 影片生成 Prompt

```text
An elegant enterprise workflow orchestration sequence, task nodes connecting through plan do check act phases, intelligent verification loops glowing as tasks are validated, workflow status transitioning from pending to active to verified, premium enterprise automation brand film, dark graphite and navy palette, cyan process nodes, electric blue verification links, cinematic sequential activation, clean professional corporate technology aesthetic
```

### 用途說明

這段適合純 AI 生成，用來表達「EEA 的工作能力是有流程、有驗證、可追溯的」。如果你有 workflow 操作錄影，可以補在後面當佐證。

---

## 鏡頭 14｜艾企助手跟隨情境

### 基本資訊

| 項目 | 內容 |
|------|------|
| 時間碼 | 6:30–7:00 |
| 用途 | AIQ 助手不是等 prompt，而是跟著使用者操作脈絡 |
| 建議時長 | 5–7 秒 |
| 重要程度 | 高 |

### AI 影片生成 Prompt

```text
A professional user working at a modern enterprise software interface, a subtle intelligent AI assistant overlay appearing contextually beside the active screen section, adaptive AI support adapting to the user's current workflow context, gentle glowing assistant indicator following the user's focus point, premium enterprise human-AI collaboration brand film, dark office environment, cyan AI assistant glow, realistic professional workspace, elegant contextual appearance, cinematic
```

### 用途說明

接你錄的浮動助手操作畫面。AI 生成版給「AI 像個聰明同事一直在旁邊」的溫暖感，真實 UI 給「這個功能真的存在」的可信度。

---

## 鏡頭 15｜從混亂到秩序的轉場

### 基本資訊

| 項目 | 內容 |
|------|------|
| 時間碼 | 7:00–7:30 |
| 用途 | 從前面的順暢感，帶到全面整合的企業智慧 |
| 建議時長 | 5–7 秒 |
| 重要程度 | 中 |

### AI 影片生成 Prompt

```text
A visual transformation sequence from fragmented enterprise chaos to a unified intelligent system, scattered data nodes and workflow fragments converging into one clean integrated enterprise intelligence network, elegance and order emerging from complexity, premium enterprise technology brand film, dark navy and graphite, cyan integration lines, electric blue convergence effect, cinematic slow-motion, sophisticated high-end corporate aesthetic
```

### 用途說明

這段是情緒轉換點，用 AI 生成的抽象畫面讓觀眾感受到「從混亂到秩序」的釋放感。可以疊在你錄的使用者流暢操作畫面上。

---

## 鏡頭 16｜品牌收尾主視覺

### 基本資訊

| 項目 | 內容 |
|------|------|
| 時間碼 | 7:30–8:00 |
| 用途 | 全系統收束成 EEA 品牌核心，停留給 Logo 與標語 |
| 建議時長 | 6–8 秒 |
| 重要程度 | 核心鏡頭 |

### AI 影片生成 Prompt

```text
A complete enterprise intelligence network converging into a single powerful branded core, knowledge nodes, data graphs, workflow streams, tool modules, and agent systems all flowing toward and absorbed into the central EEA brand emblem, calm confident final composition, premium enterprise technology brand film, dark navy and graphite, electric blue accents, clean elegant convergence, cinematic slow pull-back, sophisticated corporate finale
```

### 用途說明

這是全片最後一個鏡頭。AI 生成版的襯底給「所有能力整合成一」的力量感，Logo、標語「Slogan」在後製時蓋上去。建議最後留 2 秒乾淨的 Logo 靜止，讓觀眾有時間吸收。

---

## 快速對照表

| 鏡頭 | 時長 | AI 生成 | 實錄補充 | 核心程度 |
|------|------|--------|------|------|
| 1 企業混亂 | 6–8s | ✅ | ✅ 建議補 | 核心 |
| 2 知識斷裂 | 5–7s | ✅ 可選 | ✅ 建議補 | 高 |
| 3 AI 風險感 | 5–7s | ✅ 純AI | ❌ | 高 |
| 4 有邊界概念 | 5–7s | ✅ 純AI | ❌ | 高 |
| 5 EEA 出場 | 6–8s | ✅ | ✅ 建議補 | 核心 |
| 6 分層架構 | 5–7s | ✅ 純AI | ❌ | 中 |
| 7 文件理解 | 5–7s | ✅ | ✅ 建議補 | 高 |
| 8 知識圖譜 | 5–7s | ✅ | ✅ 建議補 | 中 |
| 9 知識成長 | 5–7s | ✅ 純AI | ❌ | 中 |
| 10 資料圖譜 | 5–7s | ✅ | ✅ 建議補 | 高 |
| 11 批次追溯 | 6–8s | ✅ | ✅ 建議補 | 高 |
| 12 智能體協作 | 5–7s | ✅ | ✅ 建議補 | 高 |
| 13 PDCA 編排 | 5–7s | ✅ 純AI | ❌ | 中 |
| 14 助手情境 | 5–7s | ✅ | ✅ 建議補 | 高 |
| 15 混沌到秩序 | 5–7s | ✅ 純AI | ❌ | 中 |
| 16 品牌收尾 | 6–8s | ✅ | ✅ 建議補 | 核心 |

---

## 使用建議

### 第一步

先把這 16 支 AI 生成 prompt 拿去跑，產出 16 支測試片段。

### 第二步

對照你的實錄素材，看看哪些鏡頭：
- AI 版很好 → 直接用
- AI 版太假 → 改用實錄
- AI 版 + 實錄結合 → 疊加

### 第三步

把確定的片段帶進 Filmora 時間軸，按：
**AI 片段（2–3 秒）→ 實錄片段（3–6 秒）→ 字卡（1 秒）**
的節奏組裝。

---

## 與其他文件的對應關係

- 原始分鏡腳本：`.docs/宣傳片/EEA-宣傳片腳本-v1.md`
- 錄製畫面表：`.docs/宣傳片/EEA-宣傳片-畫面表-v1.md`
- 統一風格設定：`.docs/宣傳片/EEA-Seedance片段生成建議.md`
