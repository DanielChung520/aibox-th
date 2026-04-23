/**
 * @file        ActionTrail — 使用者操作軌跡收集器
 * @description 收集前端細粒度操作事件（點擊、停留、排序、篩選、搜尋、翻頁、頁面切換等），
 *              供艾企（FloatingAssistant）讀取以推斷使用者意圖。
 *              環形緩衝 + 定時/滿量 flush 到後端 S3 備存。
 * @lastUpdate  2026-04-16 11:43:44
 * @author      Daniel Chung
 * @version     2.0.0
 */

import type { EntityContext } from '../components/FloatingAssistant/types';
import { ENTITY_INTERACT_EVENT } from '../hooks/useEntityPerception';

export type ActionEventType =
  | 'cell_click'
  | 'row_dwell'
  | 'column_sort'
  | 'filter_apply'
  | 'filter_clear'
  | 'global_search'
  | 'page_change'
  | 'refresh'
  | 'mode_switch'
  | 'page_navigate'
  | 'modal_open'
  | 'modal_close'
  | 'intent_accepted'
  | 'intent_rejected'
  | 'intent_confirmed'
  | 'entity_view'
  | 'entity_list'
  | 'entity_create'
  | 'entity_edit'
  | 'entity_delete'
  | 'entity_search'
  | 'entity_filter'
  | 'entity_export'
  | 'entity_import'
  | 'entity_execute';

export interface ActionEvent {
  type: ActionEventType;
  timestamp: number;
  page: string;
  meta: Record<string, unknown>;
}

type TrailListener = (event: ActionEvent) => void;

const MAX_BUFFER = 200;
const DWELL_THRESHOLD_MS = 3000;
const FLUSH_INTERVAL_MS = 30_000;
const FLUSH_THRESHOLD = 100;

class ActionTrailService {
  private buffer: ActionEvent[] = [];
  private flushQueue: ActionEvent[] = [];
  private listeners: Set<TrailListener> = new Set();
  private dwellTimers: Map<string, { timer: ReturnType<typeof setTimeout>; start: number }> = new Map();
  private currentPage = '/';
  private flushTimer: ReturnType<typeof setInterval> | null = null;
  private flushing = false;

  setCurrentPage(page: string) {
    this.currentPage = page;
  }

  record(type: ActionEventType, meta: Record<string, unknown> = {}) {
    const event: ActionEvent = {
      type,
      timestamp: Date.now(),
      page: this.currentPage,
      meta,
    };
    this.buffer.push(event);
    this.flushQueue.push(event);
    if (this.buffer.length > MAX_BUFFER) {
      this.buffer = this.buffer.slice(-MAX_BUFFER);
    }
    this.listeners.forEach(fn => fn(event));
    if (this.flushQueue.length >= FLUSH_THRESHOLD) {
      this.flush();
    }
  }

  startDwell(key: string, meta: Record<string, unknown> = {}) {
    this.clearDwell(key);
    const timer = setTimeout(() => {
      this.record('row_dwell', { dwellKey: key, durationMs: DWELL_THRESHOLD_MS, ...meta });
      this.dwellTimers.delete(key);
    }, DWELL_THRESHOLD_MS);
    this.dwellTimers.set(key, { timer, start: Date.now() });
  }

  clearDwell(key: string) {
    const entry = this.dwellTimers.get(key);
    if (entry) {
      clearTimeout(entry.timer);
      this.dwellTimers.delete(key);
    }
  }

  getTrail(limit = 50): ActionEvent[] {
    return this.buffer.slice(-limit);
  }

  getTrailByType(type: ActionEventType, limit = 20): ActionEvent[] {
    return this.buffer.filter(e => e.type === type).slice(-limit);
  }

  getRecentSummary(windowMs = 60000): Record<ActionEventType, number> {
    const cutoff = Date.now() - windowMs;
    const counts = {} as Record<ActionEventType, number>;
    for (const e of this.buffer) {
      if (e.timestamp >= cutoff) {
        counts[e.type] = (counts[e.type] || 0) + 1;
      }
    }
    return counts;
  }

  subscribe(listener: TrailListener): () => void {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  }

  startAutoFlush() {
    this.stopAutoFlush();
    this.flushTimer = setInterval(() => this.flush(), FLUSH_INTERVAL_MS);
    window.addEventListener('beforeunload', this.handleBeforeUnload);

    window.addEventListener(ENTITY_INTERACT_EVENT, this.handleEntityInteract as EventListener);
  }

  stopAutoFlush() {
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
      this.flushTimer = null;
    }
    window.removeEventListener('beforeunload', this.handleBeforeUnload);
    window.removeEventListener(ENTITY_INTERACT_EVENT, this.handleEntityInteract as EventListener);
  }

  private handleEntityInteract = (e: Event) => {
    const customEvent = e as CustomEvent<EntityContext & { timestamp: number; page: string }>;
    const { entity_type, entity_id, action, metadata } = customEvent.detail;
    if (!entity_type || !entity_id) return;

    const actionType = `entity_${action}` as ActionEventType;
    this.record(actionType, {
      entity_type,
      entity_id,
      entity_name: metadata?.entity_name as string || entity_id,
      ...metadata,
    });
  };

  private handleBeforeUnload = () => {
    if (this.flushQueue.length === 0) return;
    const token = localStorage.getItem('token');
    if (!token) return;
    const payload = JSON.stringify({ events: this.flushQueue });
    const blob = new Blob([payload], { type: 'application/json' });
    navigator.sendBeacon('/api/v1/action-trail/batch', blob);
    this.flushQueue = [];
  };

  async flush() {
    if (this.flushing || this.flushQueue.length === 0) return;
    this.flushing = true;
    const batch = this.flushQueue.splice(0);
    try {
      const { default: api } = await import('./api');
      await api.post('/api/v1/action-trail/batch', { events: batch });
    } catch {
      this.flushQueue.unshift(...batch);
    } finally {
      this.flushing = false;
    }
  }

  clear() {
    this.buffer = [];
    this.flushQueue = [];
    this.dwellTimers.forEach(entry => clearTimeout(entry.timer));
    this.dwellTimers.clear();
  }
}

export const actionTrail = new ActionTrailService();
