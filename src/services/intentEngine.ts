/**
 * @file        intentEngine.ts
 * @description 意圖推斷引擎 — AIQ Adapter 模式，主路徑走 AIQ perception/inquiry，降級走模板匹配
 * @lastUpdate  2026-04-18 21:33:24
 * @author      Daniel Chung
 * @version     3.1.0
 */

import api from './api';
import { actionTrail } from './actionTrail';
import type { ActionEvent } from './actionTrail';
import type { IntentGuess, ResponseStrategy, SideEffect } from '../components/FloatingAssistant/types';
import { PAGE_TYPE_MAP } from '../components/FloatingAssistant/types';
import type { IntentCatalogEntry, IntentCatalogListResponse } from './intentCatalogApi';
import { intentLogApi } from './intentLogApi';
import type { IntentLogAction } from './intentLogApi';

export type { IntentGuess };
export type IntentTrigger = 'table_open' | 'cell_click' | 'field_click' | 'action_pattern' | 'page_view';

interface IntentContext {
  trigger: IntentTrigger; tableName?: string; fieldName?: string; cellValue?: string;
  pageName?: string; pageDescription?: string; pagePath?: string;
  recentActions?: ActionEvent[]; pageVars?: Record<string, string>;
}
interface WorkingContext {
  active_anchors?: Array<Record<string, unknown>>;
  page_context?: { path?: string; page_name?: string; page_type?: string };
}
interface Hypothesis {
  id: string; intent_label: string; execution_path?: string; confidence: number;
  evidence_chain?: unknown[]; parameters?: Record<string, unknown>;
}
interface InquiryResult {
  decision: 'commit' | 'clarify' | 'stay' | 'escalate';
  state?: { hypotheses?: Hypothesis[] }; committed_hypothesis?: Hypothesis;
  clarification_questions?: string[]; escalation_reason?: string;
}
interface TemplateCacheEntry { expiresAt: number; entries: IntentCatalogEntry[]; }
interface CommitResult { status: string; action: string; hypothesis_id?: string; result?: Record<string, unknown>; error?: string; }
type IntentListener = (guesses: IntentGuess[], trigger: IntentTrigger) => void;

const ANALYZE_DEBOUNCE_MS = 300;
const ANALYZE_THROTTLE_MS = 1000;
const CELL_IDLE_MS = 800;
const POLL_INTERVAL_MS = 4000;
const TEMPLATE_CACHE_TTL_MS = 300000;

class IntentEngine {
  private listeners = new Set<IntentListener>();
  private lastGuesses: IntentGuess[] = [];
  private loading = false;
  private unsubTrail: (() => void) | null = null;
  private rawTemplateCache = new Map<string, TemplateCacheEntry>();
  private currentPagePath = '';
  private currentPageVars: Record<string, string> = {};
  private lastContext: IntentContext = { trigger: 'page_view' };
  private lastFingerprint = '';
  private lastAnalyzeAt = 0;
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private analyzeTimer: ReturnType<typeof setTimeout> | null = null;
  private cellClickTimer: ReturnType<typeof setTimeout> | null = null;
  private activeController: AbortController | null = null;
  private pendingContext: IntentContext | null = null;

  subscribe(listener: IntentListener): () => void { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; }
  getLastGuesses(): IntentGuess[] { return this.lastGuesses; }
  isLoading(): boolean { return this.loading; }

  startListening() {
    if (this.unsubTrail) return;
    this.unsubTrail = actionTrail.subscribe((event) => this.handleTrailEvent(event));
    void this.pollIntentState();
    this.pollTimer = setInterval(() => { void this.pollIntentState(); }, POLL_INTERVAL_MS);
  }

  stopListening() {
    this.unsubTrail?.();
    if (this.pollTimer) clearInterval(this.pollTimer);
    if (this.analyzeTimer) clearTimeout(this.analyzeTimer);
    if (this.cellClickTimer) clearTimeout(this.cellClickTimer);
    this.unsubTrail = null; this.pollTimer = null; this.analyzeTimer = null; this.cellClickTimer = null; this.pendingContext = null;
    this.cancelAnalyze();
  }

