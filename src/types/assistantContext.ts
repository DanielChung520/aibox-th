/**
 * @file        assistantContext.ts
 * @description 艾企 page-aware chat 上下文型別
 * @lastUpdate  2026-04-23 20:54:38
 * @author      Daniel Chung
 * @version     1.0.0
 */

export interface AssistantContextPage {
  pathname: string;
  name: string;
  description?: string;
  pageTypes?: string[];
}

export interface AssistantContextFocus {
  component?: string;
  componentName?: string;
  entity?: string;
  entityType?: string;
  action?: string;
  dataSummary?: string;
}

export interface AssistantContextModal {
  modal: string;
  mode?: string;
  summary?: string;
}

export interface AssistantContextIntentHint {
  text: string;
  confidence: number;
  source: 'template' | 'rule' | 'llm';
  strategy?: string;
}

export interface AssistantContextRecentAction {
  type: string;
  at: number;
  page: string;
  summary?: string;
}

export interface AssistantContextBehaviorStats {
  mostFrequentType: string;
  totalRecentActions: number;
  actionTypes: string[];
}

export interface AssistantContextPayload {
  page: AssistantContextPage;
  focus?: AssistantContextFocus;
  modal?: AssistantContextModal;
  entity?: AssistantContextFocus;
  intentHints?: AssistantContextIntentHint[];
  recentActions?: AssistantContextRecentAction[];
  behaviorStats?: AssistantContextBehaviorStats;
}
