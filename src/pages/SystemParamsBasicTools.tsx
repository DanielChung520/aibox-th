import { useState, useEffect } from 'react';
import { Card, Switch, Input, Button, Space, Typography, App, Tag, Divider } from 'antd';
import { CheckCircleFilled, CloseCircleFilled, ReloadOutlined } from '@ant-design/icons';
import { paramsApi } from '../services/api';
import { useContentTokens } from '../contexts/AppThemeProvider';

const { Title } = Typography;

interface ProviderCard {
  key: string;
  name: string;
  description: string;
  category: 'web_search' | 'weather';
  enabledKey: string;
  apiKeyParamKey: string;
  extraKeys?: { key: string; label: string; placeholder: string }[];
  color: string;
  docsUrl?: string;
}

const PROVIDERS: ProviderCard[] = [
  {
    key: 'serper',
    name: 'Serper.dev',
    description: '首選 · 便宜快速，支持答案框',
    category: 'web_search',
    enabledKey: 'web_search.serper_enabled',
    apiKeyParamKey: 'web_search.serper_api_key',
    color: '#3b82f6',
    docsUrl: 'https://serper.dev',
  },
  {
    key: 'serpapi',
    name: 'SerpAPI',
    description: '備用 · 功能完整，支持多類型結果',
    category: 'web_search',
    enabledKey: 'web_search.serpapi_enabled',
    apiKeyParamKey: 'web_search.serpapi_api_key',
    color: '#8b5cf6',
    docsUrl: 'https://serpapi.com',
  },
  {
    key: 'scraper',
    name: 'ScraperAPI',
    description: '備用 · 大量爬取',
    category: 'web_search',
    enabledKey: 'web_search.scraper_enabled',
    apiKeyParamKey: 'web_search.scraper_api_key',
    color: '#f59e0b',
    docsUrl: 'https://scraperapi.com',
  },
  {
    key: 'google_cse',
    name: 'Google CSE',
    description: '最後備用 · 官方 API（需同時填 API Key 與 CX）',
    category: 'web_search',
    enabledKey: 'web_search.google_cse_enabled',
    apiKeyParamKey: 'web_search.google_cse_api_key',
    color: '#10b981',
    extraKeys: [
      { key: 'web_search.google_cse_cx', label: 'Search Engine ID (CX)', placeholder: 'e.g. 56c53c7b593564e30' },
    ],
    docsUrl: 'https://console.cloud.google.com',
  },
  {
    key: 'openweathermap',
    name: 'OpenWeatherMap',
    description: '天氣查詢 · 當前天氣與預報',
    category: 'weather',
    enabledKey: 'weather.openweathermap_enabled',
    apiKeyParamKey: 'weather.openweathermap_api_key',
    color: '#ec4899',
    docsUrl: 'https://openweathermap.org/api',
  },
];

export default function SystemParamsBasicTools() {
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
        if (p.param_key.startsWith('web_search.') || p.param_key.startsWith('weather.')) {
          data[p.param_key] = p.param_value;
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
    setValues(prev => ({ ...prev, [key]: String(checked) }));
  };

  const handleInput = (key: string, val: string) => {
    setValues(prev => ({ ...prev, [key]: val }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      for (const [key, val] of Object.entries(values)) {
        if (key.startsWith('web_search.') || key.startsWith('weather.')) {
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

  const webSearchProviders = PROVIDERS.filter(p => p.category === 'web_search');
  const weatherProviders = PROVIDERS.filter(p => p.category === 'weather');
  const activeWebSearch = webSearchProviders.filter(p => values[p.enabledKey] === 'true');
  const activeWeather = weatherProviders.filter(p => values[p.enabledKey] === 'true');

  const renderCard = (provider: ProviderCard) => {
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
            onChange={checked => handleToggle(provider.enabledKey, checked)}
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
              onChange={e => handleInput(provider.apiKeyParamKey, e.target.value)}
              placeholder="填入 API Key"
              disabled={loading}
              style={{ fontFamily: 'monospace', fontSize: 12 }}
            />
          </div>

          {provider.extraKeys?.map(extra => (
            <div key={extra.key}>
              <div style={{ fontSize: 12, color: contentTokens.textSecondary, marginBottom: 4 }}>
                {extra.label}
              </div>
              <Input
                value={values[extra.key] || ''}
                onChange={e => handleInput(extra.key, e.target.value)}
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
  };

  return (
    <div style={{ padding: '0 0 24px' }}>
      <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <Title level={5} style={{ margin: 0 }}>基礎工具</Title>
          <div style={{ fontSize: 12, color: contentTokens.textSecondary, marginTop: 4 }}>
            配置系統聊天所使用的基礎工具，包括上網搜索與天氣查詢。已啟用：上網 {activeWebSearch.length} 個、天氣 {activeWeather.length} 個
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

      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <Title level={5} style={{ margin: 0 }}>上網搜索</Title>
          {activeWebSearch.length > 0 && <Tag color="blue">已啟用 {activeWebSearch.length} 個</Tag>}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))', gap: 16 }}>
          {webSearchProviders.map(renderCard)}
        </div>
        <Card size="small" style={{ marginTop: 12, background: `${contentTokens.colorPrimary}08`, border: `1px solid ${contentTokens.colorPrimary}30` }}>
          <div style={{ fontSize: 12, color: contentTokens.textSecondary, lineHeight: 1.8 }}>
            <strong>優先級順序</strong>：Serper.dev &rarr; SerpAPI &rarr; ScraperAPI &rarr; Google CSE
            <br />
            當前啟用的提供商越多，搜索成功率越高。
            {' · '}
            {webSearchProviders.map(p => (
              <span key={p.key}>
                {p.docsUrl && <a href={p.docsUrl} target="_blank" rel="noopener noreferrer">{p.name}</a>}
                {' · '}
              </span>
            ))}
          </div>
        </Card>
      </div>

      <Divider style={{ margin: '8px 0' }} />

      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <Title level={5} style={{ margin: 0 }}>天氣查詢</Title>
          {activeWeather.length > 0 && <Tag color="pink">已啟用 {activeWeather.length} 個</Tag>}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))', gap: 16 }}>
          {weatherProviders.map(renderCard)}
        </div>
        <Card size="small" style={{ marginTop: 12, background: `${contentTokens.colorPrimary}08`, border: `1px solid ${contentTokens.colorPrimary}30` }}>
          <div style={{ fontSize: 12, color: contentTokens.textSecondary, lineHeight: 1.8 }}>
            天氣工具支援當前天氣查詢與未來預報。API Key 已預設填入 OpenWeatherMap Key，確認啟用開關後即可使用。
            {' · '}
            <a href="https://openweathermap.org/api" target="_blank" rel="noopener noreferrer">申請 API Key</a>
          </div>
        </Card>
      </div>
    </div>
  );
}
