/**
 * @file        主題標記編輯器
 * @description 渲染外殼與內容的 tokens 表單，用於 ThemeTemplateManagement
 * @lastUpdate  2026-03-25 15:07:58
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { Form, Input, InputNumber, Slider, ColorPicker, Typography, theme } from 'antd';
import type { ShellTokens, ContentTokens } from '../services/api';

const { Text } = Typography;

type ShellColorKey = Extract<keyof ShellTokens, string>;
type ContentColorKey = Extract<keyof ContentTokens, string>;

const SHELL_COLOR_FIELDS: { key: ShellColorKey; label: string }[] = [
  { key: 'siderBg', label: '側邊欄背景' },
  { key: 'headerBg', label: '頂部列背景' },
  { key: 'menuItemColor', label: '選單項目文字' },
  { key: 'menuItemHoverBg', label: '選單項目懸停背景' },
  { key: 'menuItemSelectedBg', label: '選單項目選中背景' },
  { key: 'menuItemSelectedColor', label: '選單項目選中文字' },
  { key: 'logoColor', label: 'Logo 顏色' },
  { key: 'siderBorder', label: '側邊欄邊框' },
];

const SHELL_SHADOW_FIELDS: { key: ShellColorKey; label: string }[] = [
  { key: 'headerShadow', label: '頂部列陰影' },
  { key: 'siderShadow', label: '側邊欄陰影' },
];

const CONTENT_COLOR_FIELDS: { key: ContentColorKey; label: string; group: string }[] = [
  { key: 'colorPrimary', label: '主題色', group: '品牌顏色' },
  { key: 'colorSuccess', label: '成功色', group: '品牌顏色' },
  { key: 'colorWarning', label: '警告色', group: '品牌顏色' },
  { key: 'colorError', label: '錯誤色', group: '品牌顏色' },
  { key: 'colorInfo', label: '資訊色', group: '品牌顏色' },
  { key: 'colorBgBase', label: '內容背景', group: '背景顏色' },
  { key: 'colorTextBase', label: '主文字', group: '背景顏色' },
  { key: 'textSecondary', label: '次要文字', group: '背景顏色' },
  { key: 'pageBg', label: '頁面底層背景 (Layout)', group: '背景顏色' },
  { key: 'contentBg', label: '內容頁容器背景 (Content)', group: '背景顏色' },
  { key: 'containerBg', label: '元件容器背景 (Table/Card/Tabs)', group: '背景顏色' },
  { key: 'tableExpandedRowBg', label: '表格展開列背景', group: '表格' },
  { key: 'tableHeaderBg', label: '表格標題背景', group: '表格' },
  { key: 'tableRowHoverBg', label: '表格列懸停背景', group: '表格' },
  { key: 'chatInputBg', label: '聊天輸入框背景', group: '聊天' },
  { key: 'chatUserBubble', label: '聊天使用者氣泡', group: '聊天' },
  { key: 'chatAssistantBubble', label: '聊天助理氣泡', group: '聊天' },
  { key: 'iconDefault', label: '圖示預設顏色', group: '圖示' },
  { key: 'iconHover', label: '圖示懸停顏色', group: '圖示' },
  { key: 'btnClear', label: '清除按鈕', group: '按鈕' },
  { key: 'btnClearHover', label: '清除按鈕懸停', group: '按鈕' },
  { key: 'btnSend', label: '發送按鈕', group: '按鈕' },
  { key: 'btnSendHover', label: '發送按鈕懸停', group: '按鈕' },
  { key: 'btnText', label: '按鈕文字', group: '按鈕' },
  { key: 'tooltipBg', label: '提示背景', group: '提示 (Tooltip)' },
  { key: 'tooltipText', label: '提示文字', group: '提示 (Tooltip)' },
];

const CONTENT_SHADOW_FIELDS: { key: ContentColorKey; label: string }[] = [
  { key: 'boxShadow', label: '全域陰影' },
  { key: 'boxShadowSecondary', label: '全域陰影 (次要)' },
  { key: 'cardShadow', label: '卡片陰影' },
  { key: 'cardShadowHover', label: '卡片懸停陰影' },
  { key: 'tableShadow', label: '表格陰影' },
];

function groupContentFields(fields: typeof CONTENT_COLOR_FIELDS): Record<string, typeof CONTENT_COLOR_FIELDS> {
  const grouped: Record<string, typeof CONTENT_COLOR_FIELDS> = {};
  for (const f of fields) {
    if (!grouped[f.group]) grouped[f.group] = [];
    grouped[f.group].push(f);
  }
  return grouped;
}

interface ColorFieldProps {
  label: string;
  fieldKey: string;
}

function ColorField({ label, fieldKey }: ColorFieldProps) {
  return (
    <Form.Item
      name={['tokens', fieldKey]}
      label={label}
      style={{ marginBottom: 8 }}
      getValueFromEvent={(color) => color?.toHexString?.() ?? color}
    >
      <ColorPicker
        showText
        format="hex"
        size="small"
      />
    </Form.Item>
  );
}

interface TextFieldProps {
  label: string;
  fieldKey: string;
  rows?: number;
}

function TextField({ label, fieldKey, rows = 1 }: TextFieldProps) {
  return (
    <Form.Item
      name={['tokens', fieldKey]}
      label={label}
      style={{ marginBottom: 8 }}
    >
      {rows === 1 ? (
        <Input />
      ) : (
        <Input.TextArea rows={rows} />
      )}
    </Form.Item>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  const { token } = theme.useToken();
  return <Text strong style={{ display: 'block', marginBottom: 12, marginTop: 8, color: token.colorPrimary }}>{children}</Text>;
}

export function ShellTokensForm() {
  return (
    <>
      <SectionTitle>顏色設置</SectionTitle>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0 16px' }}>
        {SHELL_COLOR_FIELDS.map(f => (
          <ColorField
            key={f.key}
            label={f.label}
            fieldKey={f.key}
          />
        ))}
      </div>
      <SectionTitle>陰影設置</SectionTitle>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0 16px' }}>
        {SHELL_SHADOW_FIELDS.map(f => (
          <TextField
            key={f.key}
            label={f.label}
            fieldKey={f.key}
            rows={1}
          />
        ))}
      </div>
    </>
  );
}

export function ContentTokensForm() {
  const grouped = groupContentFields(CONTENT_COLOR_FIELDS);

  return (
    <>
      <SectionTitle>品牌顏色</SectionTitle>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0 16px' }}>
        {(grouped['品牌顏色'] || []).map(f => (
          <ColorField
            key={f.key}
            label={f.label}
            fieldKey={f.key}
          />
        ))}
      </div>

      <SectionTitle>背景與文字</SectionTitle>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0 16px' }}>
        {(grouped['背景顏色'] || []).map(f => (
          <ColorField
            key={f.key}
            label={f.label}
            fieldKey={f.key}
          />
        ))}
      </div>

      <SectionTitle>表格</SectionTitle>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0 16px' }}>
        {(grouped['表格'] || []).map(f => (
          <ColorField
            key={f.key}
            label={f.label}
            fieldKey={f.key}
          />
        ))}
      </div>

      <SectionTitle>聊天</SectionTitle>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0 16px' }}>
        {(grouped['聊天'] || []).map(f => (
          <ColorField
            key={f.key}
            label={f.label}
            fieldKey={f.key}
          />
        ))}
      </div>

      <SectionTitle>圖示</SectionTitle>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0 16px' }}>
        {(grouped['圖示'] || []).map(f => (
          <ColorField
            key={f.key}
            label={f.label}
            fieldKey={f.key}
          />
        ))}
      </div>

      <SectionTitle>按鈕</SectionTitle>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0 16px' }}>
        {(grouped['按鈕'] || []).map(f => (
          <ColorField
            key={f.key}
            label={f.label}
            fieldKey={f.key}
          />
        ))}
      </div>

      <SectionTitle>陰影與圓角</SectionTitle>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0 16px' }}>
        {CONTENT_SHADOW_FIELDS.map(f => (
          <TextField
            key={f.key}
            label={f.label}
            fieldKey={f.key}
            rows={1}
          />
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0 16px' }}>
        <Form.Item name={['tokens', 'borderRadius']} label="圓角" style={{ marginBottom: 8 }}>
          <InputNumber min={0} max={100} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name={['tokens', 'bgOpacity']} label="內容背景透明度 (%)" style={{ marginBottom: 8 }}>
          <Slider min={0} max={100} tooltip={{ formatter: (v) => `${v}%` }} />
        </Form.Item>
        <Form.Item name={['tokens', 'tooltipBgOpacity']} label="提示背景透明度 (%)" style={{ marginBottom: 8 }}>
          <Slider min={50} max={100} tooltip={{ formatter: (v) => `${v}%` }} />
        </Form.Item>
      </div>
      <Form.Item name={['tokens', 'fontFamily']} label="字體" style={{ marginBottom: 8 }}>
        <Input />
      </Form.Item>
    </>
  );
}
