/**
 * @file        設計令牌
 * @description 全域設計令牌，定義亮色/暗色主題的顏色、陰影、字體等
 * @lastUpdate  2026-03-25 15:07:58
 * @author      Daniel Chung
 * @version     1.2.0
 */

import type { ShellTokens, ContentTokens } from '../../services/api';

export const DEFAULT_SHELL_TOKENS: ShellTokens = {
  siderBg: '#1e293b',
  headerBg: '#0f172a',
  menuItemColor: '#94a3b8',
  menuItemHoverBg: '#334155',
  menuItemSelectedBg: '#3b82f6',
  menuItemSelectedColor: '#ffffff',
  logoColor: '#ffffff',
  siderBorder: '#334155',
  headerShadow: '0 2px 8px rgba(0, 0, 0, 0.4)',
  siderShadow: '2px 0 8px rgba(0, 0, 0, 0.3)',
};

const DEFAULT_FONT_FAMILY =
  "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif";

export const DEFAULT_CONTENT_LIGHT_TOKENS: ContentTokens = {
  colorPrimary: '#1e40af',
  colorSuccess: '#22c55e',
  colorWarning: '#f59e0b',
  colorError: '#dc2626',
  colorInfo: '#1e40af',
  colorBgBase: '#696d6f',
  colorTextBase: '#030213',
  pageBg: '#e8eaed',
  contentBg: '#ffffff',
  containerBg: '#ffffff',
  borderRadius: 10,
  fontFamily: DEFAULT_FONT_FAMILY,
  boxShadow: '0 6px 24px rgba(30, 64, 175, 0.25)',
  boxShadowSecondary: '0 12px 40px rgba(30, 64, 175, 0.35)',
  tableExpandedRowBg: '#f0f4ff',
  tableHeaderBg: '#f0f4ff',
  tableRowHoverBg: '#e6f0ff',
  chatInputBg: '#f1f5f9',
  chatUserBubble: '#dbeafe',
  chatAssistantBubble: '#e2e8f0',
  textSecondary: '#64748b',
  iconDefault: '#64748b',
  iconHover: '#1e40af',
  btnClear: '#f59e0b',
  btnClearHover: '#d97706',
  btnSend: '#1e40af',
  btnSendHover: '#1e3a8a',
  btnText: '#030213',
  cardShadow: '0 6px 24px rgba(30, 64, 175, 0.25)',
  cardShadowHover: '0 12px 40px rgba(30, 64, 175, 0.35)',
  tableShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
  bgOpacity: 100,
  tooltipBg: '#1e293b',
  tooltipText: '#f1f5f9',
  tooltipBgOpacity: 88,
};

export const DEFAULT_CONTENT_DARK_TOKENS: ContentTokens = {
  colorPrimary: '#3b82f6',
  colorSuccess: '#22c55e',
  colorWarning: '#f59e0b',
  colorError: '#ef4444',
  colorInfo: '#3b82f6',
  colorBgBase: '#0f172a',
  colorTextBase: '#f1f5f9',
  pageBg: '#0a0f1a',
  contentBg: '#0f172a',
  containerBg: '#1e293b',
  borderRadius: 10,
  fontFamily: DEFAULT_FONT_FAMILY,
  boxShadow: '0 6px 24px rgba(100, 80, 220, 0.35)',
  boxShadowSecondary: '0 12px 40px rgba(100, 80, 220, 0.50)',
  tableExpandedRowBg: '#0a1120',
  tableHeaderBg: '#1a2235',
  tableRowHoverBg: '#1a2744',
  chatInputBg: '#1e293b',
  chatUserBubble: '#1e3a8a',
  chatAssistantBubble: '#1e293b',
  textSecondary: '#8892a0',
  iconDefault: '#8892a0',
  iconHover: '#ffffff',
  btnClear: '#f59e0b',
  btnClearHover: '#d97706',
  btnSend: '#3b82f6',
  btnSendHover: '#2563eb',
  btnText: '#ffffff',
  cardShadow: '0 6px 24px rgba(100, 80, 220, 0.35)',
  cardShadowHover: '0 12px 40px rgba(100, 80, 220, 0.50)',
  tableShadow: '0 2px 8px rgba(0, 0, 0, 0.3)',
  bgOpacity: 100,
  tooltipBg: '#1e293b',
  tooltipText: '#f1f5f9',
  tooltipBgOpacity: 88,
};
