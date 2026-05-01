/**
 * @file        API 服務層
 * @description Axios 實例配置、API 請求封裝、所有業務 API 接口定義
 * @lastUpdate  2026-04-09 12:21:28
 * @author      Daniel Chung
 * @version     1.5.1
 * @history
 * - 2026-03-25 15:07:58 | Daniel Chung | 1.4.0 | 新增 activate() 方法到 themeTemplateApi
 * - 2026-03-24 23:01:20 | Daniel Chung | 1.3.0 | 新增 Knowledge Base 介面定義與 API 方法
 * - 2026-03-24 20:58:11 | Daniel Chung | 1.2.0 | 新增 Ontology 介面定義與 API 方法
 * - 2026-03-22 19:11:57 | Daniel Chung | 1.1.0 | 新增 ThemeTemplate 介面定義
 * - 2026-03-17 23:27:55 | Daniel Chung | 1.0.0 | 初始版本
 */

import axios from 'axios';
import type { AssistantContextPayload } from '../types/assistantContext';

function resolveApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_URL;

  if (!configured) {
    return import.meta.env.DEV ? '' : 'http://localhost:3001';
  }

  if (!import.meta.env.DEV) {
    return configured;
  }

  try {
    const parsed = new URL(configured);
    if (parsed.hostname === 'localhost' || parsed.hostname === '127.0.0.1') {
      return '';
    }
  } catch {
    return configured;
  }

  return configured;
}

const api = axios.create({
  baseURL: resolveApiBaseUrl(),
  timeout: 30000,
});

