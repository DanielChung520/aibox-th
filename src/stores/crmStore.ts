/**
 * @file        CRM 狀態管理
 * @description 管理 EEA-CRM 頁面共享狀態：Agent Drawer 開關、選中的 Agent/Record
 * @lastUpdate  2026-06-08 12:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { create } from 'zustand';

export type CRMContext =
  | 'dashboard'
  | 'customers'
  | 'contacts'
  | 'timeline'
  | 'tags'
  | 'params';

export interface CrmState {
  // Agent Drawer state
  agentDrawerOpen: boolean;
  agentDrawerContext: CRMContext | null;
  selectedAgentCode: string | null; // null = showing grid view
  selectedRecordId: string | null;

  // Actions
  openAgentDrawer: (context: CRMContext, recordId?: string) => void;
  closeAgentDrawer: () => void;
  selectAgent: (code: string) => void;
  backToAgentList: () => void;
}

export const useCrmStore = create<CrmState>((set) => ({
  agentDrawerOpen: false,
  agentDrawerContext: null,
  selectedAgentCode: null,
  selectedRecordId: null,

  openAgentDrawer: (context: CRMContext, recordId?: string) =>
    set({
      agentDrawerOpen: true,
      agentDrawerContext: context,
      selectedAgentCode: null,
      selectedRecordId: recordId ?? null,
    }),

  closeAgentDrawer: () =>
    set({
      agentDrawerOpen: false,
      agentDrawerContext: null,
      selectedAgentCode: null,
      selectedRecordId: null,
    }),

  selectAgent: (code: string) =>
    set({ selectedAgentCode: code }),

  backToAgentList: () =>
    set({ selectedAgentCode: null }),
}));
