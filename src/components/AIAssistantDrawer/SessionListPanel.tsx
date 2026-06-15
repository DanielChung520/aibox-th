/**
 * @file        SessionListPanel.tsx
 * @description 對話歷史列表下拉面板 — 從 AI Assistant Drawer 時鐘按鈕觸發
 *              按時間分組（今日/昨天/本週/本月/更早），支援刪除、重新命名
 * @lastUpdate  2026-06-16 12:00:00
 * @author      AI Agent
 * @version     1.0.0
 */

import { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { Input, Button, Popconfirm, Typography } from 'antd';
import type { InputRef } from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  HistoryOutlined,
} from '@ant-design/icons';
import type { ChatSession } from '../../services/api';

// ── Types ──

interface SessionListPanelProps {
  sessions: ChatSession[];
  activeSessionKey: string | null;
  agentColor?: string;
  onSelect: (sessionKey: string) => void;
  onNewChat: () => void;
  onDelete: (sessionKey: string) => void;
  onRename: (sessionKey: string, title: string) => void;
  onClose: () => void;
}

// ── Time grouping ──

type TimeGroup = { label: string; sessions: ChatSession[] };

function getGroupLabel(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterdayStart = new Date(todayStart.getTime() - 86_400_000);
  const weekStart = new Date(todayStart.getTime() - todayStart.getDay() * 86_400_000);
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);

  if (date >= todayStart) return '今日';
  if (date >= yesterdayStart) return '昨天';
  if (date >= weekStart) return '本週';
  if (date >= monthStart) return '本月';
  return '更早';
}

function groupSessionsByTime(sessions: ChatSession[]): TimeGroup[] {
  const order = ['今日', '昨天', '本週', '本月', '更早'];
  const map = new Map<string, ChatSession[]>();

  const sorted = [...sessions].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  for (const session of sorted) {
    const group = getGroupLabel(session.created_at);
    if (!map.has(group)) map.set(group, []);
    map.get(group)!.push(session);
  }

  return order
    .filter((label) => map.has(label))
    .map((label) => ({ label, sessions: map.get(label)! }));
}

