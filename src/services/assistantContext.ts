/**
 * @file        assistantContext.ts
 * @description 建立艾企聊天請求用的 page-aware assistant context
 * @lastUpdate  2026-04-23 20:54:38
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { PAGE_TYPE_MAP, resolvePageContext, type IntentGuess, type PageContext } from '../components/FloatingAssistant/types';
import type { ActionEvent } from './actionTrail';
import type { AssistantContextPayload, AssistantContextFocus, AssistantContextRecentAction, AssistantContextBehaviorStats } from '../types/assistantContext';

interface BuildAssistantContextInput {
  pathname?: string;
  pageContext?: PageContext | null;
  fullPageContext?: {
    page?: string;
    pageName?: string;
    component?: string;
    componentName?: string;
    entity?: string;
    entityType?: string;
    action?: string;
    data?: Record<string, unknown>;
  } | null;
  modalContext?: Record<string, unknown> | null;
  entityContext?: Record<string, unknown> | null;
  intentGuesses?: IntentGuess[];
  recentActions?: ActionEvent[];
}

const MAX_SUMMARY_LENGTH = 280;

function compactText(text: string, maxLength = MAX_SUMMARY_LENGTH): string {
  const normalized = text.replace(/\s+/g, ' ').trim();
  return normalized.length > maxLength ? `${normalized.slice(0, maxLength - 1)}…` : normalized;
}

function summarizeUnknown(value: unknown, maxLength = MAX_SUMMARY_LENGTH): string | undefined {
  if (value == null) {
    return undefined;
  }
  if (typeof value === 'string') {
    const trimmed = compactText(value, maxLength);
    return trimmed || undefined;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  try {
    const serialized = JSON.stringify(value);
    return serialized ? compactText(serialized, maxLength) : undefined;
  } catch {
    return undefined;
  }
}

function pickFocus(input: BuildAssistantContextInput['fullPageContext']): AssistantContextFocus | undefined {
  if (!input) {
    return undefined;
  }

  const focus: AssistantContextFocus = {
    component: input.component,
    componentName: input.componentName,
    entity: input.entity,
    entityType: input.entityType,
    action: input.action,
    dataSummary: summarizeUnknown(input.data),
  };

  return Object.values(focus).some((value) => value) ? focus : undefined;
}

function pickEntity(entityContext: BuildAssistantContextInput['entityContext']): AssistantContextFocus | undefined {
  if (!entityContext) {
    return undefined;
  }

  const focus: AssistantContextFocus = {
    entity: typeof entityContext.entity_id === 'string' ? entityContext.entity_id : undefined,
    entityType: typeof entityContext.entity_type === 'string' ? entityContext.entity_type : undefined,
    action: typeof entityContext.action === 'string' ? entityContext.action : undefined,
    dataSummary: summarizeUnknown(entityContext.metadata),
  };

  return Object.values(focus).some((value) => value) ? focus : undefined;
}

function buildModalSummary(modalContext: BuildAssistantContextInput['modalContext']): { modal: string; mode?: string; summary?: string } | undefined {
  if (!modalContext || typeof modalContext.modal !== 'string') {
    return undefined;
  }

  const summarySource = {
    modal: modalContext.modal,
    mode: modalContext.mode,
    agent_name: modalContext.agent_name,
    demand: modalContext.demand,
  };

  return {
    modal: modalContext.modal,
    mode: typeof modalContext.mode === 'string' ? modalContext.mode : undefined,
    summary: summarizeUnknown(summarySource),
  };
}

function summarizeAction(event: ActionEvent): string | undefined {
  const meta = event.meta;
  const candidates = [
    typeof meta.pageName === 'string' ? `頁面 ${meta.pageName}` : undefined,
    typeof meta.tableName === 'string' ? `表 ${meta.tableName}` : undefined,
    typeof meta.fieldName === 'string' ? `欄位 ${meta.fieldName}` : undefined,
    typeof meta.entity_name === 'string' ? `實體 ${meta.entity_name}` : undefined,
    typeof meta.entity_id === 'string' ? `ID ${meta.entity_id}` : undefined,
    typeof meta.action === 'string' ? `動作 ${meta.action}` : undefined,
    typeof meta.cellValue === 'string' ? `值 ${meta.cellValue}` : undefined,
  ].filter(Boolean);

  if (candidates.length > 0) {
    return compactText(candidates.join('｜'));
  }

  return summarizeUnknown(meta, 160);
}

function pickRecentActions(recentActions: ActionEvent[] | undefined): AssistantContextRecentAction[] | undefined {
  if (!recentActions || recentActions.length === 0) {
    return undefined;
  }

  const items = recentActions
    .filter((event) => !event.type.startsWith('intent_'))
    .slice(-20)
    .map((event) => ({
      type: event.type,
      at: event.timestamp,
      page: event.page,
      summary: summarizeAction(event),
    }));

  return items.length > 0 ? items : undefined;
}

function buildBehaviorStats(recentActions: ActionEvent[] | undefined): AssistantContextBehaviorStats | undefined {
  if (!recentActions || recentActions.length === 0) return undefined;
  const nonIntent = recentActions.filter(e => !e.type.startsWith('intent_'));
  if (nonIntent.length === 0) return undefined;

  const typeCounts: Record<string, number> = {};
  for (const action of nonIntent) {
    typeCounts[action.type] = (typeCounts[action.type] || 0) + 1;
  }
  const entries = Object.entries(typeCounts).sort((a, b) => b[1] - a[1]);

  return {
    mostFrequentType: entries[0][0],
    totalRecentActions: nonIntent.length,
    actionTypes: entries.map(([type]) => type),
  };
}

export function buildAssistantContext(input: BuildAssistantContextInput): AssistantContextPayload {
  const pathname = input.pathname || input.fullPageContext?.page || window.location.pathname;
  const fallbackPageContext = resolvePageContext(pathname);
  const pageContext = input.pageContext ?? fallbackPageContext;
  const fullPageContext = input.fullPageContext;

  return {
    page: {
      pathname,
      name: fullPageContext?.pageName || pageContext.name,
      description: pageContext.description,
      pageTypes: PAGE_TYPE_MAP[pathname] || [],
    },
    focus: pickFocus(fullPageContext),
    modal: buildModalSummary(input.modalContext),
    entity: pickEntity(input.entityContext),
    intentHints: input.intentGuesses?.slice(0, 3).map((guess) => ({
      text: guess.text,
      confidence: guess.confidence,
      source: guess.source,
      strategy: guess.strategy,
    })),
    recentActions: pickRecentActions(input.recentActions),
    behaviorStats: buildBehaviorStats(input.recentActions),
  };
}
