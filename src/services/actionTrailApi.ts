/**
 * @file        actionTrailApi.ts
 * @description Action Trail API service — 操作歷史記錄的後端查詢服務
 *              支援分頁、事件類型篩選、排序
 * @lastUpdate  2026-05-15 10:00:00
 * @author      AI Agent
 * @version     1.0.0
 */

import { authStore } from '../stores/auth';
import { default as api } from './api';
import type { ActionEvent } from './actionTrail';

export interface ActionHistoryResponse {
  data: ActionEvent[];
  total: number;
  page: number;
  page_size: number;
}

export interface FetchActionHistoryParams {
  page?: number;
  pageSize?: number;
  eventType?: string;
  sort?: 'asc' | 'desc';
  date?: string;
}

export async function fetchActionHistory(params: FetchActionHistoryParams = {}): Promise<ActionHistoryResponse> {
  const userKey = authStore.getState().user?._key || 'unknown';
  const query: Record<string, string> = {};
  if (params.page) query.page_num = String(params.page);
  if (params.pageSize) query.page_size = String(params.pageSize);
  if (params.eventType) query.event_type = params.eventType;
  if (params.sort) query.sort = params.sort;
  if (params.date) query.date = params.date;

  const res = await api.get(`/api/v1/action-trail/${userKey}`, { params: query });
  const responseData = res.data?.data;
  if (responseData && typeof responseData === 'object' && 'data' in responseData) {
    return responseData as ActionHistoryResponse;
  }
  // Fallback: if API returns flat array (backward compat)
  return {
    data: Array.isArray(responseData) ? responseData : [],
    total: Array.isArray(responseData) ? responseData.length : 0,
    page: 1,
    page_size: 50,
  };
}