  requestGuesses(context: IntentContext) { this.lastContext = context; this.scheduleAnalyze(context, ANALYZE_DEBOUNCE_MS); }
  acceptGuess(guess: IntentGuess) { this.recordFeedback('intent_accepted', 'confirmed', guess, guess.text); }
  confirmGuess(guess: IntentGuess) { this.recordFeedback('intent_confirmed', 'confirmed', guess, guess.text); }

  async commitToAgent(guess: IntentGuess, naturalLanguage: string): Promise<CommitResult> {
    try {
      const resp = await api.post<CommitResult>('/api/v1/aiq/intent-state/commit', {
        hypothesis_id: guess.intent_id || '',
        execution_path: guess.strategy || 'llm_answer',
        natural_language: naturalLanguage,
        context: {
          page_path: this.currentPagePath,
          page_name: this.currentPageVars.page_name || '',
          table_name: this.currentPageVars.table_name || '',
          domain_name: this.currentPageVars.domain_name || '',
          field_hints: guess.context?.parameters ? Object.keys(guess.context.parameters as Record<string, unknown>) : [],
          active_anchors: [],
        },
      });
      return this.unwrap(resp.data);
    } catch (err) {
      console.warn('[intentEngine] commitToAgent failed:', err);
      return { status: 'error', action: 'chat', error: 'Commit failed' };
    }
  }

  rejectGuess(originalGuess: string, userInput: string) {
    actionTrail.record('intent_rejected', { original_guess: originalGuess, user_input: userInput });
    this.logIntent('rejected', { text: originalGuess, confidence: 0, source: 'template' }, userInput);
  }

  clear() { this.lastGuesses = []; this.rawTemplateCache.clear(); }

  private handleTrailEvent(event: ActionEvent) {
    if (event.type === 'page_navigate' && event.meta.pageName) return void this.requestGuesses(this.buildPageContext(event));
    if (event.type === 'modal_open' && event.meta.tableId) {
      return void this.requestGuesses({
        trigger: 'table_open', tableName: this.asString(event.meta.tableName), pagePath: this.currentPagePath,
        pageVars: this.currentPageVars, recentActions: actionTrail.getTrail(5),
      });
    }
    if (event.type === 'cell_click' && event.meta.fieldName) {
      if (this.cellClickTimer) clearTimeout(this.cellClickTimer);
      this.cellClickTimer = setTimeout(() => this.requestGuesses({
        trigger: 'cell_click', tableName: this.asString(event.meta.tableName), fieldName: this.asString(event.meta.fieldName),
        cellValue: this.asString(event.meta.cellValue), pagePath: this.currentPagePath, pageVars: this.currentPageVars,
        recentActions: actionTrail.getTrail(10),
      }), CELL_IDLE_MS);
    }
  }

  private buildPageContext(event: ActionEvent): IntentContext {
    const pageVars: Record<string, string> = {
      page_name: this.asString(event.meta.pageName) || '', page_description: this.asString(event.meta.pageDescription) || '',
    };
    if (event.meta.recordCount !== undefined) pageVars.record_count = String(event.meta.recordCount);
    if (this.asString(event.meta.domainName)) pageVars.domain_name = this.asString(event.meta.domainName) || '';
    if (this.asString(event.meta.tableName)) pageVars.table_name = this.asString(event.meta.tableName) || '';
    this.currentPagePath = this.asString(event.meta.path) || '';
    this.currentPageVars = pageVars;
    return {
      trigger: 'page_view', pageName: this.asString(event.meta.pageName), pageDescription: this.asString(event.meta.pageDescription),
      pagePath: this.currentPagePath, pageVars, recentActions: actionTrail.getTrail(5),
    };
  }

  private scheduleAnalyze(context: IntentContext, delayMs: number) {
    this.pendingContext = context;
    if (this.analyzeTimer) clearTimeout(this.analyzeTimer);
    const throttleWait = Math.max(0, this.lastAnalyzeAt + ANALYZE_THROTTLE_MS - Date.now());
    this.analyzeTimer = setTimeout(() => {
      const next = this.pendingContext;
      this.pendingContext = null;
      if (next) void this.runAnalyze(next);
    }, Math.max(delayMs, throttleWait));
  }

