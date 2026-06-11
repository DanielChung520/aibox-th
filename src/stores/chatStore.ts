/**
 * @file        任務聊天狀態管理
 * @description 管理聊天工作階段、訊息列表、模型供應商與 SSE 串流狀態
 * @lastUpdate  2026-04-23 20:09:00
 * @author      Daniel Chung
 * @version     1.5.0
 */

import {
  ChatMessage,
  ChatSession,
  FileStatusPayload,
  ModelProvider,
  SendMessageRequest,
  chatApi,
  modelProviderApi,
  paramsApi,
} from '../services/api';
import { SSEConnection, sendMessageSSE } from '../services/sseManager';
import { ChatState, INITIAL_CHAT_STATE, type DataSourceRecord } from './chatStoreTypes';
import type { AssistantContextPayload } from '../types/assistantContext';
import {
  loadSessionFiles as loadFiles,
  uploadFile as uploadFileHelper,
  deleteFile as deleteFileHelper,
  applyFileStatusUpdate as applyFileUpdate,
} from './chatStoreFiles';

class ChatStore {
  namespace: string = 'default';

  private state: ChatState = { ...INITIAL_CHAT_STATE };

  private listeners: Set<() => void> = new Set();

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  getState(): ChatState {
    return this.state;
  }

  setActiveSessionKey(key: string | null) {
    this.setState({ activeSessionKey: key });
    try {
      if (key) {
        localStorage.setItem(`chat_active_session_${this.namespace}`, key);
      } else {
        localStorage.removeItem(`chat_active_session_${this.namespace}`);
      }
    } catch { /* localStorage unavailable */ }
  }

  /** 取得上次持久化的 session key（reload 後恢復） */
  getLastSessionKey(): string | null {
    try {
      return localStorage.getItem(`chat_active_session_${this.namespace}`);
    } catch {
      return null;
    }
  }

  resetCurrentSession() {
    this.activeConnection?.abort();
    this.activeConnection = null;
    try { localStorage.removeItem(`chat_active_session_${this.namespace}`); } catch { /* noop */ }
    this.setState({
      messages: [],
      uploadedFiles: [],
      streamingContent: '',
      streamingThinking: '',
      isStreaming: false,
      activeSessionKey: null,
    });
  }