function formatTimestamp(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterdayStart = new Date(todayStart.getTime() - 86_400_000);

  if (date >= todayStart) {
    return date.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' });
  }
  if (date >= yesterdayStart) {
    return date.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' });
  }
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

// ── Constants ──

const PANEL_WIDTH = 320;
const ITEM_HEIGHT = 44;
const MAX_VISIBLE_ITEMS = 9;

// ── Styles (inline) ──

const styles = {
  overlay: {
    position: 'fixed' as const,
    inset: 0,
    zIndex: 10000,
    pointerEvents: 'auto' as const,
  },
  panel: (mounted: boolean): React.CSSProperties => ({
    position: 'fixed' as const,
    top: 60,
    right: 16,
    width: PANEL_WIDTH,
    maxHeight: MAX_VISIBLE_ITEMS * ITEM_HEIGHT + 88,
    zIndex: 10001,
    background: 'rgba(22, 27, 34, 0.95)',
    backdropFilter: 'blur(16px)',
    WebkitBackdropFilter: 'blur(16px)',
    border: '1px solid rgba(255, 255, 255, 0.10)',
    borderRadius: 12,
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), 0 2px 8px rgba(0, 0, 0, 0.3)',
    overflow: 'hidden',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    opacity: mounted ? 1 : 0,
    transform: mounted ? 'translateY(0)' : 'translateY(8px)',
    transition: 'opacity 0.2s ease, transform 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
    pointerEvents: 'auto' as const,
    display: 'flex',
    flexDirection: 'column' as const,
  }),
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 14px 8px',
    userSelect: 'none' as const,
  },
  headerTitle: {
    fontSize: 12,
    fontWeight: 600,
    color: 'rgba(255, 255, 255, 0.5)',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px',
    display: 'flex',
    alignItems: 'center',
    gap: 6,
  },
  body: {
    flex: 1,
    overflowY: 'auto' as const,
    overflowX: 'hidden' as const,
    padding: '0 0 4px',
  },
  empty: {
    padding: '20px 14px',
    textAlign: 'center' as const,
    fontSize: 12,
    color: 'rgba(255, 255, 255, 0.35)',
  },
  groupLabel: {
    padding: '6px 14px 4px',
    fontSize: 11,
    fontWeight: 600,
    color: 'rgba(255, 255, 255, 0.35)',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.4px',
    userSelect: 'none' as const,
  },
  item: (isActive: boolean): React.CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '0 14px',
    cursor: 'pointer',
    minHeight: ITEM_HEIGHT,
    background: isActive ? 'rgba(59, 130, 246, 0.12)' : 'transparent',
    transition: 'background 0.15s ease',
    userSelect: 'none' as const,
  }),
  dot: (color: string): React.CSSProperties => ({
    width: 8,
    height: 8,
    borderRadius: '50%',
    backgroundColor: color,
    flexShrink: 0,
  }),
  title: {
    flex: 1,
    minWidth: 0,
    fontSize: 13,
    fontWeight: 400,
    color: '#e2e8f0',
    whiteSpace: 'nowrap' as const,
    overflow: 'hidden' as const,
    textOverflow: 'ellipsis' as const,
  },
  titleActive: {
    flex: 1,
    minWidth: 0,
    fontSize: 13,
    fontWeight: 600,
    color: '#f1f5f9',
    whiteSpace: 'nowrap' as const,
    overflow: 'hidden' as const,
    textOverflow: 'ellipsis' as const,
  },
  time: {
    fontSize: 11,
    color: 'rgba(255, 255, 255, 0.35)',
    flexShrink: 0,
    marginLeft: 4,
  },
  deleteBtn: {
    flexShrink: 0,
    color: 'rgba(255, 255, 255, 0.25)',
    opacity: 0,
    transition: 'opacity 0.15s ease, color 0.15s ease',
    width: 22,
    height: 22,
    minWidth: 22,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 4,
    border: 'none',
    background: 'transparent',
    cursor: 'pointer',
    padding: 0,
    fontSize: 12,
  },
  footer: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'flex-end',
    padding: '8px 14px',
    borderTop: '1px solid rgba(255, 255, 255, 0.08)',
    userSelect: 'none' as const,
  },
  footerCount: {
    fontSize: 11,
    color: 'rgba(255, 255, 255, 0.35)',
  },
  divider: {
    height: 1,
    background: 'rgba(255, 255, 255, 0.06)',
    margin: '0 14px',
  },
};

// ── Component ──

