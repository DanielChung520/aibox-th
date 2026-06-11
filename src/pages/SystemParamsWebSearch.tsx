/**
 * @file        上網設置 Tab
 * @description Web 搜索 API Key 配置：Serper / SerpAPI / ScraperAPI / Google CSE
 * @lastUpdate  2026-03-27 17:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import { Card, Switch, Input, Button, Space, Typography, App, Tag } from 'antd';
import { CheckCircleFilled, CloseCircleFilled, ReloadOutlined } from '@ant-design/icons';
import { paramsApi } from '../services/api';
import { useContentTokens } from '../contexts/AppThemeProvider';

const { Title } = Typography;

interface WebSearchProvider {
  key: string;
  name: string;
  description: string;
  enabledKey: string;
  apiKeyParamKey: string;
  extraKeys?: { key: string; label: string; placeholder: string }[];
  color: string;
}

const PROVIDERS: WebSearchProvider[] = [
  {
    key: 'serper',
    name: 'Serper.dev',
    description: '首選 · 便宜快速，支持答案框',
    enabledKey: 'web_search.serper_enabled',
    apiKeyParamKey: 'web_search.serper_api_key',
    color: '#3b82f6',
  },
  {
    key: 'serpapi',
    name: 'SerpAPI',
    description: '備用 · 功能完整，支持多類型結果',
    enabledKey: 'web_search.serpapi_enabled',
    apiKeyParamKey: 'web_search.serpapi_api_key',
    color: '#8b5cf6',
  },
  {
    key: 'scraper',
    name: 'ScraperAPI',
    description: '備用 · 大量爬取',
    enabledKey: 'web_search.scraper_enabled',
    apiKeyParamKey: 'web_search.scraper_api_key',
    color: '#f59e0b',
  },
  {
    key: 'google_cse',
    name: 'Google CSE',
    description: '最後備用 · 官方 API（需同時填 API Key 與 CX）',
    enabledKey: 'web_search.google_cse_enabled',
    apiKeyParamKey: 'web_search.google_cse_api_key',
    color: '#10b981',
    extraKeys: [
      { key: 'web_search.google_cse_cx', label: 'Search Engine ID (CX)', placeholder: 'e.g. 56c53c7b593564e30' },
    ],
  },
];

export default function SystemParamsWebSearch() {
  const contentTokens = useContentTokens();
  const { message } = App.useApp();
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
      response.data.data?.forEach((p: { param_key: string; param_value: string; param_type: string }) => {
        if (p.param_key.startsWith('web_search.')) {
          if (p.param_type === 'boolean') {
            data[p.param_key] = p.param_value;
          } else {
            data[p.param_key] = p.param_value;
          }
        }
      });
      setValues(data);
    } catch {
      message.error('載入失敗');
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = (key: string, checked: boolean) => {
    setValues((prev) => ({ ...prev, [key]: String(checked) }));
  };

  const handleInput = (key: string, val: string) => {
    setValues((prev) => ({ ...prev, [key]: val }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      for (const [key, val] of Object.entries(values)) {
        if (key.startsWith('web_search.')) {
          await paramsApi.update(key, val);
        }
      }
      message.success('保存成功');
    } catch {
      message.error('保存失敗');
    } finally {
      setSaving(false);
    }
  };

  const activeProviders = PROVIDERS.filter(
    (p) => values[p.enabledKey] === 'true'
  );

  return (
    <div style={{ padding: '0 0 24px' }}>
      <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <Title level={5} style={{ margin: 0 }}>上網搜索設置</Title>
          <div style={{ fontSize: 12, color: contentTokens.textSecondary, marginTop: 4 }}>
            配置 Web 搜索 API Key。系統會自動按優先級嘗試可用提供商（Serper &rarr; SerpAPI &rarr; ScraperAPI &rarr; Google CSE）。
            {activeProviders.length > 0 && (
              <Tag color="green" style={{ marginLeft: 8 }}>已啟用 {activeProviders.length} 個</Tag>
            )}
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

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))', gap: 16 }}>
        {PROVIDERS.map((provider) => {
          const enabled = values[provider.enabledKey] === 'true';
          return (
            <Card
              key={provider.key}
              size="small"
              style={{
                border: `1px solid ${enabled ? provider.color + '60' : contentTokens.colorBgBase}`,
                borderRadius: 8,
                opacity: loading ? 0.6 : 1,
              }}
              styles={{ body: { padding: 16 } }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 12 }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14, color: contentTokens.colorTextBase }}>
                    {provider.name}
                  </div>
                  <div style={{ fontSize: 12, color: contentTokens.textSecondary, marginTop: 2 }}>
                    {provider.description}
                  </div>
                </div>
                <Switch
                  checked={enabled}
                  onChange={(checked) => handleToggle(provider.enabledKey, checked)}
                  loading={loading}
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div>
                  <div style={{ fontSize: 12, color: contentTokens.textSecondary, marginBottom: 4 }}>
                    API Key
                  </div>
                  <Input.Password
                    value={values[provider.apiKeyParamKey] || ''}
                    onChange={(e) => handleInput(provider.apiKeyParamKey, e.target.value)}
                    placeholder="填入 API Key"
                    disabled={loading}
                    style={{ fontFamily: 'monospace', fontSize: 12 }}
                  />
                </div>

                {provider.extraKeys?.map((extra) => (
                  <div key={extra.key}>
                    <div style={{ fontSize: 12, color: contentTokens.textSecondary, marginBottom: 4 }}>
                      {extra.label}
                    </div>
                    <Input
                      value={values[extra.key] || ''}
                      onChange={(e) => handleInput(extra.key, e.target.value)}
                      placeholder={extra.placeholder}
                      disabled={loading}
                      style={{ fontFamily: 'monospace', fontSize: 12 }}
                    />
                  </div>
                ))}
              </div>

              {enabled && (
                <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 4, fontSize: 11 }}>
                  {values[provider.apiKeyParamKey] ? (
                    <CheckCircleFilled style={{ color: '#22c55e', fontSize: 12 }} />
                  ) : (
                    <CloseCircleFilled style={{ color: '#ef4444', fontSize: 12 }} />
                  )}
                  <span style={{ color: values[provider.apiKeyParamKey] ? '#22c55e' : '#ef4444' }}>
                    {values[provider.apiKeyParamKey] ? '已填寫 API Key' : '請填寫 API Key'}
                  </span>
                </div>
              )}
            </Card>
          );
        })}
      </div>

      <Card size="small" style={{ marginTop: 16, background: `${contentTokens.colorPrimary}08`, border: `1px solid ${contentTokens.colorPrimary}30` }}>
        <div style={{ fontSize: 12, color: contentTokens.textSecondary, lineHeight: 1.8 }}>
          <strong>優先級順序</strong>：Serper.dev &rarr; SerpAPI &rarr; ScraperAPI &rarr; Google CSE
          <br />
          當前啟用的提供商越多，搜索成功率越高。API Key 可至各服務官網申請：
          <br />
          &bull; <a href="https://serper.dev" target="_blank" rel="noopener noreferrer">Serper.dev</a>
          {' · '}
          &bull; <a href="https://serpapi.com" target="_blank" rel="noopener noreferrer">SerpAPI</a>
          {' · '}
          &bull; <a href="https://scraperapi.com" target="_blank" rel="noopener noreferrer">ScraperAPI</a>
          {' · '}
          &bull; <a href="https://console.cloud.google.com" target="_blank" rel="noopener noreferrer">Google CSE</a>
        </div>
      </Card>
    </div>
  );
}
