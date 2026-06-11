/**
 * @file        types.ts
 * @description 浮動助手共用型別、預設配置、頁面感知上下文對照表
 * @lastUpdate  2026-04-23 22:29:26
 * @author      Daniel Chung
 * @version     1.5.0
 */

// ============================================================================
// 實體類型定義（Entity Types）
// ============================================================================

/**
 * 系統中所有可操作的業務實體類型
 * 每個實體類型對應一個或多個頁面的操作對象
 */
export const ENTITY_TYPES = {
  // 系統管理
  user: {
    name: '用戶',
    nameEn: 'User',
    fields: ['username', 'name', 'role_key', 'status', 'created_at'],
    pageTypes: ['data_table', 'form_crud'],
  },
  role: {
    name: '角色',
    nameEn: 'Role',
    fields: ['role_name', 'description', 'permissions', 'status'],
    pageTypes: ['data_table', 'form_crud'],
  },
  function: {
    name: '功能選單',
    nameEn: 'Function',
    fields: ['code', 'name', 'path', 'icon', 'sort_order'],
    pageTypes: ['data_table', 'form_crud'],
  },
  system_param: {
    name: '系統參數',
    nameEn: 'SystemParam',
    fields: ['param_key', 'param_value', 'category'],
    pageTypes: ['config'],
  },

  // 客戶管理
  lead: {
    name: '客戶線索',
    nameEn: 'Lead',
    fields: ['company_name', 'contact', 'status', 'source'],
    pageTypes: ['data_table', 'form_crud'],
  },

  // 業務管理
  requirement: {
    name: '需求',
    nameEn: 'Requirement',
    fields: ['goal', 'status', 'version', 'account', 'submitted_at'],
    pageTypes: ['data_table'],
  },
  action: {
    name: '行動腳本',
    nameEn: 'ActionScript',
    fields: ['skill_no', 'title', 'status', 'skill_type', 'version'],
    pageTypes: ['data_table'],
  },
  preorder: {
    name: '預訂購',
    nameEn: 'Preorder',
    fields: ['preorder_id', 'user_name', 'status', 'source', 'message_date'],
    pageTypes: ['data_table'],
  },

  // 資料管理（Data Agent）
  table: {
    name: '資料表',
    nameEn: 'Table',
    fields: ['table_name', 'column_count', 'record_count'],
    pageTypes: ['schema_manage', 'data_table'],
  },
  column: {
    name: '欄位',
    nameEn: 'Column',
    fields: ['column_name', 'data_type', 'is_nullable', 'key_type'],
    pageTypes: ['schema_manage'],
  },
  query: {
    name: '查詢',
    nameEn: 'Query',
    fields: ['sql', 'result_count', 'executed_at'],
    pageTypes: ['data_query'],
  },
  datalake_dataset: {
    name: '資料集',
    nameEn: 'DataLakeDataset',
    fields: ['dataset_name', 'file_count', 'size_bytes'],
    pageTypes: ['data_query', 'data_table'],
  },

  // 知識管理
  knowledge_base: {
    name: '知識庫',
    nameEn: 'KnowledgeBase',
    fields: ['kb_name', 'description', 'doc_count', 'status'],
    pageTypes: ['knowledge', 'data_table'],
  },
  document: {
    name: '文件',
    nameEn: 'Document',
    fields: ['filename', 'size', 'uploaded_at', 'vectorized'],
    pageTypes: ['knowledge'],
  },
  ontology: {
    name: '本體',
    nameEn: 'Ontology',
    fields: ['name', 'entity_count', 'relation_count'],
    pageTypes: ['knowledge', 'data_table'],
  },

  // AI 對話
  chat_session: {
    name: '對話',
    nameEn: 'ChatSession',
    fields: ['title', 'message_count', 'created_at', 'updated_at'],
    pageTypes: ['chat', 'data_table'],
  },
  scheduled_task: {
    name: '排程任務',
    nameEn: 'ScheduledTask',
    fields: ['task_name', 'cron', 'last_run', 'next_run', 'status'],
    pageTypes: ['data_table'],
  },

  // 任務會話（統一 task_session 涵蓋 chat/history/scheduled）
  task_session: {
    name: '任務會話',
    nameEn: 'TaskSession',
    fields: ['title', 'message_count', 'created_at', 'updated_at'],
    pageTypes: ['chat', 'data_table'],
  },

  // 瀏覽探索
  agent: {
    name: 'AI Agent',
    nameEn: 'Agent',
    fields: ['agent_key', 'name', 'description', 'status'],
    pageTypes: ['browse'],
  },
  tool: {
    name: '工具',
    nameEn: 'Tool',
    fields: ['tool_key', 'name', 'provider', 'status'],
    pageTypes: ['browse'],
  },

  // 平台整合
  line_platform: {
    name: 'LINE Channel',
    nameEn: 'LinePlatform',
    fields: ['channel_name', 'channel_id', 'publication_status'],
    pageTypes: ['platform'],
  },
  bot: {
    name: 'Bot',
    nameEn: 'Bot',
    fields: ['bot_name', 'platform', 'status'],
    pageTypes: ['platform'],
  },

  // 意圖編排
  intent: {
    name: '意圖',
    nameEn: 'Intent',
    fields: ['intent_id', 'name', 'agent_scope', 'status'],
    pageTypes: ['data_table', 'form_crud'],
  },

  // 頁面層級
  placeholder: {
    name: '預留頁面',
    nameEn: 'Placeholder',
    fields: [],
    pageTypes: [],
  },
  welcome: {
    name: '歡迎頁',
    nameEn: 'Welcome',
    fields: [],
    pageTypes: [],
  },
  login: {
    name: '登入頁',
    nameEn: 'Login',
    fields: [],
    pageTypes: [],
  },

  // 數據湖
  datalake: {
    name: '數據湖',
    nameEn: 'DataLake',
    fields: ['table_name', 'data_source', 'record_count'],
    pageTypes: ['data_query', 'data_table'],
  },

  // 技能
  skill: {
    name: '技能',
    nameEn: 'Skill',
    fields: ['skill_no', 'title', 'status', 'skill_type', 'version'],
    pageTypes: ['data_table'],
  },

  // 待辦事項
  todo: {
    name: '待辦事項',
    nameEn: 'Todo',
    fields: ['title', 'status', 'priority', 'assignee'],
    pageTypes: ['data_table'],
  },

  // Mermaid 圖表驗證
  mermaid: {
    name: 'Mermaid 圖表',
    nameEn: 'Mermaid',
    fields: ['test_case', 'status', 'error'],
    pageTypes: ['data_table'],
  },

  // 儀表板
  dashboard: {
    name: '儀表板',
    nameEn: 'Dashboard',
    fields: ['metric', 'value', 'period'],
    pageTypes: ['dashboard'],
  },

  // 備份
  backup_record: {
    name: '備份記錄',
    nameEn: 'BackupRecord',
    fields: ['backup_type', 'created_at', 'size_bytes', 'status'],
    pageTypes: ['data_table'],
  },
} as const;

