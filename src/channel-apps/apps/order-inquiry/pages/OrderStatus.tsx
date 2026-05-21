/**
 * @file        OrderStatus.tsx
 * @description 訂單查詢頁面 — 查詢預購單狀態與進度，支援列表/明細兩種視圖
 * @lastUpdate  2026-05-21 17:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import ChannelShellBase from '../../../shell/ChannelShell';
import { getUserPreorders, getPreorderItems } from '../services/orderApi';
import type { Preorder, PreorderItem } from '../services/orderApi';
import './OrderStatus.css';

/** ChannelShell supports onBack at runtime (second default export handles it) */
const ChannelShell = ChannelShellBase as React.FC<{
  title: string;
  children: React.ReactNode;
  onBack?: () => void;
}>;

type ViewState = 'list' | 'detail';

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  '開立': { label: '開立', className: 'order-status__status--blue' },
  '預購確認中': { label: '預購確認中', className: 'order-status__status--orange' },
  '已正式立單': { label: '已正式立單', className: 'order-status__status--green' },
};

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  } catch {
    return dateStr;
  }
}

export default function OrderStatus() {
  const [view, setView] = useState<ViewState>('list');
  const [preorders, setPreorders] = useState<Preorder[]>([]);
  const [selectedPreorder, setSelectedPreorder] = useState<Preorder | null>(null);
  const [items, setItems] = useState<PreorderItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const getStatusInfo = (status: string) =>
    STATUS_CONFIG[status] || { label: status, className: '' };

  // ─── Fetch preorders when entering list view ────────────────────────────

  useEffect(() => {
    if (view !== 'list') return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    getUserPreorders()
      .then((data) => {
        if (cancelled) return;
        const sorted = [...data].sort(
          (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
        );
        setPreorders(sorted);
      })
      .catch(() => {
        if (!cancelled) setError('無法載入預購單資料，請稍後再試');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [view]);

  // ─── Handlers ───────────────────────────────────────────────────────────

  const handleCardClick = async (preorder: Preorder) => {
    setSelectedPreorder(preorder);
    setView('detail');
    setLoading(true);

    try {
      const itemData = preorder.items ?? await getPreorderItems(preorder._key);
      setItems(itemData);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    setView('list');
    setSelectedPreorder(null);
    setItems([]);
  };

  // ─── List View ──────────────────────────────────────────────────────────

  const renderList = () => {
    if (loading) {
      return <div className="order-status__loading">載入中...</div>;
    }

    if (error) {
      return <div className="order-status__error">{error}</div>;
    }

    if (preorders.length === 0) {
      return <div className="order-status__empty">尚無預購單記錄</div>;
    }

    return (
      <div className="order-status__list">
        {preorders.map((preorder) => {
          const statusInfo = getStatusInfo(preorder.status);
          const itemCount = preorder.items?.length ?? '?';
          return (
            <div
              key={preorder._key}
              className="order-status__card"
              onClick={() => handleCardClick(preorder)}
              role="button"
              tabIndex={0}
              onKeyDown={(e: React.KeyboardEvent) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleCardClick(preorder);
                }
              }}
            >
              <div className="order-status__card-header">
                <span className="order-status__id">{preorder.preorder_id}</span>
                <span className={`order-status__status ${statusInfo.className}`}>
                  {statusInfo.label}
                </span>
              </div>
              <div className="order-status__card-body">
                <div className="order-status__date">{formatDate(preorder.created_at)}</div>
                <div className="order-status__summary">{itemCount} 項品項</div>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  // ─── Detail View ────────────────────────────────────────────────────────

  const renderDetail = () => {
    if (!selectedPreorder) return null;

    if (loading) {
      return <div className="order-status__loading">載入中...</div>;
    }

    const preorder = selectedPreorder;
    const statusInfo = getStatusInfo(preorder.status);

    return (
      <div className="order-status__detail">
        {/* Header */}
        <div className="order-status__detail-header">
          <h2 className="order-status__detail-id">{preorder.preorder_id}</h2>
          <span className={`order-status__status ${statusInfo.className}`}>
            {statusInfo.label}
          </span>
        </div>

        {/* Meta info */}
        <dl className="order-status__detail-meta">
          <dt>來源</dt>
          <dd>{preorder.source || '-'}</dd>
          <dt>日期</dt>
          <dd>{formatDate(preorder.created_at)}</dd>
          <dt>建立者</dt>
          <dd>{preorder.user_name || '-'}</dd>
        </dl>

        {/* Items table */}
        {items.length > 0 && (
          <div className="order-status__detail-section">
            <h3 className="order-status__detail-section-title">
              品項明細（{items.length} 項）
            </h3>
            <table className="order-status__items-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>產品名稱</th>
                  <th>規格</th>
                  <th>數量</th>
                  <th>單位</th>
                  <th>備註</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, idx) => (
                  <tr key={idx}>
                    <td>{idx + 1}</td>
                    <td>{item.product_name}</td>
                    <td>{item.spec || '-'}</td>
                    <td>{item.quantity}</td>
                    <td>{item.unit}</td>
                    <td>{item.notes || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Notes */}
        {preorder.notes && (
          <div className="order-status__detail-section">
            <h3 className="order-status__detail-section-title">備註</h3>
            <div className="order-status__notes">{preorder.notes}</div>
          </div>
        )}
      </div>
    );
  };

  // ─── Render ─────────────────────────────────────────────────────────────

  return (
    <ChannelShell title="訂單查詢" onBack={view === 'detail' ? handleBack : undefined}>
      <div className="order-status">
        {view === 'list' ? renderList() : renderDetail()}
      </div>
    </ChannelShell>
  );
}