  private async pollIntentState() {
    try {
      const resp = await api.get<{ code?: number; data?: WorkingContext } | WorkingContext>('/api/v1/aiq/intent-state', { timeout: 3000 });
      const state = this.unwrap(resp.data); const fingerprint = this.createFingerprint(state);
      if (!fingerprint || fingerprint === this.lastFingerprint) return;
      this.lastFingerprint = fingerprint;
      this.currentPagePath = state.page_context?.path || this.currentPagePath;
      this.lastContext = {
        ...this.lastContext,
        trigger: 'page_view',
        pageName: state.page_context?.page_name,
        pagePath: state.page_context?.path,
        pageVars: { ...this.currentPageVars, page_name: state.page_context?.page_name || '', page_type: state.page_context?.page_type || '' },
        recentActions: actionTrail.getTrail(5),
      };
      this.scheduleAnalyze(this.lastContext, ANALYZE_DEBOUNCE_MS);
    } catch (err) {
      console.warn('[intentEngine] pollIntentState failed:', err);
    }
  }

  private async runAnalyze(context: IntentContext) {
    if (this.loading) return void this.scheduleAnalyze(context, ANALYZE_THROTTLE_MS);
    this.loading = true; this.lastAnalyzeAt = Date.now(); this.notify([], context.trigger); this.cancelAnalyze(); this.activeController = new AbortController();

    try {
      const resp = await api.post<{ code?: number; data?: InquiryResult } | InquiryResult>('/api/v1/aiq/inquiry/analyze', { query: null }, { timeout: 3000, signal: this.activeController.signal });
      this.lastGuesses = this.mapInquiryToGuesses(this.unwrap(resp.data));
    } catch (error) {
      if (this.isAbortError(error)) return;
      const templateGuesses = await this.fetchTemplateGuesses(context);
      this.lastGuesses = templateGuesses.length > 0 ? templateGuesses : this.buildFallbackGuesses(context);
    } finally {
      this.loading = false; this.activeController = null;
    }

    this.notify(this.lastGuesses, context.trigger);
  }

  private async fetchTemplateGuesses(context: IntentContext): Promise<IntentGuess[]> {
    if (context.trigger !== 'page_view' || !context.pagePath) return [];
    const pageTypes = PAGE_TYPE_MAP[context.pagePath];
    if (!pageTypes?.length) return [];
    let rawEntries = this.getCachedEntries(context.pagePath);
    if (!rawEntries) rawEntries = await this.loadCatalogEntries(context.pagePath, pageTypes);
    if (!rawEntries) return [];
    const vars = context.pageVars || this.currentPageVars;
    const guesses = rawEntries.map((entry) => this.catalogEntryToGuess(entry, vars)).filter((guess): guess is IntentGuess => guess !== null);
    return [...new Map(guesses.map((guess) => [guess.text, guess])).values()].sort((a, b) => b.confidence - a.confidence).slice(0, 6);
  }

  private getCachedEntries(pagePath: string): IntentCatalogEntry[] | null {
    const cached = this.rawTemplateCache.get(pagePath);
    return cached && cached.expiresAt > Date.now() ? cached.entries : null;
  }

  private async loadCatalogEntries(pagePath: string, pageTypes: string[]): Promise<IntentCatalogEntry[] | null> {
    const rawEntries: IntentCatalogEntry[] = []; const seenIds = new Set<string>();
    try {
      for (const pageType of [...pageTypes, 'common']) {
        const resp = await api.get<IntentCatalogListResponse>('/api/v1/intents/catalog', { params: { agent_scope: 'page_action', page_type: pageType, status: 'enabled', page_size: pageType === 'common' ? 10 : 20 } });
        for (const entry of resp.data?.data?.records || []) if (!seenIds.has(entry.intent_id)) { seenIds.add(entry.intent_id); rawEntries.push(entry); }
      }
      this.rawTemplateCache.set(pagePath, { entries: rawEntries, expiresAt: Date.now() + TEMPLATE_CACHE_TTL_MS });
      return rawEntries;
    } catch (err) { console.warn('[intentEngine] fetchTemplates failed:', err); return null; }
  }

  private catalogEntryToGuess(entry: IntentCatalogEntry, vars: Record<string, string>): IntentGuess | null {
    const text = this.substituteVars(entry.suggested_text || entry.name, vars);
    if (text.includes('{') && text.includes('}')) return null;
    return { text, confidence: Math.min(0.95, (entry.priority || 10) / 20), source: 'template', intent_id: entry.intent_id, strategy: (entry.response_strategy as ResponseStrategy) || 'direct_llm', side_effect: (entry.side_effect as SideEffect) || 'none' };
  }

