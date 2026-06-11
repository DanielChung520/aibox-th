/**
 * @file        ProductBrowser.tsx
 * @description Browse available products page with stock quantities
 * @lastUpdate  2026-05-21 17:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect, useRef } from 'react';
import ChannelShell from '../../../shell/ChannelShell';
import { queryProducts } from '../services/orderApi';
import type { ProductItem } from '../services/orderApi';
import './ProductBrowser.css';

export default function ProductBrowser() {
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function loadProducts(filter: string) {
    setLoading(true);
    setError(null);
    try {
      const data = await queryProducts(filter || undefined);
      setProducts(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '無法載入品項資料');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadProducts('');
  }, []);

  function handleSearchChange(value: string) {
    setSearchTerm(value);
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }
    debounceRef.current = setTimeout(() => {
      loadProducts(value);
    }, 350);
  }

  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, []);

  return (
    <ChannelShell title="可訂購品項">
      <div className="product-browser">
        <div className="product-browser__search">
          <input
            type="text"
            className="product-browser__search-input"
            placeholder="搜尋品項..."
            value={searchTerm}
            onChange={(e) => handleSearchChange(e.target.value)}
            aria-label="搜尋品項"
          />
        </div>

        {loading && (
          <div className="product-browser__loading">載入中...</div>
        )}

        {!loading && error && (
          <div className="product-browser__error">{error}</div>
        )}

        {!loading && !error && products.length === 0 && (
          <div className="product-browser__empty">暫無可訂購品項</div>
        )}

        {!loading && !error && products.length > 0 && (
          <div className="product-browser__list">
            {products.map((product, index) => (
              <div key={`${product.item_name}-${index}`} className="product-browser__card">
                <div className="product-browser__name">{product.item_name}</div>
                {product.spec && (
                  <div className="product-browser__spec">{product.spec}</div>
                )}
                <div className="product-browser__stock-row">
                  <span className="product-browser__stock">{product.stock_qty}</span>
                  <span className="product-browser__unit">{product.unit}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </ChannelShell>
  );
}
