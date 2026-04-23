/**
 * @file        意圖分析系統參數頁面
 * @description 意圖分析系統配置，包含意圖匹配閾值、小模型配置、Qdrant 向量庫設置等
 * @lastUpdate  2026-04-14 11:00:00
 * @author      Daniel Chung
 * @version     1.1.0
 */

import { useState, useEffect } from 'react';
import { Card, Switch, Input, InputNumber, Button, Space, Typography, App, Select, Alert } from 'antd';
import { ReloadOutlined, SyncOutlined } from '@ant-design/icons';
import { paramsApi } from '../services/api';
import { intentCatalogApi } from '../services/intentCatalogApi';
import { useContentTokens } from '../contexts/AppThemeProvider';

const { Title, Text } = Typography;

interface IntentParam {
  key: string;
  label: string;
  description: string;
  type: 'boolean' | 'string' | 'number' | 'select';
  defaultValue?: string | number | boolean;
  options?: { value: string; label: string }[];
  placeholder?: string;
  category: 'matching' | 'model' | 'qdrant' | 'action' | 'orchestrator';
}

const INTENT_PARAMS: IntentParam[] = [
  // Matching Settings
  {
    key: 'intent.matching_enabled',
    label: '啟用意圖匹配',
    description: '啟用時，用戶輸入將先經過意圖分析再分流',
    type: 'boolean',
    defaultValue: true,
    category: 'matching',
  },
  {
    key: 'intent.matching_threshold',
    label: '匹配閾值',
    description: 'Qdrant 向量相似度閾值 (0.0-1.0)，越高越嚴格',
    type: 'number',
    defaultValue: 0.75,
    category: 'matching',
  },
  {
    key: 'intent.use_small_model',
    label: '使用小模型分析',
    description: '使用小型專用語義模型進行意圖分析（推薦 Qwen3.5-0.8B）',
    type: 'boolean',
    defaultValue: true,
    category: 'matching',
  },
  {
    key: 'intent.fallback_to_keyword',
    label: '關鍵詞回退',
    description: '當向量匹配失敗時，是否回退到關鍵詞匹配',
    type: 'boolean',
    defaultValue: true,
    category: 'matching',
  },

  // Model Settings
  {
    key: 'intent.small_model_provider',
    label: '小模型 Provider',
    description: '意圖分析小模型的 API Provider',
    type: 'select',
    defaultValue: 'ollama',
    options: [
      { value: 'ollama', label: 'Ollama (本地)' },
      { value: 'lm_studio', label: 'LM Studio (本地)' },
      { value: 'openai', label: 'OpenAI' },
      { value: 'anthropic', label: 'Anthropic' },
    ],
    category: 'model',
  },
  {
    key: 'intent.small_model_name',
    label: '小模型名稱',
    description: '小模型名稱，如 qwen3.5:0.8b 或 qwen2.5-0.5b',
    type: 'string',
    defaultValue: 'qwen3.5:0.8b',
    placeholder: 'qwen3.5:0.8b',
    category: 'model',
  },
  {
    key: 'intent.small_model_temperature',
    label: 'Temperature',
    description: '生成隨機性 (0.0-1.0)，越低越確定',
    type: 'number',
    defaultValue: 0.3,
    category: 'model',
  },
  {
    key: 'intent.small_model_max_tokens',
    label: '最大 Token 數',
    description: '單次請求最大 Token 數',
    type: 'number',
    defaultValue: 256,
    category: 'model',
  },

  // Qdrant Settings
  {
    key: 'intent.qdrant_collection',
    label: 'Qdrant Collection',
    description: '意圖向量存儲的 Collection 名稱',
    type: 'string',
    defaultValue: 'intent_catalog',
    placeholder: 'intent_catalog',
    category: 'qdrant',
  },
  {
    key: 'intent.qdrant_top_k',
    label: 'Qdrant 檢索數',
    description: '向量檢索返回的最相似意圖數量',
    type: 'number',
    defaultValue: 5,
    category: 'qdrant',
  },
  {
    key: 'intent.qdrant_embedding_model',
    label: 'Embedding 模型',
    description: '向量嵌入使用的模型名稱',
    type: 'select',
    defaultValue: 'BAAI/bge-m3',
    options: [
      { value: 'BAAI/bge-m3', label: 'BGE-M3 (推薦, 多語言, 1024維)' },
      { value: 'intfloat/e5-mistral-7b-v2', label: 'E5-Mistral-7B (1024維)' },
      { value: 'sentence-transformers/all-MiniLM-L12-v2', label: 'All-MiniLM-L12 (384維)' },
      { value: 'sentence-transformers/all-mpnet-base-v2', label: 'All-MPNet-Base (768維)' },
    ],
    category: 'qdrant',
  },
  {
    key: 'intent.qdrant_embedding_dimensions',
    label: '向量維度',
    description: 'Embedding 向量維度數 (需與模型輸出匹配)',
    type: 'number',
    defaultValue: 1024,
    category: 'qdrant',
  },

  // Action Settings
  {
    key: 'intent.action_timeout',
    label: 'Action 逾時 (秒)',
    description: '執行 ActionPlan 的逾時時間',
    type: 'number',
    defaultValue: 30,
    category: 'action',
  },
  {
    key: 'intent.action_max_retries',
    label: 'Action 最大重試次數',
    description: 'Action 失敗後的最大重試次數',
    type: 'number',
    defaultValue: 3,
    category: 'action',
  },
  {
    key: 'intent.enable_action_feedback',
    label: '啟用 Action 反饋學習',
    description: '允許用戶對 Action 結果提供反饋以改進意圖匹配',
    type: 'boolean',
    defaultValue: true,
    category: 'action',
  },

  // Orchestrator Settings (TopIntentRAG)
  {
    key: 'intent.orchestrator_collection',
    label: 'Orchestrator Collection',
    description: 'Top Orchestrator 意圖使用的 Qdrant Collection 名稱',
    type: 'string',
    defaultValue: 'orchestrator_intents',
    placeholder: 'orchestrator_intents',
    category: 'orchestrator',
  },
  {
    key: 'intent.orchestrator_threshold',
    label: 'Orchestrator 匹配閾值',
    description: 'TopIntentRAG 向量匹配閾值 (0.0-1.0)',
    type: 'number',
    defaultValue: 0.7,
    category: 'orchestrator',
  },
  {
    key: 'intent.default_action_type',
    label: '預設 Action 類型',
    description: '當無法確定 Action Type 時的預設值',
    type: 'select',
    defaultValue: 'direct_answer',
    options: [
      { value: 'direct_answer', label: '直接回答 (direct_answer)' },
      { value: 'tool_call', label: '工具調用 (tool_call)' },
      { value: 'process_orchestration', label: '流程編排 (process_orchestration)' },
    ],
    category: 'orchestrator',
  },
  {
    key: 'intent.default_target_agent',
    label: '預設目標 Agent',
    description: '當無法確定 Target Agent 時的預設值',
    type: 'select',
    defaultValue: 'chat',
    options: [
      { value: 'chat', label: '聊天 (chat)' },
      { value: 'tool', label: '工具 (tool)' },
      { value: 'pdca', label: 'PDCA (pdca)' },
      { value: 'bpa', label: 'BPA (bpa)' },
      { value: 'ca', label: 'CA (ca)' },
    ],
    category: 'orchestrator',
  },
  {
    key: 'intent.use_matcher_node',
    label: '啟用 Matcher Node',
    description: '在意圖分類後啟用 Matcher Node 進行 TopIntentRAG 匹配',
    type: 'boolean',
    defaultValue: true,
    category: 'orchestrator',
  },
];

