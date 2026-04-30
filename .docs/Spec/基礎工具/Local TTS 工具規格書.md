---
lastUpdate: 2026-04-25 16:25:01
author: Hephaestus
version: 1.0.0
---

# Local TTS 工具規格書

## 修改歷程

| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| 2026-04-25 | 1.0.0 | Hephaestus | 初始版本：定義本地中文 TTS 的 CLI-first 工具化方案、後續 API / Agent 整合方向 |

---

## 1. 概述

Local TTS 是一個面向 AIBox / EEA 專案的**本地中文語音合成工具**，定位為：

1. 將逐字稿、Markdown、文案檔案轉成語音旁白
2. 先以 CLI 驗證音質、停頓、切段與輸出流程
3. 保留 `BaseTool` 介面，未來可整合至 `shared/tools/`、`mcp_tools`、`unified_agents`

此工具主要應用場景包括：

- 宣傳片逐字稿轉旁白
- Agent 回覆轉語音
- 內部工作流通知語音化
- 多聲線樣本試聽與品牌音色選型

---

## 2. 工具定位與技術線

### 2.1 技術線決策

第一階段採用 **CLI-first**，不先做前端頁面。

原因：

- 最快驗證模型與聲音品質
- 最快驗證逐字稿切段與停頓策略
- 最適合宣傳片、長文案、批次旁白輸出
- UI 需求仍未穩定前，避免過早綁死交互形式

### 2.2 分階段規劃

| 階段 | 形式 | 目的 |
|------|------|------|
| Phase 1 | CLI | 先讓本地逐字稿轉 WAV，可快速試跑 |
| Phase 2 | BaseTool | 讓本地 TTS 成為專案內可調用工具 |
| Phase 3 | shared/tools / API | 讓 agent / workflow / Rust Gateway 可調用 |
| Phase 4 | Frontend UI | 提供聲線選擇、試聽、下載、儲存介面 |

---

## 3. 架構設計

```text
逐字稿 / Markdown / 純文字
        │
        ▼
CLI: python -m tools.local_tts.cli
        │
        ▼
LocalTTSTool (BaseTool)
        │
        ▼
ChatTTSProvider
        │
        ├── 切段
        ├── 停頓標記解析 [[⏱️1200]]
        ├── 多 speaker seed 樣本
        └── WAV 輸出
        │
        ▼
ai-services/.tmp/tts/*.wav
```

未來可延伸為：

```text
Frontend / Agent / Workflow
        │
        ▼
Rust API Gateway (6500)
        │
        ▼
unified_agents / mcp_tools
        │
        ▼
LocalTTSTool
```

---

## 4. 模型選型

### 4.1 第一階段模型：ChatTTS

選型理由：

- 中文表現最佳
- 適合宣傳片旁白與口播
- 可本地運行
- 可用 speaker seed 快速生成多個聲線樣本

### 4.2 已知限制

| 項目 | 說明 |
|------|------|
| 商用授權 | ChatTTS 目前不應直接視為正式商用最終方案 |
| 長文本穩定性 | 長文需切段，不建議一次塞整篇 |
| macOS | 建議啟用 `PYTORCH_ENABLE_MPS_FALLBACK=1` |

### 4.3 備選模型

若 ChatTTS 實機效果或授權不符合正式商用需求，後續可評估：

- XTTS / Coqui 類方案
- 可商用授權的本地多語 TTS 模型
- 未來加入 reference audio voice cloning 路線

---

## 5. 功能需求

### 5.1 核心功能

| 功能 | 說明 |
|------|------|
| 文字轉語音 | 讀取 text / txt / md 並輸出 WAV |
| Markdown 清理 | 自動移除 frontmatter、標題、分隔線、全文完 |
| 停頓標記解析 | 解析 `[[⏱️1200]]` 類型標記 |
| 長文切段 | 依字數與標點切段，降低長文本不穩定性 |
| 多聲線樣本 | 透過 speaker seed 產生多個候選聲線 |
| 固定音色 | 指定 voice seed 產生可重現音色 |

### 5.2 第一階段不做

以下能力**不在第一版實作範圍**：

- 前端管理頁面
- 真人 reference audio 聲紋複製
- MP3 轉碼
- SeaweedFS 長期儲存
- 系統參數管理頁面

---

## 6. 目錄結構

```text
ai-services/
├── requirements-local-tts.txt
└── tools/
    ├── __init__.py
    └── local_tts/
        ├── __init__.py
        ├── cli.py
        ├── local_tts_tool.py
        ├── chattts_provider.py
        └── README.md
```

輸出音檔預設建議位置：

```text
ai-services/.tmp/tts/
```

符合 AGENTS.md 對臨時輸出與測試檔案的管理規範。

---

## 7. CLI 規格

### 7.1 synthesize

