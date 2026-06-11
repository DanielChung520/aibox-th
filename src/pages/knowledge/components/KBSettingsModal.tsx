/**
 * @file        知識庫參數設置 Modal
 * @description 向量模型、維度、圖譜模型、生成 Token 上限的設置
 * @lastUpdate  2026-03-26 22:49:44
 * @author      Daniel Chung
 * @version     1.1.0
 */

import { useState, useEffect } from 'react';
import { Modal, Form, Select, InputNumber, App } from 'antd';
import { paramsApi } from '../../../services/api';

interface KBSettingsModalProps {
  open: boolean;
  onCancel: () => void;
}

interface OllamaModel {
  name: string;
}

interface KnowledgeParams {
  embedding_model: string;
  embedding_dimension: number;
  graph_model: string;
  graph_num_predict: number;
}

export default function KBSettingsModal({ open, onCancel }: KBSettingsModalProps) {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [embeddingModels, setEmbeddingModels] = useState<string[]>([]);
  const [loadedParams, setLoadedParams] = useState<KnowledgeParams | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    paramsApi.list()
      .then(res => {
        const params: KnowledgeParams = {
          embedding_model: 'bge-m3:latest',
          embedding_dimension: 1024,
          graph_model: 'llama3.2:latest',
          graph_num_predict: 4096,
        };
        for (const p of res.data.data || []) {
          if (p.param_key === 'knowledge.embedding_model') params.embedding_model = p.param_value;
          if (p.param_key === 'knowledge.embedding_dimension') params.embedding_dimension = parseInt(p.param_value, 10);
          if (p.param_key === 'knowledge.graph_model') params.graph_model = p.param_value;
          if (p.param_key === 'knowledge.graph_num_predict') params.graph_num_predict = parseInt(p.param_value, 10);
        }
        setLoadedParams(params);
      })
      .catch(() => message.error('載入參數失敗'))
      .finally(() => setLoading(false));

    fetch('http://localhost:11434/api/tags')
      .then(res => res.ok ? res.json() : null)
      .then((data: { models: OllamaModel[] } | null) => {
        if (!data) return;
        const all = (data.models || []).map(m => m.name);
        setOllamaModels(all);
        setEmbeddingModels(all.filter(n => n.includes('embed') || n.includes('bge') || n.includes('nomic')));
      })
      .catch(() => {});
  }, [open]);

  useEffect(() => {
    if (loadedParams) {
      form.setFieldsValue(loadedParams);
    }
  }, [loadedParams, form]);

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      await Promise.all([
        paramsApi.update('knowledge.embedding_model', values.embedding_model),
        paramsApi.update('knowledge.embedding_dimension', String(values.embedding_dimension)),
        paramsApi.update('knowledge.graph_model', values.graph_model),
        paramsApi.update('knowledge.graph_num_predict', String(values.graph_num_predict)),
      ]);
      message.success('參數已儲存');
      onCancel();
    } catch {
      message.error('儲存失敗');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title="知識庫參數設置"
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      confirmLoading={saving}
      width={480}
    >
      <Form form={form} layout="vertical" disabled={loading}>
        <Form.Item name="embedding_model" label="向量模型" rules={[{ required: true }]}>
          <Select placeholder="選擇向量模型">
            {embeddingModels.map(m => (
              <Select.Option key={m} value={m}>{m}</Select.Option>
            ))}
          </Select>
        </Form.Item>
        <Form.Item name="embedding_dimension" label="向量維度" rules={[{ required: true }]}>
          <InputNumber min={128} max={4096} step={128} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="graph_model" label="圖譜模型" rules={[{ required: true }]}>
          <Select placeholder="選擇圖譜抽取模型">
            {ollamaModels.map(m => (
              <Select.Option key={m} value={m}>{m}</Select.Option>
            ))}
          </Select>
        </Form.Item>
        <Form.Item name="graph_num_predict" label="圖譜生成 Token 上限" rules={[{ required: true }]} tooltip="LLM 單次最大輸出 token 數，-1 為無限制">
          <InputNumber min={-1} max={32768} step={512} style={{ width: '100%' }} />
        </Form.Item>
      </Form>
    </Modal>
  );
}