export type EntityTypeKey = keyof typeof ENTITY_TYPES;

/**
 * 實體上下文 — 用戶當前正在操作的業務實體
 */
export interface EntityContext {
  /** 實體類型 */
  entity_type: EntityTypeKey;
  /** 實體 ID（如 username, table_name） */
  entity_id: string;
  /** 實體顯示名稱 */
  entity_name?: string;
  /** 操作動作 */
  action: EntityAction;
  /** 額外元資料 */
  metadata?: Record<string, unknown>;
}

export type EntityAction =
  | 'view'       // 查看
  | 'list'       // 列表瀏覽
  | 'create'     // 新增
  | 'edit'       // 編輯
  | 'delete'     // 刪除
  | 'search'     // 搜尋
  | 'filter'     // 篩選
  | 'export'     // 匯出
  | 'import'     // 匯入
  | 'execute'    // 執行（如執行 SQL）
  | 'chat'       // 對話
  | 'history'    // 歷史紀錄
  | 'scheduled'; // 排程任務

export type ResponseStrategy =
  | 'direct_llm'
  | 'tool_execute'
  | 'confirm_then_execute'
  | 'handoff_bpa'
  | 'navigate'
  | 'route_to_data'
  | 'knowledge_search'
  | 'operation_guide'
  | 'todo_generate'
  | 'clarify'
  | 'escalate';

export type SideEffect = 'none' | 'reversible' | 'destructive';

export interface IntentGuess {
  text: string;
  confidence: number;
  source: 'template' | 'rule' | 'llm';
  intent_id?: string;
  strategy?: ResponseStrategy;
  side_effect?: SideEffect;
  context?: Record<string, unknown>;
}