export default function SystemParamsIntent() {
  const contentTokens = useContentTokens();
  const { message: antMessage } = App.useApp();
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncedCount, setSyncedCount] = useState<number | null>(null);

  useEffect(() => {
    void loadParams();
  }, []);

  const loadParams = async () => {
    setLoading(true);
    try {
      const response = await paramsApi.list();
      const data: Record<string, string> = {};
      response.data.data?.forEach((p: { param_key: string; param_value: string }) => {
        if (p.param_key.startsWith('intent.')) {
          data[p.param_key] = p.param_value;
        }
      });
      // Apply defaults for missing params
      INTENT_PARAMS.forEach(param => {
        if (data[param.key] === undefined && param.defaultValue !== undefined) {
          data[param.key] = String(param.defaultValue);
        }
      });
      setValues(data);
    } catch {
      antMessage.error('載入失敗');
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = (key: string, checked: boolean) => {
    setValues(prev => ({ ...prev, [key]: String(checked) }));
  };

  const handleInput = (key: string, val: string | number) => {
    setValues(prev => ({ ...prev, [key]: String(val) }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      for (const [key, val] of Object.entries(values)) {
        if (key.startsWith('intent.')) {
          await paramsApi.update(key, val);
        }
      }
      antMessage.success('保存成功');
    } catch {
      antMessage.error('保存失敗');
    } finally {
      setSaving(false);
    }
  };

  const handleSyncToQdrant = async () => {
    setSyncing(true);
    try {
      const response = await intentCatalogApi.syncToQdrant({ agent_scope: 'orchestrator' });
      setSyncedCount(response.data.synced_count);
      antMessage.success(`同步成功：${response.data.synced_count} 個意圖已同步到 Qdrant`);
    } catch (err: any) {
      antMessage.error(err.response?.data?.message || '同步失敗');
    } finally {
      setSyncing(false);
    }
  };

  const groupedParams = INTENT_PARAMS.reduce((acc, param) => {
    if (!acc[param.category]) {
      acc[param.category] = [];
    }
    acc[param.category].push(param);
    return acc;
  }, {} as Record<string, IntentParam[]>);

  const categoryInfo: Record<string, { title: string; color: string }> = {
    matching: { title: '匹配設置', color: '#3b82f6' },
    model: { title: '小模型配置', color: '#8b5cf6' },
    qdrant: { title: 'Qdrant 向量庫', color: '#10b981' },
    action: { title: 'Action 設置', color: '#f59e0b' },
    orchestrator: { title: 'Orchestrator 設置', color: '#ec4899' },
  };

  const renderParamInput = (param: IntentParam) => {
    const value = values[param.key] || String(param.defaultValue ?? '');

    switch (param.type) {
      case 'boolean':
        return (
          <Switch
            checked={value === 'true'}
            onChange={checked => handleToggle(param.key, checked)}
            disabled={loading}
          />
        );

      case 'number':
        return (
          <InputNumber
            value={parseFloat(value) || 0}
            onChange={val => handleInput(param.key, val ?? 0)}
            min={0}
            max={param.key.includes('threshold') || param.key.includes('temperature') ? 1 : undefined}
            step={param.key.includes('threshold') || param.key.includes('temperature') ? 0.05 : 1}
            disabled={loading}
            style={{ width: '100%' }}
          />
        );

      case 'select':
        return (
          <Select
            value={value || param.defaultValue}
            onChange={val => handleInput(param.key, val as string | number)}
            disabled={loading}
            style={{ width: '100%' }}
            options={param.options}
          />
        );

      case 'string':
      default:
        return (
          <Input
            value={value}
            onChange={e => handleInput(param.key, e.target.value)}
            placeholder={param.placeholder}
            disabled={loading}
          />
        );
    }
  };

  const renderCategory = (category: string, categoryParams: IntentParam[]) => {
    const info = categoryInfo[category];
    return (
      <div key={category} style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <Title level={5} style={{ margin: 0, color: info.color }}>
            {info.title}
          </Title>
        </div>
        <Card styles={{ body: { padding: 16 } }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))', gap: 16 }}>
            {categoryParams.map(param => {
              const isBoolean = param.type === 'boolean';

              return (
                <div
                  key={param.key}
                  style={{
                    display: 'flex',
                    flexDirection: isBoolean ? 'row' : 'column',
                    alignItems: isBoolean ? 'center' : 'flex-start',
                    justifyContent: isBoolean ? 'space-between' : 'flex-start',
                    padding: isBoolean ? '8px 0' : 0,
                    gap: isBoolean ? 16 : 4,
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <Text strong style={{ fontSize: 13 }}>
                      {param.label}
                    </Text>
                    <div style={{ fontSize: 12, color: contentTokens.textSecondary, marginTop: 2 }}>
                      {param.description}
                    </div>
                  </div>
                  <div style={{ minWidth: isBoolean ? 'auto' : 200 }}>
                    {renderParamInput(param)}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>
    );
  };

  const isIntentEnabled = values['intent.matching_enabled'] === 'true';
  const smallModelProvider = values['intent.small_model_provider'] || 'ollama';
  const smallModelName = values['intent.small_model_name'] || 'qwen3.5:0.8b';

  return (
    <div style={{ padding: '0 0 24px' }}>
      <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <Title level={5} style={{ margin: 0 }}>意圖分析系統參數</Title>
          <div style={{ fontSize: 12, color: contentTokens.textSecondary, marginTop: 4 }}>
            配置 Top Orchestrator 意圖分析系統的各項參數，包括匹配閾值、小模型配置與 Qdrant 向量庫設置
          </div>
        </div>
        <Space>
          <Button
            icon={<SyncOutlined spin={syncing} />}
            onClick={handleSyncToQdrant}
            loading={syncing}
          >
            同步到 Qdrant
          </Button>
          <Button icon={<ReloadOutlined />} onClick={loadParams} loading={loading}>
            刷新
          </Button>
          <Button type="primary" onClick={handleSave} loading={saving}>
            保存全部
          </Button>
        </Space>
      </div>

      {syncedCount !== null && (
        <Alert
          message={`同步完成`}
          description={`已成功同步 ${syncedCount} 個意圖到 Qdrant 向量庫`}
          type="success"
          showIcon
          closable
          onClose={() => setSyncedCount(null)}
          style={{ marginBottom: 16 }}
        />
      )}

      <Alert
        message="意圖分析系統"
        description={
          <div>
            <div style={{ marginBottom: 8 }}>
              系統採用<strong>雙軌意圖匹配</strong>：Qdrant 向量匹配 + 小模型語義分析。
              當前配置：{isIntentEnabled ? '已啟用' : '已停用'}
              {isIntentEnabled && (
                <>
                  {' '}· 小模型：{smallModelProvider}/{smallModelName}
                </>
              )}
            </div>
            <div style={{ fontSize: 12 }}>
              同步按鈕會將意圖目錄（Intent Catalog）中的所有意圖同步到 Qdrant 向量庫，以支持向量相似度匹配。
            </div>
          </div>
        }
        type={isIntentEnabled ? 'info' : 'warning'}
        showIcon
        style={{ marginBottom: 16 }}
      />

      {Object.entries(groupedParams).map(([category, params]) =>
        renderCategory(category, params)
      )}

      <Card style={{ background: `${contentTokens.colorPrimary}08`, border: `1px solid ${contentTokens.colorPrimary}30` }}>
        <div style={{ fontSize: 12, color: contentTokens.textSecondary, lineHeight: 1.8 }}>
          <strong>關於意圖分析系統</strong>
          <br />
          1. <strong>匹配閾值</strong>：建議範圍 0.7-0.85，過高可能導致匹配失敗，過低可能導致誤匹配
          <br />
          2. <strong>小模型</strong>：推薦使用 qwen3.5:0.8b（性價比最高），需確保 Ollama/LM Studio 已啟動
          <br />
          3. <strong>Qdrant Embedding</strong>：需確保維度數與模型輸出匹配，BGE-M3 為 1024 維，All-MiniLM-L12 為 384 維
          <br />
          4. <strong>同步</strong>：變更 Embedding 模型或維度後，需重新同步意圖到 Qdrant
          <br />
          5. <strong>Action 逾時</strong>：建議值 30-60 秒，複雜操作可適當增加
        </div>
      </Card>
    </div>
  );
}