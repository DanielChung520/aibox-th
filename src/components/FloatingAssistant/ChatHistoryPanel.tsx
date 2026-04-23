/**
 * @file        ChatHistoryPanel.tsx
 * @description 意圖歷史與操作記錄面板元件
 * @lastUpdate  2026-04-18 22:12:08
 * @author      AI Agent
 * @version     1.0.0
 */

import { Button, Tag } from 'antd';
import type { ActionEvent } from '../../services/actionTrail';

interface HistoryPanelProps {
  currentView: 'chat' | 'intentHistory' | 'actionTrail';
  intentHistory: ActionEvent[];
  actionHistory: ActionEvent[];
  onBackToChat: () => void;
}

export function ChatHistoryPanel({ currentView, intentHistory, actionHistory, onBackToChat }: HistoryPanelProps) {
  if (currentView === 'intentHistory') {
    return (
      <div className="intent-history-panel">
        <div className="intent-history-header">
          <span>🔍 意圖歷史記錄</span>
          <Button type="text" size="small" onClick={onBackToChat}>返回對話</Button>
        </div>
        <div className="intent-history-list">
          {intentHistory.length === 0 && <div className="intent-history-empty">暫無意圖記錄</div>}
          {intentHistory.map((event, i) => (
            <div key={i} className="intent-history-item">
              <Tag color={event.type === 'intent_confirmed' ? 'green' : event.type === 'intent_accepted' ? 'blue' : 'red'}>
                {event.type === 'intent_confirmed' ? '✓ 確認' : event.type === 'intent_accepted' ? '→ 選取' : '✕ 修正'}
              </Tag>
              <span className="intent-history-text">{String(event.meta?.guess || event.meta?.original_guess || '-')}</span>
              {event.meta?.confidence != null && (
                <span className="intent-history-conf">{Math.round(Number(event.meta.confidence) * 100)}%</span>
              )}
              <span className="intent-history-time">
                {new Date(event.timestamp).toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (currentView === 'actionTrail') {
    return (
      <div className="intent-history-panel">
        <div className="intent-history-header">
          <span>📋 操作記錄</span>
          <Button type="text" size="small" onClick={onBackToChat}>返回對話</Button>
        </div>
        <div className="intent-history-list">
          {actionHistory.length === 0 && <div className="intent-history-empty">暫無操作記錄</div>}
          {actionHistory.map((event, i) => (
            <div key={i} className="intent-history-item">
              <Tag color="blue">{event.type}</Tag>
              <span className="intent-history-text">
                {String(event.meta?.pageName || event.meta?.tableName || event.meta?.tableId || event.page)}
                {event.meta?.field ? ` → ${String(event.meta.fieldName || event.meta.field)}` : ''}
                {event.meta?.keyword ? ` 🔍${String(event.meta.keyword)}` : ''}
              </span>
              <span className="intent-history-time">
                {new Date(event.timestamp).toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return null;
}
