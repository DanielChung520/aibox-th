/**
 * @file        SignalCollector — 艾企助手 L3 信號收集器
 * @description 訂閱 actionTrail 事件，過濾有意義的 state-change，
 *              debounce 後推送到後端 /api/v1/aiq/signals/push。
 *              只推送關鍵狀態變化，不是每個事件都推送。
 *              參數從 system_params (aiq.*) 讀取，fallback 為預設值。
 * @lastUpdate  2026-04-18 17:49:39
 * @author      Daniel Chung
 * @version     1.1.0
 */

import { actionTrail, ActionEvent, ActionEventType } from './actionTrail';

const SIGNIFICANT_EVENTS: Set<ActionEventType> = new Set([
  'page_navigate',
  'modal_open',
  'modal_close',
]);

const DEFAULTS = {
  debounceMs: 1000,
  maxRetryMs: 30000,
  retryBackoff: 2,
};

interface SignalEvent {
  type: string;
  timestamp: number;
  page: string;
  meta: Record<string, unknown>;
}

class SignalCollectorService {
  private unsubscribe: (() => void) | null = null;
  private pendingSignals: SignalEvent[] = [];
  private debounceTimer: ReturnType<typeof setTimeout> | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private retryDelayMs = DEFAULTS.debounceMs;
  private lastPushedPage = '';

  private debounceMs = DEFAULTS.debounceMs;
  private maxRetryMs = DEFAULTS.maxRetryMs;
  private retryBackoff = DEFAULTS.retryBackoff;

  async start(): Promise<void> {
    if (this.unsubscribe) return;
    await this.loadConfig();
    this.unsubscribe = actionTrail.subscribe(this.handleEvent);
  }

  stop(): void {
    if (this.unsubscribe) {
      this.unsubscribe();
      this.unsubscribe = null;
    }
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }
    if (this.retryTimer) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
    void this.flush();
  }

  private async loadConfig(): Promise<void> {
    try {
      const { paramsApi } = await import('./api');
      const res = await paramsApi.list();
      const params = res.data?.data || [];
      const map = new Map(params.map((p: { param_key: string; param_value: string }) => [p.param_key, p.param_value]));
      this.debounceMs = parseInt(map.get('aiq.signal_debounce_ms') || '', 10) || DEFAULTS.debounceMs;
      this.maxRetryMs = parseInt(map.get('aiq.signal_max_retry_ms') || '', 10) || DEFAULTS.maxRetryMs;
      this.retryBackoff = parseInt(map.get('aiq.signal_retry_backoff') || '', 10) || DEFAULTS.retryBackoff;
      this.retryDelayMs = this.debounceMs;
    } catch {
      // fallback to defaults
    }
  }

  private handleEvent = (event: ActionEvent): void => {
    if (!SIGNIFICANT_EVENTS.has(event.type)) return;

    if (event.type === 'page_navigate' && event.page === this.lastPushedPage) {
      return;
    }
    if (event.type === 'page_navigate') {
      this.lastPushedPage = event.page;
    }
    this.enqueue({
      type: event.type,
      timestamp: event.timestamp,
      page: event.page,
      meta: event.meta,
    });
  };

  private enqueue(signal: SignalEvent): void {
    this.pendingSignals.push(signal);
    this.schedulePush();
  }

  private schedulePush(): void {
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }
    this.debounceTimer = setTimeout(() => {
      void this.flush();
    }, this.debounceMs);
  }

  private async flush(): Promise<void> {
    if (this.pendingSignals.length === 0) return;
    const batch = this.pendingSignals.splice(0);
    try {
      const { default: api } = await import('./api');
      await api.post('/api/v1/aiq/signals/push', { signals: batch });
      this.retryDelayMs = this.debounceMs;
    } catch {
      this.pendingSignals.unshift(...batch);
      this.retryDelayMs = Math.min(this.retryDelayMs * this.retryBackoff, this.maxRetryMs);
      this.retryTimer = setTimeout(() => { void this.flush(); }, this.retryDelayMs);
    }
  }
}

export const signalCollector = new SignalCollectorService();
