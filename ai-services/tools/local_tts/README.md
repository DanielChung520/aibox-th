---
lastUpdate: 2026-04-25 16:25:01
author: Hephaestus
version: 1.0.0
---

# Local TTS Tool

## 修改歷程
| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| 2026-04-25 | 1.0.0 | Hephaestus | 建立 CLI-first 本地中文 TTS 工具，支援 ChatTTS、逐字稿切段與多聲線樣本 |

## 定位

這個工具先以 **CLI 優先** 的方式落地，目的是：

1. 先驗證本地中文 TTS 的聲音品質
2. 先驗證逐字稿切段、停頓與輸出流程
3. 保留 `BaseTool` 介面，未來可再掛入 `shared/tools/` 或 API 路由

## 技術線建議

### 第一階段：CLI

- 最快驗證模型品質
- 最快試跑聲線樣本
- 最適合宣傳片逐字稿這種批次輸出場景

### 第二階段：專案工具

- 將 `LocalTTSTool` 註冊到專案工具框架
- 由 agent / workflow 直接呼叫

目前已整合進 `shared/tools` 的 builtin tool，工具名稱為 `local_tts`。

### 第三階段：API / UI

- 若內部使用穩定，再包成 API 或前端頁面
- 前端再處理聲線選擇、試聽、下載、儲存等功能

## 安裝

### 1. 啟用 Python 環境

```bash
cd /Users/daniel/GitHub/AIBox/ai-services
source .venv/bin/activate
```

### 2. 安裝本地 TTS 依賴

```bash
pip install -r requirements-local-tts.txt
export PYTORCH_ENABLE_MPS_FALLBACK=1
```

> macOS 上建議保留 `PYTORCH_ENABLE_MPS_FALLBACK=1`，避免某些運算在 Apple MPS 下失敗。

## 使用方式

### 透過 shared/tools 調用

當 `ToolRegistry` 初始化完成後，agent 可直接呼叫 builtin tool：

```python
from shared.tools import ToolExecutionContext, ToolRegistry
import uuid

registry = ToolRegistry()
await registry.initialize(
    mcp_tools_url="http://localhost:8004",
    data_agent_url="http://localhost:8011/da",
    knowledge_agent_url="http://localhost:8007",
)

result = await registry.execute(
    "local_tts",
    {
        "file_path": "/Users/daniel/GitHub/AIBox/.docs/宣傳片/文字稿-8分鐘版.md",
        "output_path": "/Users/daniel/GitHub/AIBox/ai-services/.tmp/tts/eea-8min.wav",
        "voice_seed": 23,
    },
    ToolExecutionContext(
        user_id="demo-user",
        session_id="demo-session",
        trace_id=f"demo-{uuid.uuid4().hex[:8]}",
        auth_token="",
        correlation_id="local-tts-001",
    ),
)
```

> 若未提供 `output_path`，builtin executor 會預設輸出到 `ai-services/.tmp/tts/`。

### 產生單一旁白音檔

```bash
python -m tools.local_tts.cli synthesize \
  --input "/Users/daniel/GitHub/AIBox/.docs/宣傳片/文字稿-8分鐘版.md" \
  --output "/Users/daniel/GitHub/AIBox/ai-services/.tmp/tts/eea-8min.wav" \
  --voice-seed 23
```

### 產生多個聲線樣本

```bash
python -m tools.local_tts.cli sample-voices \
  --input "/Users/daniel/GitHub/AIBox/.docs/宣傳片/文字稿-8分鐘版.md" \
  --output-dir "/Users/daniel/GitHub/AIBox/ai-services/.tmp/tts/samples" \
  --seeds 11,23,47,89
```

## 輸入特性

工具會自動：

- 移除 Markdown frontmatter
- 忽略 `#` 標題與 `---`
- 忽略 `（全文完）`
- 解析 `[[⏱️1200]]` 這類停頓標記
- 長句過長時自動切段

## 聲音樣本策略

第一版不需要真人錄音。

目前先用 **speaker seed** 產生多個候選聲線，讓你先挑：

- seed 11
- seed 23
- seed 47
- seed 89

等你確認喜歡的聲線，再把固定 seed 寫進工作流即可。

## 風險與限制

### ChatTTS 授權

目前 ChatTTS 比較適合：

- 本地驗證
- PoC
- 內部流程試跑

若要正式商用上線，建議再評估可商用授權的替代模型。

### 長文本穩定性

- 長文本仍建議切段輸出
- 預設每段上限約 180 字

## 下一步

1. 先安裝 `requirements-local-tts.txt`
2. 先跑 `sample-voices`
3. 選出一個你喜歡的 seed
4. 再用該 seed 跑正式宣傳片旁白
