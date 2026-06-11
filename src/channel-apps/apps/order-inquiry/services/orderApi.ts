/**
 * @file        orderApi.ts
 * @description Order-inquiry API service layer — provides functions for querying products,
 *              creating preorders, uploading preorder files, and retrieving preorder data.
 * @lastUpdate  2026-05-21 11:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

const API_BASE = '/order-secretary';

// ─── Types ───────────────────────────────────────────────────────────────────

export interface ProductItem {
  item_name: string;
  spec: string;
  stock_qty: number;
  unit: string;
}

export interface PreorderItem {
  product_name: string;
  quantity: number;
  unit: string;
  spec: string;
  notes?: string;
}

export interface Preorder {
  _key: string;
  preorder_id: string;
  user_id: string;
  user_name: string;
  status: string;
  source: string;
  items?: PreorderItem[];
  notes: string;
  created_at: string;
}

// ─── API Functions ───────────────────────────────────────────────────────────

/**
 * Query available products/stock from Ragic STOCK_16.
 * @param filterTerm - Optional filter term to narrow results.
 * @returns Array of product items.
 */
export async function queryProducts(filterTerm?: string): Promise<ProductItem[]> {
  const res = await fetch(`${API_BASE}/preorder-agent/skills/query_preorder_items`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: `channel:${Date.now()}`,
      user_id: 'channel_user',
      filter_term: filterTerm || '',
    }),
  });
  if (!res.ok) return [];
  const json = await res.json();
  return json.data || [];
}

/**
 * Create a preorder via structured order data.
 */
export async function createPreorder(params: {
  items: PreorderItem[];
  notes?: string;
  userId?: string;
  userName?: string;
}): Promise<{ status: string; order_id?: string; message?: string }> {
  const res = await fetch(`${API_BASE}/skills/order_preorder_collect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content: JSON.stringify({
        items: params.items,
        notes: params.notes || '',
      }),
      media_type: 'structured',
      user_id: params.userId || 'channel_user',
      user_name: params.userName || 'channel_user',
      session_id: `channel:${Date.now()}`,
    }),
  });
  return res.json();
}

/**
 * Upload a preorder via file/image (base64).
 */
export async function uploadPreorderFile(params: {
  fileBase64: string;
  filename: string;
  mediaType: 'image' | 'file';
  userId?: string;
  userName?: string;
}): Promise<{ status: string; order_id?: string; message?: string }> {
  const res = await fetch(`${API_BASE}/skills/order_preorder_collect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content: params.fileBase64,
      media_type: params.mediaType,
      filename: params.filename,
      user_id: params.userId || 'channel_user',
      user_name: params.userName || 'channel_user',
      session_id: `channel:${Date.now()}`,
    }),
  });
  return res.json();
}

/**
 * Get preorders for a user.
 */
export async function getUserPreorders(userId?: string): Promise<Preorder[]> {
  const res = await fetch(`${API_BASE}/preorders?user_id=${userId || 'channel_user'}`, {
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) return [];
  const json = await res.json();
  return Array.isArray(json) ? json : [];
}

/**
 * Get preorder items by master key.
 */
export async function getPreorderItems(masterKey: string): Promise<PreorderItem[]> {
  const res = await fetch(`${API_BASE}/preorders/${masterKey}/items`, {
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) return [];
  return res.json();
}
