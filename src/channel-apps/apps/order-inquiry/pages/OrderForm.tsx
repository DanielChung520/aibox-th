/**
 * @file        OrderForm.tsx
 * @description Order placement form — two-step flow: select products with quantities, then review & confirm
 * @lastUpdate  2026-05-21 17:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect, useCallback } from 'react';
import ChannelShell from '../../../shell/ChannelShell';
import { queryProducts, createPreorder, ProductItem } from '../services/orderApi';
import './OrderForm.css';

type SelectedMap = Record<string, number>;

interface OrderResult {
  order_id?: string;
  message?: string;
}

export default function OrderForm() {
  const [step, setStep] = useState<1 | 2>(1);
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [selected, setSelected] = useState<SelectedMap>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<OrderResult | null>(null);
  const [notes, setNotes] = useState('');
  const [fetchError, setFetchError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    queryProducts()
      .then((data) => {
        if (!cancelled) setProducts(data);
      })
      .catch(() => {
        if (!cancelled) setFetchError('無法載入產品資料，請稍後再試');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const handleCheck = useCallback((itemName: string, checked: boolean) => {
    setSelected((prev) => {
      if (checked) {
        return { ...prev, [itemName]: prev[itemName] || 1 };
      }
      const next = { ...prev };
      delete next[itemName];
      return next;
    });
  }, []);

  const handleQtyChange = useCallback((itemName: string, value: string) => {
    const qty = Math.max(0, parseInt(value, 10) || 0);
    setSelected((prev) => {
      const next = { ...prev };
      if (qty > 0) {
        next[itemName] = qty;
      } else {
        delete next[itemName];
      }
      return next;
    });
  }, []);

  const selectedCount = Object.keys(selected).length;
  const selectedNames = new Set(Object.keys(selected));

  const handleSubmit = useCallback(async () => {
    setSubmitting(true);
    setResult(null);
    const items = Object.entries(selected)
      .filter(([, qty]) => qty > 0)
      .map(([name, qty]) => {
        const product = products.find((p) => p.item_name === name);
        return {
          product_name: name,
          quantity: qty,
          unit: product?.unit || '個',
          spec: product?.spec || '',
        };
      });

    try {
      const res = await createPreorder({ items, notes });
      setResult(res);
    } catch {
      setResult({ message: '訂單送出失敗，請稍後再試' });
    } finally {
      setSubmitting(false);
    }
  }, [selected, notes, products]);

  const handleReset = useCallback(() => {
    setStep(1);
    setSelected({});
    setResult(null);
    setNotes('');
  }, []);

  /* ─── Step 1: Select Products ─────────────────────────────────────────── */

  const renderProductList = () => (
    <>
      <div className="order-form__step-header">
        <span className="order-form__step-indicator">1</span>
        <h2 className="order-form__step-title">選擇產品</h2>
      </div>

      {loading && (
        <div className="order-form__loading">
          <div className="order-form__spinner" />
          <span className="order-form__loading-text">載入產品資料中...</span>
        </div>
      )}

      {fetchError && (
        <div className="order-form__error">{fetchError}</div>
      )}

      {!loading && !fetchError && products.length === 0 && (
        <div className="order-form__empty">目前沒有可訂購的產品</div>
      )}

      {!loading && products.length > 0 && (
        <>
          <div className="order-form__product-list">
            {products.map((product) => {
              const isSelected = selectedNames.has(product.item_name);
              return (
                <label
                  key={product.item_name}
                  className={`order-form__product${isSelected ? ' order-form__product--selected' : ''}`}
                >
                  <input
                    type="checkbox"
                    className="order-form__checkbox"
                    checked={isSelected}
                    onChange={(e) => handleCheck(product.item_name, e.target.checked)}
                  />
                  <div className="order-form__product-info">
                    <div className="order-form__product-name">{product.item_name}</div>
                    <div className="order-form__product-spec">{product.spec}</div>
                    <div className={`order-form__product-stock${product.stock_qty <= 5 ? ' order-form__product-stock--low' : ''}`}>
                      庫存: {product.stock_qty} {product.unit}
                    </div>
                  </div>
                  <div className="order-form__qty-wrapper">
                    <span className="order-form__qty-label">數量</span>
                    <input
                      type="number"
                      className="order-form__qty-input"
                      min={0}
                      value={selected[product.item_name] || 0}
                      disabled={!isSelected}
                      onChange={(e) => handleQtyChange(product.item_name, e.target.value)}
                    />
                  </div>
                </label>
              );
            })}
          </div>

          <div className="order-form__selected-count">
            已選擇 <strong>{selectedCount}</strong> 項產品
          </div>
        </>
      )}

      <div className="order-form__actions">
        <button
          className="order-form__submit-btn"
          disabled={selectedCount === 0}
          onClick={() => setStep(2)}
        >
          確認訂單
        </button>
      </div>
    </>
  );

  /* ─── Step 2: Review & Confirm ────────────────────────────────────────── */

  const renderReview = () => {
    const selectedItems = products.filter((p) => selectedNames.has(p.item_name));

    return (
      <>
        <div className="order-form__step-header">
          <span className="order-form__step-indicator order-form__step-indicator--complete">&#10003;</span>
          <span className="order-form__step-indicator" style={{ marginLeft: 8 }}>2</span>
          <h2 className="order-form__step-title">確認訂單</h2>
        </div>

        <div className="order-form__summary">
          {selectedItems.map((product) => (
            <div key={product.item_name} className="order-form__summary-item">
              <div className="order-form__summary-item-info">
                <div className="order-form__summary-item-name">{product.item_name}</div>
                <div className="order-form__summary-item-spec">
                  {product.spec} &middot; {product.unit}
                </div>
              </div>
              <span className="order-form__summary-item-qty">&times;{selected[product.item_name]}</span>
            </div>
          ))}
        </div>

        <div className="order-form__notes">
          <label className="order-form__notes-label" htmlFor="order-notes">備註</label>
          <textarea
            id="order-notes"
            className="order-form__notes-textarea"
            placeholder="選填：訂單備註或特殊需求"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </div>

        {result && (
          result.order_id ? (
            <div className="order-form__result">
              <div className="order-form__result-icon">&#10003;</div>
              <div className="order-form__result-title">訂單已送出</div>
              <div className="order-form__result-message">
                {result.message || '您的預訂訂單已成功提交'}
              </div>
              <div className="order-form__result-id">訂單編號: {result.order_id}</div>
              <button className="order-form__submit-btn" onClick={handleReset}>
                繼續訂購
              </button>
            </div>
          ) : (
            <div className="order-form__error">
              {result.message || '訂單送出失敗，請稍後再試'}
            </div>
          )
        )}

        {!result && (
          <div className="order-form__actions">
            <button
              className="order-form__submit-btn"
              disabled={submitting}
              onClick={handleSubmit}
            >
              {submitting ? '送出中...' : '確認送出'}
            </button>
            <button
              className="order-form__back-btn"
              disabled={submitting}
              onClick={() => setStep(1)}
            >
              返回修改
            </button>
          </div>
        )}

        {submitting && (
          <div className="order-form__submitting-overlay">
            <div className="order-form__spinner" />
            <span>正在送出訂單...</span>
          </div>
        )}
      </>
    );
  };

  /* ─── Progress Bar (always visible in Step 2) ─────────────────────────── */

  const renderProgress = () => (
    <div className="order-form__progress">
      <div className="order-form__progress-step order-form__progress-step--done">
        <span className="order-form__progress-dot order-form__progress-dot--done" />
        選擇產品
      </div>
      <div className="order-form__progress-line order-form__progress-line--done" />
      <div className={`order-form__progress-step${step === 2 ? ' order-form__progress-step--active' : ''}`}>
        <span className={`order-form__progress-dot${step === 2 ? ' order-form__progress-dot--active' : ''}`} />
        確認訂單
      </div>
    </div>
  );

  return (
    <ChannelShell title="預訂下單">
      <div className="order-form">
        {step === 2 && renderProgress()}
        {step === 1 ? renderProductList() : renderReview()}
      </div>
    </ChannelShell>
  );
}