export const PAGE_TYPE_MAP: Record<string, string[]> = {
  '/app/home':                    ['dashboard'],
  '/app/users':                   ['data_table', 'form_crud'],
  '/app/roles':                   ['data_table', 'form_crud'],
  '/app/params':                  ['config'],
  '/app/functions':               ['data_table', 'form_crud', 'config'],
  '/app/lead-management':         ['data_table', 'form_crud'],
  '/app/browse-agent':            ['browse'],
  '/app/browse-tools':            ['browse'],
  '/app/task-session/chat':       ['chat'],
  '/app/task-session/history':    ['data_table'],
  '/app/task-session/scheduled':  ['data_table'],
  '/app/data-agent/schema':       ['schema_manage'],
  '/app/data-agent/playground':   ['data_query'],
  '/app/data-agent/datalake':     ['data_query', 'data_table'],
  '/app/knowledge/ontology':      ['knowledge', 'data_table'],
  '/app/knowledge/management':    ['knowledge', 'data_table'],
  '/app/intent-orchestration':    ['data_table', 'form_crud'],
};

/**
 * 頁面 → 實體類型對應表
 * 每個頁面可能操作的業務實體類型
 */
export const PAGE_ENTITY_MAP: Record<string, EntityTypeKey[]> = {
  '/app/home':                    [],
  '/app/users':                   ['user'],
  '/app/roles':                   ['role'],
  '/app/params':                  ['system_param'],
  '/app/functions':               ['function'],
  '/app/lead-management':         ['lead'],
  '/app/browse-agent':            ['agent'],
  '/app/browse-tools':            ['tool'],
  '/app/task-session/chat':       ['task_session', 'chat_session'],
  '/app/task-session/history':    ['task_session', 'chat_session'],
  '/app/task-session/scheduled':  ['task_session', 'scheduled_task'],
  '/app/data-agent/schema':       ['table', 'column'],
  '/app/data-agent/playground':    ['query'],
  '/app/data-agent/datalake':      ['datalake_dataset'],
  '/app/knowledge/ontology':        ['ontology'],
  '/app/knowledge/management':      ['knowledge_base', 'document'],
  '/app/intent-orchestration':     ['intent'],
};

export interface FloatingAssistantConfig {
  enabled: boolean;
  modalWidth: number;
  modalHeight: number;
  blurIntensity: number;
  glassOpacity: number;
  saturation: number;
  borderRadius: number;
  modalBg: string;
  headerBg: string;
  headerBorderColor: string;
  titleColor: string;
  closeBtnColor: string;
  bodyBg: string;
  footerBg: string;
  footerBorderColor: string;
  inputBg: string;
  inputTextColor: string;
  inputBorderColor: string;
  inputPlaceholderColor: string;
  sendBtnBg: string;
  sendBtnColor: string;
  bubbleAiBg: string;
  bubbleAiTextColor: string;
  bubbleUserBg: string;
  bubbleUserTextColor: string;
  buttonBg: string;
  buttonIconColor: string;
  buttonShadowColor: string;
  buttonPulseColor: string;
  shadowColor: string;
  shadowInnerColor: string;
  gradientStart: string;
  gradientRadial1: string;
  gradientRadial2: string;
  resizeHandleColor: string;
  mermaidBg: string;
  mermaidTextColor: string;
  linkColor: string;
  quoteBorderColor: string;
  warningColorDark: string;
  warningColorLight: string;
}

export const defaultConfig: FloatingAssistantConfig = {
  enabled: true,
  modalWidth: 480,
  modalHeight: 600,
  blurIntensity: 20,
  glassOpacity: 65,
  saturation: 180,
  borderRadius: 12,
  modalBg: 'rgba(30, 41, 59, 0.85)',
  headerBg: 'rgba(22, 27, 34, 0.75)',
  headerBorderColor: 'rgba(255, 255, 255, 0.1)',
  titleColor: '#ffffff',
  closeBtnColor: 'rgba(255, 255, 255, 0.45)',
  bodyBg: 'rgba(30, 41, 59, 0.6)',
  footerBg: 'rgba(22, 27, 34, 0.75)',
  footerBorderColor: 'rgba(255, 255, 255, 0.1)',
  inputBg: '#1e293b',
  inputTextColor: '#f1f5f9',
  inputBorderColor: '#334155',
  inputPlaceholderColor: '#8892a0',
  sendBtnBg: '#3b82f6',
  sendBtnColor: '#ffffff',
  bubbleAiBg: '#1e293b',
  bubbleAiTextColor: '#f1f5f9',
  bubbleUserBg: '#1e3a8a',
  bubbleUserTextColor: '#f1f5f9',
  buttonBg: '#3b82f6',
  buttonIconColor: '#ffffff',
  buttonShadowColor: 'rgba(0, 0, 0, 0.15)',
  buttonPulseColor: 'rgba(59, 130, 246, 0.4)',
  shadowColor: 'rgba(0, 0, 0, 0.12)',
  shadowInnerColor: 'rgba(255, 255, 255, 0.05)',
  gradientStart: 'rgba(99, 102, 241, 0.05)',
  gradientRadial1: 'rgba(99, 102, 241, 0.08)',
  gradientRadial2: 'rgba(14, 165, 233, 0.05)',
  resizeHandleColor: 'rgba(255, 255, 255, 0.35)',
  mermaidBg: 'rgba(0, 0, 0, 0.3)',
  mermaidTextColor: '#ffffff',
  linkColor: '#3b82f6',
  quoteBorderColor: 'rgba(255, 255, 255, 0.2)',
  warningColorDark: '#ff4d4f',
  warningColorLight: '#1677ff',
};

