/**
 * @file        資料深度追蹤 — 場景配置
 * @description 定義 8 大追蹤場景的配置（名稱、描述、圖示、輸入參數）
 * @lastUpdate  2026-05-17
 */

export enum TraceScenario {
  SHIPMENT_BATCH = 'shipment_batch',
  INCOMING_BATCH = 'incoming_batch',
  PRODUCT_FULL_HISTORY = 'product_full_history',
  WORK_ORDER = 'work_order',
  COMPLAINT_RECALL = 'complaint_recall',
  EXPIRY_TRACKING = 'expiry_tracking',
  QUALITY_ISSUE = 'quality_issue',
  SUPPLIER_TRACE = 'supplier_trace',
}

export interface ScenarioDefinition {
  id: TraceScenario;
  name: string;
  description: string;
  icon: string;          // Ant Design icon name
  inputLabel: string;
  inputPlaceholder: string;
  defaultDepth: number;
  direction: 'forward' | 'reverse' | 'bidirectional';
  hasDateRange: boolean;  // true only for expiry_tracking
  hasSupplierInput: boolean; // true only for supplier_trace
  entryTables: string[];
}

export const SCENARIO_DEFINITIONS: ScenarioDefinition[] = [
  {
    id: TraceScenario.SHIPMENT_BATCH,
    name: '出貨批號追蹤',
    description: '查詢同批成品出給哪些客戶、庫存狀況、同原料的其他成品',
    icon: 'ExportOutlined',
    inputLabel: '出貨批號',
    inputPlaceholder: '請輸入出貨批號，例如 BATCH001',
    defaultDepth: 3,
    direction: 'bidirectional',
    hasDateRange: false,
    hasSupplierInput: false,
    entryTables: ['ERP_26', 'ERP_23'],
  },
  {
    id: TraceScenario.INCOMING_BATCH,
    name: '進料批號追蹤',
    description: '查詢該原料批號用於哪些成品批、出貨給誰',
    icon: 'ImportOutlined',
    inputLabel: '進貨批號',
    inputPlaceholder: '請輸入進貨批號，例如 B001',
    defaultDepth: 3,
    direction: 'forward',
    hasDateRange: false,
    hasSupplierInput: false,
    entryTables: ['ERP_48', 'ERP_15'],
  },
  {
    id: TraceScenario.PRODUCT_FULL_HISTORY,
    name: '成品批號全履歷',
    description: '原料來源→生產工單→QC→入庫→出貨→客戶完整鏈條',
    icon: 'BranchesOutlined',
    inputLabel: '成品批號',
    inputPlaceholder: '請輸入成品批號',
    defaultDepth: 5,
    direction: 'bidirectional',
    hasDateRange: false,
    hasSupplierInput: false,
    entryTables: ['MES2_17', 'STOCK_16', 'STOCK_17'],
  },
  {
    id: TraceScenario.WORK_ORDER,
    name: '工單追溯',
    description: '查詢製令用了哪批原料、產出哪些成品、對應銷售單',
    icon: 'FileTextOutlined',
    inputLabel: '工單號/製令單號',
    inputPlaceholder: '請輸入工單號，例如 MFG001',
    defaultDepth: 3,
    direction: 'bidirectional',
    hasDateRange: false,
    hasSupplierInput: false,
    entryTables: ['MES2_17'],
  },
  {
    id: TraceScenario.COMPLAINT_RECALL,
    name: '客訴/召回追溯',
    description: '某批有問題時的影響範圍分析（客戶、原料、其他成品）',
    icon: 'WarningOutlined',
    inputLabel: '客訴成品批號',
    inputPlaceholder: '請輸入客訴涉及的成品批號',
    defaultDepth: 3,
    direction: 'bidirectional',
    hasDateRange: false,
    hasSupplierInput: false,
    entryTables: ['ERP_26', 'STOCK_17'],
  },
  {
    id: TraceScenario.EXPIRY_TRACKING,
    name: '效期追蹤',
    description: '查詢即將到期的批次、庫存狀態、持有客戶',
    icon: 'ClockCircleOutlined',
    inputLabel: '物料/品項',
    inputPlaceholder: '選擇物料或留空查詢全部',
    defaultDepth: 3,
    direction: 'forward',
    hasDateRange: true,
    hasSupplierInput: false,
    entryTables: ['STOCK_17', 'STOCK_16', 'STOCK_9'],
  },
  {
    id: TraceScenario.QUALITY_ISSUE,
    name: '品質異常追溯',
    description: 'QC不合格批號的原料來源、成品去向、供應商分析',
    icon: 'BugOutlined',
    inputLabel: '品檢記錄編號',
    inputPlaceholder: '請輸入 QC 記錄編號',
    defaultDepth: 3,
    direction: 'bidirectional',
    hasDateRange: false,
    hasSupplierInput: false,
    entryTables: ['ERP_60', 'ERP_62'],
  },
  {
    id: TraceScenario.SUPPLIER_TRACE,
    name: '供應商追溯',
    description: '查詢特定供應商的原料批用於哪些成品、出貨給誰',
    icon: 'ShopOutlined',
    inputLabel: '供應商代碼',
    inputPlaceholder: '請輸入供應商代碼',
    defaultDepth: 3,
    direction: 'forward',
    hasDateRange: true,
    hasSupplierInput: true,
    entryTables: ['ERP_48', 'ERP_52'],
  },
];

export function getScenarioById(id: TraceScenario): ScenarioDefinition | undefined {
  return SCENARIO_DEFINITIONS.find(s => s.id === id);
}
