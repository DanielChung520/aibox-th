/**
 * @file        FloatingAssistantSettings.tsx
 * @description 浮動助手樣式配置
 * @lastUpdate  2026-04-18 19:12:57
 * @author      Daniel Chung
 * @version     3.0.0
 */

import { useState, useEffect } from 'react';
import { App, Card, Form, InputNumber, Slider, Switch, Button, Typography, ColorPicker, Space, Select, Collapse, theme, Tooltip } from 'antd';
import { SaveOutlined, ReloadOutlined, QuestionCircleOutlined } from '@ant-design/icons';
import { paramsApi, SystemParam, modelProviderApi, ModelProvider } from '../services/api';
import { FloatingAssistantConfig, defaultConfig } from '../components/FloatingAssistant/types';

const { Title } = Typography;

const CONFIG_KEY = 'floating_assistant.';
const NUMBER_FIELDS: Array<keyof FloatingAssistantConfig> = [
  'modalWidth',
  'modalHeight',
  'blurIntensity',
  'glassOpacity',
  'saturation',
  'borderRadius',
];
const colorPickerProps = { format: 'rgb' as const, showText: true };

interface ColorValueLike {
  toRgbString: () => string;
}

const isColorValue = (value: unknown): value is ColorValueLike => {
  return typeof value === 'object' && value !== null && 'toRgbString' in value && typeof value.toRgbString === 'function';
};

const toColorString = (value: unknown, fallback: string): string => {
  if (isColorValue(value)) {
    return value.toRgbString();
  }

  if (typeof value === 'string' && value.trim() !== '') {
    return value;
  }

  return fallback;
};

const toNumberValue = (value: unknown, fallback: number): number => {
  if (typeof value === 'number' && !Number.isNaN(value)) {
    return value;
  }

  const parsedValue = Number.parseInt(String(value ?? ''), 10);
  return Number.isNaN(parsedValue) ? fallback : parsedValue;
};

const toBooleanValue = (value: unknown, fallback: boolean): boolean => {
  if (typeof value === 'boolean') {
    return value;
  }

  if (value === 'true') {
    return true;
  }

  if (value === 'false') {
    return false;
  }

  return fallback;
};

const normalizeConfig = (values: Partial<Record<keyof FloatingAssistantConfig, unknown>>): FloatingAssistantConfig => {
  const normalizedConfig: FloatingAssistantConfig = { ...defaultConfig };
  const normalizedConfigRecord = normalizedConfig as Record<keyof FloatingAssistantConfig, unknown>;

  (Object.keys(defaultConfig) as Array<keyof FloatingAssistantConfig>).forEach((key) => {
    const value = values[key];

    if (key === 'enabled') {
      normalizedConfigRecord[key] = toBooleanValue(value, defaultConfig.enabled);
      return;
    }

    if (NUMBER_FIELDS.includes(key)) {
      normalizedConfigRecord[key] = toNumberValue(value, defaultConfig[key] as number);
      return;
    }

    normalizedConfigRecord[key] = toColorString(value, defaultConfig[key] as string);
  });

  return normalizedConfig;
};

const defaultAiqConfig = {
  'aiq.signal_debounce_ms': 1000,
  'aiq.signal_max_retry_ms': 30000,
  'aiq.signal_retry_backoff': 2,
  'aiq.max_signals_per_push': 100,
  'aiq.max_contexts': 500,
  'aiq.context_ttl_seconds': 3600,
};

