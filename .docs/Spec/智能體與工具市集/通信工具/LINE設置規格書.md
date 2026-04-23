---
lastUpdate: 2026-04-19 01:41:15
author: Daniel Chung
version: 1.0.0
---

# LINE 智能機器人設置規格書

## 1. 概述

本文檔定義在「工具市集」中建立和管理 LINE 智能機器人的設置規格。

### 1.1 LINE 架構對應

根據 LINE 官方文件，一個 LINE Provider 可擁有多個 Messaging API Channels：

```
LINE Provider (組織/公司)
│
├── Channel 1 (例：客服Bot)
│   ├── Channel ID: 2001234xxx
│   ├── Channel Secret: xxx
│   ├── Channel Access Token: xxx
│   └── Webhook URL: https://api.aibox.com/webhook/line/christcoffee
│
├── Channel 2 (例：採購Bot)
│   ├── Channel ID: 2005678xxx
│   ├── Channel Secret: xxx
│   ├── Channel Access Token: xxx
│   └── Webhook URL: https://api.aibox.com/webhook/line/danlinepv
│
└── Channel 3 (例：庫存Bot)
    └── ...
```

### 1.2 系統資料模型

```typescript
/**
 * @file        LINE 智能機器人資料模型
 * @description LINE 官方帳號與 Channel 的層次化設定結構
 * @lastUpdate  2026-04-19 01:41:15
 * @author      Daniel Chung
 * @version     1.0.0
 */

export interface LINEOfficialAccount {
  /** 官方帳號唯一識別鍵 */
  _key: string;
  
  /** 所屬 Provider 名稱 */
  provider_name: string;
  
  /** 官方帳號名稱（顯示用） */
  name: string;
  
  /** 狀態 */
  status: 'active' | 'inactive' | 'error';
  
  /** 建立時間 */
  created_at: string;
  
  /** 最後更新時間 */
  updated_at: string;
  
  /** 關聯的 Channels */
  channels: LINEChannel[];
}

export interface LINEChannel {
  /** Channel 唯一識別鍵 */
  _key: string;
  
  /** 所属官方帳號的 key */
  official_account_key: string;
  
  /** Channel 名稱（需與 LINE Developers Console 一致） */
  channel_name: string;
  
  /** LINE Channel ID（格式：200xxxxxxx） */
  channel_id: string;
  
  /** LINE Channel Secret */
  channel_secret: string;
  
  /** Channel Access Token (Long-lived) */
  channel_access_token: string;
  
  /** Webhook URL（此系統自動生成） */
  webhook_url: string;
  
  /** 是否啟用 Webhook */
  webhook_enabled: boolean;
  
  /** Bot User ID（用於識別官方帳號） */
  bot_user_id: string;
  
  /** 發布狀態 */
  publication_status: 'unpublished' | 'published' | 'error';
  
  /** 最後連線時間 */
  last_connected_at: string | null;
  
  /** 建立時間 */
  created_at: string;
}

export interface LINEChannelConfig {
  /** LINE Channel ID */
  channel_id: string;
  
  /** LINE Channel Secret */
  channel_secret: string;
  
  /** Channel Access Token（Long-lived） */
  channel_access_token: string;
  
  /** Provider 名稱 */
  provider_name: string;
  
  /** Channel 名稱 */
  channel_name: string;
}
```

---

## 2. 頁面架構

### 2.1 路由設計

```
路徑：/platforms/line
```

### 2.2 頁面佈局

