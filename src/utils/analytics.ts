/**
 * @file        前端埋點追蹤工具
 * @description 使用者行為追蹤、頁面瀏覽、點擊事件、API 調用監控
 * @lastUpdate  2026-04-22 10:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

export type EventCategory =
  | 'page_view'
  | 'user_action'
  | 'agent_interaction'
  | 'demand_management'
  | 'intent_config'
  | 'api_call'
  | 'error';

export type EventAction =
  | 'page_enter'
  | 'page_leave'
  | 'button_click'
  | 'form_submit'
  | 'modal_open'
  | 'modal_close'
  | 'tab_switch'
  | 'intent_create'
  | 'intent_update'
  | 'intent_delete'
  | 'demand_create'
  | 'demand_submit'
  | 'demand_review'
  | 'demand_approve'
  | 'demand_reject'
  | 'demand_cancel'
  | 'agent_create'
  | 'agent_update'
  | 'agent_delete'
  | 'tool_execute'
  | 'api_request'
  | 'error_occur';

export interface AnalyticsEvent {
  category: EventCategory;
  action: EventAction;
  label?: string;
  value?: number;
  metadata?: Record<string, unknown>;
}

export interface PageViewEvent {
  page: string;
  title?: string;
  referrer?: string;
}

export interface QueuedEvent {
  event: AnalyticsEvent | PageViewEvent;
  timestamp: number;
  session_id: string;
  user_key?: string;
}

const EVENT_QUEUE: QueuedEvent[] = [];
const FLUSH_INTERVAL = 3000; // 3 seconds
const MAX_QUEUE_SIZE = 50;
const LOCAL_STORAGE_KEY = 'aibox_analytics_events';
const MAX_LOCAL_EVENTS = 200;

let sessionId: string | null = null;
let flushTimer: ReturnType<typeof setTimeout> | null = null;

/**
 * 生成 session ID
 */
function getSessionId(): string {
  if (!sessionId) {
    sessionId = `sess_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }
  return sessionId;
}

/**
 * 取得目前用戶 key
 */
function getUserKey(): string | undefined {
  try {
    const token = localStorage.getItem('token');
    if (!token) return undefined;
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.sub || payload.username;
  } catch {
    return undefined;
  }
}

function saveToLocalStorage(events: QueuedEvent[]): void {
  try {
    const stored = localStorage.getItem(LOCAL_STORAGE_KEY);
    const existing: QueuedEvent[] = stored ? JSON.parse(stored) : [];
    const combined = [...existing, ...events].slice(-MAX_LOCAL_EVENTS);
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(combined));
  } catch {
  }
}

function queueEvent(event: AnalyticsEvent | PageViewEvent): void {
  const queued: QueuedEvent = {
    event,
    timestamp: Date.now(),
    session_id: getSessionId(),
    user_key: getUserKey(),
  };

  EVENT_QUEUE.push(queued);
  saveToLocalStorage([queued]);

  if (EVENT_QUEUE.length >= MAX_QUEUE_SIZE) {
    flush();
  }

  if (!flushTimer) {
    flushTimer = setTimeout(flush, FLUSH_INTERVAL);
  }
}

/**
 * 發送事件到後端
 */
async function flush(): Promise<void> {
  if (flushTimer) {
    clearTimeout(flushTimer);
    flushTimer = null;
  }

  if (EVENT_QUEUE.length === 0) return;

  const events = EVENT_QUEUE.splice(0, EVENT_QUEUE.length);

  try {
    const response = await fetch('/api/v1/events', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token') || ''}`,
      },
      body: JSON.stringify({ events }),
    });

    if (!response.ok) {
      console.warn('[Analytics] Failed to send events:', response.status);
    }
  } catch (error) {
    console.warn('[Analytics] Error sending events:', error);
  }
}

/**
 * 追蹤頁面瀏覽
 */
export function trackPageView(page: string, title?: string): void {
  queueEvent({ page, title } as PageViewEvent);
}

/**
 * 追蹤使用者行為
 */
export function trackEvent(
  category: EventCategory,
  action: EventAction,
  label?: string,
  value?: number,
  metadata?: Record<string, unknown>
): void {
  queueEvent({ category, action, label, value, metadata });
}

