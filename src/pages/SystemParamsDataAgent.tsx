/**
 * @file        資料代理系統參數頁面
 * @description Data Agent 設定頁面，包含 SQL 模型、嵌入模型、推理模型、資料源等分組配置
 * @lastUpdate  2026-04-16 17:31:16
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import { Card, Switch, Input, InputNumber, Button, Space, Typography, App, Select } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { paramsApi } from '../services/api';
import { useContentTokens } from '../contexts/AppThemeProvider';

const { Title, Text } = Typography;

interface DataAgentParam {
  key: string;
  label: string;
  description: string;
  type: 'boolean' | 'string' | 'number' | 'select';
  defaultValue?: string | number | boolean;
  options?: { value: string; label: string }[];
  placeholder?: string;
  step?: number;
  max?: number;
  category: 'sql' | 'embedding' | 'inference' | 'source';
}

const DATA_AGENT_PARAMS: DataAgentParam[] = [
  // SQL Settings
  {
    key: 'da.sql_model',
    label: 'SQL 生成主模型',
    description: 'SQL 生成主模型',
    type: 'string',
    defaultValue: 'duckdb-nsql:latest',
    placeholder: 'duckdb-nsql:latest',
    category: 'sql',
  },
  {
    key: 'da.sql_model_provider',
    label: '模型提供者',
    description: '模型提供者',
    type: 'select',
    defaultValue: 'ollama',
    options: [
      { value: 'ollama', label: 'Ollama' },
      { value: 'lm_studio', label: 'LM Studio' },
    ],
    category: 'sql',
  },
  {
    key: 'da.sql_fallback_model',
    label: '備用模型',
    description: '備用模型',
    type: 'string',
    defaultValue: 'sqlcoder:7b',
    placeholder: 'sqlcoder:7b',
    category: 'sql',
  },
  {
    key: 'da.sql_fallback_provider',
    label: '備用模型提供者',
    description: '備用模型提供者',
    type: 'select',
    defaultValue: 'ollama',
    options: [
      { value: 'ollama', label: 'Ollama' },
      { value: 'lm_studio', label: 'LM Studio' },
    ],
    category: 'sql',
  },
  {
    key: 'da.sql_temperature',
    label: '生成溫度',
    description: '生成溫度',
    type: 'number',
    defaultValue: 0.1,
    step: 0.05,
    max: 1,
    category: 'sql',
  },
  {
    key: 'da.sql_max_retries',
    label: '驗證失敗重試次數',
    description: '驗證失敗重試次數',
    type: 'number',
    defaultValue: 2,
    step: 1,
    category: 'sql',
  },

  // Embedding Settings
  {
    key: 'da.embedding_model',
    label: '嵌入模型',
    description: '嵌入模型',
    type: 'string',
    defaultValue: 'qwen3-embedding:latest',
    placeholder: 'qwen3-embedding:latest',
    category: 'embedding',
  },
  {
    key: 'da.embedding_dimension',
    label: '嵌入維度',
    description: '嵌入維度',
    type: 'number',
    defaultValue: 4096,
    step: 1,
    category: 'embedding',
  },

  // Inference Settings
  {
    key: 'da.large_llm_model',
    label: '大型推理模型',
    description: '用於複雜查詢分析與意圖理解',
    type: 'string',
    defaultValue: 'qwen3-coder:30b',
    placeholder: 'qwen3-coder:30b',
    category: 'inference',
  },
  {
    key: 'da.llm_model',
    label: '通用模型',
    description: '用於一般查詢處理',
    type: 'string',
    defaultValue: 'qwen3-coder:30b',
    placeholder: 'qwen3-coder:30b',
    category: 'inference',
  },

  // Source Settings
  {
    key: 'da.data_source',
    label: '原始資料源',
    description: '原始資料源',
    type: 'select',
    defaultValue: 'ragic',
    options: [
      { value: 'ragic', label: 'Ragic' },
      { value: 'sap', label: 'SAP' },
    ],
    category: 'source',
  },
  {
    key: 'da.query_source',
    label: '查詢資料源',
    description: '查詢資料源',
    type: 'select',
    defaultValue: 'server_cache',
    options: [
      { value: 'server_cache', label: 'Server DuckDB Cache' },
      { value: 'browser', label: '瀏覽器 DuckDB' },
      { value: 'datalake', label: 'S3 Datalake (舊)' },
    ],
    category: 'source',
  },
];

export default function SystemParamsDataAgent() {
  const contentTokens = useContentTokens();
  const { message: antMessage } = App.useApp();
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    void loadParams();
  }, []);

  const loadParams = async () => {
    setLoading(true);
    try {
      const response = await paramsApi.list();
      const data: Record<string, string> = {};
      response.data.data?.forEach((p: { param_key: string; param_value: string }) => {
        if (p.param_key.startsWith('da.')) {
          data[p.param_key] = p.param_value;
        }
      });
      // Apply defaults for missing params
      DATA_AGENT_PARAMS.forEach(param => {
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
        if (key.startsWith('da.')) {
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

  const groupedParams = DATA_AGENT_PARAMS.reduce((acc, param) => {
    if (!acc[param.category]) {
      acc[param.category] = [];
    }
    acc[param.category].push(param);
    return acc;
  }, {} as Record<string, DataAgentParam[]>);

  const categoryInfo: Record<string, { title: string; color: string }> = {
    sql: { title: 'SQL 模型設定', color: '#3b82f6' },
    embedding: { title: '嵌入模型設定', color: '#8b5cf6' },
    inference: { title: '推理模型設定', color: '#10b981' },
    source: { title: '資料源設定', color: '#f59e0b' },
  };

  const renderParamInput = (param: DataAgentParam) => {
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
            max={param.max}
            step={param.step || 1}
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

  const renderCategory = (category: string, categoryParams: DataAgentParam[]) => {
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

  return (
    <div style={{ padding: '0 0 24px' }}>
      <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <Title level={5} style={{ margin: 0 }}>
            資料代理設定
          </Title>
          <div style={{ fontSize: 12, color: contentTokens.textSecondary, marginTop: 4 }}>
            配置 Data Agent 的 SQL 生成、嵌入模型、推理模型與資料源設置
          </div>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={loadParams} loading={loading}>
            刷新
          </Button>
          <Button type="primary" onClick={handleSave} loading={saving}>
            保存全部
          </Button>
        </Space>
      </div>

      {Object.entries(groupedParams).map(([category, params]) => renderCategory(category, params))}

      <Card style={{ background: `${contentTokens.colorPrimary}08`, border: `1px solid ${contentTokens.colorPrimary}30` }}>
        <div style={{ fontSize: 12, color: contentTokens.textSecondary, lineHeight: 1.8 }}>
          <strong>關於資料代理系統</strong>
          <br />
          1. <strong>SQL 模型</strong>：負責自然語言轉 SQL 查詢，建議使用 duckdb-nsql 或 sqlcoder
          <br />
          2. <strong>嵌入模型</strong>：用於向量嵌入和 RAG 檢索，推薦 qwen3-embedding
          <br />
          3. <strong>推理模型</strong>：大型模型用於複雜查詢分析，通用模型用於一般處理
          <br />
          4. <strong>資料源</strong>：配置原始資料源（Ragic/SAP）和查詢緩存位置
          <br />
          5. <strong>溫度設置</strong>：SQL 溫度越低越確定，建議值 0.1-0.3，以確保 SQL 查詢的準確性
        </div>
      </Card>
    </div>
  );
}
