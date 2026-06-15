/**
 * @file        AI Assistant Drawer 狀態管理
 * @description 控制 AI Assistant Drawer 的開啟/關閉、當前視圖、當前選中 Agent
 * @lastUpdate  2026-06-16 12:00:00
 * @author      Daniel Chung
 * @version     1.1.0
 */

import { createContext, useState, useContext, useCallback, ReactNode } from 'react';
import type { Agent } from '../services/api';

export type DrawerView = 'chat' | 'intentHistory' | 'actionTrail';

interface DrawerContextValue {
  isOpen: boolean;
  activeView: DrawerView;
  activeAgent: Agent | null;
  open: () => void;
  close: () => void;
  toggle: () => void;
  setActiveView: (view: DrawerView) => void;
  setActiveAgent: (agent: Agent | null) => void;
}

const defaultCtx: DrawerContextValue = {
  isOpen: false,
  activeView: 'chat',
  activeAgent: null,
  open: () => {},
  close: () => {},
  toggle: () => {},
  setActiveView: () => {},
  setActiveAgent: () => {},
};

export const AIAssistantDrawerContext = createContext<DrawerContextValue>(defaultCtx);

export function AIAssistantDrawerProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeView, setActiveViewState] = useState<DrawerView>('chat');
  const [activeAgent, setActiveAgent] = useState<Agent | null>(null);

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);
  const toggle = useCallback(() => setIsOpen(prev => !prev), []);
  const setActiveView = useCallback((view: DrawerView) => setActiveViewState(view), []);

  return (
    <AIAssistantDrawerContext.Provider
      value={{ isOpen, activeView, activeAgent, open, close, toggle, setActiveView, setActiveAgent }}
    >
      {children}
    </AIAssistantDrawerContext.Provider>
  );
}

export function useAIAssistantDrawer(): DrawerContextValue {
  return useContext(AIAssistantDrawerContext);
}
