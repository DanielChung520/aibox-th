/**
 * @file        SSE 串流連線管理
 * @description 使用 fetch + ReadableStream 解析聊天 SSE 事件
 * @lastUpdate  2026-04-11 10:54:59
 * @author      Daniel Chung
 * @version     1.2.0
 */

import { FileStatusPayload, SendMessageRequest } from './api';
import type {
  IntentDetectedPayload,
  ToolCallStartPayload,
  ToolCallResultPayload,
  DaQueryStartPayload,
  DaQueryResultPayload,
  KaSearchResultPayload,
  BpaStepStartPayload,
  BpaStepCompletePayload,
  BpaAskUserPayload,
  BpaCompletePayload,
  BpaFailedPayload,
  SessionStatePayload,
} from '../types/sseEvents';

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

interface SSECallbacks {
  onChunk: (delta: string) => void;
  onThinkingChunk?: (delta: string) => void;
  onDone: () => void;
  onError: (error: string) => void;
}

interface ExtendedSSECallbacks extends SSECallbacks {
  onIntentDetected?: (data: IntentDetectedPayload) => void;
  onToolCallStart?: (data: ToolCallStartPayload) => void;
  onToolCallResult?: (data: ToolCallResultPayload) => void;
  onDaQueryStart?: (data: DaQueryStartPayload) => void;
  onDaQueryResult?: (data: DaQueryResultPayload) => void;
  onKaSearchResult?: (data: KaSearchResultPayload) => void;
  onBpaStepStart?: (data: BpaStepStartPayload) => void;
  onBpaStepComplete?: (data: BpaStepCompletePayload) => void;
  onBpaAskUser?: (data: BpaAskUserPayload) => void;
  onBpaComplete?: (data: BpaCompletePayload) => void;
  onBpaFailed?: (data: BpaFailedPayload) => void;
  onSessionState?: (data: SessionStatePayload) => void;
}

interface SSEConnection {
  abort: () => void;
}

interface SSEChunkPayload {
  message?: {
    content?: string;
    thinking?: string;
  };
  choices?: Array<{
    delta?: {
      content?: string;
    };
    finish_reason?: string | null;
  }>;
}

interface SSEErrorPayload {
  error?: string;
}

function extractChunkDelta(payload: SSEChunkPayload): string {
  return payload.message?.content
    ?? payload.choices?.[0]?.delta?.content
    ?? '';
}

function parseSSEEvent(rawEvent: string): { event: string; data: string } {
  const normalized = rawEvent.replace(/\r/g, '');
  const lines = normalized.split('\n');
  let event = '';
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim();
      continue;
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim());
    }
  }

  return { event, data: dataLines.join('\n') };
}

/** 統一分派 SSE 事件到對應的 callback */
function dispatchSSEEvent(
  evt: { event: string; data: string },
  callbacks: ExtendedSSECallbacks,
): void {
  switch (evt.event) {
    case 'thinking_chunk': {
      try {
        const payload = JSON.parse(evt.data) as SSEChunkPayload;
        const delta = payload.message?.thinking ?? '';
        if (delta && callbacks.onThinkingChunk) callbacks.onThinkingChunk(delta);
      } catch { callbacks.onError('SSE thinking_chunk 解析失敗'); }
      break;
    }
    case 'chat_chunk': {
      try {
        const payload = JSON.parse(evt.data) as SSEChunkPayload;
        const delta = extractChunkDelta(payload);
        if (delta) callbacks.onChunk(delta);
      } catch { callbacks.onError('SSE chunk 解析失敗'); }
      break;
    }
    case 'chat_done':
      callbacks.onDone();
      break;
    case 'chat_error': {
      try {
        const payload = JSON.parse(evt.data) as SSEErrorPayload;
        callbacks.onError(payload.error ?? '串流處理失敗');
      } catch { callbacks.onError('SSE error 解析失敗'); }
      break;
    }
    case 'intent_detected': {
      try { callbacks.onIntentDetected?.(JSON.parse(evt.data) as IntentDetectedPayload); }
      catch { /* ignore optional event parse errors */ }
      break;
    }
    case 'tool_call_start': {
      try { callbacks.onToolCallStart?.(JSON.parse(evt.data) as ToolCallStartPayload); }
      catch { /* ignore */ }
      break;
    }
    case 'tool_call_result': {
      try { callbacks.onToolCallResult?.(JSON.parse(evt.data) as ToolCallResultPayload); }
      catch { /* ignore */ }
      break;
    }
    case 'da_query_start': {
      try { callbacks.onDaQueryStart?.(JSON.parse(evt.data) as DaQueryStartPayload); }
      catch { /* ignore */ }
      break;
    }
    case 'da_query_result': {
      try { callbacks.onDaQueryResult?.(JSON.parse(evt.data) as DaQueryResultPayload); }
      catch { /* ignore */ }
      break;
    }
    case 'ka_search_result': {
      try { callbacks.onKaSearchResult?.(JSON.parse(evt.data) as KaSearchResultPayload); }
      catch { /* ignore */ }
      break;
    }
    case 'bpa_step_start': {
      try { callbacks.onBpaStepStart?.(JSON.parse(evt.data) as BpaStepStartPayload); }
      catch { /* ignore */ }
      break;
    }
    case 'bpa_step_complete': {
      try { callbacks.onBpaStepComplete?.(JSON.parse(evt.data) as BpaStepCompletePayload); }
      catch { /* ignore */ }
      break;
    }
    case 'bpa_ask_user': {
      try { callbacks.onBpaAskUser?.(JSON.parse(evt.data) as BpaAskUserPayload); }
      catch { /* ignore */ }
      break;
    }
    case 'bpa_complete': {
      try { callbacks.onBpaComplete?.(JSON.parse(evt.data) as BpaCompletePayload); }
      catch { /* ignore */ }
      break;
    }
    case 'bpa_failed': {
      try { callbacks.onBpaFailed?.(JSON.parse(evt.data) as BpaFailedPayload); }
      catch { /* ignore */ }
      break;
    }
    case 'session_state': {
      try { callbacks.onSessionState?.(JSON.parse(evt.data) as SessionStatePayload); }
      catch { /* ignore */ }
      break;
    }
  }
}