export default function SessionListPanel({
  sessions,
  activeSessionKey,
  agentColor = '#3b82f6',
  onSelect,
  onNewChat,
  onDelete,
  onRename,
  onClose,
}: SessionListPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(false);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const editInputRef = useRef<InputRef>(null);
  const [hoveredKey, setHoveredKey] = useState<string | null>(null);

  // ── Mount animation ──
  useEffect(() => {
    const timer = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(timer);
  }, []);

  // ── Close on outside click ──
  useEffect(() => {
    const timer = setTimeout(() => {
      const handleClick = (e: MouseEvent) => {
        if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
          onClose();
        }
      };
      document.addEventListener('click', handleClick, true);
      return () => document.removeEventListener('click', handleClick, true);
    }, 0);
    return () => clearTimeout(timer);
  }, [onClose]);

  // ── Close on Escape ──
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (editingKey) {
          setEditingKey(null);
          setEditValue('');
        } else {
          onClose();
        }
      }
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onClose, editingKey]);

  // ── Focus edit input when entering edit mode ──
  useEffect(() => {
    if (editingKey && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingKey]);

  // ── Group sessions ──
  const groups = useMemo(() => groupSessionsByTime(sessions), [sessions]);

  // ── Handlers ──

  const handleDoubleClick = useCallback((session: ChatSession) => {
    setEditingKey(session._key);
    setEditValue(session.title || '');
  }, []);

  const confirmRename = useCallback(
    (sessionKey: string) => {
      const trimmed = editValue.trim();
      if (trimmed && trimmed !== sessions.find((s) => s._key === sessionKey)?.title) {
        onRename(sessionKey, trimmed);
      }
      setEditingKey(null);
      setEditValue('');
    },
    [editValue, onRename, sessions],
  );

  const handleRenameKeyDown = useCallback(
    (e: React.KeyboardEvent, sessionKey: string) => {
      if (e.key === 'Enter') {
        confirmRename(sessionKey);
      } else if (e.key === 'Escape') {
        setEditingKey(null);
        setEditValue('');
      }
    },
    [confirmRename],
  );

  const handleItemClick = useCallback(
    (sessionKey: string) => {
      if (!editingKey) {
        onSelect(sessionKey);
        onClose();
      }
    },
    [editingKey, onSelect, onClose],
  );

  // ── Render ──

  return (
    <>
      <div style={styles.overlay} onClick={onClose} />

      <div ref={panelRef} style={styles.panel(mounted)} role="listbox" aria-label="對話歷史">
        {/* ── Header ── */}
        <div style={styles.header}>
          <span style={styles.headerTitle}>
            <HistoryOutlined />
            對話歷史
          </span>
          <Button
            type="primary"
            size="small"
            icon={<PlusOutlined />}
            onClick={(e) => {
              e.stopPropagation();
              onNewChat();
              onClose();
            }}
            style={{
              fontSize: 12,
              height: 26,
              borderRadius: 6,
              display: 'flex',
              alignItems: 'center',
              gap: 4,
            }}
          >
            新對話
          </Button>
        </div>

        {/* ── Session list ── */}
        <div style={styles.body}>
          {groups.length === 0 ? (
            <div style={styles.empty}>尚無對話記錄</div>
          ) : (
            groups.map((group) => (
              <div key={group.label}>
                <div style={styles.groupLabel}>{group.label}</div>
                {group.sessions.map((session) => {
                  const isActive = session._key === activeSessionKey;
                  const isEditing = editingKey === session._key;
                  const isHovered = hoveredKey === session._key;

                  return (
                    <div
                      key={session._key}
                      role="option"
                      aria-selected={isActive}
                      style={styles.item(isActive)}
                      onClick={() => handleItemClick(session._key)}
                      onDoubleClick={() => handleDoubleClick(session)}
                      onMouseEnter={() => setHoveredKey(session._key)}
                      onMouseLeave={() => setHoveredKey(null)}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        onDelete(session._key);
                      }}
                    >
                      <span style={styles.dot(agentColor)} />

                      {isEditing ? (
                        <Input
                          ref={editInputRef}
                          size="small"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          onBlur={() => confirmRename(session._key)}
                          onKeyDown={(e) => handleRenameKeyDown(e, session._key)}
                          onClick={(e) => e.stopPropagation()}
                          style={{
                            flex: 1,
                            height: 26,
                            fontSize: 12,
                            borderRadius: 4,
                            background: 'rgba(0, 0, 0, 0.3)',
                            border: '1px solid rgba(59, 130, 246, 0.5)',
                            color: '#f1f5f9',
                          }}
                        />
                      ) : (
                        <span style={isActive ? styles.titleActive : styles.title}>
                          {session.title || '(無標題)'}
                        </span>
                      )}

                      <span style={styles.time}>{formatTimestamp(session.created_at)}</span>

                      {!isEditing && (
                        <Popconfirm
                          title="刪除此對話？"
                          description="此操作無法復原。"
                          onConfirm={(e) => {
                            if (e) e.stopPropagation();
                            onDelete(session._key);
                          }}
                          onCancel={(e) => {
                            if (e) e.stopPropagation();
                          }}
                          okText="刪除"
                          cancelText="取消"
                          placement="left"
                          okButtonProps={{ danger: true, size: 'small' }}
                          cancelButtonProps={{ size: 'small' }}
                        >
                          <span
                            style={{
                              ...styles.deleteBtn,
                              opacity: isHovered ? 1 : 0,
                            }}
                            onClick={(e) => e.stopPropagation()}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.color = 'rgba(239, 68, 68, 0.8)';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.color = 'rgba(255, 255, 255, 0.25)';
                            }}
                          >
                            <DeleteOutlined style={{ fontSize: 12 }} />
                          </span>
                        </Popconfirm>
                      )}
                    </div>
                  );
                })}
                <div style={styles.divider} />
              </div>
            ))
          )}
        </div>

        {/* ── Footer ── */}
        <div style={styles.footer}>
          <Typography.Text style={styles.footerCount}>
            共 {sessions.length} 個
          </Typography.Text>
        </div>
      </div>
    </>
  );
}