export default function FloatingAssistantSettings() {
  const { message } = App.useApp();
  const { token } = theme.useToken();
  const [form] = Form.useForm<FloatingAssistantConfig & typeof defaultAiqConfig>();
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [providers, setProviders] = useState<ModelProvider[]>([]);
  const [chatModel, setChatModel] = useState<string>('');

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const [paramsRes, providersRes] = await Promise.all([
        paramsApi.list(),
        modelProviderApi.list(),
      ]);
      const data = paramsRes.data.data || [];
      
      const activeProviders = (providersRes.data.data || []).filter(
        (p: ModelProvider) => p.status === 'enabled'
      );
      setProviders(activeProviders);
      
      const config: Record<string, unknown> = {};
      const aiqConfig: Record<string, unknown> = { ...defaultAiqConfig };
      
      data.forEach((param: SystemParam) => {
        if (param.param_key === 'floating_assistant.chatModel') {
          setChatModel(param.param_value || '');
        } else if (param.param_key.startsWith(CONFIG_KEY)) {
          const key = param.param_key.replace(CONFIG_KEY, '');
          if (key === 'enabled') {
            config[key] = param.param_value === 'true';
          } else if (NUMBER_FIELDS.includes(key as keyof FloatingAssistantConfig)) {
            config[key] = Number.parseInt(param.param_value, 10);
          } else {
            config[key] = param.param_value;
          }
        } else if (param.param_key.startsWith('aiq.')) {
          aiqConfig[param.param_key] = Number.parseInt(param.param_value, 10);
        }
      });
      
      const mergedConfig = normalizeConfig(config as Partial<Record<keyof FloatingAssistantConfig, unknown>>);
      form.setFieldsValue({ ...mergedConfig, ...aiqConfig } as any);
      applyStylesToCss(mergedConfig);
    } catch {
      message.error('獲取配置失敗');
    } finally {
      setLoading(false);
    }
  };

  const applyStylesToCss = (cfg: Partial<Record<keyof FloatingAssistantConfig, unknown>>) => {
    const root = document.documentElement;
    const normalizedConfig = normalizeConfig(cfg);
    
    root.style.setProperty('--fa-modal-width', `${normalizedConfig.modalWidth}px`);
    root.style.setProperty('--fa-modal-height', `${normalizedConfig.modalHeight}px`);
    root.style.setProperty('--fa-blur-intensity', `${normalizedConfig.blurIntensity}px`);
    root.style.setProperty('--fa-glass-opacity', `${normalizedConfig.glassOpacity / 100}`);
    root.style.setProperty('--fa-saturation', `${normalizedConfig.saturation}%`);
    root.style.setProperty('--fa-border-radius', `${normalizedConfig.borderRadius}px`);
    root.style.setProperty('--fa-modal-bg', normalizedConfig.modalBg);
    root.style.setProperty('--fa-header-bg', normalizedConfig.headerBg);
    root.style.setProperty('--fa-header-border', `1px solid ${normalizedConfig.headerBorderColor}`);
    root.style.setProperty('--fa-title-color', normalizedConfig.titleColor);
    root.style.setProperty('--fa-close-btn-color', normalizedConfig.closeBtnColor);
    root.style.setProperty('--fa-body-bg', normalizedConfig.bodyBg);
    root.style.setProperty('--fa-footer-bg', normalizedConfig.footerBg);
    root.style.setProperty('--fa-footer-border', `1px solid ${normalizedConfig.footerBorderColor}`);
    root.style.setProperty('--fa-input-bg', normalizedConfig.inputBg);
    root.style.setProperty('--fa-input-text-color', normalizedConfig.inputTextColor);
    root.style.setProperty('--fa-input-border-color', normalizedConfig.inputBorderColor);
    root.style.setProperty('--fa-input-placeholder-color', normalizedConfig.inputPlaceholderColor);
    root.style.setProperty('--fa-send-btn-bg', normalizedConfig.sendBtnBg);
    root.style.setProperty('--fa-send-btn-color', normalizedConfig.sendBtnColor);
    root.style.setProperty('--fa-bubble-ai-bg', normalizedConfig.bubbleAiBg);
    root.style.setProperty('--fa-bubble-ai-text-color', normalizedConfig.bubbleAiTextColor);
    root.style.setProperty('--fa-bubble-user-bg', normalizedConfig.bubbleUserBg);
    root.style.setProperty('--fa-bubble-user-text-color', normalizedConfig.bubbleUserTextColor);
    root.style.setProperty('--fa-button-bg', normalizedConfig.buttonBg);
    root.style.setProperty('--fa-button-icon-color', normalizedConfig.buttonIconColor);
    root.style.setProperty('--fa-button-shadow-color', normalizedConfig.buttonShadowColor);
    root.style.setProperty('--fa-button-pulse-color', normalizedConfig.buttonPulseColor);
    root.style.setProperty('--fa-shadow-color', normalizedConfig.shadowColor);
    root.style.setProperty('--fa-shadow-inner-color', normalizedConfig.shadowInnerColor);
    root.style.setProperty('--fa-gradient-start', normalizedConfig.gradientStart);
    root.style.setProperty('--fa-gradient-radial-1', normalizedConfig.gradientRadial1);
    root.style.setProperty('--fa-gradient-radial-2', normalizedConfig.gradientRadial2);
    root.style.setProperty('--fa-resize-handle-color', normalizedConfig.resizeHandleColor);
    root.style.setProperty('--fa-mermaid-bg', normalizedConfig.mermaidBg);
    root.style.setProperty('--fa-mermaid-text-color', normalizedConfig.mermaidTextColor);
    root.style.setProperty('--fa-link-color', normalizedConfig.linkColor);
    root.style.setProperty('--fa-quote-border-color', normalizedConfig.quoteBorderColor);
    root.style.setProperty('--fa-warning-color-dark', normalizedConfig.warningColorDark);
    root.style.setProperty('--fa-warning-color-light', normalizedConfig.warningColorLight);
  };

  useEffect(() => {
    fetchConfig();
  }, []);

  const handleSave = async () => {
    try {
      const values = form.getFieldsValue();
      const normalizedValues = normalizeConfig(values as Partial<Record<keyof FloatingAssistantConfig, unknown>>);
      setSaving(true);

      const promises = Object.entries(normalizedValues).map(([key, value]) => {
        let strValue: string;

        if (NUMBER_FIELDS.includes(key as keyof FloatingAssistantConfig)) {
          strValue = String(value ?? '');
        } else if (key === 'enabled') {
          strValue = String(value ?? 'true');
        } else {
          strValue = toColorString(value, defaultConfig[key as keyof FloatingAssistantConfig] as string);
        }

        return paramsApi.update(CONFIG_KEY + key, strValue);
      });

      Object.keys(defaultAiqConfig).forEach((key) => {
        const val = values[key as keyof typeof defaultAiqConfig];
        if (val !== undefined && val !== null) {
          promises.push(paramsApi.update(key, String(val)));
        }
      });

      await Promise.all(promises);
      await paramsApi.update('floating_assistant.chatModel', chatModel);
      
      const formValues = { ...normalizedValues };
      Object.keys(defaultAiqConfig).forEach((key) => {
        (formValues as any)[key] = values[key as keyof typeof defaultAiqConfig];
      });
      
      form.setFieldsValue(formValues as any);
      applyStylesToCss(normalizedValues);
      window.dispatchEvent(new CustomEvent('floating-assistant-config-update', { detail: normalizedValues }));
      message.success('保存成功');
    } catch {
      message.error('保存失敗');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    form.setFieldsValue({ ...defaultConfig, ...defaultAiqConfig } as any);
    applyStylesToCss(defaultConfig);
    window.dispatchEvent(new CustomEvent('floating-assistant-config-update', { detail: defaultConfig }));
  };

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving}>
          保存
        </Button>
        <Button icon={<ReloadOutlined />} onClick={handleReset} style={{ marginLeft: 8 }}>
          重置
        </Button>
      </div>

      <Card loading={loading} style={{ background: token.colorBgContainer }}>
        <Form form={form} layout="vertical" initialValues={{ ...defaultConfig, ...defaultAiqConfig }}>
          <Collapse defaultActiveKey={['basic']} ghost>
            <Collapse.Panel header={<Title level={5} style={{ margin: 0 }}>基本設置</Title>} key="basic">
              <Space size="large" style={{ display: 'flex', flexWrap: 'wrap' }}>
                <Form.Item name="enabled" label="啟用浮動助手" valuePropName="checked">
                  <Switch />
                </Form.Item>
                <Form.Item label="聊天模型">
                  <Select
                    value={chatModel || undefined}
                    onChange={(val: string) => setChatModel(val)}
                    placeholder="選擇 AI 模型"
                    style={{ width: 320 }}
                    allowClear
                    options={providers.flatMap((p) =>
                      (p.models || [])
                        .filter((m) => m.status === 'enabled')
                        .map((m) => ({
                          label: `${p.name} / ${m.display_name || m.name}`,
                          value: `${p.code}:${m.model_id}`,
                        }))
                    )}
                  />
                </Form.Item>
              </Space>
            </Collapse.Panel>

            <Collapse.Panel header={<Title level={5} style={{ margin: 0 }}>窗口尺寸</Title>} key="size">
              <Space size="large" style={{ display: 'flex', flexWrap: 'wrap' }}>
                <Form.Item name="modalWidth" label="寬度 (px)">
                  <InputNumber min={280} max={800} style={{ width: 100 }} />
                </Form.Item>
                <Form.Item name="modalHeight" label="高度 (px)">
                  <InputNumber min={300} max={900} style={{ width: 100 }} />
                </Form.Item>
                <Form.Item name="borderRadius" label="圓角 (px)">
                  <Slider min={0} max={24} style={{ width: 150 }} marks={{ 0: '0', 12: '12', 24: '24' }} />
                </Form.Item>
              </Space>
            </Collapse.Panel>

            <Collapse.Panel header={<Title level={5} style={{ margin: 0 }}>磨砂效果</Title>} key="glass">
              <Space size="large" style={{ display: 'flex', flexWrap: 'wrap' }}>
                <Form.Item name="blurIntensity" label="模糊強度">
                  <Slider min={0} max={40} style={{ width: 150 }} marks={{ 0: '0', 20: '20', 40: '40' }} />
                </Form.Item>
                <Form.Item name="glassOpacity" label="透明度 (%)">
                  <Slider min={20} max={100} style={{ width: 150 }} marks={{ 20: '20%', 50: '50%', 100: '100%' }} />
                </Form.Item>
                <Form.Item name="saturation" label="飽和度 (%)">
                  <Slider min={100} max={200} style={{ width: 150 }} marks={{ 100: '100%', 150: '150%', 200: '200%' }} />
                </Form.Item>
              </Space>
            </Collapse.Panel>

            <Collapse.Panel header={<Title level={5} style={{ margin: 0 }}>窗口顏色</Title>} key="colors">
              <Space size="large" style={{ display: 'flex', flexWrap: 'wrap', marginBottom: 16 }}>
                <Form.Item name="modalBg" label="窗口背景" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="headerBg" label="Header 背景" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="headerBorderColor" label="Header 邊框" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="titleColor" label="標題顏色" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
              </Space>
              <Space size="large" style={{ display: 'flex', flexWrap: 'wrap' }}>
                <Form.Item name="closeBtnColor" label="關閉按鈕" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="bodyBg" label="內容區背景" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="footerBg" label="Footer 背景" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="footerBorderColor" label="Footer 邊框" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
              </Space>
            </Collapse.Panel>

            <Collapse.Panel header={<Title level={5} style={{ margin: 0 }}>輸入框</Title>} key="input">
              <Space size="large" style={{ display: 'flex', flexWrap: 'wrap' }}>
                <Form.Item name="inputBg" label="輸入框背景" trigger="onChange">
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="inputTextColor" label="輸入框文字" trigger="onChange">
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="inputBorderColor" label="輸入框邊框" trigger="onChange">
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="inputPlaceholderColor" label="輸入框佔位" trigger="onChange">
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
              </Space>
            </Collapse.Panel>

            <Collapse.Panel header={<Title level={5} style={{ margin: 0 }}>按鈕</Title>} key="button">
              <Space size="large" style={{ display: 'flex', flexWrap: 'wrap', marginBottom: 16 }}>
                <Form.Item name="sendBtnBg" label="送出按鈕背景" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="sendBtnColor" label="送出按鈕文字" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="buttonBg" label="浮動按鈕背景" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
              </Space>
              <Space size="large" style={{ display: 'flex', flexWrap: 'wrap' }}>
                <Form.Item name="buttonIconColor" label="浮動按鈕圖示" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="buttonShadowColor" label="浮動按鈕陰影" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="buttonPulseColor" label="浮動按鈕動畫" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
              </Space>
            </Collapse.Panel>

            <Collapse.Panel header={<Title level={5} style={{ margin: 0 }}>氣泡</Title>} key="bubble">
              <Space size="large" style={{ display: 'flex', flexWrap: 'wrap' }}>
                <Form.Item name="bubbleAiBg" label="AI 氣泡背景" trigger="onChange">
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="bubbleAiTextColor" label="AI 氣泡文字" trigger="onChange">
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="bubbleUserBg" label="用戶氣泡背景" trigger="onChange">
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="bubbleUserTextColor" label="用戶氣泡文字" trigger="onChange">
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
              </Space>
            </Collapse.Panel>

            <Collapse.Panel header={<Title level={5} style={{ margin: 0 }}>陰影與裝飾</Title>} key="shadow">
              <Space size="large" style={{ display: 'flex', flexWrap: 'wrap', marginBottom: 16 }}>
                <Form.Item name="shadowColor" label="窗口陰影" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="shadowInnerColor" label="內部光澤" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="resizeHandleColor" label="調整大小控制點" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
              </Space>
              <Space size="large" style={{ display: 'flex', flexWrap: 'wrap' }}>
                <Form.Item name="gradientStart" label="漸層起始" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="gradientRadial1" label="漸層放射1" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="gradientRadial2" label="漸層放射2" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
              </Space>
            </Collapse.Panel>

            <Collapse.Panel header={<Title level={5} style={{ margin: 0 }}>Markdown / Mermaid</Title>} key="markdown">
              <Space size="large" style={{ display: 'flex', flexWrap: 'wrap', marginBottom: 16 }}>
                <Form.Item name="mermaidBg" label="Mermaid 背景" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="mermaidTextColor" label="Mermaid 文字" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="linkColor" label="連結顏色" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
              </Space>
              <Space size="large" style={{ display: 'flex', flexWrap: 'wrap' }}>
                <Form.Item name="quoteBorderColor" label="引用框邊框" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="warningColorDark" label="警告 (深色)" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
                <Form.Item name="warningColorLight" label="警告 (淺色)" trigger="onChange" style={{ marginBottom: 0 }}>
                  <ColorPicker {...colorPickerProps} />
                </Form.Item>
              </Space>
            </Collapse.Panel>

            <Collapse.Panel header={<Title level={5} style={{ margin: 0 }}>信號參數 (AIQ)</Title>} key="aiq">
              <Space size="large" style={{ display: 'flex', flexWrap: 'wrap', marginBottom: 16 }}>
                <Form.Item
                  name="aiq.signal_debounce_ms"
                  label={
                    <Space>
                      信號防抖延遲 (ms)
                      <Tooltip title="兩次信號之間的防抖時間，避免過於頻繁的觸發"><QuestionCircleOutlined /></Tooltip>
                    </Space>
                  }
                  style={{ marginBottom: 0 }}
                >
                  <InputNumber min={0} step={100} style={{ width: 140 }} />
                </Form.Item>
                <Form.Item
                  name="aiq.signal_max_retry_ms"
                  label={
                    <Space>
                      最大重試延遲 (ms)
                      <Tooltip title="信號推送失敗時的最大重試時間上限"><QuestionCircleOutlined /></Tooltip>
                    </Space>
                  }
                  style={{ marginBottom: 0 }}
                >
                  <InputNumber min={0} step={1000} style={{ width: 140 }} />
                </Form.Item>
                <Form.Item
                  name="aiq.signal_retry_backoff"
                  label={
                    <Space>
                      重試倍率
                      <Tooltip title="重試的退避倍率（指數退避）"><QuestionCircleOutlined /></Tooltip>
                    </Space>
                  }
                  style={{ marginBottom: 0 }}
                >
                  <InputNumber min={1} step={0.1} style={{ width: 140 }} />
                </Form.Item>
              </Space>
              <Space size="large" style={{ display: 'flex', flexWrap: 'wrap' }}>
                <Form.Item
                  name="aiq.max_signals_per_push"
                  label={
                    <Space>
                      單次推送信號上限
                      <Tooltip title="一次推送請求中最多包含的信號數量"><QuestionCircleOutlined /></Tooltip>
                    </Space>
                  }
                  style={{ marginBottom: 0 }}
                >
                  <InputNumber min={1} max={1000} style={{ width: 140 }} />
                </Form.Item>
                <Form.Item
                  name="aiq.max_contexts"
                  label={
                    <Space>
                      最大上下文數量
                      <Tooltip title="同時保留的最大上下文數量"><QuestionCircleOutlined /></Tooltip>
                    </Space>
                  }
                  style={{ marginBottom: 0 }}
                >
                  <InputNumber min={1} max={5000} style={{ width: 140 }} />
                </Form.Item>
                <Form.Item
                  name="aiq.context_ttl_seconds"
                  label={
                    <Space>
                      上下文存活時間 (秒)
                      <Tooltip title="上下文在記憶體中保留的時間（秒）"><QuestionCircleOutlined /></Tooltip>
                    </Space>
                  }
                  style={{ marginBottom: 0 }}
                >
                  <InputNumber min={0} step={60} style={{ width: 140 }} />
                </Form.Item>
              </Space>
            </Collapse.Panel>

          </Collapse>
        </Form>
      </Card>
    </div>
  );
}