  addLocalMessage(role: 'user' | 'assistant' | 'system', content: string): string {
    const key = `local-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const msg: ChatMessage = {
      _key: key,
      session_key: this.state.activeSessionKey || '',
      role,
      content,
      thinking: null,
      tokens: null,
      created_at: new Date().toISOString(),
    };
    this.setState({ messages: [...this.state.messages, msg] });
    return key;
  }

  addDataSource(record: DataSourceRecord) {
    this.setState({ dataSources: [...this.state.dataSources, record] });
  }

  clearDataSources() {
    this.setState({ dataSources: [] });
  }

  removeMessageByKey(key: string) {
    this.setState({ messages: this.state.messages.filter((m) => m._key !== key) });
  }

  private lastFinishedContent: string = '';

  private activeConnection: SSEConnection | null = null;

  private setState(next: Partial<ChatState>) {
    this.state = { ...this.state, ...next };
    this.listeners.forEach((listener) => listener());
  }

  private getDefaultProviderCode(): string | null {
    return this.state.chatDefaults['task_chat.default_provider'] ?? null;
  }

  private getDefaultModel(): string | undefined {
    return this.state.chatDefaults['task_chat.default_model'] || undefined;
  }

  private getDefaultNumber(key: string): number | undefined {
    const raw = this.state.chatDefaults[key];
    const parsed = raw ? Number(raw) : Number.NaN;
    return Number.isFinite(parsed) ? parsed : undefined;
  }

  private getProviderByCode(code: string | null): ModelProvider | undefined {
    return code ? this.state.providers.find((p) => p.code === code) : undefined;
  }

  private resolveProviderModel(providerConfig: ModelProvider | undefined, preferredModel?: string): string | undefined {
    const models = providerConfig?.models ?? [];
    if (!models.length) {
      return preferredModel;
    }

    if (preferredModel && models.some((model) => model.model_id === preferredModel)) {
      return preferredModel;
    }

    return models.find((model) => model.status === 'enabled')?.model_id
      ?? models[0]?.model_id
      ?? preferredModel;
  }

  private parseAssistantChatModel(raw: string | undefined): { provider?: string; model?: string } {
    if (!raw) {
      return {};
    }

    const trimmed = raw.trim();
    if (!trimmed) {
      return {};
    }

    const separatorIndex = trimmed.indexOf(':');
    if (separatorIndex <= 0 || separatorIndex === trimmed.length - 1) {
      return { model: trimmed };
    }

    const providerCandidate = trimmed.slice(0, separatorIndex);
    const modelCandidate = trimmed.slice(separatorIndex + 1);
    const hasMatchingProvider = this.state.providers.some((provider) => provider.code === providerCandidate);

    if (!hasMatchingProvider) {
      return { model: trimmed };
    }

    return {
      provider: providerCandidate,
      model: modelCandidate,
    };
  }

  private async resolveChatTarget(): Promise<{ provider?: string; model?: string }> {
    let provider = this.state.selectedProvider ?? this.getDefaultProviderCode() ?? undefined;
    let providerConfig = this.getProviderByCode(provider ?? null);
    let model = this.resolveProviderModel(providerConfig, this.getDefaultModel());

    if (this.namespace === 'aiq') {
      try {
        const response = await paramsApi.get('floating_assistant.chatModel');
        const raw = response.data?.data?.param_value;
        const preferred = this.parseAssistantChatModel(raw);

        if (preferred.provider) {
          provider = preferred.provider;
          providerConfig = this.getProviderByCode(provider ?? null);
          model = this.resolveProviderModel(providerConfig, preferred.model ?? model);
        }

        if (preferred.model) {
          model = this.resolveProviderModel(providerConfig, preferred.model);
        } else if (preferred.provider) {
          model = this.resolveProviderModel(providerConfig, model);
        }
      } catch {
        // fallback to task_chat defaults when assistant-specific param is unavailable
      }
    }

    return { provider, model };
  }

  async loadProviders(): Promise<void> {
    const response = await modelProviderApi.list();
    const providers = response.data.data || [];
    this.setState({ providers });

    await this.loadChatDefaults();

    if (!this.state.selectedProvider) {
      const defaultProvider = this.getDefaultProviderCode();
      const validProvider = this.getProviderByCode(defaultProvider);
      this.setState({ selectedProvider: validProvider?.code ?? providers[0]?.code ?? null });
    }
  }

  async loadChatDefaults(): Promise<void> {
    const response = await paramsApi.list();
    const rows = response.data.data || [];
    const chatDefaults = rows
      .filter((item) => item.category === 'task_chat')
      .reduce<Record<string, string>>((acc, item) => {
        acc[item.param_key] = item.param_value;
        return acc;
      }, {});

    const greeting = chatDefaults['task_chat.greeting_message'] ?? '';
    const defaultProvider = chatDefaults['task_chat.default_provider'] ?? null;
    const selectedProvider = this.state.selectedProvider ?? defaultProvider;

    this.setState({
      chatDefaults,
      greeting,
      selectedProvider,
    });
  }

  setSelectedProvider(providerCode: string | null) {
    this.setState({ selectedProvider: providerCode });
  }

  async deleteSession(sessionKey: string): Promise<void> {
    await chatApi.deleteSession(sessionKey);
    this.setState({
      sessions: this.state.sessions.filter((s) => s._key !== sessionKey),
    });
    if (this.state.activeSessionKey === sessionKey) {
      this.setActiveSessionKey(null);
      this.setState({ messages: [], uploadedFiles: [] });
    }
  }

  async batchDeleteSessions(sessionKeys: string[]): Promise<void> {
    await Promise.allSettled(sessionKeys.map((key) => chatApi.deleteSession(key)));
    const keySet = new Set(sessionKeys);
    this.setState({
      sessions: this.state.sessions.filter((s) => !keySet.has(s._key)),
    });
    if (keySet.has(this.state.activeSessionKey ?? '')) {
      this.setActiveSessionKey(null);
      this.setState({ messages: [], uploadedFiles: [] });
    }
  }

  async createSession(provider?: string, model?: string): Promise<ChatSession> {
    const preferredProvider = provider ?? this.state.selectedProvider ?? this.getDefaultProviderCode() ?? undefined;
    const payload = {
      provider: preferredProvider,
      model: model ?? this.getDefaultModel(),
    };
    const response = await chatApi.createSession(payload);
    const session = response.data.data;
    this.setActiveSessionKey(session._key);
    await this.loadSessions();
    return session;
  }

  async loadSessions(): Promise<void> {
    this.setState({ isLoadingSessions: true });
    try {
      const response = await chatApi.listSessions();
      this.setState({ sessions: response.data.data || [] });
    } finally {
      this.setState({ isLoadingSessions: false });
    }
  }

  async loadSessionMessages(sessionKey: string): Promise<void> {
    const response = await chatApi.getSession(sessionKey);
    const payload = response.data.data;
    this.setActiveSessionKey(payload.session._key);
    this.setState({
      messages: payload.messages || [],
      streamingContent: '',
      streamingThinking: '',
      isStreaming: false,
    });
  }

  addUserMessage(content: string) {
    this.addLocalMessage('user', content);
  }

  truncateAfter(key: string) {
    const idx = this.state.messages.findIndex((m) => m._key === key);
    if (idx >= 0) this.setState({ messages: this.state.messages.slice(0, idx + 1) });
  }

  updateMessage(key: string, content: string) {
    this.setState({ messages: this.state.messages.map((m) => m._key === key ? { ...m, content } : m) });
  }

  async retryMessage(key: string): Promise<SSEConnection | null> {
    const msg = this.state.messages.find((m) => m._key === key);
    if (!msg || msg.role !== 'user') return null;

    this.truncateAfter(key);
    return this.sendMessage(msg.content);
  }

  async editAndResend(key: string, newContent: string): Promise<SSEConnection | null> {
    this.updateMessage(key, newContent);
    this.truncateAfter(key);
    return this.sendMessage(newContent);
  }

  startStreaming() {
    this.lastFinishedContent = '';
    this.setState({ isStreaming: true, streamingContent: '', streamingThinking: '' });
  }

  stopStreaming() {
    this.activeConnection?.abort();
    this.activeConnection = null;
    this.setState({ isStreaming: false, streamingContent: '', streamingThinking: '' });
  }

  appendStreamChunk(delta: string) {
    this.setState({ streamingContent: `${this.state.streamingContent}${delta}` });
  }

  appendThinkingChunk(delta: string) {
    this.setState({ streamingThinking: `${this.state.streamingThinking}${delta}` });
  }

  finishStreaming(fullContent: string, thinkingContent: string) {
    if (!this.state.isStreaming) return;
    const content = fullContent.trim();
    if (content === this.lastFinishedContent) return;
    this.lastFinishedContent = content;
    const thinking = thinkingContent.trim();
    if (!content) {
      this.activeConnection = null;
      this.setState({ isStreaming: false, streamingContent: '', streamingThinking: '' });
      return;
    }

    const sessionKey = this.state.activeSessionKey ?? '';
    const message: ChatMessage = {
      _key: `local-assistant-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      session_key: sessionKey,
      role: 'assistant',
      content,
      thinking: thinking || null,
      tokens: null,
      created_at: new Date().toISOString(),
    };