  private mapInquiryToGuesses(result: InquiryResult): IntentGuess[] {
    const hypotheses = [...(result.state?.hypotheses || [])];
    if (result.committed_hypothesis && !hypotheses.some((item) => item.id === result.committed_hypothesis?.id)) hypotheses.unshift(result.committed_hypothesis);
    const regular = hypotheses.map((h) => ({ text: h.intent_label, confidence: h.confidence, source: 'llm' as const, intent_id: h.id, strategy: h.execution_path as ResponseStrategy | undefined, context: { evidence_chain: h.evidence_chain, parameters: h.parameters, decision: result.decision } }));
    if (result.decision === 'clarify') {
      const q = result.clarification_questions?.[0];
      return [...(q ? [{ text: `需要澄清：${q}`, confidence: 0, source: 'llm' as const, strategy: 'clarify' as ResponseStrategy, context: { clarification_questions: result.clarification_questions || [] } }] : []), ...regular];
    }
    if (result.decision === 'escalate') return [{ text: result.escalation_reason || '需要人工協助', confidence: 0, source: 'llm', strategy: 'escalate' as ResponseStrategy, context: { escalation_reason: result.escalation_reason } }];
    return regular;
  }

  private buildFallbackGuesses(context: IntentContext): IntentGuess[] {
    if (context.trigger === 'page_view' && context.pageName) return [
      { text: `告訴我「${context.pageName}」的操作說明`, confidence: 0.95, source: 'template' },
      { text: `${context.pageName}有哪些主要功能？`, confidence: 0.7, source: 'template' },
      { text: `如何在${context.pageName}中完成常見任務？`, confidence: 0.6, source: 'template' },
    ];
    if (context.trigger === 'table_open' && context.tableName) return [
      { text: `告訴我「${context.tableName}」這張表的意思與用途`, confidence: 0.95, source: 'template' },
      { text: `${context.tableName}目前有多少筆記錄？`, confidence: 0.7, source: 'template' },
      { text: `${context.tableName}有哪些欄位？`, confidence: 0.65, source: 'template' },
    ];
    if ((context.trigger === 'cell_click' || context.trigger === 'field_click') && context.fieldName) return [
      { text: `告訴我「${context.fieldName}」欄位的含義`, confidence: 0.9, source: 'template' },
      { text: `${context.fieldName}的分布統計？`, confidence: 0.6, source: 'template' },
    ];
    return [];
  }

  private substituteVars(template: string, vars: Record<string, string>): string { return template.replace(/\{(\w+)\}/g, (match, key: string) => vars[key] !== undefined ? vars[key] : match); }
  private asString(value: unknown): string | undefined { return typeof value === 'string' ? value : undefined; }
  private createFingerprint(context: WorkingContext): string { return JSON.stringify({ anchors: context.active_anchors || [], page: context.page_context?.path || '' }); }
  private unwrap<T>(payload: { data?: T } | T): T { return (typeof payload === 'object' && payload !== null && 'data' in payload ? payload.data : payload) as T; }
  private cancelAnalyze() { this.activeController?.abort(); this.activeController = null; }
  private isAbortError(error: unknown): boolean { return error instanceof Error && (error.name === 'CanceledError' || error.name === 'AbortError'); }

  private recordFeedback(trailAction: 'intent_accepted' | 'intent_confirmed', logAction: IntentLogAction, guess: IntentGuess, finalText: string) {
    actionTrail.record(trailAction, { guess: guess.text, confidence: guess.confidence, source: guess.source, intent_id: guess.intent_id });
    this.logIntent(logAction, guess, finalText);
  }

  private logIntent(action: IntentLogAction, guess: IntentGuess, finalText: string) {
    intentLogApi.create({
      intent_id: guess.intent_id, action, page_path: this.currentPagePath, page_type: PAGE_TYPE_MAP[this.currentPagePath]?.[0],
      original_text: guess.text, final_text: finalText, confidence: guess.confidence, source: guess.source,
    }).catch((err) => { console.warn('[intentEngine] logIntent failed:', err); });
  }

  private notify(guesses: IntentGuess[], trigger: IntentTrigger) { this.listeners.forEach((listener) => listener(guesses, trigger)); }
}

export const intentEngine = new IntentEngine();