用途：將逐字稿或文字直接轉成單一 WAV。

```bash
python -m tools.local_tts.cli synthesize \
  --input "/path/to/script.md" \
  --output "/path/to/output.wav" \
  --voice-seed 23
```

#### 參數

| 參數 | 必填 | 說明 |
|------|------|------|
| `--input` | 否 | 輸入檔案路徑 |
| `--text` | 否 | 直接輸入文字 |
| `--output` | 是 | 輸出 WAV 檔案路徑 |
| `--voice-seed` | 否 | 固定音色 seed |
| `--pause-ms` | 否 | 預設段落間停頓 |
| `--max-chars` | 否 | 單段最大字數 |

### 7.2 sample-voices

用途：同一段文字輸出多個聲線樣本。

```bash
python -m tools.local_tts.cli sample-voices \
  --input "/path/to/script.md" \
  --output-dir "/path/to/samples" \
  --seeds 11,23,47,89
```

#### 參數

| 參數 | 必填 | 說明 |
|------|------|------|
| `--input` | 否 | 輸入檔案路徑 |
| `--text` | 否 | 直接輸入文字 |
| `--output-dir` | 是 | 樣本輸出目錄 |
| `--seeds` | 否 | 逗號分隔的聲線 seed |
| `--pause-ms` | 否 | 預設段落間停頓 |
| `--max-chars` | 否 | 單段最大字數 |

---

## 8. Tool 介面規格

### 8.1 Input Model

```python
class LocalTTSInput(ToolInput):
    text: str | None
    file_path: str | None
    output_path: str
    voice_seed: int | None
    sample_voices: bool
    sample_text: str | None
    voice_seeds: list[int]
    paragraph_pause_ms: int
    max_chars_per_chunk: int
```

### 8.2 Output Model

```python
class LocalTTSOutput(ToolOutput):
    provider: str
    sample_rate: int
    segment_count: int
    files: list[GeneratedAudioFile]
    mode: str
```

---

## 9. 聲線樣本策略

第一版不依賴真人錄音。

改用 **speaker seed** 作為音色選擇方式：

| Seed | 用途 |
|------|------|
| 11 | 樣本 1 |
| 23 | 樣本 2 |
| 47 | 樣本 3 |
| 89 | 樣本 4 |

流程：

1. 先輸出多個聲線樣本
2. 人工挑選一個喜歡的聲線
3. 將該 seed 固定在正式旁白工作流中

此策略比一開始就做 voice cloning 更穩、更快，也更容易驗證。

---

## 10. 輸入處理規則

工具需支援以下文字清理規則：

- 移除 YAML frontmatter
- 忽略 Markdown 標題 `#`
- 忽略分隔線 `---`
- 忽略 `（全文完）`
- 解析 `[[⏱️1200]]` 為靜音停頓
- 長句依標點與最大字數切段

---

## 11. 驗證策略

### 11.1 第一階段驗證

| 驗證項目 | 方式 |
|------|------|
| CLI 可執行 | `python -m tools.local_tts.cli --help` |
| import 正常 | `python -c "from tools.local_tts import LocalTTSTool"` |
| 聲線樣本模式 | `sample-voices` 產出多個 wav |
| 單檔輸出模式 | `synthesize` 產出單一 wav |
| 逐字稿清理 | 使用現有宣傳片 md 驗證 |

### 11.2 第二階段驗證

待模型安裝後補做：

- 實際音質驗證
- seed 可重現性驗證
- 長文穩定性驗證

---

## 12. 未來整合方向

### 12.1 shared/tools

將 `LocalTTSTool` 註冊進 `shared/tools/registry.py`，讓 agent 可直接調用。

### 12.2 API

未來可新增：

| 方法 | 路徑 | 用途 |
|------|------|------|
| POST | `/tools/local-tts/synthesize` | 產生單一語音 |
| POST | `/tools/local-tts/sample-voices` | 產生多聲線樣本 |

### 12.3 儲存

正式版若需長期保存：

- 先輸出到 `ai-services/.tmp/tts/`
- 再透過 SeaweedFS 上傳

---

## 13. 風險與注意事項

| 風險 | 說明 |
|------|------|
| 授權 | ChatTTS 不應直接默認為正式商用最終模型 |
| 模型穩定性 | 長文仍可能有不自然片段 |
| 效能 | macOS MPS 可能 fallback 到 CPU，生成較慢 |
| 音色一致性 | 不同 seed 雖可重現，但不等於品牌級 voice clone |

---

## 14. 實施結論

Local TTS 應先走 **CLI-first + Tool-ready** 路線：

- 先做本地可跑 CLI
- 同時實作 `BaseTool` 介面
- 等聲音品質與流程驗證完成，再往 API / agent / UI 擴展

這條路線最符合目前專案節奏，也能避免過早投入前端與平台整合成本。
