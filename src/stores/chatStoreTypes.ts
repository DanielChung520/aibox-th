/**
 * @file        chatStoreTypes.ts
 * @description ChatStore 的狀態介面與類型定義
 * @lastUpdate  2026-04-18 23:30:00
 * @author      AI Agent
 * @version     1.0.0
 */

import type {
  ChatSession,
  ChatMessage,
  ModelProvider,
  SessionFile,
} from '../services/api';

export interface ChatState {
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

export const INITIAL_CHAT_STATE: ChatState = {
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