```
┌─────────────────────────────────────────────────────────────────────┐
│  頁面標題：LINE 智能機器人                                          │
│  ----------------------------------------------------------------  │
│  [新增官方帳號]                                                    │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  官方帳號列表 (Accordion /折疊面板)                                │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                      │
│  ▼ 客戶A的LINE官方帳號 (provider: 客戶A公司)              [刪除]  │
│    狀態：🟢 已連接                                                 │
│    Channels：3 個                                                   │
│    ─────────────────────────────────────────────────────────────   │
│                                                                      │
│    ┌───────────────────────────────────────────────────────────┐   │
│    │  Channel 列表                                              │   │
│    │  ─────────────────────────────────────────────────────── │   │
│    │                                                            │   │
│    │  📱 ChristCoffee (客服)                        [編輯][刪除] │   │
│    │     Channel ID: 2001234567                                 │   │
│    │     Webhook: https://api.aibox.com/webhook/line/xxx      │   │
│    │     狀態：🟢 已發布 (客服Bot)                              │   │
│    │     ────────────────────────────────────────────────────  │   │
│    │                                                            │   │
│    │  📱 DanLinePV (採購)                            [編輯][刪除] │   │
│    │     Channel ID: 2007654321                                 │   │
│    │     Webhook: https://api.aibox.com/webhook/line/yyy      │   │
│    │     狀態：🟢 已發布 (採購Bot)                             │   │
│    │     ────────────────────────────────────────────────────  │   │
│    │                                                            │   │
│    │  📱 stockAst (庫存)                            [編輯][刪除] │   │
│    │     Channel ID: 2009876543                                 │   │
│    │     Webhook: https://api.aibox.com/webhook/line/zzz      │   │
│    │     狀態：⚠️ 未發布                                        │   │
│    │                                                            │   │
│    │  [+ 新增 Channel]                                          │   │
│    └───────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ▼ 客戶B的LINE官方帳號 (provider: 客戶B公司)              [刪除]  │
│    ...                                                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. 新增/編輯官方帳號 Modal

### 3.1 欄位設計

```
┌─────────────────────────────────────────────────────────────────┐
│  新增 LINE 官方帳號                                           [X] │
│  ────────────────────────────────────────────────────────────   │
│                                                                  │
│  Provider 名稱 *                                                │
│  [________________________________________________]              │
│  (例：客戶A公司 / ChristCoffee官方帳號)                         │
│                                                                  │
│  官方帳號名稱 *                                                 │
│  [________________________________________________]              │
│  (例：客戶A LINE客服)                                          │
│                                                                  │
│  ────────────────────────────────────────────────────────────   │
│                                                                  │
│                              [取消]              [儲存]           │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 欄位說明

| 欄位 | 必填 | 說明 | 驗證規則 |
|------|------|------|---------|
| Provider 名稱 | 是 | LINE Developer Console 中的 Provider 名稱 | 最少2字元 |
| 官方帳號名稱 | 是 | 顯示用的名稱，方便識別 | 最少2字元 |

---

## 4. 新增/編輯 Channel Modal

### 4.1 欄位設計

```
┌─────────────────────────────────────────────────────────────────┐
│  新增 LINE Channel                                            [X] │
│  ────────────────────────────────────────────────────────────   │
│                                                                  │
│  官方帳號                                                       │
│  [客戶A的LINE官方帳號 ________________________▼]                  │
│                                                                  │
│  Channel 名稱 *                                                 │
│  [________________________________________________]              │
│  (需與 LINE Developers Console 中的 Channel 名稱一致)           │
│                                                                  │
│  Channel ID *                                                   │
│  [________________________________________________]              │
│  (格式：200xxxxxxx，可從 LINE Developers Console 取得)           │
│                                                                  │
│  Channel Secret *                                               │
│  [________________________________________________]              │
│  (可從 LINE Developers Console > Basic settings 取得)            │
│                                                                  │
│  Channel Access Token (Long-lived) *                            │
│  [________________________________________________]              │
│  [請至 LINE Developers Console > Messaging API > Channel Access] │
│  [Token (long-lived) 取得]                                      │
│                                                                  │
│  ────────────────────────────────────────────────────────────   │
│                                                                  │
│  Webhook URL (自動產生，僅供複製)                               │
│  [https://api.aibox.com/webhook/line/xxx______________] [複製]  │
│  請至 LINE Developers Console 貼上此 URL作為 Webhook URL        │
│                                                                  │
│  Bot User ID                                                    │
│  [U1234567890abcdef________________________] (自動帶入)          │
│                                                                  │
│  ────────────────────────────────────────────────────────────   │
│                                                                  │
│                              [取消]              [儲存]           │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 欄位說明

| 欄位 | 必填 | 說明 | 驗證規則 | 範例 |
|------|------|------|---------|------|
| 官方帳號 | 是 | 所屬的官方帳號 | 下拉選擇 | - |
| Channel 名稱 | 是 | 需與 LINE Developers Console 一致 | 最少2字元 | `ChristCoffee` |
| Channel ID | 是 | LINE 頻道的唯一識別碼 | 數字，200開頭 | `2001234567` |
| Channel Secret | 是 | 用於驗證 Webhook 簽章 | 字串 | `xxx...` |
| Channel Access Token | 是 | Long-lived Token，用於發送訊息 | 字串 | `xxx...` |
| Webhook URL | 否 | 自動產生，不可修改 | URL格式 | `https://api.aibox.com/webhook/line/xxx` |
| Bot User ID | 否 | 官方帳號的 Bot 用戶 ID | LINE格式 | `U1234567890abcdef` |