// Add token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle response errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      // Avoid self-reloading on public routes like /login or /
      // while still forcing a hard reset when a protected route loses auth.
      if (window.location.pathname.startsWith('/app')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export interface User {
  _key: string;
  username: string;
  name: string;
  role_keys: string[];
  status: string;
  tier?: string;
  created_at: string;
}

export interface Role {
  _key: string;
  name: string;
  description: string;
  created_at: string;
}

export interface SystemParam {
  _key: string;
  param_key: string;
  param_value: string;
  param_type: string;
  require_restart: boolean;
  category: string;
}

export interface Function {
  _key: string;
  code: string;
  name: string;
  description: string;
  function_type: 'group' | 'sub_function' | 'tab';
  parent_key: string | null;
  path: string | null;
  icon: string | null;
  sort_order: number;
  status: string;
  created_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
  remember?: boolean;
}

export interface LoginResponse {
  token: string;
  user: {
    _key: string;
    username: string;
    name: string;
    role_key: string;
    role_name: string;
    tier?: string;
  };
}

export const authApi = {
  login: (data: LoginRequest) => api.post<{ code: number; message: string; data: LoginResponse }>('/api/v1/auth/login', data),
  logout: () => api.post('/api/v1/auth/logout'),
  me: () => api.get<{ code: number; data: LoginResponse['user'] }>('/api/v1/auth/me'),
};

export const userApi = {
  list: () => api.get<{ code: number; data: User[] }>('/api/v1/users'),
  get: (key: string) => api.get<{ code: number; data: User }>(`/api/v1/users/${key}`),
  create: (data: Partial<User> & { password_hash: string }) => api.post('/api/v1/users', data),
  update: (key: string, data: Partial<User>) => api.put(`/api/v1/users/${key}`, data),
  delete: (key: string) => api.delete(`/api/v1/users/${key}`),
  resetPassword: (key: string, password: string) => api.post(`/api/v1/users/${key}/reset-password`, { password }),
};

export const roleApi = {
  list: () => api.get<{ code: number; data: Role[] }>('/api/v1/roles'),
  get: (key: string) => api.get<{ code: number; data: Role }>(`/api/v1/roles/${key}`),
  create: (data: Partial<Role>) => api.post('/api/v1/roles', data),
  update: (key: string, data: Partial<Role>) => api.put(`/api/v1/roles/${key}`, data),
  delete: (key: string) => api.delete(`/api/v1/roles/${key}`),
};

export const paramsApi = {
  list: () => api.get<{ code: number; data: SystemParam[] }>('/api/v1/system-params'),
  get: (key: string) => api.get<{ code: number; data: SystemParam }>(`/api/v1/system-params/${key}`),
  update: (key: string, param_value: string) => api.put(`/api/v1/system-params/${key}`, { param_value }),
};

export interface FunctionRoleAuth {
  function_key: string;
  role_keys: string[];
  inherited_role_keys: string[];
}

export interface Agent {
  _key?: string;
  name: string;
  description?: string;
  icon?: string;
  usage_count?: number;
  group_key: string;
  agent_type?: 'knowledge' | 'data' | 'bpa' | 'tool';
  source?: 'local' | 'third_party';
  endpoint_url?: string;
  api_key?: string;
  auth_type?: 'none' | 'bearer' | 'basic' | 'oauth2';
  llm_model?: string;
  temperature?: number;
  max_tokens?: number;
  system_prompt?: string;
  knowledge_bases?: string[];
  data_sources?: string[];
  tools?: string[];
  opening_lines?: string[];
  capabilities?: string[];
  is_favorite?: boolean;
  visibility?: 'public' | 'private' | 'role';
  created_by?: string;
  updated_by?: string;
  created_at?: string;
  updated_at?: string;
  status?: 'online' | 'maintenance' | 'deprecated' | 'registering' | 'developing';
  visibility_roles?: string[];
}

export type DemandStatus = 'draft' | 'submitted' | 'accepted' | 'in_development' | 'pending_acceptance' | 'online' | 'cancelled';

export interface UploadedFile {
  name: string;
  url: string;
  size?: number;
  mime_type?: string;
}

export interface AIReview {
  completeness: string;
  reasonableness: string;
  feasibility: string;
  estimated_hours: number;
  confidence: string;
  summary: string;
  suggestions: string[];
  score: number;
  hour_breakdown?: {
    consulting: number;
    development: number;
    testing: number;
    review: number;
  };
}

export interface Demand {
  _key?: string;
  agent_key?: string;
  version?: string;
  status?: DemandStatus;
  goal?: string;
  expected_effect?: string;
  problem_description?: string;
  target_users?: string;
  scope?: string;
  excluded_scope?: string;
  conversation_style?: string;
  conversation_examples?: Array<{ role: string; content: string }>;
  estimated_hours?: number | null;
  estimated_confidence?: 'low' | 'medium' | 'high';
  final_hours?: number | null;
  rejection_history?: Array<{ rejected_at: string; reason: string }>;
  references?: string[];
  input_description?: string;
  input_format?: string;
  example_documents?: UploadedFile[];
  example_images?: UploadedFile[];
  output_description?: string;
  output_format?: string;
  output_examples?: UploadedFile[];
  ai_review?: AIReview;
  created_at?: string;
  updated_at?: string;
  submitted_at?: string;
  accepted_at?: string;
  cancelled_at?: string;
  online_at?: string;
}

export interface AgentChatRequest {
  session_id: string;
  message: string;
  user_id?: string;
}

export interface AgentChatResponse {
  session_id: string;
  reply: string;
  sources?: string[];
}

export const agentApi = {
  list: (agentType?: string) => {
    const url = agentType ? `/api/v1/agents?agent_type=${agentType}` : '/api/v1/agents';
    return api.get<{ code: number; data: Agent[] }>(url);
  },
  get: (key: string) => api.get<{ code: number; data: Agent }>(`/api/v1/agents/${key}`),
  create: (data: Partial<Agent>) => api.post('/api/v1/agents', data),
  update: (key: string, data: Partial<Agent>) => api.put(`/api/v1/agents/${key}`, data),
  delete: (key: string) => api.delete(`/api/v1/agents/${key}`),
  toggleFavorite: (key: string) => api.patch<{ code: number; data: Agent }>(`/api/v1/agents/${key}/favorite`, {}),
  chat: (key: string, data: AgentChatRequest) => api.post<AgentChatResponse>(`/api/v1/agents/${key}/chat?_t=${Date.now()}`, data, { timeout: 180000, headers: { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' } }),
  listIntents: (key: string) => api.get<{ code: number; data: any[] }>(`/api/v1/agents/${key}/intents`),
  createIntent: (key: string, data: any) => api.post(`/api/v1/agents/${key}/intents`, data),
  updateIntent: (key: string, intentKey: string, data: any) => api.put(`/api/v1/agents/${key}/intents/${intentKey}`, data),
  deleteIntent: (key: string, intentKey: string) => api.delete(`/api/v1/agents/${key}/intents/${intentKey}`),
  syncIntents: (key: string) => api.post(`/api/v1/agents/${key}/intents/sync`, {}),
  listDemands: (key: string) => api.get<{ code: number; data: Demand[] }>(`/api/v1/agents/${key}/demands`),
  getDemand: (key: string, demandKey: string) => api.get<{ code: number; data: Demand }>(`/api/v1/agents/${key}/demands/${demandKey}`),
  createDemand: (key: string, data: Partial<Demand>) => api.post(`/api/v1/agents/${key}/demands`, data),
  updateDemand: (key: string, demandKey: string, data: Partial<Demand>) => api.put(`/api/v1/agents/${key}/demands/${demandKey}`, data),
  deleteDemand: (key: string, demandKey: string) => api.delete(`/api/v1/agents/${key}/demands/${demandKey}`),
  updateDemandStatus: (key: string, demandKey: string, data: { status: string; reason?: string; estimated_hours?: number; final_hours?: number; ai_review?: AIReview }) =>
    api.patch(`/api/v1/agents/${key}/demands/${demandKey}/status`, data),
  suggestIntents: (key: string, demandKey: string) =>
    api.post<{ code: number; data: any[] }>(`/api/v1/agents/${key}/demands/${demandKey}/suggest-intents`, {}),
};

export const demandApi = {
  estimateHours: (data: { goal: string; expected_effect: string; problem_description: string; target_users?: string; scope?: string; systems_to_integrate?: string[] }) =>
    api.post<{ code: number; data: { estimated_hours: number; range_min: number; range_max: number; confidence: string; reasoning: string } }>('/api/v1/demands/estimate-hours', data),
  reviewDemand: (data: Partial<Demand>) =>
    api.post<{ code: number; data: AIReview }>('/api/v1/demands/review', data),
};

export interface SkillSpec {
  _key: string;
  skill_no: string;
  title?: string;
  name: string;
  skill_type: string;
  tags: string[];
  description: string;
  version: string;
  status: string;
  steps: string[];
  guardrails: string[];
  data_scope?: Record<string, unknown>;
  linked_intents: string[];
  spec_version: string;
  code_language: string;
  created_by: string;
  developed_by: string;
  created_at: string;
  updated_at: string;
}

export const skillApi = {
  list: () => api.get<{ code: number; data: SkillSpec[] }>('/api/v1/skills'),
  get: (id: string) => api.get<{ code: number; data: SkillSpec }>(`/api/v1/skills/${id}`),
  create: (data: Partial<SkillSpec>) => api.post('/api/v1/skills', data),
  update: (id: string, data: Partial<SkillSpec>) => api.put(`/api/v1/skills/${id}`, data),
  delete: (id: string) => api.delete(`/api/v1/skills/${id}`),
  getByNo: (no: string) => api.get<{ code: number; data: SkillSpec }>(`/api/v1/skills/by-no/${no}`),
  analyze: (id: string, data?: { revision?: string }) => api.post<{ code: number; message: string; data: any }>(`/api/v1/skills/${id}/analyze`, data || {}),
};

// ============= Tool Registry =============

export interface Tool {
  _key?: string;
  code: string;
  name: string;
  description?: string;
  tool_type?: 'tool' | 'advisor' | 'oracle' | 'mcp' | 'builtin' | 'custom';
  icon?: string;
  status?: 'online' | 'maintenance' | 'deprecated' | 'registering';
  usage_count?: number;
  group_key?: string;
  intent_tags?: string[];
  nl_examples?: string[];
  endpoint_url?: string;
  input_schema?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
  timeout_ms?: number;
  llm_model?: string;
  temperature?: number;
  max_tokens?: number;
  auth_config?: Record<string, unknown>;
  visibility?: 'public' | 'role' | 'account';
  visibility_roles?: string[];
  visibility_accounts?: string[];
  created_by?: string;
  updated_by?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ToolLog {
  _key?: string;
  tool_key: string;
  caller?: string;
  input_params?: Record<string, unknown>;
  output_result?: Record<string, unknown>;
  success: boolean;
  error_message?: string;
  duration_ms?: number;
  created_at?: string;
}

export const toolApi = {
  list: (toolType?: string) => {
    const url = toolType ? `/api/v1/tools?tool_type=${toolType}` : '/api/v1/tools';
    return api.get<{ code: number; data: Tool[] }>(url);
  },
  get: (key: string) => api.get<{ code: number; data: Tool }>(`/api/v1/tools/${key}`),
  create: (data: Partial<Tool>) => api.post('/api/v1/tools', data),
  update: (key: string, data: Partial<Tool>) => api.put(`/api/v1/tools/${key}`, data),
  delete: (key: string) => api.delete(`/api/v1/tools/${key}`),
  syncIntents: (key: string, data: { intent_tags: string[]; nl_examples: string[] }) =>
    api.post<{ code: number; message: string }>(`/api/v1/tools/${key}/intents`, data),
};

export const functionApi = {
  list: () => api.get<{ code: number; data: Function[] }>('/api/v1/functions'),
  get: (key: string) => api.get<{ code: number; data: Function }>(`/api/v1/functions/${key}`),
  create: (data: Partial<Function>) => api.post('/api/v1/functions', data),
  update: (key: string, data: Partial<Function>) => api.put(`/api/v1/functions/${key}`, data),
  delete: (key: string) => api.delete(`/api/v1/functions/${key}`),
  getRoles: (key: string) => api.get<{ code: number; data: FunctionRoleAuth }>(`/api/v1/functions/${key}/roles`),
  setRoles: (key: string, role_keys: string[], inherited_role_keys: string[] = []) => 
    api.put(`/api/v1/functions/${key}/roles`, { function_key: key, role_keys, inherited_role_keys }),
  getAuthorized: () => api.get<{ code: number; data: Function[] }>('/api/v1/auth/functions'),
};

export interface LLMModel {
  model_id: string;
  name: string;
  display_name?: string;
  context_window?: number;
  input_cost_per_1k?: number;
  output_cost_per_1k?: number;
  supports_vision?: boolean;
  status?: string;
}

export interface ModelProvider {
  _key: string;
  code: string;
  name: string;
  description?: string;
  icon?: string;
  base_url: string;
  api_key?: string;
  status: string;
  sort_order: number;
  models: LLMModel[];
  created_at: string;
  updated_at: string;
}

export const modelProviderApi = {
  list: () => api.get<{ code: number; data: ModelProvider[] }>('/api/v1/model-providers'),
  get: (key: string) => api.get<{ code: number; data: ModelProvider }>(`/api/v1/model-providers/${key}`),
  create: (data: Partial<ModelProvider>) => api.post('/api/v1/model-providers', data),
  update: (key: string, data: Partial<ModelProvider>) => api.put(`/api/v1/model-providers/${key}`, data),
  delete: (key: string) => api.delete(`/api/v1/model-providers/${key}`),
  sync: (key: string) => api.post(`/api/v1/model-providers/${key}/sync`),
};

// ===== Session Files =====

export interface SessionFile {
  file_key: string;
  filename: string;
  file_size: number;
  file_type: string;
  vector_status: string;
  graph_status: string;
  failed_reason?: string;
  upload_time: string;
  graph_stats: {
    nodes: number;
    edges: number;
  };
}

export interface FileStatusPayload {
  file_key: string;
  vector_status?: string;
  graph_status?: string;
  failed_reason?: string;
  graph_stats?: { nodes: number; edges: number };
}

export const sessionFilesApi = {
  list: (sessionKey: string) =>
    api.get<ApiResponse<SessionFile[]>>(`/api/v1/chat/sessions/${encodeURIComponent(sessionKey)}/files`),
  upload: (sessionKey: string, formData: FormData) =>
    api.post<ApiResponse<SessionFile>>(`/api/v1/chat/sessions/${encodeURIComponent(sessionKey)}/files`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  delete: (sessionKey: string, fileKey: string) =>
    api.delete<ApiMessage>(`/api/v1/chat/sessions/${encodeURIComponent(sessionKey)}/files?file_key=${encodeURIComponent(fileKey)}`),
};

// ===== Chat (任務聊天) =====

export interface ChatSession {
  _key: string;
  title: string | null;
  provider: string;
  model: string;
  status: string;
  tags_5w1h: Record<string, string> | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  _key: string;
  session_key: string;
  role: string;
  content: string;
  thinking?: string | null;
  tokens: number | null;
  created_at: string;
}

export interface CreateSessionRequest {
  title?: string;
  provider?: string;
  model?: string;
}

export interface SendMessageRequest {
  content: string;
  provider?: string;
  model?: string;
  temperature?: number;
  max_tokens?: number;
  assistant_context?: AssistantContextPayload;
}

export interface SessionWithMessages {
  session: ChatSession;
  messages: ChatMessage[];
}

export const chatApi = {
  createSession: (data: CreateSessionRequest) =>
    api.post<ApiResponse<ChatSession>>('/api/v1/chat/sessions', data),
  listSessions: () =>
    api.get<ApiResponse<ChatSession[]>>('/api/v1/chat/sessions'),
  getSession: (key: string) =>
    api.get<ApiResponse<SessionWithMessages>>(`/api/v1/chat/sessions/${key}`),
  updateSession: (key: string, data: { title?: string; status?: string; tags_5w1h?: Record<string, string> }) =>
    api.put<ApiResponse<ChatSession>>(`/api/v1/chat/sessions/${key}`, data),
  deleteSession: (key: string) =>
    api.delete<ApiResponse<string>>(`/api/v1/chat/sessions/${key}`),
};

export interface KbJobFile {
  _key: string;
  filename: string;
  file_size: number;
  file_type: string;
  upload_time: string;
  vector_status: string;
  graph_status: string;
  knowledge_root_id: string;
  s3_path?: string;
  local_path?: string;
  failed_reason?: string;
  vector_task_id?: string;
  graph_task_id?: string;
}

export interface JobLog {
  file_id: string;
  task_type: string;
  event: string;
  message: string;
  detail?: string;
  timestamp: string;
}

export const jobsApi = {
  list: (status?: 'active' | 'failed' | 'completed') =>
    api.get<{ code: number; data: KbJobFile[] }>(
      '/api/v1/jobs',
      status ? { params: { status } } : undefined,
    ),
  listStuck: () =>
    api.get<{ code: number; data: KbJobFile[] }>('/api/v1/jobs/stuck'),
  clear: (status: 'failed' | 'completed') =>
    api.delete<{ code: number; message: string }>('/api/v1/jobs/clear', {
      params: { status },
    }),
  abort: (fileKey: string) =>
    api.post<{ code: number; data: { file_id: string; revoked_tasks: string[] } }>(
      `/api/v1/jobs/${fileKey}/abort`,
    ),
  deleteJob: (fileKey: string) =>
    api.post<ApiResponse<{ status: string; file_id: string }>>(
      `/api/v1/jobs/${fileKey}/delete`,
    ),
  retry: (fileKey: string) =>
    api.post<ApiResponse<{ status: string; file_id: string; vector_task_id: string; graph_task_id: string }>>(
      `/api/v1/jobs/${fileKey}/retry`,
    ),
  logs: (fileKey: string) =>
    api.get<{ code: number; data: { file_id: string; logs: JobLog[]; count: number } }>(
      `/api/v1/jobs/${fileKey}/logs`,
    ),
};

export interface ShellTokens {
  siderBg: string;
  headerBg: string;
  menuItemColor: string;
  menuItemHoverBg: string;
  menuItemSelectedBg: string;
  menuItemSelectedColor: string;
  logoColor: string;
  siderBorder: string;
  headerShadow: string;
  siderShadow: string;
}

export interface ContentTokens {
  colorPrimary: string;
  colorSuccess: string;
  colorWarning: string;
  colorError: string;
  colorInfo: string;
  colorBgBase: string;
  colorTextBase: string;
  pageBg: string;
  contentBg: string;
  containerBg: string;
  borderRadius: number;
  fontFamily: string;
  boxShadow: string;
  boxShadowSecondary: string;
  tableExpandedRowBg: string;
  tableHeaderBg: string;
  tableRowHoverBg: string;
  chatInputBg: string;
  chatUserBubble: string;
  chatAssistantBubble: string;
  textSecondary: string;
  iconDefault: string;
  iconHover: string;
  btnClear: string;
  btnClearHover: string;
  btnSend: string;
  btnSendHover: string;
  btnText: string;
  cardShadow: string;
  cardShadowHover: string;
  tableShadow: string;
  bgOpacity: number;
  tooltipBg: string;
  tooltipText: string;
  tooltipBgOpacity: number;
}

export interface ThemeTemplate {
  _key: string;
  name: string;
  description: string;
  template_type: 'shell' | 'content';
  tokens: ShellTokens | ContentTokens;
  is_default: boolean;
  is_active?: boolean;
  status: string;
  created_at: string;
  updated_at: string;
}

export const themeTemplateApi = {
  list: () => api.get<{ code: number; data: ThemeTemplate[] }>('/api/v1/theme-templates'),
  get: (key: string) => api.get<{ code: number; data: ThemeTemplate }>(`/api/v1/theme-templates/${key}`),
  create: (data: Partial<ThemeTemplate>) => api.post('/api/v1/theme-templates', data),
  update: (key: string, data: Partial<ThemeTemplate>) => api.put(`/api/v1/theme-templates/${key}`, data),
  delete: (key: string) => api.delete(`/api/v1/theme-templates/${key}`),
  activate: (key: string) => api.put<{ code: number; message: string }>(`/api/v1/theme-templates/${key}/activate`, {}),
};

// ===== Ontology (知識本體) =====

export interface EntityClass {
  name: string;
  base_class: string;
  description: string;
}

export interface ObjectProperty {
  name: string;
  description: string;
  domain: string[];
  range: string[];
}

export type OntologyLayer = 'basic' | 'domain' | 'major';

export interface OntologyMetadata {
  domain_owner?: string;
  domain?: string;
  major_owner?: string;
  data_classification?: string;
  intended_usage?: string[];
}

export interface Ontology {
  _key: string;
  type: OntologyLayer;
  name: string;
  version: string;
  default_version: boolean;
  ontology_name: string;
  description: string;
  author: string;
  last_modified: string;
  inherits_from: string[];
  compatible_domains?: string[];
  tags: string[];
  use_cases: string[];
  entity_classes: EntityClass[];
  object_properties: ObjectProperty[];
  metadata: OntologyMetadata;
  status?: string;
}

export const ontologyApi = {
  list: (layer?: OntologyLayer) =>
    api.get<{ code: number; data: Ontology[] }>('/api/v1/ontologies', { params: layer ? { type: layer } : {} }),
  get: (key: string) =>
    api.get<{ code: number; data: Ontology }>(`/api/v1/ontologies/${key}`),
  create: (data: Partial<Ontology>) =>
    api.post('/api/v1/ontologies', data),
  importOntology: (data: Partial<Ontology>) =>
    api.post('/api/v1/ontologies/import', data),
  update: (key: string, data: Partial<Ontology>) =>
    api.put(`/api/v1/ontologies/${key}`, data),
  delete: (key: string) =>
    api.delete(`/api/v1/ontologies/${key}`),
};

// ===== Services =====

export type ServiceStatus = 'running' | 'stopped' | 'starting' | 'stopping' | 'error';

export interface ServiceInfo {
  name: string;
  display_name: string;
  status: ServiceStatus;
  port: number;
  url: string;
  health_url: string | null;
  last_check: string | null;
  latency_ms: number | null;
}

export interface ServiceListResponse {
  services: ServiceInfo[];
}

export const servicesApi = {
  list: () => api.get<ServiceListResponse>('/api/v1/services'),
  get: (name: string) => api.get<{ service: ServiceInfo }>(`/api/v1/services/${name}`),
  restart: (name: string) => api.post<{ success: boolean; message: string }>(`/api/v1/services/${name}/restart`),
};

// ===== Health Check (基礎設施健檢) =====

export interface HealthServices {
  main_api: boolean;
  chat_api: boolean;
  arangodb: boolean;
  qdrant: boolean;
}

export interface HealthResponse {
  status: string;
  version: string;
  uptime: number;
  services: HealthServices;
}

export const healthApi = {
  check: () => api.get<HealthResponse>('/health'),
};

// ===== Knowledge Base (知識庫) =====

export interface KnowledgeRoot {
  _key: string;
  name: string;
  description?: string;
  ontology_domain: string;
  ontology_majors: string[];
  tags: string[];
  source_count: number;
  vector_status: 'pending' | 'processing' | 'completed' | 'failed';
  graph_status: 'pending' | 'processing' | 'completed' | 'failed';
  is_favorite: boolean;
  created_at: string;
}

export interface KnowledgeFile {
  _key: string;
  filename: string;
  file_size: number;
  file_type: string;
  upload_time: string;
  vector_status: 'pending' | 'processing' | 'queued' | 'completed' | 'failed';
  graph_status: 'pending' | 'processing' | 'queued' | 'completed' | 'failed';
  knowledge_root_id: string;
  document_type?: string[];
  document_summary?: string;
  ontology_major?: string;
}

export interface VectorChunk {
  chunk_id: string;
  text: string;
  vector_preview: number[];
  metadata: Record<string, string>;
}

export interface SimilarChunk {
  chunk_id: string;
  text: string;
  score: number;
  metadata?: Record<string, string>;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties: Record<string, string>;
}

export interface GraphEdge {
  source: string;
  target: string;
  label: string;
}

export interface PreviewData {
  file_id: string;
  type: 'markdown' | 'text' | 'table' | 'binary' | 'pdf_url';
  content?: string;
  headers?: string[];
  rows?: Record<string, string | number>[];
  message?: string;
  url?: string;
}

export interface KnowledgeRoleAuth {
  root_key: string;
  role_keys: string[];
  inherited_role_keys: string[];
}

interface ApiResponse<T> { code: number; data: T }
interface ApiMessage { code: number; message: string }

export const knowledgeApi = {
  listRoots: (params?: { search?: string; is_favorite?: boolean }) =>
    api.get<ApiResponse<KnowledgeRoot[]>>('/api/v1/knowledge/roots', { params }),
  createRoot: (data: Partial<KnowledgeRoot>) =>
    api.post<ApiResponse<{ _key: string }>>('/api/v1/knowledge/roots', data),
  getRoot: (id: string) =>
    api.get<ApiResponse<KnowledgeRoot>>(`/api/v1/knowledge/roots/${id}`),
  updateRoot: (id: string, data: Partial<KnowledgeRoot>) =>
    api.put<ApiMessage>(`/api/v1/knowledge/roots/${id}`, data),
  deleteRoot: (id: string) =>
    api.delete<ApiMessage>(`/api/v1/knowledge/roots/${id}`),
  copyRoot: (id: string) =>
    api.post<ApiResponse<{ _key: string }>>(`/api/v1/knowledge/roots/${id}/copy`),
  toggleFavorite: (id: string) =>
    api.patch<ApiResponse<{ is_favorite: boolean }>>(`/api/v1/knowledge/roots/${id}/favorite`),
  listFiles: (rootId: string) =>
    api.get<ApiResponse<KnowledgeFile[]>>(`/api/v1/knowledge/roots/${rootId}/files`),
  uploadFile: (rootId: string, formData: FormData) =>
    api.post<ApiResponse<{ fileId: string }>>(`/api/v1/knowledge/roots/${rootId}/files/upload`, formData),
  getFile: (fileId: string) =>
    api.get<ApiResponse<KnowledgeFile>>(`/api/v1/knowledge/files/${fileId}`),
  deleteFile: (fileId: string) =>
    api.delete<ApiMessage>(`/api/v1/knowledge/files/${fileId}`),
  getPreview: (fileId: string) =>
    api.get<ApiResponse<PreviewData>>(`/api/v1/knowledge/files/${fileId}/preview`),
  getVectors: (fileId: string, params: { limit: number; offset: number }) =>
    api.get<ApiResponse<{ chunks: VectorChunk[]; total: number }>>(`/api/v1/knowledge/files/${fileId}/vectors`, { params }),
  getGraph: (fileId: string) =>
    api.get<ApiResponse<{ nodes: GraphNode[]; edges: GraphEdge[] }>>(`/api/v1/knowledge/files/${fileId}/graph`),
  getSimilarChunks: (fileId: string, chunkId: string, topK: number = 10) =>
    api.get<ApiResponse<{ similar: SimilarChunk[] }>>(
      `/api/v1/knowledge/files/${fileId}/similar`,
      { params: { chunk_id: chunkId, top_k: topK } },
    ),
  regenerateFile: (fileId: string) =>
    api.post<ApiResponse<{ status: string; vector_task_id: string; graph_task_id: string }>>(`/api/v1/knowledge/files/${fileId}/regenerate`),
  regenerateVector: (fileId: string) =>
    api.post<ApiResponse<{ status: string; file_id: string; type: string; task_id: string }>>(`/api/v1/knowledge/files/${fileId}/regenerate-vector`),
  regenerateGraph: (fileId: string) =>
    api.post<ApiResponse<{ status: string; file_id: string; type: string; task_id: string }>>(`/api/v1/knowledge/files/${fileId}/regenerate-graph`),
  getRoles: (rootId: string) =>
    api.get<ApiResponse<KnowledgeRoleAuth>>(`/api/v1/knowledge/roots/${rootId}/roles`),
  setRoles: (rootId: string, role_keys: string[], inherited_role_keys: string[]) =>
    api.put<ApiMessage>(`/api/v1/knowledge/roots/${rootId}/roles`, { role_keys, inherited_role_keys }),
};

export interface DaSchemaModule {
  key: string;
  label: string;
  source: string;
}

export const daApi = {
  listSchemaModules: () =>
    api.get<ApiResponse<DaSchemaModule[]>>('/api/v1/da/schema/modules'),
};

export interface SchemaReportRecord {
  _key: string;
  table_id: string;
  report_name: string;
  report_url: string;
  chart_type?: string;
  analysis_summary?: string;
  username: string;
  created_at: string;
}

export const schemaReportsApi = {
  list: (tableId: string) =>
    api.get<ApiResponse<SchemaReportRecord[]>>(`/api/v1/da/schema-reports?table_id=${encodeURIComponent(tableId)}`),
  create: (data: Omit<SchemaReportRecord, '_key'>) =>
    api.post<ApiResponse<SchemaReportRecord>>('/api/v1/da/schema-reports', data),
  patch: (key: string, data: Record<string, unknown>) =>
    api.patch<ApiResponse<SchemaReportRecord>>(`/api/v1/da/schema-reports/${key}`, data),
  delete: (key: string) =>
    api.delete<ApiResponse<{ _key: string }>>(`/api/v1/da/schema-reports/${key}`),
};

export interface SchemaReportTemplate {
  _key: string;
  table_id: string;
  name: string;
  goal: string;
  description: string;
  chart_type: string;
  notes: string;
  created_at: string;
}

export const schemaReportTemplatesApi = {
  list: (tableId: string) =>
    api.get<ApiResponse<SchemaReportTemplate[]>>(
      `/api/v1/da/schema-report-templates?table_id=${encodeURIComponent(tableId)}`
    ),
  create: (data: Omit<SchemaReportTemplate, '_key' | 'created_at'>) =>
    api.post<ApiResponse<SchemaReportTemplate>>('/api/v1/da/schema-report-templates', data),
  delete: (key: string) =>
    api.delete<ApiResponse<{ _key: string }>>(`/api/v1/da/schema-report-templates/${key}`),
};

export const downloadFile = async (fileId: string): Promise<Blob> => {
  const token = localStorage.getItem('token');
  const resp = await fetch(`/api/v1/knowledge/files/${encodeURIComponent(fileId)}/download`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!resp.ok) {
    const detail = await resp.text().catch(() => `HTTP ${resp.status}`);
    throw new Error(detail || `下載失敗 (${resp.status})`);
  }
  return resp.blob();
};

export interface Lead {
  _key: string;
  name: string;
  company: string;
  email: string;
  phone: string | null;
  budget: string | null;
  message: string | null;
  github: string | null;
  status: 'pending' | 'approved' | 'rejected';
  note: string | null;
  can_download: boolean;
  open_github: boolean;
  created_at: string;
  updated_at: string | null;
  approved_at: string | null;
  approved_by: string | null;
}

export interface LeadListResponse {
  leads: Lead[];
  total: number;
  page: number;
  page_size: number;
}

export const leadApi = {
  list: (params?: { status?: string; page?: number; page_size?: number }) =>
    api.get<{ code: number; message: string; data: LeadListResponse }>('/api/v1/leads/admin/list', { params }),
  get: (key: string) =>
    api.get<{ code: number; message: string; data: Lead }>(`/api/v1/leads/admin/${key}`),
  update: (key: string, data: Partial<Lead>) =>
    api.put(`/api/v1/leads/admin/${key}`, data),
  approve: (key: string, data: { note?: string; can_download?: boolean; open_github?: boolean }) =>
    api.put(`/api/v1/leads/admin/${key}/approve`, data),
  reject: (key: string, data: { note?: string }) =>
    api.put(`/api/v1/leads/admin/${key}/reject`, data),
  delete: (key: string) =>
    api.delete(`/api/v1/leads/admin/${key}`),
};

// ─── Backup ─────────────────────────────────────────────────────────────────────

export interface BackupSnapshot {
  collection: string;
  snapshot_id: string;
  snapshot_name: string;
  size_bytes: number;
  size_mb: number;
}

export interface BackupRecord {
  backup_id: string;
  backup_name: string;
  backup_path: string;
  size_mb: number;
  size_bytes: number;
  status: string;
  duration_seconds: number;
  strategy: string;
  collections_count?: number;
  collections?: string[];
  snapshots?: BackupSnapshot[];
  created_at: string;
  error?: string;
}

export interface DiskUsage {
  total_gb: number;
  used_gb: number;
  free_gb: number;
  usage_percent: number;
}

export interface DeleteResult {
  backup_id: string;
  deleted: string[];
  errors: string[];
  status: string;
}

export interface BackupStatus {
  arangodb: DiskUsage & { backup_count: number };
  qdrant: DiskUsage & { backup_count: number };
}

export const backupApi = {
  // ArangoDB
  backupArango: (data: { backup_path?: string; retention?: number }) =>
    api.post<ApiResponse<BackupRecord>>('/api/v1/backup/arangodb', data),
  restoreArango: (backup_id: string) =>
    api.post<ApiResponse<BackupRecord>>('/api/v1/backup/arangodb/restore', { backup_id }),
  arangoHistory: () =>
    api.get<ApiResponse<BackupRecord[]>>('/api/v1/backup/arangodb/history'),
  deleteArangoBackup: (backup_id: string) =>
    api.delete<ApiResponse<DeleteResult>>(`/api/v1/backup/arangodb/${backup_id}`),
  arangoDiskUsage: () =>
    api.get<ApiResponse<DiskUsage>>('/api/v1/backup/arangodb/disk-usage'),

  // Qdrant
  backupQdrant: (data: { backup_path?: string; retention?: number; collections?: string[] }) =>
    api.post<ApiResponse<BackupRecord>>('/api/v1/backup/qdrant', data),
  restoreQdrant: (backup_id: string, collection_name?: string) =>
    api.post<ApiResponse<BackupRecord>>('/api/v1/backup/qdrant/restore', { backup_id, collection_name }),
  qdrantHistory: () =>
    api.get<ApiResponse<BackupRecord[]>>('/api/v1/backup/qdrant/history'),
  deleteQdrantBackup: (backup_id: string) =>
    api.delete<ApiResponse<DeleteResult>>(`/api/v1/backup/qdrant/${backup_id}`),
  qdrantDiskUsage: () =>
    api.get<ApiResponse<DiskUsage>>('/api/v1/backup/qdrant/disk-usage'),

  // Status
  status: () =>
    api.get<ApiResponse<BackupStatus>>('/api/v1/backup/status'),
};

// LINE Platform API
export interface LINEChannel {
  _key: string;
  official_account_key: string;
  channel_name: string;
  channel_id: string;
  channel_secret?: string;
  channel_access_token?: string;
  webhook_url: string;
  webhook_enabled: boolean;
  bot_user_id?: string;
  publication_status: 'unpublished' | 'published' | 'error';
  published_bot_key?: string;
  published_bot_name?: string;
  linked_agent_key?: string;
  last_connected_at?: string;
  created_at: string;
  channel_icon?: string;
  channel_description?: string;
}

export interface LINEOfficialAccount {
  _key: string;
  provider_name: string;
  name: string;
  status: 'active' | 'inactive' | 'error';
  channels: LINEChannel[];
  created_at: string;
  updated_at: string;
}

export interface CreateOfficialAccountRequest {
  provider_name: string;
  name: string;
}

export interface CreateChannelRequest {
  channel_name: string;
  channel_id: string;
  channel_secret: string;
  channel_access_token: string;
  channel_icon?: string;
  channel_description?: string;
}

export interface UpdateChannelRequest {
  channel_name?: string;
  channel_id?: string;
  channel_secret?: string;
  channel_access_token?: string;
  webhook_enabled?: boolean;
  channel_icon?: string;
  channel_description?: string;
  linked_agent_key?: string;
}

export interface PublishChannelRequest {
  bot_key: string;
  greeting?: string;
  delay?: number;
}

export interface TestConnectionResult {
  success: boolean;
  bot_user_id?: string;
  error?: string;
}

export const linePlatformApi = {
  // Official Accounts
  listOfficialAccounts: () =>
    api.get<ApiResponse<LINEOfficialAccount[]>>('/api/v1/platforms/line/official-accounts'),
  getOfficialAccount: (key: string) =>
    api.get<ApiResponse<LINEOfficialAccount>>(`/api/v1/platforms/line/official-accounts/${key}`),
  createOfficialAccount: (data: CreateOfficialAccountRequest) =>
    api.post<ApiResponse<LINEOfficialAccount>>('/api/v1/platforms/line/official-accounts', data),
  updateOfficialAccount: (key: string, data: Partial<LINEOfficialAccount>) =>
    api.put<ApiResponse<LINEOfficialAccount>>(`/api/v1/platforms/line/official-accounts/${key}`, data),
  deleteOfficialAccount: (key: string) =>
    api.delete<ApiResponse<{ message: string }>>(`/api/v1/platforms/line/official-accounts/${key}`),

  // Channels
  createChannel: (officialAccountKey: string, data: CreateChannelRequest) =>
    api.post<ApiResponse<LINEChannel>>(
      `/api/v1/platforms/line/official-accounts/${officialAccountKey}/channels`,
      data,
    ),
  getChannel: (channelKey: string) =>
    api.get<ApiResponse<LINEChannel>>(`/api/v1/platforms/line/channels/${channelKey}`),
  updateChannel: (channelKey: string, data: UpdateChannelRequest) =>
    api.put<ApiResponse<LINEChannel>>(`/api/v1/platforms/line/channels/${channelKey}`, data),
  deleteChannel: (channelKey: string) =>
    api.delete<ApiResponse<{ message: string }>>(`/api/v1/platforms/line/channels/${channelKey}`),

  // Connection & Publish
  testConnection: (channelKey: string) =>
    api.post<ApiResponse<TestConnectionResult>>(
      `/api/v1/platforms/line/channels/${channelKey}/test-connection`,
    ),
  publishChannel: (channelKey: string, data: PublishChannelRequest) =>
    api.post<ApiResponse<{ success: boolean; message: string }>>(
      `/api/v1/platforms/line/channels/${channelKey}/publish`,
      data,
    ),
  unpublishChannel: (channelKey: string) =>
    api.delete<ApiResponse<{ success: boolean; message: string }>>(
      `/api/v1/platforms/line/channels/${channelKey}/publish`,
    ),
};

export default api;

// Ragic Session History
export interface RagicHistoryMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
  created_at?: string;
  metadata?: {
    media_type?: string;
    media_url?: string;
    seaweed_url?: string;
    file_name?: string;
    file_url?: string;
    file_size?: number;
  };
}

export interface RagicSessionHistoryResponse {
  session_id: string;
  history: RagicHistoryMessage[];
  count: number;
}

export const ragicApi = {
  getChatHistory: (sessionId: string, limit: number = 50) =>
    api.get<RagicSessionHistoryResponse>(`/api/v1/ragic/session/${sessionId}/history?limit=${limit}`),
  listSessions: (platform: string = 'line', channelId?: string) =>
    api.get<{ sessions: any[]; count: number }>(
      `/api/v1/ragic/sessions?platform=${platform}&channel_id=${channelId || ''}`
    ),
};

export interface ToolExecuteResult {
  tool: string;
  success: boolean;
  result?: {
    report_url: string;
    filename: string;
    title: string;
    chart_type: string;
    analysis_summary: string;
    size_bytes: number;
    warnings: string[];
  };
  error: string | null;
}

export const toolsApi = {
  execute: (tool: string, parameters: Record<string, unknown>) =>
    api.post<ToolExecuteResult>('/api/v1/mcp/execute', { tool, parameters }, { timeout: 300000 }),
  executeAsync: (tool: string, parameters: Record<string, unknown>) =>
    api.post<ToolExecuteResult>('/api/v1/mcp/execute-async', { tool, parameters }, { timeout: 15000 }),
};