/**
 * 追蹤按鈕點擊
 */
export function trackButtonClick(
  buttonLabel: string,
  location: string,
  metadata?: Record<string, unknown>
): void {
  trackEvent('user_action', 'button_click', buttonLabel, undefined, {
    location,
    ...metadata,
  });
}

export function trackFormSubmit(
  _formName: string,
  success: boolean,
  metadata?: Record<string, unknown>
): void {
  trackEvent('user_action', 'form_submit', success ? 'success' : 'failure', undefined, metadata);
}

/**
 * 追蹤 Modal 開關
 */
export function trackModal(
  modalName: string,
  action: 'open' | 'close',
  metadata?: Record<string, unknown>
): void {
  trackEvent(
    'user_action',
    action === 'open' ? 'modal_open' : 'modal_close',
    modalName,
    undefined,
    metadata
  );
}

/**
 * 追蹤 Agent 操作
 */
export function trackAgentAction(
  action: 'create' | 'update' | 'delete' | 'favorite' | 'chat',
  agentKey: string,
  agentName?: string,
  metadata?: Record<string, unknown>
): void {
  trackEvent(
    'agent_interaction',
    `agent_${action}` as EventAction,
    agentName || agentKey,
    undefined,
    { agent_key: agentKey, ...metadata }
  );
}

/**
 * 追蹤 Demand 操作
 */
export function trackDemandAction(
  action: 'create' | 'submit' | 'review' | 'approve' | 'reject' | 'cancel' | 'withdraw',
  demandKey: string,
  demandTitle?: string,
  metadata?: Record<string, unknown>
): void {
  trackEvent(
    'demand_management',
    `demand_${action}` as EventAction,
    demandTitle || demandKey,
    undefined,
    { demand_key: demandKey, ...metadata }
  );
}

/**
 * 追蹤 Intent 配置
 */
export function trackIntentAction(
  action: 'create' | 'update' | 'delete' | 'suggest',
  agentKey: string,
  intentName?: string,
  metadata?: Record<string, unknown>
): void {
  trackEvent(
    'intent_config',
    `intent_${action}` as EventAction,
    intentName,
    undefined,
    { agent_key: agentKey, ...metadata }
  );
}

/**
 * 頁面進入追蹤（自動）
 */
export function setupPageViewTracking(): () => void {
  const handleRouteChange = () => {
    const pathname = window.location.pathname;
    const title = document.title;
    trackPageView(pathname, title);
  };

  // 初始追蹤
  handleRouteChange();

  // 監聽 popstate（瀏覽器前進/後退）
  window.addEventListener('popstate', handleRouteChange);

  // 監聽 History API 變化
  const originalPushState = window.history.pushState;
  window.history.pushState = function (...args) {
    originalPushState.apply(window.history, args);
    handleRouteChange();
  };

  return () => {
    window.removeEventListener('popstate', handleRouteChange);
    window.history.pushState = originalPushState;
  };
}

/**
 * 離開頁面時 flush 剩餘事件
 */
export function setupBeforeUnload(): void {
  window.addEventListener('beforeunload', () => {
    if (EVENT_QUEUE.length > 0) {
      navigator.sendBeacon('/api/v1/events', JSON.stringify({ events: EVENT_QUEUE }));
    }
  });
}

export function getLocalEvents(): QueuedEvent[] {
  try {
    const stored = localStorage.getItem(LOCAL_STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

export function clearLocalEvents(): void {
  localStorage.removeItem(LOCAL_STORAGE_KEY);
}

// ============ 掛鉤，方便 React 使用 ============

import { useEffect, useRef } from 'react';

/**
 * React 掛鉤：自動追蹤組件曝光
 */
export function usePageTracking(pageName: string): void {
  const hasTracked = useRef(false);

  useEffect(() => {
    if (!hasTracked.current) {
      trackPageView(pageName);
      hasTracked.current = true;
    }
  }, [pageName]);
}

/**
 * React 掛鉤：追蹤組件內的用戶操作
 */
export function useAnalytics() {
  return {
    trackEvent,
    trackButtonClick,
    trackFormSubmit,
    trackModal,
    trackAgentAction,
    trackDemandAction,
    trackIntentAction,
  };
}
