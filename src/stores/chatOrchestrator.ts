/**
 * @file        ChatOrchestrator 狀態機
 * @description FSM 模式管理、TaskStatus 追蹤、工具調用狀態
 * @lastUpdate  2026-04-11 08:54:32
 * @author      AI Agent
 * @version     1.0.0
 */

import type {
  IntentDetectedPayload,
  ToolCallStartPayload,
  ToolCallResultPayload,
} from '../types/sseEvents';

export type ChatMode = 'open_chat' | 'bpa_workflow' | 'bpa_param_collection';
export type TaskStatus = 'idle' | 'sending' | 'streaming' | 'waiting_tool' | 'waiting_user' | 'completed' | 'failed';

export interface ToolCallInfo {
  tool: string;
  parameters: Record<string, unknown>;
  status: 'executing' | 'completed' | 'failed';
  result?: unknown;
  startedAt: number;
  duration?: number;
}

interface OrchestratorState {
  mode: ChatMode;
  taskStatus: TaskStatus;
  currentToolCalls: ToolCallInfo[];
  lastIntent: IntentDetectedPayload | null;
}

class ChatOrchestrator {
  private state: OrchestratorState = {
    mode: 'open_chat',
    taskStatus: 'idle',
    currentToolCalls: [],
    lastIntent: null,
  };

  private listeners: Set<() => void> = new Set();

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  getState(): OrchestratorState {
    return this.state;
  }

  private setState(next: Partial<OrchestratorState>) {
    this.state = { ...this.state, ...next };
    this.notify();
  }

  private notify() {
    this.listeners.forEach((listener) => listener());
  }

  setMode(mode: ChatMode) {
    this.setState({ mode });
  }

  setTaskStatus(status: TaskStatus) {
    this.setState({ taskStatus: status });
  }

  handleSendStart() {
    this.setState({ taskStatus: 'sending', currentToolCalls: [], lastIntent: null });
  }

  handleStreamStart() {
    this.setState({ taskStatus: 'streaming' });
  }

  handleIntentDetected(data: IntentDetectedPayload) {
    this.setState({ lastIntent: data });
  }

  handleToolCallStart(data: ToolCallStartPayload) {
    const toolCall: ToolCallInfo = {
      tool: data.tool,
      parameters: data.parameters,
      status: 'executing',
      startedAt: Date.now(),
    };

    this.setState({
      taskStatus: 'waiting_tool',
      currentToolCalls: [...this.state.currentToolCalls, toolCall],
    });
  }

  handleToolCallResult(data: ToolCallResultPayload) {
    const updated = this.state.currentToolCalls.map((toolCall) => {
      if (toolCall.tool === data.tool && toolCall.status === 'executing') {
        return {
          ...toolCall,
          status: (data.success ? 'completed' : 'failed') as ToolCallInfo['status'],
          result: data.result,
          duration: data.duration_ms,
        };
      }

      return toolCall;
    });

    this.setState({
      taskStatus: 'streaming',
      currentToolCalls: updated,
    });
  }

  handleDone() {
    this.setState({ taskStatus: 'idle' });
  }

  handleError() {
    this.setState({ taskStatus: 'failed' });
  }

  reset() {
    this.setState({
      taskStatus: 'idle',
      currentToolCalls: [],
      lastIntent: null,
    });
  }
}

export const chatOrchestrator = new ChatOrchestrator();
export type { OrchestratorState };