export function sendMessageSSE(
  sessionKey: string,
  request: SendMessageRequest,
  callbacks: ExtendedSSECallbacks,
): SSEConnection {
  const controller = new AbortController();
  const baseURL = resolveApiBaseUrl();
  const token = localStorage.getItem('token');
  const url = `${baseURL}/api/v1/chat/sessions/${encodeURIComponent(sessionKey)}/messages`;

  void (async () => {
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(request),
        signal: controller.signal,
      });

      if (!response.ok) {
        const detail = await response.text().catch(() => `HTTP ${response.status}`);
        callbacks.onError(detail || `HTTP ${response.status}`);
        return;
      }

      if (!response.body) {
        callbacks.onError('SSE 連線無回應內容');
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          if (buffer.trim()) {
            const evt = parseSSEEvent(buffer);
            if (evt.event) dispatchSSEEvent(evt, callbacks);
          }
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop() ?? '';

        for (const rawEvent of events) {
          const evt = parseSSEEvent(rawEvent);
          if (evt.event) dispatchSSEEvent(evt, callbacks);
        }
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        return;
      }
      callbacks.onError(error instanceof Error ? error.message : 'SSE 連線失敗');
    }
  })();

  return {
    abort: () => {
      controller.abort();
    },
  };
}

interface FileStatusCallbacks {
  onFileStatus: (payload: FileStatusPayload) => void;
  onError: (error: string) => void;
  onConnected?: () => void;
}

export function subscribeSessionFileStatus(
  sessionKey: string,
  callbacks: FileStatusCallbacks,
): SSEConnection {
  const controller = new AbortController();
  const baseURL = resolveApiBaseUrl();
  const token = localStorage.getItem('token');
  const url = `${baseURL}/api/v1/sse/session-files/${encodeURIComponent(sessionKey)}`;

  void (async () => {
    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          Accept: 'text/event-stream',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        signal: controller.signal,
      });

      if (!response.ok) {
        callbacks.onError(`SSE 連線失敗 (${response.status})`);
        return;
      }

      if (!response.body) {
        callbacks.onError('SSE 連線無回應內容');
        return;
      }

      callbacks.onConnected?.();

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop() ?? '';

        for (const rawEvent of events) {
          const evt = parseSSEEvent(rawEvent);
          if (!evt.event) continue;

          if (evt.event === 'file_status') {
            try {
              const payload = JSON.parse(evt.data) as FileStatusPayload;
              callbacks.onFileStatus(payload);
            } catch {
              callbacks.onError('file_status 解析失敗');
            }
          } else if (evt.event === 'heartbeat') {
            // ignore
          } else if (evt.event === 'error') {
            try {
              const payload = JSON.parse(evt.data) as { error?: string };
              callbacks.onError(payload.error ?? 'SSE 錯誤');
            } catch {
              callbacks.onError('SSE error 解析失敗');
            }
          }
        }
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        return;
      }
      callbacks.onError(error instanceof Error ? error.message : 'SSE 連線失敗');
    }
  })();

  return {
    abort: () => {
      controller.abort();
    },
  };
}

export type { SSECallbacks, ExtendedSSECallbacks, SSEConnection };