export interface PageContext {
  name: string;
  description: string;
  suggestions: string[];
}

const defaultPageContext: PageContext = {
  name: '首頁',
  description: '系統總覽',
  suggestions: ['系統有哪些功能？', '如何開始使用？'],
};

const PAGE_CONTEXT_MAP: Record<string, PageContext> = {
  '/app/home': {
    name: '首頁',
    description: '系統總覽與快速入口',
    suggestions: ['今天有什麼待辦？', '系統運行狀態如何？'],
  },
  '/app/users': {
    name: '用戶管理',
    description: '管理系統使用者帳號',
    suggestions: ['如何新增用戶？', '如何重設密碼？', '如何停用帳號？'],
  },
  '/app/roles': {
    name: '角色管理',
    description: '管理角色與權限分配',
    suggestions: ['如何建立新角色？', '如何分配權限？'],
  },
  '/app/params': {
    name: '系統參數',
    description: '系統配置與參數管理',
    suggestions: ['如何修改系統參數？', '有哪些可配置項？'],
  },
  '/app/functions': {
    name: '功能管理',
    description: '管理系統功能選單與模組',
    suggestions: ['如何新增功能選單？', '如何調整排序？'],
  },
  '/app/lead-management': {
    name: '客戶線索管理',
    description: '管理潛在客戶與銷售線索',
    suggestions: ['如何新增線索？', '如何追蹤客戶狀態？'],
  },
  '/app/browse-agent': {
    name: 'AI Agent 瀏覽',
    description: '瀏覽與管理可用的 AI Agent',
    suggestions: ['有哪些 Agent 可用？', '如何啟用 Agent？'],
  },
  '/app/browse-tools': {
    name: '工具瀏覽',
    description: '瀏覽 MCP 工具與外部整合',
    suggestions: ['有哪些工具可用？', '如何整合新工具？'],
  },
  '/app/task-session/chat': {
    name: 'AI 對話',
    description: 'AI 任務對話與指令執行',
    suggestions: ['如何開始新對話？', '支持哪些指令？'],
  },
  '/app/task-session/history': {
    name: '對話歷史',
    description: '查看歷史 AI 對話記錄',
    suggestions: ['如何搜尋歷史對話？', '如何匯出記錄？'],
  },
  '/app/task-session/scheduled': {
    name: '排程任務',
    description: '管理排程執行的 AI 任務',
    suggestions: ['如何建立排程？', '如何查看執行結果？'],
  },
  '/app/data-agent/schema': {
    name: 'Schema 管理',
    description: '資料表結構瀏覽、欄位檢視與 Schema 設定',
    suggestions: ['如何查看表結構？', '如何查看欄位資訊？', '如何匯入 Schema？'],
  },
  '/app/data-agent/playground': {
    name: '查詢遊樂場',
    description: '自然語言轉 SQL 查詢測試',
    suggestions: ['幫我查詢訂單數據', '如何寫更精確的查詢？'],
  },
  '/app/data-agent/datalake': {
    name: '資料湖',
    description: '資料湖檔案管理',
    suggestions: ['如何上傳資料？', '如何管理資料集？'],
  },
  '/app/knowledge/ontology': {
    name: '知識本體',
    description: '知識圖譜本體管理',
    suggestions: ['如何定義本體？', '如何建立關聯？'],
  },
  '/app/knowledge/management': {
    name: '知識庫管理',
    description: '知識庫建立與向量化管理',
    suggestions: ['如何建立知識庫？', '如何上傳文件？', '如何進行向量化？'],
  },
  '/app/intent-orchestration': {
    name: '意圖編排',
    description: '意圖辨識與流程編排',
    suggestions: ['如何建立新意圖？', '如何設定觸發條件？'],
  },
};

export function resolvePageContext(pathname: string): PageContext {
  const exact = PAGE_CONTEXT_MAP[pathname];
  if (exact) return exact;

  const match = Object.keys(PAGE_CONTEXT_MAP)
    .filter((key) => pathname.startsWith(key))
    .sort((a, b) => b.length - a.length)[0];

  return match ? PAGE_CONTEXT_MAP[match] : defaultPageContext;
}