### 4.3 操作說明

#### 4.3.1 取得 Channel ID 和 Channel Secret

1. 前往 [LINE Developers Console](https://developers.line.biz/console/)
2. 選擇您的 Provider
3. 選擇要使用的 Messaging API Channel
4. 在 **Basic settings** 分頁複製：
   - **Channel ID**
   - **Channel secret**

#### 4.3.2 取得 Channel Access Token (Long-lived)

1. 在 LINE Developers Console 選擇 Channel
2. 前往 **Messaging API** 分頁
3. 點擊 **Channel Access Token (long-lived)**
4. 複製產生的 Token

#### 4.3.3 設定 Webhook URL

1. 複製系統產生的 Webhook URL
2. 在 LINE Developers Console 的 **Messaging API** 分頁
3. 貼上 Webhook URL
4. 點擊 **Update**
5. 啟用 **Use webhook** 選項

---

## 5. 連線測試功能

### 5.1 測試按鈕位置

在 Channel 列表每個項目右側有 **測試連線** 按鈕。

### 5.2 測試流程

```
1. 使用者點擊「測試連線」
   ↓
2. 系統呼叫 LINE API 驗證憑證
   - POST https://api.line.me/v2/profile
   - Header: Authorization: Bearer {channel_access_token}
   ↓
3. 成功
   - 顯示：✅ 連線成功
   - 更新 Bot User ID
   - 狀態改為「已連接」
   ↓
4. 失敗
   - 顯示：❌ 連線失敗
   - 顯示錯誤原因（無效Token、網路問題等）
   - 狀態改為「錯誤」
```

### 5.3 錯誤訊息對照

| 錯誤碼 | 錯誤訊息 | 可能原因 |
|--------|---------|---------|
| 401 | 無效的 Access Token | Token 過期或無效 |
| 403 | 無法存取此資源 | 權限不足 |
| 429 | 請求次數過多 | Rate limit |
| 500 | LINE 伺服器錯誤 | LINE 端問題 |
| - | 網路連線失敗 | 網路問題 |

---

## 6. Channel 列表卡片設計

### 6.1 卡片佈局

```
┌─────────────────────────────────────────────────────────────────┐
│  📱 ChristCoffee                                    🟢 已連接   │
│  ────────────────────────────────────────────────────────────   │
│                                                                  │
│  Channel ID    │  2001234567                                    │
│  Webhook URL   │  https://api.aibox.com/webhook/line/xxx  [📋]│
│  發布狀態      │  ✅ 已發布 → 客服Bot                           │
│  最後連線      │  2026-04-19 10:30:00                          │
│                                                                  │
│  ────────────────────────────────────────────────────────────   │
│  [測試連線]                    [編輯]  [刪除]                    │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 狀態標示

| 狀態 | 圖示 | 顏色 | 說明 |
|------|------|------|------|
| 已連接 | 🟢 | 綠色 | 憑證有效，可正常通訊 |
| 未連接 | ⚪ | 灰色 | 尚未設定或測試 |
| 錯誤 | 🔴 | 紅色 | 憑證無效或過期 |
| 未發布 | ⚠️ | 黃色 | 已設定但未發布到任何 Bot |

---

## 7. 發布管理連動

### 7.1 發布按鈕

當 Channel 設定完成後，可點擊 **發布管理** 將其與 Bot Agent 綁定。

### 7.2 發布 Modal

```
┌─────────────────────────────────────────────────────────────────┐
│  發布 LINE Channel                                         [X] │
│  ────────────────────────────────────────────────────────────   │
│                                                                  │
│  Channel                                                      │
│  ChristCoffee (2001234567)                                     │
│                                                                  │
│  選擇 Bot Agent *                                              │
│  [請選擇 Bot Agent ________________________▼]                  │
│  ────────────────────────────────────────────────────────────   │
│  可用的 Bot：                                                   │
│  • 客服Bot (意圖：售後、訂單查詢)                              │
│  • 採購Bot (意圖：詢價、下單)                                  │
│  • CRM Bot (意圖：客戶關係)                                    │
│                                                                  │
│  客製化設定（選填）                                            │
│  ────────────────────────────────────────────────────────────   │
│  歡迎訊息                                                      │
│  [您好！歡迎使用客服服務，請問有什麼可以幫您？____]              │
│                                                                  │
│  自動回覆延遲（秒）                                            │
│  [0________________] (0表示立即回覆)                           │
│                                                                  │
│  ────────────────────────────────────────────────────────────   │
│                                                                  │
│                              [取消]              [發布]           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. API 端點設計

### 8.1 後端 API

```typescript
// LINE 官方帳號相關
POST   /api/v1/platforms/line/official-accounts
GET    /api/v1/platforms/line/official-accounts
GET    /api/v1/platforms/line/official-accounts/:key
PUT    /api/v1/platforms/line/official-accounts/:key
DELETE /api/v1/platforms/line/official-accounts/:key

// LINE Channel 相關
POST   /api/v1/platforms/line/official-accounts/:key/channels
GET    /api/v1/platforms/line/official-accounts/:key/channels
GET    /api/v1/platforms/line/channels/:channelKey
PUT    /api/v1/platforms/line/channels/:channelKey
DELETE /api/v1/platforms/line/channels/:channelKey

// 連線測試
POST   /api/v1/platforms/line/channels/:channelKey/test-connection

// 發布相關
POST   /api/v1/platforms/line/channels/:channelKey/publish
DELETE /api/v1/platforms/line/channels/:channelKey/publish
```

### 8.2 前端 API 服務層

```typescript
// src/services/api/platforms/line.ts

export interface LINEOfficialAccount {
  _key: string;
  provider_name: string;
  name: string;
  status: 'active' | 'inactive' | 'error';
  channels: LINEChannel[];
  created_at: string;
  updated_at: string;
}

export interface LINEChannel {
  _key: string;
  official_account_key: string;
  channel_name: string;
  channel_id: string;
  channel_secret: string;  // 只在建立/編輯時傳送，回應時遮蔽
  channel_access_token: string;  // 只在建立/編輯時傳送，回應時遮蔽
  webhook_url: string;
  webhook_enabled: boolean;
  bot_user_id: string;
  publication_status: 'unpublished' | 'published' | 'error';
  last_connected_at: string | null;
  published_bot_key?: string;
}

export const linePlatformApi = {
  // 官方帳號
  listOfficialAccounts: () => 
    api.get<{ code: number; data: LINEOfficialAccount[] }>('/platforms/line/official-accounts'),
  
  createOfficialAccount: (data: { provider_name: string; name: string }) =>
    api.post('/platforms/line/official-accounts', data),
  
  updateOfficialAccount: (key: string, data: Partial<LINEOfficialAccount>) =>
    api.put(`/platforms/line/official-accounts/${key}`, data),
  
  deleteOfficialAccount: (key: string) =>
    api.delete(`/platforms/line/official-accounts/${key}`),

  // Channel
  listChannels: (officialAccountKey: string) =>
    api.get<{ code: number; data: LINEChannel[] }>(
      `/platforms/line/official-accounts/${officialAccountKey}/channels`
    ),
  
  createChannel: (officialAccountKey: string, data: Omit<LINEChannel, '_key' | 'official_account_key' | 'webhook_url' | 'webhook_enabled' | 'bot_user_id' | 'publication_status' | 'last_connected_at' | 'created_at'>) =>
    api.post(`/platforms/line/official-accounts/${officialAccountKey}/channels`, data),
  
  updateChannel: (channelKey: string, data: Partial<LINEChannel>) =>
    api.put(`/platforms/line/channels/${channelKey}`, data),
  
  deleteChannel: (channelKey: string) =>
    api.delete(`/platforms/line/channels/${channelKey}`),

  // 連線測試
  testConnection: (channelKey: string) =>
    api.post<{ code: number; data: { success: boolean; bot_user_id?: string; error?: string } }>(
      `/platforms/line/channels/${channelKey}/test-connection`
    ),

  // 發布
  publish: (channelKey: string, botKey: string, customSettings?: { greeting?: string; delay?: number }) =>
    api.post(`/platforms/line/channels/${channelKey}/publish`, { bot_key: botKey, ...customSettings }),
  
  unpublish: (channelKey: string) =>
    api.delete(`/platforms/line/channels/${channelKey}/publish`),
};
```

---

## 9. UI 設計細節

### 9.1 元件結構

```
src/components/LineMarketplace/
├── LineToolCard.tsx         # 外層市集卡片 (顯示總覽資訊)
├── ProviderList.tsx         # 點擊卡片後展開的 Provider 手風琴列表
├── ChannelItem.tsx          # 每個 Provider 下的 Channel 項目列
└── modals/
    └── ChannelEditModal.tsx # 核心：分層式編輯對話框
```

### 9.2 Ant Design 元件使用

#### A. 工具市集卡片 & 列表
- **卡片外觀**: `<Card hoverable>`
- **列表容器**: `<Collapse>` (手風琴效果) 來顯示 Provider 列表
- **狀態標籤**: `<Badge status="success" text="已連接" />` 或 `<Tag color="success">`
- **操作按鈕**: `<Button type="link">` 或 `<Button type="text">` 搭配圖示

#### B. 分層式編輯對話框
- **外層 Modal**: `<Modal width={700} title="編輯 LINE Channel" centered>`
- **分層區塊**: `<Card type="inner" title="官方帳號設定" className="mb-4">` 來包覆每個子區塊
- **唯讀與複製欄位**: `<Input readOnly addonAfter={<CopyOutlined onClick={handleCopy} />} />`
- **連線狀態區塊**: `<Descriptions column={1} bordered size="small">` 來呈現唯讀的系統狀態
- **提示訊息**: `<Alert message="請至 LINE Developers Console..." type="info" showIcon />`

### 9.3 表單驗證規則

```typescript
const rules = {
  providerName: [{ required: true, message: '請輸入 Provider 名稱' }],
  officialAccountName: [{ required: true, message: '請輸入官方帳號名稱' }],
  name: [{ required: true, message: '請輸入 Channel 名稱' }],
  channelId: [
    { required: true, message: '請輸入 Channel ID' },
    { pattern: /^\d+$/, message: 'Channel ID 必須為數字' }
  ],
  channelSecret: [
    { required: true, message: '請輸入 Channel Secret' }
  ],
  accessToken: [{ required: true, message: '請輸入 Channel Access Token' }]
};
```

### 9.4 狀態管理策略

1. **Local UI State (React `useState`)**:
   - `isModalVisible`: 控制 Modal 開關
   - `editingChannel`: 目前正在編輯的 Channel 與其 Provider 資訊
   - `isTestingConnection`: 測試連線按鈕的 loading 狀態

2. **Form State (`Form.useForm()`)**:
   - 使用 AntD 的 `form` 實例來管理輸入值
   - 當 `editingChannel` 傳入時，使用 `form.setFieldsValue()` 初始化表單

3. **Global/API State**:
   - 儲存與刪除操作應呼叫 `api.ts` 中的對應端點
   - 成功後重新 fetch 列表或更新全域狀態

### 9.5 UI 佈局草圖 (JSX 結構)

```tsx
<Modal title="編輯 LINE Channel" width={700} okText="儲存變更" cancelText="取消">
  <Form form={form} layout="vertical">
    
    {/* 區塊 1：官方帳號設定 */}
    <Card type="inner" title="官方帳號設定" className="mb-4">
      <Row gutter={16}>
        <Col span={12}>
          <Form.Item label="Provider 名稱" name="providerName" rules={rules.providerName}>
            <Input placeholder="客戶A公司" />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item label="官方帳號名稱" name="officialAccountName" rules={rules.officialAccountName}>
            <Input placeholder="客戶A LINE客服" />
          </Form.Item>
        </Col>
      </Row>
    </Card>

    {/* 區塊 2：Channel 設定 */}
    <Card type="inner" title="Channel 設定" className="mb-4">
      <Form.Item label="Channel 名稱" name="name" rules={rules.name}>
        <Input placeholder="例如: ChristCoffee (客服)" />
      </Form.Item>
      <Form.Item label="Channel ID" name="channelId" rules={rules.channelId}>
        <Input placeholder="例如: 2001234567" />
      </Form.Item>
      <Form.Item label="Channel Secret" name="channelSecret" rules={rules.channelSecret}>
        <Input.Password placeholder="輸入 Secret" />
      </Form.Item>
      <Form.Item label="Channel Access Token (Long-lived)" name="accessToken" rules={rules.accessToken} 
                 extra="請向 LINE Developers Console 取得">
        <Input.Password placeholder="輸入 Access Token" />
      </Form.Item>
    </Card>

    {/* 區塊 3：Webhook 設定 (自動產生) */}
    <Card type="inner" title="Webhook 設定" className="mb-4">
      <Form.Item label="Webhook URL (自動產生)">
        <Input readOnly value="https://api.aibox.com/webhook/line/xxx" 
               addonAfter={<CopyOutlined onClick={() => message.success('已複製')} />} />
      </Form.Item>
      <Alert message="請至 LINE Developers Console > Messaging API > Webhook settings 貼上此 URL 並啟用 Webhook" type="info" showIcon />
    </Card>

    {/* 區塊 4：連線狀態 */}
    <Card type="inner" title="連線狀態" size="small">
      <div className="flex justify-between items-center">
        <div>
          <Badge status="success" text="已驗證" className="mr-4" />
          <Typography.Text type="secondary">Bot User ID: U1234567890abcdef</Typography.Text>
          <br/>
          <Typography.Text type="secondary" className="text-xs">最後連線: 2026-04-19 10:30:00</Typography.Text>
        </div>
        <Space>
          <Button icon={<SyncOutlined />}>重新整理</Button>
          <Button type="primary" ghost>測試連線</Button>
        </Space>
      </div>
    </Card>

  </Form>
</Modal>
```

---

## 10. 元件清單

| 元件 | 說明 | 位置 |
|------|------|------|
| `LineToolCard` | 外層市集卡片 | `/src/components/LineMarketplace/LineToolCard.tsx` |
| `ProviderList` | Provider 手風琴列表 | `/src/components/LineMarketplace/ProviderList.tsx` |
| `ChannelItem` | Channel 項目列 | `/src/components/LineMarketplace/ChannelItem.tsx` |
| `ChannelEditModal` | 分層式編輯 Modal | `/src/components/LineMarketplace/modals/ChannelEditModal.tsx` |
| `LINEPublishModal` | 發布到 Bot Modal | `/src/components/LineMarketplace/modals/LINEPublishModal.tsx` |

---

## 11. 技術實作考量

### 11.1 安全性

- Channel Secret 和 Channel Access Token 在傳輸和儲存時需加密
- API 回應中不應包含完整的敏感資訊
- 前端表單提交後立即清除記憶體中的敏感資料

### 11.2 驗證

- Channel ID 格式驗證：`/^200\d+$/`
- Webhook URL 格式驗證：合法的 HTTPS URL
- 必填欄位前端驗證

### 11.3 錯誤處理

- 網路錯誤：顯示「網路連線失敗，請檢查網路」
- 驗證失敗：顯示「Channel ID 或 Secret 無效」
- 連線超時：顯示「連線逾時，請稍後再試」

---

## 12. 參考資料

- [LINE Developers Console](https://developers.line.biz/console/)
- [LINE Messaging API Documentation](https://developers.line.biz/en/docs/messaging-api/)
- [LINE Channel Configuration](https://developers.line.biz/en/docs/line-developers-console/channel-configuration/)
- [LINE Best Practices for Provider and Channel Management](https://developers.line.biz/en/docs/line-developers-console/best-practices-for-provider-and-channel-management/)

---

## 13. 修改歷程

| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| 2026-04-19 | 1.1.0 | Daniel Chung | 新增 UI 設計細節：元件結構、Ant Design 使用、表單驗證、狀態管理、JSX 佈局草圖 |
| 2026-04-19 | 1.0.0 | Daniel Chung | 初始版本 |
