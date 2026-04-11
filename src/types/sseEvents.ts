/**
 * @file        SSE 事件 Payload 型別定義
 * @description 定義 16 種 SSE 事件的 Payload 介面
 * @lastUpdate  2026-04-11 09:20:32
 * @author      AI Agent
 * @version     1.0.0
 */

export interface IntentDetectedPayload {
  session_id: string;
  intent: string;
  confidence: number;
  method: 'rule' | 'semantic' | 'llm';
  entities: Record<string, string>;
}

export interface ToolCallStartPayload {
  session_id: string;
  tool: string;
  parameters: Record<string, unknown>;
  trace_id?: string;
}

export interface ToolCallResultPayload {
  session_id: string;
  tool: string;
  success: boolean;
  result: unknown;
  duration_ms: number;
}

export interface DaQueryStartPayload {
  session_id: string;
  query: string;
  intent_id?: string;
}

export interface DaQueryResultPayload {
  session_id: string;
  success: boolean;
  data: unknown;
  sql?: string;
  row_count?: number;
}

export interface KaSearchResultPayload {
  session_id: string;
  results: Array<{
    content: string;
    source: string;
    score: number;
  }>;
}

export interface BpaStepStartPayload {
  session_id: string;
  step_id: string;
  step_name: string;
  progress?: number;
}

export interface BpaStepCompletePayload {
  session_id: string;
  step_id: string;
  step_name: string;
  result: unknown;
  progress?: number;
}

export interface BpaAskUserPayload {
  session_id: string;
  ask: {
    question: string;
    input_type: 'text' | 'select' | 'confirm';
    options?: Array<{ id: string; label: string }>;
    required: boolean;
    timeout_seconds?: number;
    default_value?: string;
  };
  task_status?: { current_step: string; progress: number };
  checkpoint_version?: number;
}

export interface BpaCompletePayload {
  session_id: string;
  result: {
    summary: string;
    tasks: Array<{ id: string; description: string; status: string; result?: string }>;
    execution_summary?: {
      total_duration_seconds: number;
      llm_calls: number;
      tool_calls: number;
      tokens_used: number;
    };
  };
  checkpoint_version?: number;
}

export interface BpaFailedPayload {
  session_id: string;
  error: string;
  code?: string;
  can_retry: boolean;
  checkpoint_version?: number;
}

export interface SessionStatePayload {
  session_id: string;
  mode?: string;
  task_status?: string;
  checkpoint_version?: number;
}
