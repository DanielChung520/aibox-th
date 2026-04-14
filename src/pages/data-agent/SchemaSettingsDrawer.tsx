/**
 * @file        SchemaSettingsDrawer.tsx
 * @description Data Agent NL 查詢模型參數設置 Drawer
 * @lastUpdate  2026-04-12 01:06:49
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Drawer,
  Form,
  Input,
  InputNumber,
  Select,
  Button,
  Space,
  Divider,
  Spin,
  Typography,
  Alert,
  App,
} from 'antd';
import {
  SettingOutlined,
  RobotOutlined,
  AimOutlined,
} from '@ant-design/icons';
import { paramsApi } from '../../services/api';

const { Text } = Typography;

/** system_params 中 Data Agent 相關的 key */
const PARAM_KEYS = [
  'da.embedding_model',
  'da.embedding_dimension',
  'da.small_llm_model',
  'da.large_llm_model',
  'da.data_source',
  'intent.match_threshold',
] as const;

type ParamKey = (typeof PARAM_KEYS)[number];

/** 各欄位的預設值（對應 config_reader.py _ENV_FALLBACKS） */
const DEFAULTS: Record<ParamKey, string> = {
  'da.embedding_model': 'bge-m3:latest',
  'da.embedding_dimension': '1024',
  'da.small_llm_model': 'mistral-nemo:12b',
  'da.large_llm_model': 'qwen3-coder:30b',
  'da.data_source': 'sap',
  'intent.match_threshold': '0.45',
};

interface SchemaSettingsDrawerProps {
  open: boolean;
  onClose: () => void;
}

