/**
 * @file        Data Agent Schema 常數定義
 * @description 定義 Schema 頁面使用的頁籤與分類常數
 * @lastUpdate  2026-04-11 18:13:37
 * @author      Daniel Chung
 * @version     1.0.0
 */

/** Ragic tab slug → 中文頁籤名稱 */
export const TAB_LABELS: Record<string, string> = {
  'database': '資料庫',
  'configuration-file': '基本資料維護檔',
  'form': 'ERP表單清單',
  'config-file-details': '設定檔清單',
  'stock': '庫存',
  'erp': '進銷存表單',
  'mes2': '生產製造',
  'iso2': 'ISO表單範本',
  'not-follow-up-form': '非追上傳表單',
  'g-4-1-02-': 'GHP表單',
  'mes': 'MES表單',
  'work-reporting-area': '報工專區',
  'ragicsystem': '系統',
  'ragicsales': 'CRM',
  'ragicpurchasing': 'SCM',
  'ragicforms6': '法務',
  'forms4': '顧客關係管理',
  'forms9': '客戶端問卷',
  'procurement': '採購(測試)',
  'ragicforms': '活動管理',
  'ragicforms3': '專案預算及支出',
  'forms': '開發資料',
};

/** 大分類 → 包含的 tab slugs + 色碼 */
export const TAB_CATEGORIES: { label: string; tabs: string[]; color: string }[] = [
  { 
    label: '基礎資料', color: '#bae0ff',
    tabs: ['database', 'configuration-file', 'config-file-details'] 
  },
  { 
    label: '進銷存', color: '#d9f7be',
    tabs: ['form', 'stock', 'erp', 'procurement'] 
  },
  { 
    label: '生產製造', color: '#ffe7ba',
    tabs: ['mes2', 'mes', 'work-reporting-area'] 
  },
  { 
    label: '品質/ISO', color: '#ffccc7',
    tabs: ['iso2', 'not-follow-up-form', 'g-4-1-02-'] 
  },
  { 
    label: 'CRM/SCM', color: '#efdbff',
    tabs: ['ragicsales', 'ragicpurchasing', 'forms4', 'forms9'] 
  },
  { 
    label: '管理', color: '#b5f5ec',
    tabs: ['ragicsystem', 'ragicforms6', 'ragicforms', 'ragicforms3', 'forms'] 
  },
];

/** 大分類標籤對應色碼（淺色模式） */
export const CATEGORY_COLOR_MAP: Record<string, string> = Object.fromEntries(
  TAB_CATEGORIES.map(c => [c.label, c.color])
);
CATEGORY_COLOR_MAP['其他'] = '#d9d9d9';

/** 大分類標籤對應色碼（深色模式）— 使用較深、對比度佳的色調 */
export const CATEGORY_COLOR_MAP_DARK: Record<string, string> = {
  '基礎資料': '#1a3a5c',
  '進銷存': '#1a3d1a',
  '生產製造': '#3d2e0a',
  '品質/ISO': '#3d1a1a',
  'CRM/SCM': '#2a1a3d',
  '管理': '#0a3d3d',
  '其他': '#3d3d3d',
};
