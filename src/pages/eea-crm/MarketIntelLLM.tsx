/**
 * @file        MarketIntelLLM.tsx
 * @description 市場觀察 LLM Provider/Model 設置（下拉選單）
 * @lastUpdate  2026-06-18
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import { Select, Button, Typography, App, Alert } from 'antd';
import { paramsApi, modelProviderApi } from '../../services/api';

const { Text } = Typography;

export default function MarketIntelLLM() {
  const { message } = App.useApp();
  const [providers, setProviders] = useState<string[]>([]);
  const [models, setModels] = useState<string[]>([]);
  const [selectedProvider, setSelectedProvider] = useState('deepseek');
  const [selectedModel, setSelectedModel] = useState('deepseek-v4-flash');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [provRes, paramProv, paramModel] = await Promise.all([
          modelProviderApi.list(),
          paramsApi.get('market_intel.llm_provider'),
          paramsApi.get('market_intel.llm_model'),
        ]);
        const provList = (provRes?.data?.data || [])
          .filter((p: any) => p.status === 'enabled')
          .map((p: any) => p.code || p._key);
        setProviders(provList);

        const allModels = (provRes?.data?.data || [])
          .filter((p: any) => p.status === 'enabled')
          .flatMap((p: any) => (p.models || []).map((m: any) => m.model_id));
        setModels([...new Set(allModels)]);

        const savedProv = paramProv?.data?.data?.param_value;
        if (savedProv) setSelectedProvider(savedProv);
        const savedModel = paramModel?.data?.data?.param_value;
        if (savedModel) setSelectedModel(savedModel);
      } catch { /* ignore */ }
      setLoading(false);
    })();
  }, []);

  const handleSave = async () => {
    try {
      await paramsApi.update('market_intel.llm_provider', selectedProvider);
      await paramsApi.update('market_intel.llm_model', selectedModel);
      message.success('市場觀察 LLM 設定已更新');
    } catch {
      message.error('儲存失敗');
    }
  };

  return (
    <div style={{ maxWidth: 480 }}>
      <Alert type="info" showIcon style={{ marginBottom: 16, fontSize: 12, padding: '8px 12px' }}
        message="設定市場觀察 AI 摘要使用的 LLM Provider 與 Model" />

      <div style={{ marginBottom: 16 }}>
        <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 4 }}>Provider</Text>
        <Select value={selectedProvider} onChange={setSelectedProvider}
          style={{ width: '100%' }} loading={loading}
          options={providers.map(p => ({ label: p, value: p }))} />
      </div>

      <div style={{ marginBottom: 16 }}>
        <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 4 }}>Model</Text>
        <Select value={selectedModel} onChange={setSelectedModel}
          style={{ width: '100%' }} loading={loading}
          options={models.map(m => ({ label: m, value: m }))} />
      </div>

      <Button type="primary" onClick={handleSave}>儲存設定</Button>
    </div>
  );
}