export default function SchemaSettingsDrawer({ open, onClose }: SchemaSettingsDrawerProps) {
  const { message, modal } = App.useApp();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [ollamaLoading, setOllamaLoading] = useState(false);
  /** 記住開啟時讀到的原始 embedding_dimension，用來偵測是否有變更 */
  const [originalDimension, setOriginalDimension] = useState<string>('');

  const fetchOllamaModels = useCallback(async () => {
    setOllamaLoading(true);
    try {
      const resp = await fetch('/ollama/api/tags');
      if (resp.ok) {
        const data = await resp.json();
        const names: string[] = (data.models || []).map((m: { name: string }) => m.name);
        setOllamaModels(names.sort());
      }
    } catch {
      setOllamaModels([]);
    } finally {
      setOllamaLoading(false);
    }
  }, []);

  const loadParams = useCallback(async () => {
    setLoading(true);
    try {
      const values: Record<string, string> = {};
      const results = await Promise.allSettled(
        PARAM_KEYS.map((key) => paramsApi.get(key)),
      );
      results.forEach((r, i) => {
        const key = PARAM_KEYS[i];
        if (r.status === 'fulfilled') {
          values[key] = r.value.data?.data?.param_value || DEFAULTS[key];
        } else {
          values[key] = DEFAULTS[key];
        }
      });
      form.setFieldsValue(values);
      setOriginalDimension(values['da.embedding_dimension']);
    } catch {
      message.error('載入設定失敗');
    } finally {
      setLoading(false);
    }
  }, [form, message]);

  useEffect(() => {
    if (open) {
      loadParams();
      fetchOllamaModels();
    }
  }, [open, loadParams, fetchOllamaModels]);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();

      const newDim = String(values['da.embedding_dimension']);
      if (newDim !== originalDimension && originalDimension) {
        const confirmed = await new Promise<boolean>((resolve) => {
          modal.confirm({
            title: '向量維度變更警告',
            content:
              '修改 Embedding 向量維度會導致現有 Qdrant collection（ragic_schemas、ragic_intents）不相容，需要重建索引。確定要繼續嗎？',
            okText: '確定修改',
            okType: 'danger',
            cancelText: '取消',
            onOk: () => resolve(true),
            onCancel: () => resolve(false),
          });
        });
        if (!confirmed) return;
      }

      setSaving(true);
      const errors: string[] = [];

      for (const key of PARAM_KEYS) {
        const val = String(values[key] ?? '');
        if (!val) continue;
        try {
          await paramsApi.update(key, val);
        } catch {
          errors.push(key);
        }
      }

      if (errors.length > 0) {
        message.warning(`部分參數儲存失敗：${errors.join(', ')}`);
      } else {
        message.success('設定已儲存');
        setOriginalDimension(newDim);
      }
    } catch {
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    form.setFieldsValue({ ...DEFAULTS });
  };

  const renderModelSelect = (placeholder: string) => {
    if (ollamaModels.length > 0) {
      return (
        <Select
          showSearch
          placeholder={placeholder}
          loading={ollamaLoading}
          options={ollamaModels.map((m) => ({ label: m, value: m }))}
          filterOption={(input, option) =>
            (option?.label as string)?.toLowerCase().includes(input.toLowerCase()) ?? false
          }
        />
      );
    }
    return <Input placeholder={placeholder} />;
  };

  return (
    <Drawer
      title={
        <Space>
          <SettingOutlined />
          NL 查詢模型設置
        </Space>
      }
      placement="right"
      width={480}
      open={open}
      onClose={onClose}
      extra={
        <Space>
          <Button onClick={handleReset} disabled={loading || saving}>
            重置預設
          </Button>
          <Button type="primary" onClick={handleSave} loading={saving} disabled={loading}>
            儲存
          </Button>
        </Space>
      }
    >
      <Spin spinning={loading}>
        <Form form={form} layout="vertical" initialValues={DEFAULTS}>
          {/* ─── Embedding 設置 ─── */}
          <Divider titlePlacement="left" plain>
            <Space>
              <SettingOutlined />
              <Text strong>Embedding 設置</Text>
            </Space>
          </Divider>

          <Form.Item
            name="da.embedding_model"
            label="Embedding 模型"
            rules={[{ required: true, message: '請選擇 Embedding 模型' }]}
            tooltip="用於 Schema 與 Intent 向量化（Qdrant）"
          >
            {renderModelSelect('例如 bge-m3:latest')}
          </Form.Item>

          <Form.Item
            name="da.embedding_dimension"
            label="向量維度"
            rules={[{ required: true, message: '請輸入向量維度' }]}
            tooltip="修改此值會導致 Qdrant collection 不相容，需重建索引"
          >
            <InputNumber
              min={1}
              max={8192}
              step={1}
              precision={0}
              style={{ width: '100%' }}
              placeholder="1024"
            />
          </Form.Item>

          {/* ─── LLM 設置 ─── */}
          <Divider titlePlacement="left" plain>
            <Space>
              <RobotOutlined />
              <Text strong>LLM 設置</Text>
            </Space>
          </Divider>

          <Form.Item
            name="da.small_llm_model"
            label="小型 LLM"
            rules={[{ required: true, message: '請選擇小型 LLM' }]}
            tooltip="當意圖匹配置信度不足時，用於 NL 查詢翻譯"
          >
            {renderModelSelect('例如 mistral-nemo:12b')}
          </Form.Item>

          <Form.Item
            name="da.large_llm_model"
            label="大型 LLM"
            rules={[{ required: true, message: '請選擇大型 LLM' }]}
            tooltip="用於複雜跨表查詢規劃（規劃中）"
          >
            {renderModelSelect('例如 qwen3-coder:30b')}
          </Form.Item>

          {/* ─── 查詢參數 ─── */}
          <Divider titlePlacement="left" plain>
            <Space>
              <AimOutlined />
              <Text strong>查詢參數</Text>
            </Space>
          </Divider>

          <Form.Item
            name="intent.match_threshold"
            label="意圖匹配門檻"
            rules={[{ required: true, message: '請輸入門檻值' }]}
            tooltip="Qdrant 意圖搜尋的最低置信度（0.0 ~ 1.0）"
          >
            <InputNumber
              min={0}
              max={1}
              step={0.05}
              precision={2}
              style={{ width: '100%' }}
              placeholder="0.45"
            />
          </Form.Item>

          <Form.Item
            name="da.data_source"
            label="資料來源"
            rules={[{ required: true, message: '請選擇資料來源' }]}
            tooltip="Data Agent 查詢的資料來源切換"
          >
            <Select
              options={[
                { label: 'SAP', value: 'sap' },
                { label: 'Ragic', value: 'ragic' },
              ]}
            />
          </Form.Item>
        </Form>

        <Alert
          type="info"
          showIcon
          message="修改後 Data Agent 會在下次請求時自動載入新設定（快取 TTL 300 秒）。"
          style={{ marginTop: 16 }}
        />
      </Spin>
    </Drawer>
  );
}
