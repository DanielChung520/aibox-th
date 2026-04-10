/**
 * @file        任務聊天狀態管理
 * @description 管理聊天工作階段、訊息列表、模型供應商與 SSE 串流狀態
 * @lastUpdate  2026-03-27 12:12:03
 * @author      Daniel Chung
 * @version     1.0.0
 */

import {
  ChatMessage,
  ChatSession,
  FileStatusPayload,
  ModelProvider,
  SendMessageRequest,
  SessionFile,
  chatApi,
  modelProviderApi,
  paramsApi,
  sessionFilesApi,
} from '../services/api';
import { SSEConnection, sendMessageSSE } from '../services/sseManager';

interface ChatState {
  sessions: ChatSession[];
  activeSessionKey: string | null;
  messages: ChatMessage[];
  streamingContent: string;
  streamingThinking: string;
  isStreaming: boolean;
  isLoadingSessions: boolean;
  selectedProvider: string | null;
  providers: ModelProvider[];
  greeting: string;
  chatDefaults: Record<string, string>;
  uploadedFiles: SessionFile[];
}

class ChatStore {
  namespace: string = 'default';

  private state: ChatState = {
    sessions: [],
    activeSessionKey: null,
    messages: [],
    streamingContent: '',
    streamingThinking: '',
    isStreaming: false,
    isLoadingSessions: false,
    selectedProvider: null,
    providers: [],
    greeting: '',
    chatDefaults: {},
    uploadedFiles: [],
  };

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
  }

  resetCurrentSession() {
    this.setState({
      messages: [],
      uploadedFiles: [],
      streamingContent: '',
      streamingThinking: '',
      isStreaming: false,
    });
  }

  private lastFinishedContent: string = '';

  private setState(next: Partial<ChatState>) {
    this.state = { ...this.state, ...next };
    this.notify();
  }

  private notify() {
    this.listeners.forEach((listener) => listener());
  }

  private getDefaultProviderCode(): string | null {
    return this.state.chatDefaults['task_chat.default_provider'] ?? null;
  }

  private getDefaultModel(): string | undefined {
    const model = this.state.chatDefaults['task_chat.default_model'];
    return model || undefined;
  }

  private getDefaultTemperature(): number | undefined {
    const raw = this.state.chatDefaults['task_chat.temperature'];
    const parsed = raw ? Number(raw) : Number.NaN;
    return Number.isFinite(parsed) ? parsed : undefined;
  }

  private getDefaultMaxTokens(): number | undefined {
    const raw = this.state.chatDefaults['task_chat.max_tokens'];
    const parsed = raw ? Number(raw) : Number.NaN;
    return Number.isFinite(parsed) ? parsed : undefined;
  }

  private getProviderByCode(code: string | null): ModelProvider | undefined {
    if (!code) return undefined;
    return this.state.providers.find((provider) => provider.code === code);
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
      this.setState({ activeSessionKey: null, messages: [], uploadedFiles: [] });
    }
  }

  async batchDeleteSessions(sessionKeys: string[]): Promise<void> {
    await Promise.allSettled(sessionKeys.map((key) => chatApi.deleteSession(key)));
    const keySet = new Set(sessionKeys);
    this.setState({
      sessions: this.state.sessions.filter((s) => !keySet.has(s._key)),
    });
    if (keySet.has(this.state.activeSessionKey ?? '')) {
      this.setState({ activeSessionKey: null, messages: [], uploadedFiles: [] });
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
    this.setState({ activeSessionKey: session._key });
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
    this.setState({
      activeSessionKey: payload.session._key,
      messages: payload.messages || [],
      streamingContent: '',
      streamingThinking: '',
      isStreaming: false,
    });
  }

  addUserMessage(content: string) {
    const sessionKey = this.state.activeSessionKey ?? '';
    const message: ChatMessage = {
      _key: `local-user-${Date.now()}`,
      session_key: sessionKey,
      role: 'user',
      content,
      thinking: null,
      tokens: null,
      created_at: new Date().toISOString(),
    };
    this.setState({ messages: [...this.state.messages, message] });
  }

  truncateAfter(key: string) {
    const idx = this.state.messages.findIndex((m) => m._key === key);
    if (idx < 0) return;
    this.setState({ messages: this.state.messages.slice(0, idx + 1) });
  }

  updateMessage(key: string, content: string) {
    const messages = this.state.messages.map((m) =>
      m._key === key ? { ...m, content } : m,
    );
    this.setState({ messages });
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
  }

  async sendMessage(content: string): Promise<SSEConnection | null> {
    const trimmed = content.trim();
    if (!trimmed || this.state.isStreaming) {
      return null;
    }

    const selectedProvider = this.state.selectedProvider ?? this.getDefaultProviderCode() ?? undefined;
    const providerConfig = this.getProviderByCode(selectedProvider ?? null);
    const resolvedModel = providerConfig?.models?.[0]?.model_id ?? this.getDefaultModel();

    let activeSessionKey = this.state.activeSessionKey;
    if (!activeSessionKey) {
      const session = await this.createSession(selectedProvider, resolvedModel);
      activeSessionKey = session._key;
    }

    this.addUserMessage(trimmed);
    this.startStreaming();

    const request: SendMessageRequest = {
      content: trimmed,
      provider: selectedProvider,
      model: resolvedModel,
      temperature: this.getDefaultTemperature(),
      max_tokens: this.getDefaultMaxTokens(),
    };

    let streamedContent = '';
    let streamedThinking = '';

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
    });

    return connection;
  }

  async updateSessionTitle(sessionKey: string, title: string): Promise<void> {
    const response = await chatApi.updateSession(sessionKey, { title });
    const updated = response.data.data;
    const sessions = this.state.sessions.map((session) => (session._key === updated._key ? updated : session));
    this.setState({ sessions });
  }

  async generateSessionTitle(): Promise<void> {
    const sessionKey = this.state.activeSessionKey;
    if (!sessionKey) {
      return;
    }

    const targetSession = this.state.sessions.find((session) => session._key === sessionKey);
    if (targetSession?.title) {
      return;
    }

    const firstUserMessage = this.state.messages.find((message) => message.role === 'user' && message.content.trim());
    if (!firstUserMessage) {
      return;
    }

    const rawTitle = firstUserMessage.content.trim();
    const title = rawTitle.length > 20 ? `${rawTitle.slice(0, 20)}...` : rawTitle;
    if (!title) {
      return;
    }

    await this.updateSessionTitle(sessionKey, title);
  }

  async loadSessionFiles(sessionKey: string): Promise<void> {
    try {
      const response = await sessionFilesApi.list(sessionKey);
      this.setState({ uploadedFiles: response.data.data || [] });
    } catch {
      // ignore - file list load failure
    }
  }

  async uploadFile(sessionKey: string, file: File): Promise<void> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await sessionFilesApi.upload(sessionKey, formData);
    const uploaded = response.data.data;
    this.setState({ uploadedFiles: [...this.state.uploadedFiles, uploaded] });
  }

  async deleteFile(sessionKey: string, fileKey: string): Promise<void> {
    await sessionFilesApi.delete(sessionKey, fileKey);
    this.setState({
      uploadedFiles: this.state.uploadedFiles.filter((f) => f.file_key !== fileKey),
    });
  }

  applyFileStatusUpdate(payload: FileStatusPayload): void {
    const files = this.state.uploadedFiles.map((f) => {
      if (f.file_key !== payload.file_key) return f;
      return {
        ...f,
        ...(payload.vector_status !== undefined && { vector_status: payload.vector_status }),
        ...(payload.graph_status !== undefined && { graph_status: payload.graph_status }),
        ...(payload.failed_reason !== undefined && { failed_reason: payload.failed_reason }),
        ...(payload.graph_stats !== undefined && { graph_stats: payload.graph_stats }),
      };
    });
    this.setState({ uploadedFiles: files });
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

export { taskChatStore, ragicChatStore };

export type { ChatState };
