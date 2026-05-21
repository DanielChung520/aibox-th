/**
 * @file        DemoApp.tsx
 * @description LINE 頻道 Demo 應用元件 - 展示頻道應用框架的範例頁面
 * @lastUpdate  2026-05-21 16:45:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import ChannelShell from '../shell/ChannelShell';

interface MiniAppItem {
  icon: string;
  name: string;
  status: 'ready' | 'coming-soon' | 'planned';
  desc: string;
}

const miniApps: MiniAppItem[] = [
  { icon: '🔍', name: '訂單查詢', status: 'coming-soon', desc: '快速查詢訂單狀態與明細' },
  { icon: '📊', name: '銷售報表', status: 'planned', desc: '即時銷售數據與圖表分析' },
  { icon: '💬', name: '客服訊息', status: 'planned', desc: '統一管理 LINE 客服對話' },
  { icon: '📦', name: '庫存管理', status: 'planned', desc: '即時庫存查詢與異動通知' },
  { icon: '🎁', name: '行銷活動', status: 'planned', desc: '優惠券、抽獎與推播管理' },
  { icon: '⚙️', name: '更多應用', status: 'planned', desc: '持續擴充中...' },
];

function getStatusBadge(status: MiniAppItem['status']): { label: string; color: string; bg: string } {
  switch (status) {
    case 'ready':
      return { label: '已就緒', color: '#059669', bg: '#d1fae5' };
    case 'coming-soon':
      return { label: '即將推出', color: '#d97706', bg: '#fef3c7' };
    case 'planned':
      return { label: '規劃中', color: '#6b7280', bg: '#f3f4f6' };
  }
}

export default function DemoApp() {
  return (
    <ChannelShell title="示範應用">
      {/* Hero Card */}
      <div style={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        borderRadius: '16px',
        padding: '28px 24px',
        marginBottom: '24px',
        color: '#fff',
        boxShadow: '0 8px 24px rgba(102, 126, 234, 0.3)',
      }}>
        <div style={{ fontSize: '36px', marginBottom: '12px', lineHeight: 1 }}>
          📱
        </div>
        <h2 style={{
          fontSize: '22px',
          fontWeight: 700,
          margin: '0 0 8px 0',
          color: '#fff',
          lineHeight: 1.3,
        }}>
          頻道應用框架
        </h2>
        <p style={{
          fontSize: '14px',
          lineHeight: 1.6,
          margin: 0,
          opacity: 0.9,
          color: '#fff',
        }}>
          Channel Apps 是建構在 LINE 頻道之上的輕量應用生態系統。
          每個子應用獨立運作，共享統一的認證與 Shell 框架，
          讓開發與擴充更快速直覺。
        </p>
      </div>

      {/* Section Title */}
      <h3 style={{
        fontSize: '16px',
        fontWeight: 600,
        color: '#374151',
        margin: '0 0 12px 0',
      }}>
        預計推出應用
      </h3>

      {/* Mini App Grid */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
      }}>
        {miniApps.map((app) => {
          const badge = getStatusBadge(app.status);
          return (
            <div
              key={app.name}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '14px',
                background: '#ffffff',
                borderRadius: '12px',
                padding: '14px 16px',
                boxShadow: '0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04)',
                border: '1px solid #f3f4f6',
                transition: 'box-shadow 0.2s ease, transform 0.2s ease',
                cursor: 'default',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.1)';
                e.currentTarget.style.transform = 'translateY(-1px)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.boxShadow = '0 1px 3px rgba(0, 0, 0, 0.06)';
                e.currentTarget.style.transform = 'translateY(0)';
              }}
            >
              <div style={{
                fontSize: '28px',
                lineHeight: 1,
                flexShrink: 0,
                width: '40px',
                textAlign: 'center',
              }}>
                {app.icon}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontSize: '15px',
                  fontWeight: 600,
                  color: '#111827',
                  marginBottom: '2px',
                }}>
                  {app.name}
                </div>
                <div style={{
                  fontSize: '13px',
                  color: '#6b7280',
                  lineHeight: 1.4,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}>
                  {app.desc}
                </div>
              </div>
              <span style={{
                fontSize: '11px',
                fontWeight: 600,
                padding: '3px 10px',
                borderRadius: '9999px',
                color: badge.color,
                background: badge.bg,
                whiteSpace: 'nowrap',
                flexShrink: 0,
              }}>
                {badge.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Footer Hint */}
      <div style={{
        marginTop: '24px',
        padding: '16px',
        background: '#f9fafb',
        borderRadius: '12px',
        border: '1px solid #f3f4f6',
        textAlign: 'center',
      }}>
        <p style={{
          fontSize: '13px',
          color: '#9ca3af',
          margin: 0,
          lineHeight: 1.5,
        }}>
          💡 點擊側邊欄「頻道應用」可返回此頁<br />
          更多子應用將陸續上線
        </p>
      </div>
    </ChannelShell>
  );
}