    this.setState({
      messages: [...this.state.messages, message],
      isStreaming: false,
      streamingContent: '',
      streamingThinking: '',
    });
    this.activeConnection = null;

    void this.generateSessionTitle();
    void this.loadSessions();
  }

  handleStreamError(error: string) {
    if (!this.state.isStreaming) return;
    const message: ChatMessage = {
      _key: `local-error-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      session_key: this.state.activeSessionKey ?? '',
      role: 'assistant',
      content: `發生錯誤：${error}`,
      thinking: null,
      tokens: null,
      created_at: new Date().toISOString(),
    };

    this.setState({
      isStreaming: false,
      streamingContent: '',
      streamingThinking: '',
      messages: [...this.state.messages, message],
    });
    this.activeConnection = null;
  }

  async sendMessage(content: string, assistantContext?: AssistantContextPayload): Promise<SSEConnection | null> {
    const trimmed = content.trim();
    if (!trimmed || this.state.isStreaming) {
      return null;
    }

    const { provider: selectedProvider, model: resolvedModel } = await this.resolveChatTarget();

    let activeSessionKey = this.state.activeSessionKey;
    if (!activeSessionKey) {
      const session = await this.createSession(selectedProvider, resolvedModel);
      activeSessionKey = session._key;
    }

    this.addUserMessage(trimmed);
    this.clearDataSources();
    this.startStreaming();

    const request: SendMessageRequest = {
      content: trimmed,
      provider: selectedProvider,
      model: resolvedModel,
      temperature: this.getDefaultNumber('task_chat.temperature'),
      max_tokens: this.getDefaultNumber('task_chat.max_tokens'),
      assistant_context: assistantContext,
    };

    let streamedContent = '';
    let streamedThinking = '';

    this.activeConnection?.abort();

    const connection = sendMessageSSE(activeSessionKey, request, {
      onChunk: (delta) => {
        streamedContent += delta;
        this.appendStreamChunk(delta);
      },
      onThinkingChunk: (delta) => {
        streamedThinking += delta;
        this.appendThinkingChunk(delta);
      },
      onDone: () => {
        this.finishStreaming(streamedContent, streamedThinking);
      },
      onError: (error) => {
        this.handleStreamError(error);
      },
      onToolCallStart: (data) => {
        this.addDataSource({ type: 'tool', label: data.tool, detail: JSON.stringify(data.parameters), success: true, timestamp: Date.now() });
      },
      onToolCallResult: (data) => {
        this.addDataSource({ type: 'tool', label: data.tool, detail: data.success ? '完成' : '失敗', success: data.success, duration_ms: data.duration_ms, timestamp: Date.now() });
      },
      onDaQueryStart: (data) => {
        this.addDataSource({ type: 'database', label: 'Data Agent 查詢', detail: data.query.slice(0, 100), success: true, timestamp: Date.now() });
      },
      onDaQueryResult: (data) => {
        this.addDataSource({ type: 'database', label: '查詢結果', detail: data.sql ? `SQL: ${data.sql.slice(0, 80)}` : `回傳 ${data.row_count ?? '?'} 筆`, success: data.success, row_count: data.row_count, timestamp: Date.now() });
      },
      onKaSearchResult: (data) => {
        for (const r of data.results.slice(0, 3)) {
          this.addDataSource({ type: 'knowledge', label: r.source, detail: r.content.slice(0, 100), success: true, timestamp: Date.now() });
        }
      },
    });

    this.activeConnection = connection;

    return connection;
  }

  async updateSessionTitle(sessionKey: string, title: string): Promise<void> {
    const response = await chatApi.updateSession(sessionKey, { title });
    const updated = response.data.data;
    const sessions = this.state.sessions.map((s) => (s._key === updated._key ? updated : s));
    this.setState({ sessions });
  }

  async generateSessionTitle(): Promise<void> {
    const sessionKey = this.state.activeSessionKey;
    if (!sessionKey) return;
    if (this.state.sessions.find((s) => s._key === sessionKey)?.title) return;
    const first = this.state.messages.find((m) => m.role === 'user' && m.content.trim());
    if (!first) return;
    const raw = first.content.trim();
    await this.updateSessionTitle(sessionKey, raw.length > 20 ? `${raw.slice(0, 20)}...` : raw);
  }

  async loadSessionFiles(sessionKey: string): Promise<void> {
    await loadFiles(sessionKey, (next) => this.setState(next));
  }

  async uploadFile(sessionKey: string, file: File): Promise<void> {
    await uploadFileHelper(sessionKey, file, this.state.uploadedFiles, (next) => this.setState(next));
  }

  async deleteFile(sessionKey: string, fileKey: string): Promise<void> {
    await deleteFileHelper(sessionKey, fileKey, this.state.uploadedFiles, (next) => this.setState(next));
  }

  applyFileStatusUpdate(payload: FileStatusPayload): void {
    applyFileUpdate(payload, this.state.uploadedFiles, (next) => this.setState(next));
  }
}

export const chatStore = new ChatStore();

export function createNamespacedChatStore(namespace: string) {
  const store = new ChatStore();
  store.namespace = namespace;
  return store;
}

const taskChatStore = createNamespacedChatStore('task');
const ragicChatStore = createNamespacedChatStore('ragic');
const aiqChatStore = createNamespacedChatStore('aiq');

export { taskChatStore, ragicChatStore, aiqChatStore };

export type { ChatState } from './chatStoreTypes';
