import { useState, useEffect } from 'react';
import { getLocalEvents, clearLocalEvents, QueuedEvent } from '../../utils/analytics';

interface DebugPanelProps {
  onClose: () => void;
}

export default function DebugPanel({ onClose }: DebugPanelProps) {
  const [events, setEvents] = useState<QueuedEvent[]>([]);

  useEffect(() => {
    setEvents(getLocalEvents());
    const interval = setInterval(() => {
      setEvents(getLocalEvents());
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const formatTime = (ts: number) => {
    const d = new Date(ts);
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
  };

  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      page_view: '#1890ff',
      user_action: '#52c41a',
      agent_interaction: '#722ed1',
      demand_management: '#fa8c16',
      intent_config: '#13c2c2',
      error: '#ff4d4f',
    };
    return colors[category] || '#999';
  };

  return (
    <div style={{
      position: 'fixed',
      bottom: 80,
      right: 24,
      width: 380,
      maxHeight: '60vh',
      background: 'var(--colorBgContainer, #1e293b)',
      border: '1px solid var(--colorBorder, #30363d)',
      borderRadius: 8,
      boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
      zIndex: 9999,
      display: 'flex',
      flexDirection: 'column',
      fontSize: 12,
      fontFamily: 'monospace',
    }}>
      <div style={{
        padding: '8px 12px',
        borderBottom: '1px solid var(--colorBorder, #30363d)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: 'var(--colorBgElevated, #252d3d)',
        borderRadius: '8px 8px 0 0',
      }}>
        <span style={{ fontWeight: 600, color: 'var(--colorText, #e6edf3)' }}>
          📊 Analytics Events ({events.length})
        </span>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={() => { clearLocalEvents(); setEvents([]); }}
            style={{
              background: 'transparent',
              border: '1px solid var(--colorBorder, #30363d)',
              borderRadius: 4,
              padding: '2px 8px',
              color: 'var(--colorTextSecondary, #8b949e)',
              cursor: 'pointer',
              fontSize: 11,
            }}
          >
            Clear
          </button>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: '1px solid var(--colorBorder, #30363d)',
              borderRadius: 4,
              padding: '2px 8px',
              color: 'var(--colorTextSecondary, #8b949e)',
              cursor: 'pointer',
              fontSize: 11,
            }}
          >
            ✕
          </button>
        </div>
      </div>

      <div style={{
        flex: 1,
        overflow: 'auto',
        padding: 8,
      }}>
        {events.length === 0 && (
          <div style={{ color: 'var(--colorTextSecondary, #8b949e)', textAlign: 'center', padding: 20 }}>
            No events yet...
          </div>
        )}
        {events.slice(-20).reverse().map((e, i) => {
          const ev = e.event as any;
          const isPageView = 'page' in ev;
          return (
            <div key={i} style={{
              padding: '6px 8px',
              marginBottom: 4,
              background: 'var(--colorBgLayout, #161b22)',
              borderRadius: 4,
              borderLeft: `3px solid ${isPageView ? '#1890ff' : getCategoryColor(ev.category)}`,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--colorTextSecondary, #8b949e)', marginBottom: 2 }}>
                <span>{e.session_id?.slice(0, 12)}</span>
                <span>{formatTime(e.timestamp)}</span>
              </div>
              {isPageView ? (
                <div style={{ color: 'var(--colorText, #e6edf3)' }}>
                  📍 <span style={{ color: '#1890ff' }}>page_view</span> → {ev.page}
                </div>
              ) : (
                <div style={{ color: 'var(--colorText, #e6edf3)' }}>
                  <span style={{ color: getCategoryColor(ev.category), fontWeight: 500 }}>{ev.category}</span>
                  {' / '}
                  <span>{ev.action}</span>
                  {ev.label && <span style={{ color: 'var(--colorTextSecondary, #8b949e)' }}> — {ev.label}</span>}
                  {ev.metadata && Object.keys(ev.metadata).length > 0 && (
                    <div style={{ fontSize: 10, color: 'var(--colorTextSecondary, #8b949e)', marginTop: 2 }}>
                      {JSON.stringify(ev.metadata).slice(0, 60)}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
