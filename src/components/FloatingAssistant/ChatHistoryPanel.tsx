/**
 * @file        ChatHistoryPanel.tsx
 * @description 意圖歷史與操作記錄面板元件 — 支援後端 API 分頁查詢、事件類型篩選
 * @lastUpdate  2026-05-15 10:00:00
 * @author      AI Agent
 * @version     1.1.0
 */

import { useState, useEffect, useMemo } from 'react';
import { Button, Tag, Select, Spin } from 'antd';
import type { ActionEvent } from '../../services/actionTrail';
import { fetchActionHistory } from '../../services/actionTrailApi';

const EVENT_TYPE_OPTIONS = [
  { value: '', label: '全部類型' },
  { value: 'page_navigate', label: '頁面導航' },
  { value: 'entity_view', label: '檢視實體' },
  { value: 'entity_edit', label: '編輯實體' },
  { value: 'entity_create', label: '建立實體' },
  { value: 'entity_delete', label: '刪除實體' },
  { value: 'cell_click', label: '儲存格點擊' },
  { value: 'click', label: '點擊' },
  { value: 'modal_open', label: '開啟彈窗' },
  { value: 'modal_close', label: '關閉彈窗' },
  { value: 'filter_apply', label: '篩選' },
  { value: 'filter_clear', label: '清除篩選' },
  { value: 'global_search', label: '搜尋' },
  { value: 'column_sort', label: '排序' },
  { value: 'tab_switch', label: '頁籤切換' },
];

interface HistoryPanelProps {
  currentView: 'chat' | 'intentHistory' | 'actionTrail';
  intentHistory: ActionEvent[];
  actionHistory: ActionEvent[];
  onBackToChat: () => void;
}

export function ChatHistoryPanel({ currentView, intentHistory, actionHistory, onBackToChat }: HistoryPanelProps) {
  // API-fetched state
  const [apiEvents, setApiEvents] = useState<ActionEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(50);
  const [selectedEventType, setSelectedEventType] = useState<string>('');
  const [loading, setLoading] = useState(false);

  // Fetch API history when page or event type changes
  useEffect(() => {
    if (currentView !== 'actionTrail') return;

    let cancelled = false;
    setLoading(true);
    fetchActionHistory({
      page: currentPage,
      pageSize,
      eventType: selectedEventType || undefined,
      sort: 'desc',
    })
      .then((resp) => {
        if (!cancelled) {
          setApiEvents(resp.data);
          setTotal(resp.total);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setApiEvents([]);
          setTotal(0);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [currentView, currentPage, pageSize, selectedEventType]);

  // Reset to page 1 when filter changes
  const handleEventTypeChange = (value: string) => {
    setSelectedEventType(value);
    setCurrentPage(1);
  };

  // Merge in-memory events with API events (for page 1 only, deduped)
  const mergedEvents = useMemo(() => {
    if (currentPage === 1 && actionHistory.length > 0) {
      let localFiltered = actionHistory.filter((e) => !e.type.startsWith('intent_'));
      if (selectedEventType) {
        localFiltered = localFiltered.filter((e) => e.type === selectedEventType);
      }
      const apiKeys = new Set(apiEvents.map((e) => `${e.type}_${e.timestamp}_${e.page}`));
      const uniqueLocal = localFiltered.filter((e) => !apiKeys.has(`${e.type}_${e.timestamp}_${e.page}`));
      return [...uniqueLocal.sort((a, b) => b.timestamp - a.timestamp), ...apiEvents];
    }
    return apiEvents;
  }, [actionHistory, apiEvents, currentPage, selectedEventType]);

  const totalPages = Math.ceil(total / pageSize) || 1;

  // ── Intent History View ──
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

  // ── Action Trail View (with API+pagination+filter) ──
  if (currentView === 'actionTrail') {
    return (
      <div className="intent-history-panel">
        <div className="intent-history-header">
          <span>📋 操作記錄</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Select
              size="small"
              value={selectedEventType}
              onChange={handleEventTypeChange}
              options={EVENT_TYPE_OPTIONS}
              style={{ width: 120 }}
              placeholder="事件類型"
            />
            <Button type="text" size="small" onClick={onBackToChat}>返回對話</Button>
          </div>
        </div>
        <div className="intent-history-list">
          {loading ? (
            <div style={{ textAlign: 'center', padding: '24px 0' }}>
              <Spin size="small" /> 載入中...
            </div>
          ) : mergedEvents.length === 0 ? (
            <div className="intent-history-empty">暫無操作記錄</div>
          ) : (
            mergedEvents.map((event, i) => (
              <div key={`${event.type}_${event.timestamp}_${i}`} className="intent-history-item">
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
            ))
          )}
        </div>
        {total > pageSize && !loading && (
          <div
            style={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              gap: 12,
              padding: '8px 16px',
              borderTop: '1px solid rgba(255,255,255,0.1)',
            }}
          >
            <Button
              size="small"
              disabled={currentPage <= 1}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            >
              &lt; 上一頁
            </Button>
            <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.65)' }}>
              第 {currentPage} 頁，共 {totalPages} 頁（總計 {total} 筆）
            </span>
            <Button
              size="small"
              disabled={currentPage >= totalPages}
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            >
              下一頁 &gt;
            </Button>
          </div>
        )}
      </div>
    );
  }

  return null;
}
